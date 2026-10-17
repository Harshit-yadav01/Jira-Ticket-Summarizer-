import atexit
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

_test_directory = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = str(Path(_test_directory.name) / "api.sqlite3")
atexit.register(_test_directory.cleanup)

from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.keys = patch.dict(os.environ, {
            "APP_VIEWER_API_KEY": "viewer-test-key",
            "APP_ANALYST_API_KEY": "analyst-test-key",
            "APP_API_KEY": "",
            "HPE_SEARCH_API_URL": "",
        })
        self.keys.start()
        self.addCleanup(self.keys.stop)

    def test_viewer_can_read_but_cannot_analyze(self):
        viewer = {"X-API-Key": "viewer-test-key"}
        analyst = {"X-API-Key": "analyst-test-key"}

        requests_response = self.client.get("/api/requests", headers=viewer)
        self.assertEqual(200, requests_response.status_code)
        self.assertGreaterEqual(requests_response.json()["total"], 5)
        self.assertTrue(all(isinstance(item["analyzed"], bool) for item in requests_response.json()["items"]))
        self.assertEqual(403, self.client.post("/api/requests/DEMO-1042/analyze", headers=viewer).status_code)

        analyzed = self.client.post("/api/requests/DEMO-1042/analyze", headers=analyst)
        self.assertEqual(200, analyzed.status_code)
        self.assertIn("AUTH-401", analyzed.json()["analysis"]["error_evidence"])
        self.assertIn("support.hpe.com", analyzed.json()["documents"][0]["url"])

        detail = self.client.get("/api/requests/DEMO-1042", headers=viewer).json()
        self.assertEqual(
            analyzed.json()["analysis"]["quick_summary"],
            detail["analysis"]["analysis"]["quick_summary"],
        )
        self.assertEqual(analyzed.json()["documents"], detail["analysis"]["documents"])

    def test_api_rejects_missing_or_invalid_keys(self):
        self.assertEqual(401, self.client.get("/api/requests").status_code)
        self.assertEqual(401, self.client.get("/api/requests", headers={"X-API-Key": "wrong"}).status_code)

    def test_jira_sync_is_read_only_and_upserts(self):
        from app import main

        sample = {
            "id": "JIRA-OPS-7", "source_key": "OPS-7", "source": "jira",
            "summary": "Read-only sync test", "description": "", "comments": "",
            "status": "Open", "priority": "Low", "assignee": "", "component": "",
            "created": "2026-10-17", "updated": "2026-10-17", "source_url": "https://jira.example/browse/OPS-7",
        }
        with patch.object(main, "fetch_jira_tickets", return_value=[sample]):
            response = self.client.post("/api/sync", headers={"X-API-Key": "analyst-test-key"})
        self.assertEqual(1, response.json()["synced"])
        self.assertEqual(sample["updated"], response.json()["updated_cursor"])
        matches = self.client.get("/api/requests?q=OPS-7", headers={"X-API-Key": "viewer-test-key"}).json()["items"]
        self.assertEqual(1, len(matches))
        history = self.client.get("/api/sync/history", headers={"X-API-Key": "viewer-test-key"}).json()["items"]
        self.assertEqual("succeeded", history[0]["status"])

    def test_configured_sync_scheduler_starts_and_stops_with_app(self):
        from app import main

        with patch.dict(os.environ, {"JIRA_SYNC_INTERVAL_MINUTES": "15"}):
            with patch.object(main, "BackgroundScheduler") as scheduler_type:
                scheduler = scheduler_type.return_value
                with TestClient(app):
                    scheduler.add_job.assert_called_once()
                    self.assertEqual("interval", scheduler.add_job.call_args.args[1])
                    self.assertEqual(15, scheduler.add_job.call_args.kwargs["minutes"])
                    scheduler.start.assert_called_once()
                scheduler.shutdown.assert_called_once_with(wait=False)

    def test_failed_sync_is_visible_in_history(self):
        from app import main

        with patch.object(main, "fetch_jira_tickets", side_effect=requests.ConnectionError("network unavailable")):
            response = self.client.post("/api/sync", headers={"X-API-Key": "analyst-test-key"})

        self.assertEqual(502, response.status_code)
        history = self.client.get("/api/sync/history", headers={"X-API-Key": "viewer-test-key"}).json()["items"]
        self.assertEqual("failed", history[0]["status"])
        self.assertIn("network unavailable", history[0]["error"])


if __name__ == "__main__":
    unittest.main()
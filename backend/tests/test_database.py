import os
import tempfile
import unittest
from pathlib import Path

from app import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = str(Path(self.directory.name) / "test.sqlite3")
        database.initialize_database()

    def tearDown(self):
        os.environ.pop("DATABASE_PATH", None)
        self.directory.cleanup()

    def test_demo_data_is_available_and_analysis_is_persisted(self):
        tickets = database.list_tickets()
        self.assertGreaterEqual(len(tickets), 5)
        ticket_id = tickets[0]["id"]
        stamp = database.save_analysis(ticket_id, {"quick_summary": "Grounded summary"})

        saved = database.get_analysis(ticket_id)
        self.assertEqual({"quick_summary": "Grounded summary"}, saved["result"])
        self.assertEqual(stamp, saved["analyzed_at"])

    def test_upsert_does_not_duplicate_source_ticket(self):
        ticket = {
            "id": "JIRA-HELP-9", "source_key": "HELP-9", "source": "jira",
            "summary": "Original", "created": "2026-10-17", "updated": "2026-10-17",
        }
        database.upsert_ticket(ticket)
        ticket["summary"] = "Updated"
        database.upsert_ticket(ticket)

        matches = [item for item in database.list_tickets() if item["id"] == "JIRA-HELP-9"]
        self.assertEqual(1, len(matches))
        self.assertEqual("Updated", matches[0]["summary"])

    def test_changed_ticket_invalidates_its_previous_analysis(self):
        ticket = {
            "id": "JIRA-HELP-10", "source_key": "HELP-10", "source": "jira",
            "summary": "Before", "created": "2026-10-17", "updated": "2026-10-17",
        }
        database.upsert_ticket(ticket)
        database.save_analysis(ticket["id"], {"quick_summary": "Old content"})
        ticket["summary"] = "After"
        database.upsert_ticket(ticket)

        self.assertIsNone(database.get_analysis(ticket["id"]))
        saved = next(item for item in database.list_tickets() if item["id"] == ticket["id"])
        self.assertFalse(saved["analyzed"])


if __name__ == "__main__":
    unittest.main()
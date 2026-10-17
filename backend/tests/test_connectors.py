import os
import unittest
from unittest.mock import patch

from app.hpe import find_related_documents
from app.jira import JiraConfigurationError, _session, _text, fetch_jira_tickets


class ConnectorTests(unittest.TestCase):
    def test_jira_text_redacts_credential_like_values(self):
        text = _text('Login failed; password="correct horse" token: abc123 Bearer xyz987')

        self.assertIn("password=[REDACTED]", text)
        self.assertIn("token: [REDACTED]", text)
        self.assertIn("Bearer [REDACTED]", text)
        self.assertNotIn("correct horse", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("xyz987", text)

    def test_jira_text_extracts_atlassian_document_content_without_metadata(self):
        document = {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": "Login fails with AUTH-401"}],
            }],
        }

        self.assertEqual("Login fails with AUTH-401", _text(document))

    def test_hpe_results_are_limited_to_hpe_support_https_links(self):
        ticket = {"summary": "iLO update failure", "description": "AUTH-401"}
        response = unittest.mock.Mock()
        response.json.return_value = {"results": [
            {"title": "HPE guide", "url": "https://support.hpe.com/docs/guide", "snippet": "Relevant guide"},
            {"title": "External result", "url": "https://example.com/unsafe"},
            {"title": "Insecure result", "url": "http://support.hpe.com/guide"},
        ]}
        with patch.dict(os.environ, {"HPE_SEARCH_API_URL": "https://support.hpe.com/api/search", "HPE_SEARCH_API_KEY": ""}):
            with patch("app.hpe.requests.get", return_value=response):
                results = find_related_documents(ticket)

        self.assertEqual(1, len(results))
        self.assertEqual("HPE guide", results[0]["title"])

    def test_unconfigured_hpe_search_links_to_the_support_portal(self):
        with patch.dict(os.environ, {"HPE_SEARCH_API_URL": ""}):
            result = find_related_documents({"summary": "OneView sync timeout"})

        self.assertEqual(1, len(result))
        self.assertIn("support.hpe.com", result[0]["url"])
        self.assertIn("OneView", result[0]["title"])

    def test_jira_refuses_insecure_or_credential_embedded_base_urls(self):
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "http://jira.example",
            "JIRA_EMAIL": "analyst@example.com",
            "JIRA_API_TOKEN": "placeholder",
        }):
            with self.assertRaises(JiraConfigurationError):
                fetch_jira_tickets()

    def test_incremental_jira_query_uses_inclusive_cursor_and_stable_order(self):
        response = unittest.mock.Mock()
        response.json.return_value = {"issues": [], "total": 0}
        session = unittest.mock.Mock()
        session.get.return_value = response
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://jira.example",
            "JIRA_EMAIL": "analyst@example.com",
            "JIRA_API_TOKEN": "placeholder",
            "JIRA_PROJECT_KEY": "OPS",
        }):
            with patch("app.jira._session", return_value=session):
                result = fetch_jira_tickets("2026-10-17T09:37:55+00:00")

        self.assertEqual([], result)
        jql = session.get.call_args.kwargs["params"]["jql"]
        self.assertIn('project = "OPS"', jql)
        self.assertIn('updated >= "2026-10-17 09:37"', jql)
        self.assertTrue(jql.endswith("ORDER BY updated ASC"))

    def test_jira_http_session_retries_rate_limits_and_server_errors(self):
        retry = _session().get_adapter("https://jira.example").max_retries

        self.assertEqual(3, retry.total)
        self.assertIn(429, retry.status_forcelist)
        self.assertIn(503, retry.status_forcelist)


if __name__ == "__main__":
    unittest.main()
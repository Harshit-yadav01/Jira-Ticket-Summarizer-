import unittest

from app.analysis import summarize_ticket


class SummarizeTicketTests(unittest.TestCase):
    def test_summary_uses_ticket_content_and_marks_unknowns(self):
        result = summarize_ticket({
            "summary": "iLO login fails",
            "description": "Production login returns error AUTH-401 after firmware update.",
            "priority": "High",
        })

        self.assertIn("iLO login fails", result["quick_summary"])
        self.assertEqual("Access or permissions", result["category"])
        self.assertEqual("iLO", result["affected_product"])
        self.assertIn("AUTH-401", result["error_evidence"])
        self.assertIn("Not explicitly stated in the ticket.", result["expected_outcome"])
        self.assertIn("Product, software, or firmware version", result["missing_information"])

    def test_empty_ticket_does_not_invent_a_root_cause(self):
        result = summarize_ticket({})

        self.assertEqual("The ticket does not include a detailed description.", result["problem_statement"])
        self.assertEqual([], result["inferences"])
        self.assertEqual("Needs review", result["category"])
        self.assertTrue(result["missing_information"])


if __name__ == "__main__":
    unittest.main()
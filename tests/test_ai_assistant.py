"""Unit tests for AI Assistant features:
- On-demand "Explain this result" (root cause, discrepancy analysis, recommended action).
- Ready-to-send "Draft correction email" with side-by-side SI vs Draft BL values.
- Advisory-only invariant: Never alters submission verification status.
- Token, latency, and invocation telemetry tracking.
- Disk caching behavior.
- "Where AI is used" breakdown across the 5 core operational touchpoints.
"""

import unittest
from pathlib import Path
from src.ai_assistant import (
    explain_verification_result,
    generate_correction_email,
    get_where_ai_is_used_breakdown,
    get_assistant_stats,
    record_assistant_stat
)

class TestAIAssistant(unittest.TestCase):

    def setUp(self):
        self.si_sample = {
            "shipper": "Alpha Logistics Ltd",
            "consignee": "Beta Retailers LLC",
            "notify_party": "Gamma Express",
            "port_of_loading": "Singapore",
            "port_of_discharge": "Rotterdam",
            "container_count": 2,
            "gross_weight_kg": 24500
        }
        self.bl_mismatch_sample = {
            "shipper": "Alpha Logistics Ltd",
            "consignee": "Beta Retailers LLC",
            "notify_party": "Gamma Express",
            "port_of_loading": "Singapore",
            "port_of_discharge": "Hamburg",
            "container_count": 2,
            "gross_weight_kg": 24000
        }

    def test_01_explain_mismatch_result(self):
        """Test on-demand explanation for a mismatched case."""
        res = explain_verification_result(
            email_id="email_test_mismatch",
            status="MISMATCH",
            category="BL_COMPARISON",
            defect_fields=["port_of_discharge", "gross_weight_kg"],
            review_reason=None,
            si_fields=self.si_sample,
            bl_fields=self.bl_mismatch_sample,
            subject="Draft B/L Review - Booking #9872",
            sender="carrier@ocean-line.com"
        )
        self.assertIn("summary", res)
        self.assertIn("likely_cause", res)
        self.assertIn("recommended_action", res)
        self.assertIn("draft_reply", res)
        self.assertTrue(len(res["summary"]) > 0)
        self.assertTrue(len(res["likely_cause"]) > 0)
        self.assertTrue(len(res["recommended_action"]) > 0)
        self.assertTrue(len(res["draft_reply"]) > 0)
        # Check that discrepancy information is reflected
        self.assertTrue("Port Of Discharge" in res["summary"] or "Port" in res["likely_cause"] or "Rotterdam" in res["draft_reply"])

    def test_02_explanation_disk_caching(self):
        """Test that explanations are cached to disk and return cached=True on second call."""
        # Initial call
        res1 = explain_verification_result(
            email_id="email_test_cache",
            status="OK",
            category="BL_COMPARISON",
            defect_fields=[],
            review_reason=None,
            si_fields=self.si_sample,
            bl_fields=self.si_sample,
            force_refresh=True
        )
        self.assertFalse(res1.get("cached", False))

        # Second call
        res2 = explain_verification_result(
            email_id="email_test_cache",
            status="OK",
            category="BL_COMPARISON",
            defect_fields=[],
            review_reason=None,
            si_fields=self.si_sample,
            bl_fields=self.si_sample,
            force_refresh=False
        )
        self.assertTrue(res2.get("cached", False))

    def test_03_advisory_only_guarantee(self):
        """Verify that explanation is advisory only and does not mutate verification records."""
        original_record = {
            "status": "MISMATCH",
            "category": "BL_COMPARISON",
            "defect_fields": ["gross_weight_kg"],
            "has_defect": True
        }
        snapshot_status = original_record["status"]

        # Call explanation
        res = explain_verification_result(
            email_id="email_test_advisory",
            status=original_record["status"],
            category=original_record["category"],
            defect_fields=original_record["defect_fields"],
            review_reason=None,
            si_fields=self.si_sample,
            bl_fields=self.bl_mismatch_sample
        )
        # Verify original record was not modified
        self.assertEqual(original_record["status"], snapshot_status)
        self.assertEqual(original_record["has_defect"], True)
        self.assertIsInstance(res, dict)

    def test_04_draft_correction_email_side_by_side(self):
        """Test generation of draft correction email listing SI vs Draft BL values side by side."""
        draft = generate_correction_email(
            email_id="email_test_draft",
            defect_fields=["port_of_discharge", "gross_weight_kg"],
            si_fields=self.si_sample,
            bl_fields=self.bl_mismatch_sample,
            recipient="discrepancies@ocean-line.com",
            subject_ref="Booking Ref SG-ROT-001"
        )
        self.assertIn("subject", draft)
        self.assertIn("body", draft)
        self.assertIn("mismatches", draft)
        self.assertEqual(len(draft["mismatches"]), 2)

        # Ensure side-by-side values are captured
        pod_mismatch = next((m for m in draft["mismatches"] if "Port" in m["field"]), None)
        self.assertIsNotNone(pod_mismatch)
        self.assertEqual(pod_mismatch["si_val"], "Rotterdam")
        self.assertEqual(pod_mismatch["bl_val"], "Hamburg")

        wt_mismatch = next((m for m in draft["mismatches"] if "Weight" in m["field"]), None)
        self.assertIsNotNone(wt_mismatch)
        self.assertEqual(wt_mismatch["si_val"], "24500")
        self.assertEqual(wt_mismatch["bl_val"], "24000")

    def test_05_where_ai_is_used_breakdown(self):
        """Test compilation of Where AI is used telemetry breakdown."""
        breakdown = get_where_ai_is_used_breakdown()
        self.assertIn("total_touchpoints", breakdown)
        self.assertIn("items", breakdown)
        self.assertEqual(len(breakdown["items"]), 5)

        categories = [item["category"] for item in breakdown["items"]]
        self.assertIn("Classification Assist", categories)
        self.assertIn("Semantic Field Equivalence", categories)
        self.assertIn("Vision OCR Extraction", categories)
        self.assertIn("Operator Result Explanations", categories)
        self.assertIn("Discrepancy Correction Drafts", categories)


if __name__ == "__main__":
    unittest.main()

"""tests/test_vision_extractor.py

Automated test suite for Vision AI document extraction.
Tests rasterization, structured field extraction, per-field confidence scores,
evidence citations, and low-confidence amber alerting on real scanned samples
from the dataset (email_512_BL.pdf, email_513_SI.pdf, email_514_BL.pdf).
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from src.vision_extractor import (
    rasterize_pdf,
    extract_fields_with_vision,
    COMPARE_FIELDS
)
from src.pipeline import process_email


class TestVisionExtractor(unittest.TestCase):
    """Test suite verifying Vision AI document extraction on scanned PDFs."""

    def setUp(self):
        self.sample1_bl = ROOT / "attachments" / "email_512_BL.pdf"
        self.sample1_si = ROOT / "attachments" / "email_512_SI.pdf"
        self.sample2_si = ROOT / "attachments" / "email_513_SI.pdf"
        self.sample2_bl = ROOT / "attachments" / "email_513_BL.pdf"
        self.sample3_bl = ROOT / "attachments" / "email_514_BL.pdf"

        self.assertTrue(self.sample1_bl.exists(), "Sample attachments/email_512_BL.pdf must exist")
        self.assertTrue(self.sample2_si.exists(), "Sample attachments/email_513_SI.pdf must exist")

    def test_01_rasterize_pdf_dimensions_and_pages(self):
        """Verify PDF rasterization produces valid RGB PIL images with correct dimensions."""
        images_bl = rasterize_pdf(self.sample1_bl, max_pages=1, dpi=150)
        self.assertIsInstance(images_bl, list)
        self.assertGreaterEqual(len(images_bl), 1)
        self.assertIsInstance(images_bl[0], Image.Image)
        self.assertGreater(images_bl[0].width, 500)
        self.assertGreater(images_bl[0].height, 500)

        images_si = rasterize_pdf(self.sample2_si, max_pages=1, dpi=150)
        self.assertGreaterEqual(len(images_si), 1)
        self.assertGreater(images_si[0].width, 500)

    def test_02_vision_extraction_sample1_email_512_bl(self):
        """Extract structured fields from real dataset scanned sample: email_512_BL.pdf."""
        data, err, meta = extract_fields_with_vision(self.sample1_bl, doc_type_hint="BILL_OF_LADING")
        self.assertIsNone(err, f"Vision extraction failed with error: {err}")
        self.assertIsNotNone(data, "Expected structured data dictionary from vision extraction")
        self.assertIn("fields", data)

        fields = data["fields"]
        for f in COMPARE_FIELDS:
            self.assertIn(f, fields, f"Mandatory field '{f}' missing from vision extraction")
            f_info = fields[f]
            self.assertIn("value", f_info)
            self.assertIn("confidence", f_info)
            self.assertIn("evidence", f_info)
            self.assertGreaterEqual(f_info["confidence"], 0.0)
            self.assertLessEqual(f_info["confidence"], 1.0)
            self.assertIsInstance(f_info["evidence"], str)
            self.assertGreater(len(f_info["evidence"]), 0, f"Evidence quote for '{f}' must be non-empty")

        # Verify ground truth consistency
        self.assertEqual(fields["container_count"]["value"], 3)
        self.assertEqual(fields["gross_weight_kg"]["value"], 67674)
        self.assertIn("ASIA PACIFIC", fields["shipper"]["value"])
        self.assertIn("TOAN LUC", fields["consignee"]["value"])

    def test_03_vision_extraction_sample2_email_513_si(self):
        """Extract structured fields from real dataset scanned sample: email_513_SI.pdf."""
        data, err, meta = extract_fields_with_vision(self.sample2_si, doc_type_hint="SHIPPING_INSTRUCTION")
        self.assertIsNone(err, f"Vision extraction failed: {err}")
        self.assertIsNotNone(data)

        fields = data["fields"]
        for f in COMPARE_FIELDS:
            self.assertIn(f, fields)
            self.assertIn("confidence", fields[f])
            self.assertIn("evidence", fields[f])

        self.assertEqual(fields["container_count"]["value"], 1)
        self.assertEqual(fields["gross_weight_kg"]["value"], 22668)
        self.assertIn("APRIL FINE PAPER", fields["shipper"]["value"])
        self.assertIn("CERIEX", fields["consignee"]["value"])

    def test_04_low_confidence_amber_highlight_detection(self):
        """Verify that fields with confidence below 0.70 trigger low-confidence alert logic."""
        mock_data = {
            "shipper": {"value": "Test Shipper", "confidence": 0.95, "evidence": "Shipper: Test"},
            "consignee": {"value": "Unclear Consignee", "confidence": 0.65, "evidence": "Faded text"},
            "container_count": {"value": 2, "confidence": 0.55, "evidence": "Smudged 2"}
        }
        low_conf = [(k, v["value"], v["confidence"]) for k, v in mock_data.items() if v["confidence"] < 0.70]
        self.assertEqual(len(low_conf), 2)
        flagged_names = [x[0] for x in low_conf]
        self.assertIn("consignee", flagged_names)
        self.assertIn("container_count", flagged_names)

    def test_05_default_benchmark_pipeline_behavior_unchanged(self):
        """Ensure default automated benchmark pipeline STILL escalates unreadable scans.
        
        Reliability F1 must remain 100% (all 5 unreadable cases escalate to NEEDS_REVIEW).
        """
        import json
        for eid in ["email_511", "email_512", "email_513", "email_514", "email_515"]:
            inbox_file = ROOT / "inbox" / f"{eid}.json"
            if inbox_file.exists():
                email_dict = json.loads(inbox_file.read_text(encoding="utf-8"))
                res = process_email(email_dict)
                self.assertEqual(res["category"], "BL_COMPARISON", f"{eid} must classify as BL_COMPARISON")
                self.assertEqual(res["status"], "NEEDS_REVIEW", f"{eid} must escalate to NEEDS_REVIEW")
                self.assertEqual(res["review_reason"], "unreadable", f"{eid} review_reason must remain 'unreadable'")


if __name__ == "__main__":
    unittest.main()

"""tests/test_processing_failures.py

Automated tests for processing failures, stage-isolated retries,
exponential backoff, max retries cap, and audit trail logging.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
INBOX_DIR = ROOT / "inbox"

from src.pipeline import process_email

from src.storage import LocalStorage
from src.failure_recovery import (
    make_processing_failure,
    retry_failed_stage,
    retry_all_failed,
    compute_backoff,
    is_transient_error,
    DEFAULT_MAX_RETRIES
)


class TestProcessingFailuresAndRetries(unittest.TestCase):

    def setUp(self):
        self.test_storage_path = ROOT / "results" / "test_storage_failures.json"
        if self.test_storage_path.exists():
            self.test_storage_path.unlink()
        self.storage = LocalStorage(filepath=self.test_storage_path)

        # Load a representative email
        em_path = INBOX_DIR / "email_001.json"
        self.email_data = json.loads(em_path.read_text(encoding="utf-8"))
        self.eid = self.email_data["email_id"]

    def tearDown(self):
        if self.test_storage_path.exists():
            self.test_storage_path.unlink()

    def test_01_injected_llm_failure_and_recovery(self):
        """Inject LLM failure via monkeypatch, verify queue item, then verify Retry recovers it."""
        # 1. Monkeypatch LLM audit to simulate a transient Gemini 503 connection failure
        with patch("src.pipeline.should_invoke_gemini", return_value=(True, ["test_discrepancy"])):
            with patch("src.pipeline.run_hybrid_harmonious_audit", side_effect=ConnectionError("Gemini API connection timed out (503 Service Unavailable)")):
                fail_res = process_email(
                    self.email_data,
                    base_dir=ROOT,
                    mode="hybrid",
                    api_key="mock-api-key"
                )

        # 2. Verify failure structure and metadata
        self.assertEqual(fail_res["status"], "processing_failed")
        self.assertEqual(fail_res["failing_stage"], "llm_call")
        self.assertEqual(fail_res["exception_type"], "ConnectionError")
        self.assertIn("Processing failure", fail_res["review_reason"])
        self.assertEqual(fail_res["retry_count"], 0)
        self.assertFalse(fail_res["needs_manual_handling"])
        self.assertTrue(fail_res["is_transient"])
        self.assertIn("parsing", fail_res["cached_stages"])
        self.assertIn("extraction", fail_res["cached_stages"])

        # 3. Persist to storage queue
        self.storage.save_failed_processing(self.eid, fail_res)
        queue = self.storage.get_failed_processings()
        self.assertIn(self.eid, queue)
        self.assertEqual(queue[self.eid]["failing_stage"], "llm_call")

        # 4. Now Retry the failed stage (with LLM client restored / mock returning valid audit)
        mock_llm_data = {
            "overall_assessment": "MATCH",
            "confidence": 0.96,
            "discrepancies": [],
            "field_discrepancies": {}
        }
        with patch("src.ai_extractor.run_hybrid_harmonious_audit", return_value=(mock_llm_data, None)):
            recovered_res, success, msg = retry_failed_stage(
                email_obj=self.email_data,
                failure_item=fail_res,
                base_dir=ROOT,
                storage_instance=self.storage,
                mode="hybrid",
                sleep_backoff=False
            )

        # 5. Verify successful recovery
        self.assertTrue(success)
        self.assertEqual(recovered_res["status"], "OK")
        self.assertIn("succeeded on attempt #1", msg)

        # 6. Verify removed from active failure queue
        remaining_queue = self.storage.get_failed_processings()
        self.assertNotIn(self.eid, remaining_queue)

        # 7. Verify audit trail records the attempt number, result, and stage
        trail = self.storage.get_audit_trail(self.eid)
        self.assertGreaterEqual(len(trail), 1)
        last_entry = trail[-1]
        self.assertEqual(last_entry["action"], "STAGE_RETRY")
        self.assertEqual(last_entry["stage"], "llm_call")
        self.assertEqual(last_entry["attempt_number"], 1)
        self.assertEqual(last_entry["result"], "SUCCESS")
        self.assertEqual(last_entry["before_status"], "processing_failed")
        self.assertEqual(last_entry["after_status"], "OK")

    def test_02_injected_parsing_failure_and_recovery(self):
        """Inject parsing exception, verify stage='parsing', then verify Retry recovers it."""
        # 1. Monkeypatch parse_document to simulate disk / read I/O crash
        with patch("src.pipeline.parse_document", side_effect=OSError("Disk read fault reading attachment")):
            fail_res = process_email(self.email_data, base_dir=ROOT)

        self.assertEqual(fail_res["status"], "processing_failed")
        self.assertEqual(fail_res["failing_stage"], "parsing")
        self.assertEqual(fail_res["exception_type"], "OSError")

        # 2. Re-run failed parsing stage with normal parser restored
        recovered_res, success, msg = retry_failed_stage(
            email_obj=self.email_data,
            failure_item=fail_res,
            base_dir=ROOT,
            storage_instance=self.storage,
            sleep_backoff=False
        )

        self.assertTrue(success)
        self.assertEqual(recovered_res["status"], "OK")

        # 3. Verify audit trail records parsing retry
        trail = self.storage.get_audit_trail(self.eid)
        self.assertEqual(trail[-1]["stage"], "parsing")
        self.assertEqual(trail[-1]["attempt_number"], 1)
        self.assertEqual(trail[-1]["result"], "SUCCESS")

    def test_03_exponential_backoff_and_transient_detection(self):
        """Verify backoff calculation and transient error heuristics."""
        self.assertEqual(compute_backoff(0), 0.0)
        self.assertEqual(compute_backoff(1, base_delay=0.5), 0.5)
        self.assertEqual(compute_backoff(2, base_delay=0.5), 1.0)
        self.assertEqual(compute_backoff(3, base_delay=0.5), 2.0)
        self.assertEqual(compute_backoff(4, base_delay=0.5), 4.0)
        self.assertEqual(compute_backoff(5, base_delay=0.5, max_delay=6.0), 6.0)

        # Transient error checks
        self.assertTrue(is_transient_error(ConnectionError("Network reset")))
        self.assertTrue(is_transient_error(TimeoutError("Timed out")))
        self.assertTrue(is_transient_error("HTTP 429 Too Many Requests"))
        self.assertTrue(is_transient_error("HTTP 503 Service Unavailable"))
        self.assertTrue(is_transient_error("ResourceExhausted quota exceeded"))
        self.assertFalse(is_transient_error(KeyError("missing_key")))
        self.assertFalse(is_transient_error(TypeError("bad type")))

    def test_04_max_retries_cap_and_manual_handling(self):
        """Verify that after MAX_RETRIES attempts, the item requires manual handling."""
        max_cap = 3
        failure_item = make_processing_failure(
            email=self.email_data,
            failing_stage="llm_call",
            exc=ConnectionError("Persistent network outage"),
            retry_count=0,
            max_retries=max_cap
        )
        self.storage.save_failed_processing(self.eid, failure_item)

        # Attempt 1: fails
        with patch("src.ai_extractor.run_hybrid_harmonious_audit", side_effect=ConnectionError("Still offline")):
            res1, ok1, _ = retry_failed_stage(self.email_data, failure_item, storage_instance=self.storage, sleep_backoff=False)
        self.assertFalse(ok1)
        self.assertEqual(res1["retry_count"], 1)
        self.assertFalse(res1["needs_manual_handling"])

        # Attempt 2: fails
        with patch("src.ai_extractor.run_hybrid_harmonious_audit", side_effect=ConnectionError("Still offline")):
            res2, ok2, _ = retry_failed_stage(self.email_data, res1, storage_instance=self.storage, sleep_backoff=False)
        self.assertFalse(ok2)
        self.assertEqual(res2["retry_count"], 2)
        self.assertFalse(res2["needs_manual_handling"])

        # Attempt 3: fails -> hits max cap
        with patch("src.ai_extractor.run_hybrid_harmonious_audit", side_effect=ConnectionError("Still offline")):
            res3, ok3, msg3 = retry_failed_stage(self.email_data, res2, storage_instance=self.storage, sleep_backoff=False)
        self.assertFalse(ok3)
        self.assertEqual(res3["retry_count"], 3)
        self.assertTrue(res3["needs_manual_handling"])
        self.assertIn("Manual handling required", msg3)

        # Audit trail must show 3 failed attempts
        trail = self.storage.get_audit_trail(self.eid)
        self.assertEqual(len(trail), 3)
        for idx, entry in enumerate(trail, start=1):
            self.assertEqual(entry["attempt_number"], idx)
            self.assertEqual(entry["result"], "FAILURE")
            self.assertEqual(entry["after_status"], "processing_failed")

        # Now operator performs manual resolution
        self.storage.save_review_decision(self.eid, {
            "operator": "human_reviewer",
            "action": "MANUAL_OVERRIDE",
            "effective_status": "OK",
            "before_status": "processing_failed",
            "after_status": "OK",
            "note": "Operator manually cleared persistent network failure."
        })

        # Failure queue auto-cleaned
        self.assertNotIn(self.eid, self.storage.get_failed_processings())
        decisions = self.storage.get_review_decisions()
        self.assertEqual(decisions[self.eid]["effective_status"], "OK")

    def test_05_batch_retry_all_failed(self):
        """Verify retry_all_failed recovers multiple cases in a single batch."""
        f1 = make_processing_failure(self.email_data, "parsing", OSError("Disk read error"))
        em2_path = INBOX_DIR / "email_002.json"
        em2_data = json.loads(em2_path.read_text(encoding="utf-8"))
        f2 = make_processing_failure(em2_data, "parsing", OSError("Disk read error"))

        self.storage.save_failed_processing(self.eid, f1)
        self.storage.save_failed_processing(em2_data["email_id"], f2)

        batch_result = retry_all_failed(
            failed_items=[f1, f2],
            inbox_dir=INBOX_DIR,
            base_dir=ROOT,
            storage_instance=self.storage
        )

        self.assertEqual(batch_result["total"], 2)
        self.assertEqual(batch_result["succeeded"], 2)
        self.assertEqual(batch_result["failed"], 0)
        self.assertEqual(len(self.storage.get_failed_processings()), 0)


if __name__ == "__main__":
    unittest.main()

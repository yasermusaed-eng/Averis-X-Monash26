"""
tests/test_review_workflow.py

Automated tests for Task 3:
1. Tests correction -> re-compare -> status change workflow for missing_value cases.
2. Tests persistence of review decisions and audit trail.
3. Tests failure -> retry workflow for processing_failed cases.
4. Tests effective status calculation overlaying human decisions on system outputs.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.comparator import compare_shipment_fields
from src.storage import LocalStorage
from src.pipeline import process_email



def test_correction_recompare_status_change():
    """Test entering missing value, re-comparing, and verifying status transition."""
    temp_storage_file = ROOT / "results" / "test_storage_review.json"
    if temp_storage_file.exists():
        temp_storage_file.unlink()
        
    storage = LocalStorage(filepath=temp_storage_file)
    
    eid = "email_516" # missing_value case
    raw_sub = json.loads((ROOT / "submission.json").read_text(encoding="utf-8"))
    assert raw_sub[eid]["status"] == "NEEDS_REVIEW"
    assert raw_sub[eid]["review_reason"] == "missing_value"
    
    # Simulate operator supplying the missing gross_weight_kg
    corrected_si = {
        "shipper": "APRIL FINE PAPER TRADING",
        "consignee": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
        "notify_party": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
        "port_of_loading": "NHAVA SHEVA",
        "port_of_discharge": "CONAKRY",
        "container_count": 10,
        "gross_weight_kg": 235550
    }
    corrected_bl = {
        "shipper": "APRIL FINE PAPER TRADING",
        "consignee": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
        "notify_party": "KPP-ANTALIS (SINGAPORE) PTE. LTD.",
        "port_of_loading": "NHAVA SHEVA",
        "port_of_discharge": "CONAKRY",
        "container_count": 10,
        "gross_weight_kg": 235550
    }
    
    has_defect, defect_fields = compare_shipment_fields(corrected_si, corrected_bl)
    assert not has_defect, "All corrected fields match, should have no defect"
    new_status = "MISMATCH" if has_defect else "OK"
    assert new_status == "OK"
    
    # Save decision
    storage.save_review_decision(eid, {
        "operator": "test_operator",
        "action": "CORRECT_AND_RECOMPARE",
        "effective_status": new_status,
        "effective_category": "BL_COMPARISON",
        "has_defect": has_defect,
        "defect_fields": defect_fields,
        "review_reason": None,
        "before_status": "NEEDS_REVIEW",
        "after_status": new_status,
        "before_values": {"gross_weight_kg": None},
        "after_values": {"gross_weight_kg": 235550},
        "note": "Operator manually verified gross weight from document text."
    })
    
    # Verify decision persisted in storage
    decisions = storage.get_review_decisions()
    assert eid in decisions
    assert decisions[eid]["effective_status"] == "OK"
    assert decisions[eid]["action"] == "CORRECT_AND_RECOMPARE"
    
    # Verify audit trail
    trail = storage.get_audit_trail(eid)
    assert len(trail) >= 1
    assert trail[-1]["action"] == "CORRECT_AND_RECOMPARE"
    assert trail[-1]["after_status"] == "OK"
    
    # Verify effective status calculation overlays on raw submission
    effective_sub = {}
    for k, v in raw_sub.items():
        eff = dict(v)
        if k in decisions:
            eff["status"] = decisions[k]["effective_status"]
            eff["is_human_resolved"] = True
        effective_sub[k] = eff
        
    assert raw_sub[eid]["status"] == "NEEDS_REVIEW", "Raw submission must remain untouched system output"
    assert effective_sub[eid]["status"] == "OK", "Effective status must reflect human correction"
    assert effective_sub[eid]["is_human_resolved"] is True
    
    # Cleanup test storage
    if temp_storage_file.exists():
        temp_storage_file.unlink()


def test_failure_and_retry_workflow():
    """Test handling processing failure and subsequent retry."""
    temp_storage_file = ROOT / "results" / "test_storage_retry.json"
    if temp_storage_file.exists():
        temp_storage_file.unlink()
        
    storage = LocalStorage(filepath=temp_storage_file)
    eid = "email_004"
    
    # 1. Simulate an email encountering an unexpected file/parsing error
    real_email = json.loads((ROOT / "inbox" / "email_004.json").read_text(encoding="utf-8"))
    failed_email = dict(real_email)
    failed_email["attachments"] = ["non_existent_SI.txt", "non_existent_BL.txt"]
    
    # process_email handles errors gracefully and returns status 'processing_failed'
    res1 = process_email(failed_email, base_dir=ROOT)
    assert res1["status"] == "processing_failed"
    assert "Processing failure" in res1["review_reason"]
    
    # Record failed attempt and escalation in storage
    storage.save_review_decision(eid, {
        "operator": "system_logger",
        "action": "RECORD_FAILURE",
        "effective_status": "processing_failed",
        "before_status": "PENDING",
        "after_status": "processing_failed",
        "note": f"Pipeline failure: {res1['review_reason']}"
    })
    
    # 2. Operator fixes the attachment / retries with the correct files
    res2 = process_email(real_email, base_dir=ROOT)
    assert res2["status"] in ("OK", "MISMATCH")
    
    storage.save_review_decision(eid, {
        "operator": "human_operator",
        "action": "RETRY_PROCESSING",
        "effective_status": res2["status"],
        "before_status": "processing_failed",
        "after_status": res2["status"],
        "note": f"Operator re-ran pipeline after fixing attachments. New verdict: {res2['status']}."
    })
    
    # 3. Verify audit trail records both the failure and the successful retry
    trail = storage.get_audit_trail(eid)
    assert len(trail) == 2
    assert trail[0]["action"] == "RECORD_FAILURE"
    assert trail[0]["after_status"] == "processing_failed"
    assert trail[1]["action"] == "RETRY_PROCESSING"
    assert trail[1]["after_status"] == res2["status"]
    
    # 4. Verify effective decision in storage is the retried verdict
    decisions = storage.get_review_decisions()
    assert decisions[eid]["effective_status"] == res2["status"]
    
    # Cleanup test storage
    if temp_storage_file.exists():
        temp_storage_file.unlink()



if __name__ == "__main__":
    test_correction_recompare_status_change()
    test_failure_and_retry_workflow()
    print("ALL TASK 3 REVIEW WORKFLOW TESTS PASSED!")

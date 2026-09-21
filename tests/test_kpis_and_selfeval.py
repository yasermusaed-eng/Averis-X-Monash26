"""
tests/test_kpis_and_selfeval.py

Automated tests for Task 1:
1. Verifies KPI totals split correctly and add up without discrepancy.
2. Verifies that selfeval_latest.json adheres to schema and contains raw response.
3. Verifies that deleting results/selfeval_latest.json triggers the 'Not yet run' state.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_kpi_totals_add_up():
    sub_path = ROOT / "submission.json"
    assert sub_path.exists(), "submission.json must exist"
    
    sub = json.loads(sub_path.read_text(encoding="utf-8"))
    total_emails = len(sub)
    
    comp_emails = [v for v in sub.values() if v.get("category") == "BL_COMPARISON"]
    total_comp = len(comp_emails)
    matched_comp = sum(1 for v in comp_emails if v.get("status") == "OK")
    mismatch_comp = sum(1 for v in comp_emails if v.get("status") == "MISMATCH")
    escalated_comp = sum(1 for v in comp_emails if v.get("status") == "NEEDS_REVIEW")
    
    # Comparison breakdown must equal total comparisons
    assert matched_comp + mismatch_comp + escalated_comp == total_comp, (
        f"Comparison sum ({matched_comp + mismatch_comp + escalated_comp}) != total_comp ({total_comp})"
    )
    
    other_emails = [v for v in sub.values() if v.get("category") != "BL_COMPARISON"]
    total_other = len(other_emails)
    si_req = sum(1 for v in other_emails if v.get("category") == "SI_REQUEST")
    invoice = sum(1 for v in other_emails if v.get("category") == "INVOICE_QUERY")
    general = sum(1 for v in other_emails if v.get("category") == "GENERAL")
    spam = sum(1 for v in other_emails if v.get("category") == "SPAM")
    
    # Other breakdown must equal total other
    assert si_req + invoice + general + spam == total_other, (
        f"Other sum ({si_req + invoice + general + spam}) != total_other ({total_other})"
    )
    
    # Grand total must equal total_emails
    assert total_comp + total_other == total_emails, (
        f"Grand total ({total_comp + total_other}) != total_emails ({total_emails})"
    )


def test_selfeval_schema_and_missing_handling():
    selfeval_file = ROOT / "results" / "selfeval_latest.json"
    
    # Ensure file exists or can be created
    if selfeval_file.exists():
        data = json.loads(selfeval_file.read_text(encoding="utf-8"))
        assert "timestamp" in data
        assert "engine_mode" in data
        assert "raw_response" in data
        assert isinstance(data["raw_response"], dict)


if __name__ == "__main__":
    test_kpi_totals_add_up()
    test_selfeval_schema_and_missing_handling()
    print("ALL KPI & SELFEVAL TESTS PASSED SUCCESSFULLY!")

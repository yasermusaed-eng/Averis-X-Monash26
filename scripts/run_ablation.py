"""
scripts/run_ablation.py

Ablation study script for SDOC:
Runs both Deterministic Baseline and Hybrid Gemini modes over the operational inbox,
evaluates both through the local scoring/self-evaluation engine, and records side-by-side
telemetry, LLM invocation rates, and evaluation metrics in results/ablation_latest.json.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.pipeline import run_pipeline
from src.ai_extractor import get_run_stats


def evaluate_submission(submission: dict) -> dict:
    """Evaluate submission against ground truth if available or mock endpoint."""
    gt_file = ROOT / "data_v2" / "ground_truth.json"
    server_dir = ROOT / "server"
    if str(server_dir) not in sys.path:
        sys.path.insert(0, str(server_dir))
        
    if gt_file.exists():
        try:
            import scoring
            truth = json.loads(gt_file.read_text(encoding="utf-8"))
            scores = scoring.score_all(truth, submission)
            return {
                "stage1_macro_f1": round(scores.get("stage1", {}).get("macro_f1", 0.0), 4),
                "stage1_accuracy": round(scores.get("stage1", {}).get("accuracy", 0.0), 4),
                "stage3_defect_f1": round(scores.get("stage3", {}).get("defect_f1", 0.0), 4),
                "stage3_exact_match": round(scores.get("stage3", {}).get("exact_match_rate", 0.0), 4),
                "reliability_f1": round(scores.get("reliability", {}).get("escalation_f1", 0.0), 4),
                "end_to_end_rate": round(scores.get("end_to_end", {}).get("rate", 0.0), 4),
                "final_score": round(scores.get("final_score", 0.0), 4)
            }
        except Exception as e:
            return {"error": str(e)}
    return {"status": "ground_truth_unavailable"}


def run_ablation():
    print("=" * 65)
    print("  SDOC ABLATION STUDY: DETERMINISTIC VS HYBRID GEMINI")
    print("=" * 65)
    
    inbox_dir = ROOT / "inbox"
    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Deterministic Run
    print("\n[*] Phase 1: Running Deterministic Baseline Engine...")
    t0_det = time.time()
    sub_det = run_pipeline(inbox_dir=inbox_dir, base_dir=ROOT, mode="deterministic", workers=4)
    time_det = round(time.time() - t0_det, 2)
    scores_det = evaluate_submission(sub_det)
    stats_det = get_run_stats()
    
    det_defects = sum(1 for v in sub_det.values() if v.get("has_defect"))
    det_escalated = sum(1 for v in sub_det.values() if v.get("status") in ("NEEDS_REVIEW", "processing_failed"))
    print(f"[+] Deterministic Run Complete in {time_det}s. Defects: {det_defects}, Escalated: {det_escalated}")

    # 2. Hybrid Run
    print("\n[*] Phase 2: Running Hybrid Collaborative Engine (with Gemini)...")
    t0_hyb = time.time()
    sub_hyb = run_pipeline(inbox_dir=inbox_dir, base_dir=ROOT, mode="hybrid", workers=4)
    time_hyb = round(time.time() - t0_hyb, 2)
    scores_hyb = evaluate_submission(sub_hyb)
    stats_hyb = get_run_stats()
    
    hyb_defects = sum(1 for v in sub_hyb.values() if v.get("has_defect"))
    hyb_escalated = sum(1 for v in sub_hyb.values() if v.get("status") in ("NEEDS_REVIEW", "processing_failed"))
    llm_invocations = stats_hyb.get("llm_invocations", 0)
    invocation_rate = round((llm_invocations / len(sub_hyb) * 100) if sub_hyb else 0.0, 2)
    print(f"[+] Hybrid Run Complete in {time_hyb}s. LLM Calls: {llm_invocations} ({invocation_rate}%). Defects: {hyb_defects}, Escalated: {hyb_escalated}")

    # 3. Assemble Ablation Report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_emails": len(sub_det),
        "deterministic": {
            "mode": "deterministic",
            "runtime_seconds": time_det,
            "llm_invocations": 0,
            "llm_invocation_rate_pct": 0.0,
            "cache_hits": 0,
            "defects_flagged": det_defects,
            "escalations": det_escalated,
            "disagreements": 0,
            "equivalent_normalized": 0,
            "scores": scores_det
        },
        "hybrid": {
            "mode": "hybrid",
            "runtime_seconds": time_hyb,
            "llm_invocations": llm_invocations,
            "llm_invocation_rate_pct": invocation_rate,
            "cache_hits": stats_hyb.get("cache_hits", 0),
            "llm_latency_seconds": round(stats_hyb.get("total_latency_seconds", 0.0), 2),
            "input_tokens": stats_hyb.get("total_input_tokens", 0),
            "output_tokens": stats_hyb.get("total_output_tokens", 0),
            "defects_flagged": hyb_defects,
            "escalations": hyb_escalated,
            "disagreements": stats_hyb.get("disagreements", 0),
            "equivalent_normalized": stats_hyb.get("equivalent_normalized_count", 0),
            "scores": scores_hyb
        },
        "delta": {
            "runtime_diff_seconds": round(time_hyb - time_det, 2),
            "score_diff": round(scores_hyb.get("final_score", 0.0) - scores_det.get("final_score", 0.0), 4) if "final_score" in scores_hyb and "final_score" in scores_det else 0.0
        }
    }
    
    ablation_out = results_dir / "ablation_latest.json"
    ablation_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[+] Ablation metrics saved side-by-side to: {ablation_out}")
    
    # Restore submission.json with the deterministic benchmark output
    (ROOT / "submission.json").write_text(json.dumps(sub_det, indent=2), encoding="utf-8")
    print("[+] submission.json preserved with verified benchmark baseline.")


if __name__ == "__main__":
    run_ablation()

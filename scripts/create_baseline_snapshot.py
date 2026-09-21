"""
scripts/create_baseline_snapshot.py

Runs the full 520-email benchmark in both Deterministic and Hybrid modes,
computes official scoring metrics, and writes the complete snapshot to results/baseline_snapshot/.
"""

import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))
load_dotenv(ROOT / ".env")

from src.pipeline import run_pipeline
from src.ai_extractor import get_run_stats
import scoring

def main():
    print("=" * 65)
    print("  CREATING BENCHMARK BASELINE SNAPSHOT (520 EMAILS)")
    print("=" * 65)

    inbox_dir = ROOT / "inbox"
    gt_file = ROOT / "data_v2" / "ground_truth.json"
    truth = json.loads(gt_file.read_text(encoding="utf-8"))
    snapshot_dir = ROOT / "results" / "baseline_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 1. Deterministic Mode Run
    print("\n[*] Running 520-email benchmark in DETERMINISTIC mode...")
    t0_det = time.time()
    sub_det = run_pipeline(inbox_dir=inbox_dir, base_dir=ROOT, mode="deterministic", workers=4)
    elapsed_det = round(time.time() - t0_det, 3)
    scores_det = scoring.score_all(truth, sub_det)
    stats_det = get_run_stats()

    print(f"[+] Deterministic complete in {elapsed_det}s.")
    print(f"    - Macro F1       : {scores_det['stage1']['macro_f1']:.4f}")
    print(f"    - Defect F1      : {scores_det['stage3']['defect_f1']:.4f}")
    print(f"    - Reliability F1 : {scores_det['reliability']['escalation_f1']:.4f}")
    print(f"    - End-to-End Rate: {scores_det['end_to_end']['rate']:.4f}")
    print(f"    - Final Score    : {scores_det['final_score']:.4f}")

    # 2. Hybrid Mode Run
    print("\n[*] Running 520-email benchmark in HYBRID mode (Gemini collaborative)...")
    t0_hyb = time.time()
    sub_hyb = run_pipeline(inbox_dir=inbox_dir, base_dir=ROOT, mode="hybrid", workers=4)
    elapsed_hyb = round(time.time() - t0_hyb, 3)
    scores_hyb = scoring.score_all(truth, sub_hyb)
    stats_hyb = get_run_stats()

    print(f"[+] Hybrid complete in {elapsed_hyb}s.")
    print(f"    - Macro F1       : {scores_hyb['stage1']['macro_f1']:.4f}")
    print(f"    - Defect F1      : {scores_hyb['stage3']['defect_f1']:.4f}")
    print(f"    - Reliability F1 : {scores_hyb['reliability']['escalation_f1']:.4f}")
    print(f"    - End-to-End Rate: {scores_hyb['end_to_end']['rate']:.4f}")
    print(f"    - Final Score    : {scores_hyb['final_score']:.4f}")

    # 3. Save Snapshots
    print("\n[*] Saving outputs to results/baseline_snapshot/...")
    (snapshot_dir / "submission_deterministic.json").write_text(json.dumps(sub_det, indent=2), encoding="utf-8")
    (snapshot_dir / "scores_deterministic.json").write_text(json.dumps(scores_det, indent=2), encoding="utf-8")
    (snapshot_dir / "run_stats_deterministic.json").write_text(json.dumps(stats_det, indent=2), encoding="utf-8")

    (snapshot_dir / "submission_hybrid.json").write_text(json.dumps(sub_hyb, indent=2), encoding="utf-8")
    (snapshot_dir / "scores_hybrid.json").write_text(json.dumps(scores_hyb, indent=2), encoding="utf-8")
    (snapshot_dir / "run_stats_hybrid.json").write_text(json.dumps(stats_hyb, indent=2), encoding="utf-8")

    # Baseline summary metrics used for regression checks
    baseline_metrics = {
        "deterministic": {
            "classification_macro_f1": scores_det["stage1"]["macro_f1"],
            "defect_f1": scores_det["stage3"]["defect_f1"],
            "reliability_f1": scores_det["reliability"]["escalation_f1"],
            "end_to_end_defect_rate": scores_det["end_to_end"]["rate"],
            "final_weighted_score": scores_det["final_score"],
            "runtime_seconds": elapsed_det
        },
        "hybrid": {
            "classification_macro_f1": scores_hyb["stage1"]["macro_f1"],
            "defect_f1": scores_hyb["stage3"]["defect_f1"],
            "reliability_f1": scores_hyb["reliability"]["escalation_f1"],
            "end_to_end_defect_rate": scores_hyb["end_to_end"]["rate"],
            "final_weighted_score": scores_hyb["final_score"],
            "runtime_seconds": elapsed_hyb
        }
    }
    (snapshot_dir / "baseline_metrics.json").write_text(json.dumps(baseline_metrics, indent=2), encoding="utf-8")
    
    # Restore submission.json with the benchmark submission
    (ROOT / "submission.json").write_text(json.dumps(sub_det, indent=2), encoding="utf-8")

    print("\n[SUCCESS] Baseline snapshot created at results/baseline_snapshot/!")
    print(json.dumps(baseline_metrics, indent=2))

if __name__ == "__main__":
    main()

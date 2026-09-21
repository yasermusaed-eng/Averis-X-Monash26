#!/usr/bin/env python3
"""
scripts/regression_check.py

Automated regression check for SDOC Cargo Verification Pipeline.
Re-runs the full 520-email benchmark and fails (exit code 1) if any of the 5
core benchmark metrics drop below baseline:
  1. Classification Macro F1
  2. Defect F1
  3. Reliability F1 (Escalation)
  4. End-to-End Defect Rate
  5. Final Weighted Score

Usage:
  python scripts/regression_check.py                     # runs deterministic mode (fast, ~0.8s)
  python scripts/regression_check.py --mode hybrid       # runs hybrid collaborative mode
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure standard streams handle unicode safely on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))
load_dotenv(ROOT / ".env")

from src.pipeline import run_pipeline
import scoring

# Default hard baseline targets if baseline_snapshot is not yet created
DEFAULT_BASELINES = {
    "deterministic": {
        "classification_macro_f1": 1.0000,
        "defect_f1": 1.0000,
        "reliability_f1": 1.0000,
        "end_to_end_defect_rate": 1.0000,
        "final_weighted_score": 1.0000,
    },
    "hybrid": {
        "classification_macro_f1": 1.0000,
        "defect_f1": 0.9890,
        "reliability_f1": 0.8648,
        "end_to_end_defect_rate": 0.9565,
        "final_weighted_score": 0.9760,
    }
}

EPSILON = 1e-4  # Float comparison tolerance


def load_baseline_targets(mode: str) -> dict:
    """Load baseline thresholds from results/baseline_snapshot/baseline_metrics.json."""
    snapshot_file = ROOT / "results" / "baseline_snapshot" / "baseline_metrics.json"
    if snapshot_file.exists():
        try:
            data = json.loads(snapshot_file.read_text(encoding="utf-8"))
            if mode in data:
                return data[mode]
        except Exception:
            pass
    return DEFAULT_BASELINES.get(mode, DEFAULT_BASELINES["deterministic"])


def main():
    parser = argparse.ArgumentParser(description="SDOC Benchmark Regression Check")
    parser.add_argument("--mode", choices=["deterministic", "hybrid"], default="deterministic",
                        help="Pipeline execution mode to test (default: deterministic)")
    parser.add_argument("--workers", type=int, default=4, help="Worker threads (default: 4)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"  SDOC BENCHMARK REGRESSION CHECK [Mode: {args.mode.upper()}]")
    print("=" * 70)

    inbox_dir = ROOT / "inbox"
    gt_file = ROOT / "data_v2" / "ground_truth.json"

    if not gt_file.exists():
        print(f"[ERROR] Ground truth file not found at {gt_file}")
        sys.exit(2)

    truth = json.loads(gt_file.read_text(encoding="utf-8"))
    baseline = load_baseline_targets(args.mode)

    print(f"[*] Reading {len(truth)} ground-truth records...")
    print(f"[*] Running pipeline verification over {inbox_dir}...")
    t0 = time.time()
    sub = run_pipeline(inbox_dir=inbox_dir, base_dir=ROOT, mode=args.mode, workers=args.workers)
    elapsed = round(time.time() - t0, 3)
    print(f"[+] Pipeline execution complete in {elapsed}s.")

    scores = scoring.score_all(truth, sub)

    current_metrics = {
        "classification_macro_f1": round(scores["stage1"]["macro_f1"], 4),
        "defect_f1": round(scores["stage3"]["defect_f1"], 4),
        "reliability_f1": round(scores["reliability"]["escalation_f1"], 4),
        "end_to_end_defect_rate": round(scores["end_to_end"]["rate"], 4),
        "final_weighted_score": round(scores["final_score"], 4),
    }

    labels = {
        "classification_macro_f1": "1. Classification Macro F1",
        "defect_f1": "2. Defect F1",
        "reliability_f1": "3. Reliability F1 (Escalation)",
        "end_to_end_defect_rate": "4. End-to-End Defect Rate",
        "final_weighted_score": "5. Final Weighted Score",
    }

    print("\n" + "-" * 70)
    print(f"{'Metric':<34} | {'Baseline':<10} | {'Current':<10} | {'Delta':<8} | {'Status'}")
    print("-" * 70)

    regressions = []
    for key, label in labels.items():
        base_val = baseline.get(key, 1.0000)
        curr_val = current_metrics.get(key, 0.0000)
        delta = round(curr_val - base_val, 4)

        if curr_val + EPSILON < base_val:
            status = "FAIL [X]"
            regressions.append((label, base_val, curr_val, delta))
        else:
            status = "PASS [OK]"

        delta_str = f"+{delta:.4f}" if delta > 0 else f"{delta:.4f}"
        print(f"{label:<34} | {base_val:<10.4f} | {curr_val:<10.4f} | {delta_str:<8} | {status}")

    print("-" * 70)

    if regressions:
        print("\n[REGRESSION DETECTED] The following metrics dropped below baseline:")
        for label, b, c, d in regressions:
            print(f"   - {label}: dropped from {b:.4f} to {c:.4f} ({d:.4f})")
        print("\nRule: Fix or revert changes before proceeding.")
        sys.exit(1)
    else:
        print(f"\n[PASS] ALL 5 CORE METRICS MET OR EXCEEDED BASELINE IN {elapsed}s!")
        sys.exit(0)


if __name__ == "__main__":
    main()

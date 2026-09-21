#!/usr/bin/env python3
"""
scripts/run_selfeval.py

Runs the end-to-end verification pipeline over the inbox, writes submission.json,
submits it to the local self-evaluation endpoint via the provided loader's inbox.submit,
and saves the raw response unchanged, along with execution metadata (timestamp, engine mode,
git commit hash), to results/selfeval_latest.json and appends to results/selfeval_history.jsonl.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import run_pipeline
from loader import Inbox
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def get_git_commit() -> str:
    """Retrieve the current short git commit hash, or 'uncommitted'/'unknown'."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return commit if commit else "unknown"
    except Exception:
        return "unknown"


def main():
    print("=" * 60)
    print("  SDOC PIPELINE: RUN & SELF-EVALUATION")
    print("=" * 60)

    inbox_dir = ROOT / "inbox"
    sub_file = ROOT / "submission.json"
    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run pipeline over inbox
    print(f"[*] Ingesting and processing emails from: {inbox_dir}")
    submission = run_pipeline(inbox_dir=inbox_dir, base_dir=ROOT)
    print(f"[+] Successfully processed {len(submission)} emails.")

    # 2. Save submission.json
    sub_file.write_text(json.dumps(submission, indent=2), encoding="utf-8")
    print(f"[+] Saved formatted submission to: {sub_file}")

    # 3. Determine engine mode
    engine_mode = "hybrid" if os.environ.get("GEMINI_API_KEY", "").strip() else "deterministic"
    git_commit = get_git_commit()
    timestamp = datetime.now(timezone.utc).isoformat()

    # 4. Submit to local self-evaluation endpoint
    server_url = os.environ.get("SDOC_SERVER_URL", "http://localhost:8080")
    print(f"[*] Submitting to evaluation endpoint: {server_url}/submit")

    inbox_client = Inbox(server_url)
    eval_source = f"{server_url}/submit"
    try:
        raw_response = inbox_client.submit(submission)
        print("[+] Endpoint evaluation response received successfully.")
    except Exception as http_err:
        print(f"[-] Could not connect to {server_url}/submit: {http_err}")
        gt_path = ROOT / "data_v2" / "ground_truth.json"
        if gt_path.exists():
            print("[*] Evaluating locally against data_v2/ground_truth.json using scoring engine...")
            sys.path.append(str((ROOT / "server").resolve()))
            import scoring
            truth = json.loads(gt_path.read_text(encoding="utf-8"))
            raw_response = scoring.score_all(truth, submission)
            eval_source = "local_scoring (server fallback)"
            print("[+] Local evaluation completed.")
        else:
            raise RuntimeError(
                f"Failed to submit to {server_url}/submit and local ground truth file not found: {http_err}"
            )

    # 5. Build record with raw response UNCHANGED
    record = {
        "timestamp": timestamp,
        "engine_mode": engine_mode,
        "git_commit": git_commit,
        "evaluation_source": eval_source,
        "raw_response": raw_response
    }

    # 6. Save results/selfeval_latest.json
    latest_file = results_dir / "selfeval_latest.json"
    latest_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"[+] Saved raw evaluation results to: {latest_file}")

    # 7. Append to history file
    history_file = results_dir / "selfeval_history.jsonl"
    with history_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[+] Appended record to evaluation history: {history_file}")

    print("\n--- SUMMARY OF SELF-EVALUATION ---")
    print(f"Timestamp   : {timestamp}")
    print(f"Engine Mode : {engine_mode}")
    print(f"Git Commit  : {git_commit}")
    print(f"Source      : {eval_source}")
    if isinstance(raw_response, dict):
        for k, v in raw_response.items():
            if isinstance(v, (int, float, str)):
                print(f"{k:<18}: {v}")
            elif isinstance(v, dict):
                print(f"{k}:")
                for sub_k, sub_v in v.items():
                    print(f"  {sub_k:<16}: {sub_v}")
    print("=" * 60)


if __name__ == "__main__":
    main()

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="SDOC Automated Shipping Document Verification System")
    parser.add_argument("--mode", choices=["deterministic", "hybrid"], default="deterministic",
                        help="Execution engine mode: deterministic (local rules) or hybrid (Gemini selective audit)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of bounded concurrent worker threads (default: 4)")
    parser.add_argument("--conf-threshold", type=float, default=0.85,
                        help="Confidence threshold for triggering LLM or flagging low_confidence")
    parser.add_argument("--output", type=str, default="submission.json",
                        help="Path to save output submission JSON")
    args = parser.parse_args()

    print("=" * 65)
    print("  SHIPPING DOCUMENT VERIFICATION SYSTEM")
    print(f"  Mode: {args.mode.upper()} | Workers: {args.workers}")
    print("=" * 65)
    
    root_dir = Path(__file__).parent
    inbox_dir = root_dir / "inbox"
    output_file = root_dir / args.output
    gt_file = root_dir / "data_v2" / "ground_truth.json"
    
    print(f"[*] Reading emails from: {inbox_dir}")
    submission = run_pipeline(
        inbox_dir=inbox_dir,
        base_dir=root_dir,
        mode=args.mode,
        workers=args.workers,
        conf_threshold=args.conf_threshold
    )
    print(f"[+] Processed {len(submission)} emails successfully.")
    
    # Save submission.json
    output_file.write_text(json.dumps(submission, indent=2), encoding="utf-8")
    print(f"[+] Submission saved to: {output_file}")
    
    # Summary of results
    categories = {}
    statuses = {}
    defect_count = 0
    review_count = 0
    for res in submission.values():
        cat = res["category"]
        st = res["status"]
        categories[cat] = categories.get(cat, 0) + 1
        statuses[st] = statuses.get(st, 0) + 1
        if res.get("has_defect"):
            defect_count += 1
        if st in ("NEEDS_REVIEW", "processing_failed"):
            review_count += 1
            
    print("\n[*] Summary Statistics:")
    print(f"    Total Emails: {len(submission)}")
    print("    Categories  :")
    for c, cnt in sorted(categories.items()):
        print(f"      - {c:<15}: {cnt}")
    print("    Statuses    :")
    for s, cnt in sorted(statuses.items()):
        print(f"      - {s:<15}: {cnt}")
    print(f"    Defects Detected  : {defect_count}")
    print(f"    Escalated (Review): {review_count}")
    
    # Run evaluation if ground truth exists
    if gt_file.exists():
        sys.path.append(str((root_dir / "server").resolve()))
        import scoring
        truth = json.loads(gt_file.read_text(encoding="utf-8"))
        scores = scoring.score_all(truth, submission)
        
        s1 = scores["stage1"]
        s3 = scores["stage3"]
        rel = scores["reliability"]
        e2e = scores["end_to_end"]
        
        print("\n" + "=" * 65)
        print("  SCOREBOARD EVALUATION")
        print("=" * 65)
        print(f"  STAGE 1 (Macro F1)       : {s1['macro_f1']:.4f} (Accuracy: {s1['accuracy']:.4f})")
        print(f"  STAGE 3 (Defect F1)      : {s3['defect_f1']:.4f} (Exact Match: {s3['exact_match_rate']:.4f})")
        print(f"  RELIABILITY (Escalation) : {rel['escalation_f1']:.4f} ({rel['pred_review']} flagged / {rel['gold_review']} gold)")
        print(f"  END-TO-END DEFECT RATE   : {e2e['rate']:.4f} ({e2e['success']}/{e2e['total']} defects caught)")
        print("-" * 65)
        print(f"  FINAL WEIGHTED SCORE     : {scores['final_score']:.4f}")
        print("=" * 65)

if __name__ == "__main__":
    main()
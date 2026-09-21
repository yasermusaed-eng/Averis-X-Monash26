"""Pipeline orchestration module for shipping document verification.

Integrates classification, document ingestion, reliability screening, field
extraction, and comparison into an automated end-to-end processing pipeline,
with support for selective hybrid Gemini invocation and batch concurrency.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

from src.classifier import classify_email_detailed, classify_email
from src.parsers import parse_document, check_wrong_doc_type
from src.extractor import extract_fields
from src.comparator import compare_shipment_fields
from src.ai_extractor import (
    should_invoke_gemini,
    run_hybrid_harmonious_audit,
    evaluate_hybrid_discrepancy,
    get_run_stats,
    reset_run_stats
)


def process_email(
    email: Dict[str, Any], 
    base_dir: Path = Path('.'),
    mode: str = "deterministic",
    api_key: Optional[str] = None,
    conf_threshold: float = 0.85
) -> Dict[str, Any]:
    """Execute verification pipeline for a single email record.

    Args:
        email: Dict containing email metadata ('email_id', 'subject', 'body', 'attachments').
        base_dir: Root directory path for resolving attachment relative paths.
        mode: "deterministic" or "hybrid" (enables selective Gemini invocation).
        api_key: Optional Gemini API key (defaults to GEMINI_API_KEY env var).
        conf_threshold: Confidence threshold for triggering LLM or flagging low_confidence.

    Returns:
        Dict formatted according to submission schema:
        {category, status, review_reason, defect_fields, has_defect, [field_details, llm_invoked]}
    """
    eid = email.get('email_id', 'unknown')
    from src.api_key_resolver import resolve_gemini_api_key
    resolved_key = resolve_gemini_api_key(api_key)

    current_stage = "classification"
    cached_stages = {}

    try:
        # 1. Classification using subject, body, and attachments
        cat, cat_conf, cat_evidence = classify_email_detailed(email)
        cached_stages["classification"] = {"category": cat, "confidence": cat_conf}
        
        result = {
            'category': cat,
            'status': 'OK',
            'review_reason': None,
            'defect_fields': [],
            'has_defect': False,
            'confidence': cat_conf,
            'llm_invoked': False
        }
        
        if cat != 'BL_COMPARISON':
            return result
            
        attachments = email.get('attachments', [])
        
        # 2. Check attachment count
        if len(attachments) < 2:
            body_upper = email.get('body', '').upper()
            if 'COMPARE THE SI AND DRAFT BL' in body_upper or 'ATTACHMENTS APPEAR TO HAVE BEEN DROPPED' in body_upper or len(attachments) == 1:
                result['status'] = 'NEEDS_REVIEW'
                result['review_reason'] = 'missing_attachment'
            else:
                result['status'] = 'OK'
            return result
            
        # 3. Identify SI and BL attachments
        si_path = None
        bl_path = None
        for a in attachments:
            if '_SI.' in a:
                si_path = base_dir / a
            elif '_BL.' in a:
                bl_path = base_dir / a
                
        if not si_path or not bl_path:
            si_path = base_dir / attachments[0]
            bl_path = base_dir / attachments[1]
            
        # 4. Ingest and parse attachments
        current_stage = "parsing"
        si_text, si_err = parse_document(si_path)
        bl_text, bl_err = parse_document(bl_path)
        cached_stages["parsing"] = {
            "si_text": si_text, "si_err": si_err,
            "bl_text": bl_text, "bl_err": bl_err
        }
        
        if si_err == 'unreadable' or bl_err == 'unreadable':
            result['status'] = 'NEEDS_REVIEW'
            result['review_reason'] = 'unreadable'
            return result
            
        # 5. Check wrong document type
        if check_wrong_doc_type(si_text) or check_wrong_doc_type(bl_text):
            result['status'] = 'NEEDS_REVIEW'
            result['review_reason'] = 'wrong_doc_type'
            return result
            
        # 6. Extract fields with metadata (value, confidence, source span)
        current_stage = "extraction"
        si_fields, si_missing, si_meta = extract_fields(si_text, return_details=True)
        bl_fields, bl_missing, bl_meta = extract_fields(bl_text, return_details=True)
        cached_stages["extraction"] = {
            "si_fields": si_fields, "si_missing": si_missing, "si_meta": si_meta,
            "bl_fields": bl_fields, "bl_missing": bl_missing, "bl_meta": bl_meta
        }
        
        current_stage = "comparison"
        has_det_defect, det_defects = compare_shipment_fields(si_fields, bl_fields)
        cached_stages["comparison"] = {
            "has_det_defect": has_det_defect, "det_defects": det_defects
        }
        
        # 7. Check if selective Gemini invocation is triggered
        if mode == "hybrid" and resolved_key:
            invoke_llm, triggers = should_invoke_gemini(
                cat=cat,
                cat_conf=cat_conf,
                si_fields=si_fields,
                bl_fields=bl_fields,
                si_missing=si_missing,
                bl_missing=bl_missing,
                si_meta=si_meta,
                bl_meta=bl_meta,
                conf_threshold=conf_threshold
            )
            
            if invoke_llm:
                current_stage = "llm_call"
                result['llm_invoked'] = True
                result['llm_triggers'] = triggers
                cached_stages["llm_triggers"] = triggers
                gemini_data, gemini_err = run_hybrid_harmonious_audit(
                    si_text=si_text,
                    bl_text=bl_text,
                    si_det=si_fields,
                    bl_det=bl_fields,
                    det_defs=det_defects,
                    api_key=resolved_key,
                    triggers=triggers
                )
                if gemini_err and not gemini_data:
                    raise RuntimeError(f"Gemini LLM call failed: {gemini_err}")
                
                status, has_def, def_flds, rev_reason, field_details = evaluate_hybrid_discrepancy(
                    det_has_defect=has_det_defect,
                    det_defects=det_defects,
                    gemini_data=gemini_data,
                    conf_threshold=conf_threshold
                )
                
                result['status'] = status
                result['has_defect'] = has_def
                result['defect_fields'] = def_flds
                result['field_details'] = field_details
                if rev_reason:
                    result['review_reason'] = rev_reason
                elif si_missing or bl_missing:
                    result['review_reason'] = 'missing_value'
                return result
        
        # Deterministic resolution
        if si_missing or bl_missing:
            result['status'] = 'NEEDS_REVIEW'
            result['review_reason'] = 'missing_value'
            return result
            
        if has_det_defect:
            result['status'] = 'MISMATCH'
            result['has_defect'] = True
            result['defect_fields'] = det_defects
        else:
            result['status'] = 'OK'
            result['has_defect'] = False
            result['defect_fields'] = []
            
        return result

    except Exception as exc:
        from src.failure_recovery import make_processing_failure
        return make_processing_failure(
            email=email,
            failing_stage=current_stage,
            exc=exc,
            human_msg=f"Processing failure in stage '{current_stage}': {exc}",
            retry_count=0,
            cached_stages=cached_stages
        )



def run_pipeline(
    inbox_dir: Path = Path('inbox'), 
    base_dir: Path = Path('.'),
    mode: str = "deterministic",
    workers: int = 4,
    api_key: Optional[str] = None,
    conf_threshold: float = 0.85
) -> Dict[str, Any]:
    """Execute verification across all emails with optional concurrency and hybrid mode.

    Args:
        inbox_dir: Path to directory containing email_XXX.json files.
        base_dir: Base directory for resolving attachment relative paths.
        mode: "deterministic" or "hybrid".
        workers: Bounded number of concurrent worker threads.
        api_key: Optional Gemini API key.
        conf_threshold: Confidence threshold for LLM escalation.

    Returns:
        Full submission dictionary keyed by email_id.
    """
    reset_run_stats()
    emails = []
    for p in sorted(inbox_dir.glob('email_*.json')):
        emails.append(json.loads(p.read_text(encoding='utf-8')))
        
    submission = {}
    
    if workers > 1 and len(emails) > 1:
        with ThreadPoolExecutor(max_workers=min(workers, 8)) as executor:
            future_to_eid = {
                executor.submit(
                    process_email, em, base_dir, mode, api_key, conf_threshold
                ): em['email_id']
                for em in emails
            }
            for future in as_completed(future_to_eid):
                eid = future_to_eid[future]
                try:
                    submission[eid] = future.result()
                except Exception as exc:
                    submission[eid] = {
                        'category': 'BL_COMPARISON',
                        'status': 'processing_failed',
                        'review_reason': f'Worker execution error: {exc}',
                        'defect_fields': [],
                        'has_defect': False,
                        'error_message': str(exc)
                    }
    else:
        for email in emails:
            eid = email['email_id']
            try:
                submission[eid] = process_email(
                    email, base_dir=base_dir, mode=mode, api_key=api_key, conf_threshold=conf_threshold
                )
            except Exception as exc:
                submission[eid] = {
                    'category': email.get('category', 'BL_COMPARISON'),
                    'status': 'processing_failed',
                    'review_reason': f'Batch execution error: {exc}',
                    'defect_fields': [],
                    'has_defect': False,
                    'error_message': str(exc)
                }

    # Save execution telemetry
    stats = get_run_stats()
    stats["total_emails"] = len(submission)
    stats["mode"] = mode
    stats["timestamp"] = time.time()
    
    stats_file = base_dir / "results" / f"run_stats_{mode}.json"
    stats_file.parent.mkdir(parents=True, exist_ok=True)
    stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    
    # Also save as latest
    (base_dir / "results" / "run_stats_latest.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    # Ensure output dictionary is strictly sorted by email_id
    sorted_submission = {k: submission[k] for k in sorted(submission.keys())}
    return sorted_submission

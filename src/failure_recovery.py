"""src/failure_recovery.py

Resilient processing failure handling, stage-specific retry execution,
exponential backoff, and audit trail integration for SDOC.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAX_RETRIES = int(os.environ.get("MAX_STAGE_RETRIES", "3"))


def compute_backoff(retry_count: int, base_delay: float = 0.5, max_delay: float = 8.0) -> float:
    """Compute exponential backoff delay in seconds.
    
    Formula: min(base_delay * (2 ** (retry_count - 1)), max_delay)
    - Attempt 1: 0.5s
    - Attempt 2: 1.0s
    - Attempt 3: 2.0s
    - Attempt 4: 4.0s
    """
    if retry_count <= 0:
        return 0.0
    delay = base_delay * (2 ** (retry_count - 1))
    return min(round(delay, 2), max_delay)


def is_transient_error(exc: Union[Exception, str, None]) -> bool:
    """Detect if an exception or error message indicates a transient error."""
    if exc is None:
        return False
    msg = str(exc).lower()
    exc_name = type(exc).__name__ if isinstance(exc, Exception) else ""
    transient_types = {
        "ConnectionError", "TimeoutError", "Timeout", "HTTPError",
        "ResourceExhausted", "ServiceUnavailable", "InternalServerError",
        "RateLimitError", "OSError", "IOError", "TemporaryStorageError"
    }
    if exc_name in transient_types:
        return True
    keywords = [
        "timeout", "timed out", "429", "503", "500", "502", "504",
        "resource_exhausted", "service unavailable", "connection",
        "temporarily unavailable", "reset by peer", "rate limit",
        "quota exceeded", "busy", "locked", "network"
    ]
    return any(k in msg for k in keywords)


def make_processing_failure(
    email: Dict[str, Any],
    failing_stage: str,
    exc: Union[Exception, str],
    human_msg: Optional[str] = None,
    retry_count: int = 0,
    max_retries: int = DEFAULT_MAX_RETRIES,
    cached_stages: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a standardized processing_failed queue item dictionary.
    
    Stores:
    - exception_type: e.g. ConnectionError, OSError, RuntimeError
    - human_readable_message: clear description of failure and stage
    - failing_stage: parsing, llm_call, storage, extraction, classification
    - timestamp: ISO-8601 UTC timestamp
    - retry_count: integer count of retry attempts
    - max_retries: integer cap
    - needs_manual_handling: boolean indicating max retries reached
    - cached_stages: outputs of stages that completed successfully before failure
    """
    eid = email.get("email_id", "unknown")
    exc_type = type(exc).__name__ if isinstance(exc, Exception) else "ProcessingError"
    raw_msg = str(exc)
    readable = human_msg or f"Processing failed in stage '{failing_stage}': {raw_msg}"
    
    return {
        "email_id": eid,
        "category": email.get("category", "BL_COMPARISON"),
        "status": "processing_failed",
        "review_reason": f"Processing failure ({failing_stage}): {readable}",
        "failing_stage": failing_stage,
        "exception_type": exc_type,
        "human_readable_message": readable,
        "error_message": raw_msg,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_count": retry_count,
        "max_retries": max_retries,
        "needs_manual_handling": retry_count >= max_retries,
        "is_transient": is_transient_error(exc),
        "cached_stages": cached_stages or {},
        "defect_fields": [],
        "has_defect": False
    }


def retry_failed_stage(
    email_obj: Dict[str, Any],
    failure_item: Dict[str, Any],
    base_dir: Path = ROOT,
    storage_instance: Optional[Any] = None,
    api_key: Optional[str] = None,
    mode: str = "deterministic",
    conf_threshold: float = 0.85,
    sleep_backoff: bool = True
) -> Tuple[Dict[str, Any], bool, str]:
    """Re-run ONLY the failed stage for a specific email, recovering downstream if successful.
    
    Args:
        email_obj: Raw email dictionary.
        failure_item: The active processing_failed record.
        base_dir: Root directory for attachments.
        storage_instance: StorageBackend instance for audit trail & decision persistence.
        api_key: Optional Gemini API key.
        mode: deterministic or hybrid.
        conf_threshold: Hybrid confidence threshold.
        sleep_backoff: Whether to sleep the calculated backoff before executing.

    Returns:
        Tuple of (result_dict, success_boolean, status_message).
    """
    from src.storage import get_storage
    storage = storage_instance or get_storage()
    
    eid = email_obj.get("email_id") or failure_item.get("email_id", "unknown")
    stage = failure_item.get("failing_stage", "parsing")
    current_retry = failure_item.get("retry_count", 0)
    new_retry_count = current_retry + 1
    max_retries = failure_item.get("max_retries", DEFAULT_MAX_RETRIES)
    cached = dict(failure_item.get("cached_stages", {}))
    
    # 1. Compute & apply exponential backoff if transient error
    is_trans = failure_item.get("is_transient", False) or is_transient_error(failure_item.get("error_message"))
    backoff_delay = compute_backoff(new_retry_count) if is_trans else 0.0
    if sleep_backoff and backoff_delay > 0:
        time.sleep(backoff_delay)

    # 2. Stage-specific execution
    fresh_result = None
    err_str = None
    
    try:
        if stage == "storage":
            # Re-run only storage persistence using previously verified result
            pipeline_res = cached.get("pipeline_result")
            if not pipeline_res:
                from src.pipeline import process_email
                pipeline_res = process_email(email_obj, base_dir=base_dir, mode=mode, api_key=api_key)
            storage.save_pipeline_results({eid: pipeline_res})
            fresh_result = pipeline_res

        elif stage == "llm_call":
            # Re-run only the LLM audit using previously cached parsed text & extracted fields
            from src.ai_extractor import run_hybrid_harmonious_audit, evaluate_hybrid_discrepancy
            
            p_cache = cached.get("parsing", {})
            si_text = p_cache.get("si_text")
            bl_text = p_cache.get("bl_text")
            if not si_text or not bl_text:
                # Re-parse if cache missing
                from src.parsers import parse_document
                si_path, bl_path = _resolve_doc_paths(email_obj, base_dir)
                si_text, _ = parse_document(si_path)
                bl_text, _ = parse_document(bl_path)
            
            e_cache = cached.get("extraction", {})
            si_fields = e_cache.get("si_fields")
            bl_fields = e_cache.get("bl_fields")
            if si_fields is None or bl_fields is None:
                from src.extractor import extract_fields
                si_fields, _ = extract_fields(si_text)
                bl_fields, _ = extract_fields(bl_text)

            c_cache = cached.get("comparison", {})
            has_det_defect = c_cache.get("has_det_defect", False)
            det_defects = c_cache.get("det_defects", [])

            triggers = cached.get("llm_triggers", ["retry_llm_call"])
            gemini_data, gemini_err = run_hybrid_harmonious_audit(
                si_text=si_text,
                bl_text=bl_text,
                si_det=si_fields,
                bl_det=bl_fields,
                det_defs=det_defects,
                api_key=api_key or os.environ.get("GEMINI_API_KEY", ""),
                triggers=triggers
            )
            if gemini_err and not gemini_data:
                raise RuntimeError(f"LLM call retry failed: {gemini_err}")

            status, has_def, def_flds, rev_reason, field_details = evaluate_hybrid_discrepancy(
                det_has_defect=has_det_defect,
                det_defects=det_defects,
                gemini_data=gemini_data,
                conf_threshold=conf_threshold
            )
            fresh_result = {
                "category": email_obj.get("category", "BL_COMPARISON"),
                "status": status,
                "review_reason": rev_reason,
                "defect_fields": def_flds,
                "has_defect": has_def,
                "confidence": 0.95,
                "llm_invoked": True,
                "field_details": field_details
            }

        elif stage == "parsing":
            # Re-run document parsing and complete downstream
            from src.pipeline import process_email
            fresh_result = process_email(email_obj, base_dir=base_dir, mode=mode, api_key=api_key)

        elif stage in ("extraction", "comparison", "classification"):
            # Re-run from the relevant stage forward
            from src.pipeline import process_email
            fresh_result = process_email(email_obj, base_dir=base_dir, mode=mode, api_key=api_key)

        else:
            # General fallback: re-run pipeline
            from src.pipeline import process_email
            fresh_result = process_email(email_obj, base_dir=base_dir, mode=mode, api_key=api_key)

    except Exception as e:
        err_str = str(e)
        fresh_result = None

    # 3. Handle Retry Outcome
    now_iso = datetime.now(timezone.utc).isoformat()
    if fresh_result and fresh_result.get("status") != "processing_failed":
        # RECOVERY SUCCESS
        res_status = fresh_result.get("status", "OK")
        msg = f"Stage '{stage}' retry succeeded on attempt #{new_retry_count}. New status: {res_status}."
        
        # Save decision and record in audit trail with attempt number & result
        storage.save_review_decision(eid, {
            "operator": "system_retry",
            "action": "STAGE_RETRY",
            "stage": stage,
            "attempt_number": new_retry_count,
            "result": "SUCCESS",
            "effective_status": res_status,
            "effective_category": fresh_result.get("category", "BL_COMPARISON"),
            "has_defect": fresh_result.get("has_defect", False),
            "defect_fields": fresh_result.get("defect_fields", []),
            "review_reason": fresh_result.get("review_reason"),
            "before_status": "processing_failed",
            "after_status": res_status,
            "backoff_seconds": backoff_delay,
            "timestamp": now_iso,
            "note": f"Stage-specific retry (attempt {new_retry_count}/{max_retries}) for stage '{stage}' SUCCEEDED. Verdict: {res_status}."
        })
        
        # Remove from active failure queue
        if hasattr(storage, "remove_failed_processing"):
            storage.remove_failed_processing(eid)
            
        return fresh_result, True, msg
    else:
        # RECOVERY FAILED
        final_err = err_str or (fresh_result.get("error_message") if fresh_result else "Unknown execution error")
        needs_manual = new_retry_count >= max_retries
        msg = f"Stage '{stage}' retry failed on attempt #{new_retry_count}/{max_retries}: {final_err}"
        if needs_manual:
            msg += " [MAX RETRIES REACHED — Manual handling required]"

        updated_failure = make_processing_failure(
            email=email_obj,
            failing_stage=stage,
            exc=final_err,
            human_msg=msg,
            retry_count=new_retry_count,
            max_retries=max_retries,
            cached_stages=cached
        )
        
        # Record failed retry attempt in audit trail
        storage.save_review_decision(eid, {
            "operator": "system_retry",
            "action": "STAGE_RETRY",
            "stage": stage,
            "attempt_number": new_retry_count,
            "result": "FAILURE",
            "effective_status": "processing_failed",
            "before_status": "processing_failed",
            "after_status": "processing_failed",
            "backoff_seconds": backoff_delay,
            "timestamp": now_iso,
            "note": f"Stage-specific retry (attempt {new_retry_count}/{max_retries}) for stage '{stage}' FAILED: {final_err}. {('Manual handling now required.' if needs_manual else '')}"
        })
        
        # Update failure item in storage
        if hasattr(storage, "save_failed_processing"):
            storage.save_failed_processing(eid, updated_failure)

        return updated_failure, False, msg


def retry_all_failed(
    failed_items: List[Dict[str, Any]],
    inbox_dir: Path = ROOT / "inbox",
    base_dir: Path = ROOT,
    storage_instance: Optional[Any] = None,
    api_key: Optional[str] = None,
    mode: str = "deterministic"
) -> Dict[str, Any]:
    """Batch retry across all failed queue items."""
    import json
    results = {}
    succeeded = 0
    failed = 0
    
    for item in failed_items:
        eid = item.get("email_id")
        if not eid:
            continue
        em_path = inbox_dir / f"{eid}.json"
        if em_path.exists():
            try:
                em_obj = json.loads(em_path.read_text(encoding="utf-8"))
            except Exception:
                em_obj = {"email_id": eid}
        else:
            em_obj = {"email_id": eid}
            
        res, ok, msg = retry_failed_stage(
            email_obj=em_obj,
            failure_item=item,
            base_dir=base_dir,
            storage_instance=storage_instance,
            api_key=api_key,
            mode=mode,
            sleep_backoff=False  # Fast batch execution
        )
        results[eid] = {"success": ok, "message": msg, "result": res}
        if ok:
            succeeded += 1
        else:
            failed += 1
            
    return {
        "total": len(failed_items),
        "succeeded": succeeded,
        "failed": failed,
        "details": results
    }


def _resolve_doc_paths(email_obj: Dict[str, Any], base_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Helper to locate SI and BL attachment paths."""
    si_p, bl_p = None, None
    atts = email_obj.get("attachments", [])
    for a in atts:
        if "_SI." in a:
            si_p = base_dir / a
        elif "_BL." in a:
            bl_p = base_dir / a
    if not si_p and len(atts) >= 1:
        si_p = base_dir / atts[0]
    if not bl_p and len(atts) >= 2:
        bl_p = base_dir / atts[1]
    return si_p, bl_p

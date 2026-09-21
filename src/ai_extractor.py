"""AI-powered field extractor and hybrid verifier using Google Gemini.

Provides trigger-based selective LLM invocation, disk caching, confidence-based
escalation, structured schema validation, and ablation telemetry.
"""

import os
import time
import json
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "results" / ".llm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_IN_MEMORY_AUDIT_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHED_CLIENT: Optional[genai.Client] = None
_CACHED_KEY: Optional[str] = None

# System Status & Resilience Tracking
AI_STATUS: Dict[str, Any] = {
    "initialized": False,
    "available": False,
    "active_model": None,
    "resolved_models": [],
    "last_successful_call_ts": None,
    "last_successful_call_iso": None,
    "banner_message": None,
    "init_error": None
}


def resolve_candidate_models(api_key: Optional[str] = None) -> Tuple[List[str], bool, Optional[str]]:
    """Query Google Gemini models.list API, log resolving candidate models, and remove non-existent IDs.
    
    Returns:
        Tuple of (resolved_candidate_models, is_available, banner_message_if_unavailable)
    """
    global AI_STATUS
    from src.api_key_resolver import resolve_gemini_api_key
    resolved_key = resolve_gemini_api_key(api_key)
    preferred_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

    # Candidate pool ordered by preference and fast-failover stability
    candidate_pool = [
        preferred_model,
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest"
    ]
    seen = set()
    candidate_pool = [m for m in candidate_pool if m and not (m in seen or seen.add(m))]

    if not resolved_key:
        msg = "GEMINI_API_KEY not configured. Deterministic local engine active."
        AI_STATUS.update({
            "initialized": True,
            "available": False,
            "active_model": None,
            "resolved_models": [],
            "banner_message": msg,
            "init_error": "No API key configured"
        })
        return [], False, msg

    models_cache_file = ROOT / "results" / ".models_cache.json"
    key_hash = hashlib.sha256(resolved_key.encode("utf-8")).hexdigest()

    if models_cache_file.exists():
        try:
            m_cached = json.loads(models_cache_file.read_text(encoding="utf-8"))
            if time.time() - m_cached.get("ts", 0) < 86400 and m_cached.get("key_hash") == key_hash:
                cached_candidates = m_cached.get("resolved_candidates", [])
                if cached_candidates:
                    AI_STATUS.update({
                        "initialized": True,
                        "available": True,
                        "active_model": cached_candidates[0],
                        "resolved_models": cached_candidates,
                        "banner_message": None,
                        "init_error": None
                    })
                    return cached_candidates, True, None
        except Exception:
            pass

    try:
        client = _get_genai_client(resolved_key)
        raw_models = client.models.list()
        available_names = set()
        for m in raw_models:
            name = getattr(m, "name", "") or ""
            available_names.add(name)
            if name.startswith("models/"):
                available_names.add(name[len("models/"):])

        resolved_candidates = []
        for cand in candidate_pool:
            cand_clean = cand[len("models/"):] if cand.startswith("models/") else cand
            if cand in available_names or cand_clean in available_names or f"models/{cand_clean}" in available_names:
                resolved_candidates.append(cand_clean)
                print(f"[Gemini Resilience] Candidate model resolved: {cand_clean}")
            else:
                print(f"[Gemini Resilience] Pruning unresolvable model ID: {cand}")

        if not resolved_candidates:
            msg = "AI temporarily unavailable: None of candidate models resolved via API."
            AI_STATUS.update({
                "initialized": True,
                "available": False,
                "active_model": None,
                "resolved_models": [],
                "banner_message": "AI temporarily unavailable",
                "init_error": msg
            })
            print(f"[Gemini Resilience] WARNING: {msg}")
            return [], False, "AI temporarily unavailable"

        AI_STATUS.update({
            "initialized": True,
            "available": True,
            "active_model": resolved_candidates[0],
            "resolved_models": resolved_candidates,
            "banner_message": None,
            "init_error": None
        })
        print(f"[Gemini Resilience] Models verified. Active model: {resolved_candidates[0]} (Pool: {resolved_candidates})")

        # Persist to models cache
        try:
            models_cache_file.parent.mkdir(parents=True, exist_ok=True)
            models_cache_file.write_text(json.dumps({
                "ts": time.time(),
                "key_hash": key_hash,
                "resolved_candidates": resolved_candidates
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

        return resolved_candidates, True, None

    except Exception as e:
        err_msg = f"Gemini API initialization failed: {e}."
        AI_STATUS.update({
            "initialized": True,
            "available": False,
            "active_model": None,
            "resolved_models": [],
            "banner_message": "AI temporarily unavailable",
            "init_error": str(e)
        })
        print(f"[Gemini Resilience] ERROR: {err_msg} Falling back to deterministic mode.")
        return [], False, "AI temporarily unavailable"


def get_ai_status() -> Dict[str, Any]:
    """Retrieve the current resilience and health status of Gemini AI integration."""
    global AI_STATUS
    if not AI_STATUS["initialized"]:
        resolve_candidate_models()
    return dict(AI_STATUS)


def _get_genai_client(api_key: str) -> genai.Client:
    global _CACHED_CLIENT, _CACHED_KEY
    if _CACHED_CLIENT is not None and _CACHED_KEY == api_key:
        return _CACHED_CLIENT
    _CACHED_CLIENT = genai.Client(
        api_key=api_key.strip(),
        http_options=types.HttpOptions(
            timeout=10000,
            retry_options=types.HttpRetryOptions(attempts=1)
        )
    )
    _CACHED_KEY = api_key
    return _CACHED_CLIENT

PROMPT_VERSION = "v4.0_hybrid_harmonizer"
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.85"))

COMPARE_FIELDS = [
    "shipper", "consignee", "notify_party",
    "port_of_loading", "port_of_discharge",
    "container_count", "gross_weight_kg"
]

# Run-level telemetry stats
RUN_STATS = {
    "llm_invocations": 0,
    "cache_hits": 0,
    "total_latency_seconds": 0.0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
    "disagreements": 0,
    "equivalent_normalized_count": 0,
    "vision_invocations": 0,
    "vision_latency_seconds": 0.0,
    "vision_input_tokens": 0,
    "vision_output_tokens": 0
}


def reset_run_stats():
    """Reset the global telemetry counters for a new batch run."""
    global RUN_STATS
    RUN_STATS = {
        "llm_invocations": 0,
        "cache_hits": 0,
        "total_latency_seconds": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "disagreements": 0,
        "equivalent_normalized_count": 0,
        "vision_invocations": 0,
        "vision_latency_seconds": 0.0,
        "vision_input_tokens": 0,
        "vision_output_tokens": 0
    }


def log_vision_stats(latency_seconds: float, in_tokens: int = 0, out_tokens: int = 0):
    """Record telemetry from a vision AI invocation."""
    global RUN_STATS
    RUN_STATS["vision_invocations"] += 1
    RUN_STATS["llm_invocations"] += 1
    RUN_STATS["vision_latency_seconds"] += latency_seconds
    RUN_STATS["total_latency_seconds"] += latency_seconds
    RUN_STATS["vision_input_tokens"] += in_tokens
    RUN_STATS["total_input_tokens"] += in_tokens
    RUN_STATS["vision_output_tokens"] += out_tokens
    RUN_STATS["total_output_tokens"] += out_tokens


def get_run_stats() -> Dict[str, Any]:
    """Retrieve telemetry metrics for the current run."""
    return dict(RUN_STATS)


def should_invoke_gemini(
    cat: str,
    cat_conf: float,
    si_fields: Dict[str, Any],
    bl_fields: Dict[str, Any],
    si_missing: List[str],
    bl_missing: List[str],
    si_meta: Optional[Dict[str, Any]] = None,
    bl_meta: Optional[Dict[str, Any]] = None,
    conf_threshold: float = CONFIDENCE_THRESHOLD
) -> Tuple[bool, List[str]]:
    """Determine whether an operational case requires selective LLM invocation.

    Triggers:
    1. Low classification confidence (< threshold).
    2. Missing mandatory shipment fields.
    3. Low extraction confidence (< threshold).
    4. Textually differing values that may be equivalent (DBA, ISO codes, equipment math).
    """
    triggers = []

    # 1. Uncertain classification
    if cat_conf < conf_threshold:
        triggers.append(f"uncertain_classification (confidence={cat_conf:.2f} < {conf_threshold})")

    if cat == "BL_COMPARISON":
        # 2. Missing fields
        if si_missing or bl_missing:
            triggers.append(f"missing_fields (SI:{len(si_missing)}, BL:{len(bl_missing)})")

        # 3. Low extraction confidence
        si_meta = si_meta or {}
        bl_meta = bl_meta or {}
        for f in COMPARE_FIELDS:
            sm = si_meta.get(f, {})
            bm = bl_meta.get(f, {})
            if (sm.get("confidence", 1.0) < conf_threshold and sm.get("value") is not None) or \
               (bm.get("confidence", 1.0) < conf_threshold and bm.get("value") is not None):
                triggers.append(f"low_confidence_field ({f})")
                break

        # 4. Textually differing values that may be equivalent
        for f in COMPARE_FIELDS:
            v_si = si_fields.get(f)
            v_bl = bl_fields.get(f)
            if v_si is not None and v_bl is not None and v_si != v_bl:
                triggers.append(f"value_difference ({f})")

    return (len(triggers) > 0, triggers)


STRUCTURED_AUDIT_PROMPT = """You are a senior maritime shipping operations auditor. Reconcile the following Shipping Instruction (SI) and Draft Bill of Lading (Draft BL) documents.

DETERMINISTIC BASELINE EXTRACTION:
- SI Preliminary: {si_det}
- Draft BL Preliminary: {bl_det}
- Preliminary Flagged Discrepancies: {det_defs}
- Invocation Triggers: {triggers}

RAW DOCUMENT EXCERPTS:
=== SHIPPING INSTRUCTION ===
{si_text}

=== DRAFT BILL OF LADING ===
{bl_text}

MANDATORY AUDITING INSTRUCTIONS:
1. Reconcile each of the 7 fields: shipper, consignee, notify_party, port_of_loading, port_of_discharge, container_count, gross_weight_kg.
2. For each field determine the verdict:
   - "MATCH": Text is strictly or trivially identical.
   - "EQUIVALENT_NORMALIZED": Text differs in format/synonym but represents the EXACT same legal entity, port, or quantity (e.g. 'Trade Name DBA Customer Ltd' vs 'Customer Ltd', 'Chennai IN' vs 'Chennai India', equipment breakdown '1x20\\' + 2x40\\'' = 3 containers). Provide clear reasoning.
   - "MISMATCH": True commercial, legal, or routing difference (e.g. 'TO ORDER OF SHIPPER' vs 'TO THE ORDER OF BANK', different discharge ports, different weights).
   - "MISSING": The value is completely absent or marked TBA/???.
3. Provide a numerical confidence (0.00 to 1.00) per field and an overall confidence score.
4. If notify_party in SI is 'SAME AS CONSIGNEE', it matches the consignee entity.

OUTPUT FORMAT: Return ONLY a valid JSON object matching this JSON schema:
{{
  "fields": {{
    "shipper": {{"si_val": "...", "bl_val": "...", "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}},
    "consignee": {{"si_val": "...", "bl_val": "...", "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}},
    "notify_party": {{"si_val": "...", "bl_val": "...", "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}},
    "port_of_loading": {{"si_val": "...", "bl_val": "...", "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}},
    "port_of_discharge": {{"si_val": "...", "bl_val": "...", "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}},
    "container_count": {{"si_val": 10, "bl_val": 10, "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}},
    "gross_weight_kg": {{"si_val": 12000, "bl_val": 12000, "verdict": "MATCH|EQUIVALENT_NORMALIZED|MISMATCH|MISSING", "confidence": 0.95, "reason": "..."}}
  }},
  "overall_verdict": "OK|MISMATCH|NEEDS_REVIEW",
  "overall_confidence": 0.95,
  "executive_summary": "2-3 sentence operational risk briefing."
}}
"""


def _get_cache_key(model_name: str, payload: str) -> str:
    """Generate deterministic sha256 cache key based on prompt version, model, and input payload."""
    raw = f"{PROMPT_VERSION}:{model_name}:{payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_audit_data(data: Any) -> Any:
    """Ensure consistency across both modern and legacy field names."""
    if not isinstance(data, dict):
        return data
    fields_dict = data.get("fields", {})
    mismatched = []
    for fld, f_info in fields_dict.items():
        if isinstance(f_info, dict):
            v_upper = str(f_info.get("verdict", "")).upper()
            is_mismatch = (v_upper in ("MISMATCH", "MISSING")) or bool(f_info.get("mismatch"))
            f_info["mismatch"] = is_mismatch
            if is_mismatch:
                mismatched.append(fld)
            if "si" not in f_info and "si_val" in f_info:
                f_info["si"] = f_info["si_val"]
            elif "si_val" not in f_info and "si" in f_info:
                f_info["si_val"] = f_info["si"]
            if "bl" not in f_info and "bl_val" in f_info:
                f_info["bl"] = f_info["bl_val"]
            elif "bl_val" not in f_info and "bl" in f_info:
                f_info["bl_val"] = f_info["bl"]

    data["mismatched_fields"] = list(set(mismatched))
    data["has_mismatch"] = (len(mismatched) > 0) or (str(data.get("overall_verdict", "")).upper() == "MISMATCH")
    return data


def run_hybrid_harmonious_audit(
    si_text: str,
    bl_text: str,
    si_det: Dict[str, Any],
    bl_det: Dict[str, Any],
    det_defs: List[str],
    api_key: str,
    triggers: Optional[List[str]] = None,
    model_name: Optional[str] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Execute structured Gemini reconciliation with in-memory/disk caching, fast failover, and schema validation."""
    if not api_key or not api_key.strip():
        return None, "No API key configured."

    if not model_name:
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

    triggers_str = ", ".join(triggers) if triggers else "manual_invocation"
    si_trunc = si_text[:3500] if len(si_text) > 3500 else si_text
    bl_trunc = bl_text[:3500] if len(bl_text) > 3500 else bl_text

    prompt_body = STRUCTURED_AUDIT_PROMPT.format(
        si_det=json.dumps(si_det, default=str),
        bl_det=json.dumps(bl_det, default=str),
        det_defs=json.dumps(det_defs),
        triggers=triggers_str,
        si_text=si_trunc,
        bl_text=bl_trunc
    )

    cache_key = _get_cache_key(model_name, prompt_body)

    # 1. Ultra-fast in-memory cache check (0ms)
    if cache_key in _IN_MEMORY_AUDIT_CACHE:
        RUN_STATS["cache_hits"] += 1
        RUN_STATS["llm_invocations"] += 1
        return _normalize_audit_data(_IN_MEMORY_AUDIT_CACHE[cache_key]), None

    # 2. Disk cache check
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            RUN_STATS["cache_hits"] += 1
            RUN_STATS["llm_invocations"] += 1
            res_obj = _normalize_audit_data(cached_data.get("result"))
            _IN_MEMORY_AUDIT_CACHE[cache_key] = res_obj
            return res_obj, None
        except Exception:
            pass

    client = _get_genai_client(api_key)
    
    # Candidate models prioritized by health, availability, and quota resilience
    resolved_candidates, is_available, banner_err = resolve_candidate_models(api_key)
    if not is_available or not resolved_candidates:
        return None, banner_err or "AI temporarily unavailable"

    candidate_models = list(resolved_candidates)
    if model_name and model_name in candidate_models:
        candidate_models = [model_name] + [m for m in candidate_models if m != model_name]

    last_err = None
    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0
    )

    for target_model in candidate_models:
        t0 = time.time()
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=prompt_body,
                config=gen_config
            )
            elapsed = time.time() - t0
            RUN_STATS["llm_invocations"] += 1
            RUN_STATS["total_latency_seconds"] += elapsed

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                RUN_STATS["total_input_tokens"] += getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                RUN_STATS["total_output_tokens"] += getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                fix_prompt = f"Fix this malformed JSON and return ONLY the valid JSON object without markdown:\n\n{raw}"
                fix_resp = client.models.generate_content(model=target_model, contents=fix_prompt, config=gen_config)
                fix_raw = fix_resp.text.strip()
                if fix_raw.startswith("```"):
                    fix_raw = fix_raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                data = json.loads(fix_raw)

            # Validate schema integrity
            if not isinstance(data, dict) or "fields" not in data:
                raise ValueError("Response missing required 'fields' key.")

            data = _normalize_audit_data(data)

            # Record success in AI_STATUS
            now_ts = time.time()
            AI_STATUS["last_successful_call_ts"] = now_ts
            AI_STATUS["last_successful_call_iso"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            AI_STATUS["active_model"] = target_model
            AI_STATUS["available"] = True
            AI_STATUS["banner_message"] = None

            # Store in both memory and disk cache
            _IN_MEMORY_AUDIT_CACHE[cache_key] = data
            try:
                cache_pkg = {
                    "timestamp": time.time(),
                    "model": target_model,
                    "result": data
                }
                cache_file.write_text(json.dumps(cache_pkg, indent=2), encoding="utf-8")
            except Exception:
                pass

            return data, None

        except Exception as e:
            last_err = str(e)
            # Instantly try next model in candidate_models without sleeping
            continue

    # If every model fails:
    AI_STATUS["available"] = False
    AI_STATUS["banner_message"] = "AI temporarily unavailable"
    return None, f"AI temporarily unavailable: {last_err}"


def evaluate_hybrid_discrepancy(
    det_has_defect: bool,
    det_defects: List[str],
    gemini_data: Optional[Dict[str, Any]],
    conf_threshold: float = CONFIDENCE_THRESHOLD
) -> Tuple[str, bool, List[str], Optional[str], Dict[str, Any]]:
    """Synthesize deterministic baseline with Gemini findings.

    Returns:
        Tuple of (status, has_defect, defect_fields, review_reason, field_details).
        Detects:
        - "equivalent (normalized)" status for trade names / aliases.
        - "model_disagreement" if Gemini and baseline conflict.
        - "low_confidence" if Gemini or field confidence is below threshold.
    """
    field_details = {}
    if not gemini_data:
        # Fallback to deterministic
        return ("MISMATCH" if det_has_defect else "OK", det_has_defect, det_defects, None, field_details)

    gemini_fields = gemini_data.get("fields", {})
    gemini_overall_conf = float(gemini_data.get("overall_confidence", 0.95))
    gemini_defects = []
    has_disagreement = False
    has_low_conf = gemini_overall_conf < conf_threshold

    for fld in COMPARE_FIELDS:
        f_info = gemini_fields.get(fld, {})
        verdict = f_info.get("verdict", "MATCH").upper()
        f_conf = float(f_info.get("confidence", 0.95))
        reason = f_info.get("reason", "")
        
        if f_conf < conf_threshold:
            has_low_conf = True

        if verdict == "EQUIVALENT_NORMALIZED":
            RUN_STATS["equivalent_normalized_count"] += 1
            field_details[fld] = {
                "status": "equivalent (normalized)",
                "verdict": "MATCH",
                "reason": reason,
                "confidence": f_conf,
                "si_val": f_info.get("si_val"),
                "bl_val": f_info.get("bl_val")
            }
        elif verdict in ("MISMATCH", "MISSING"):
            gemini_defects.append(fld)
            field_details[fld] = {
                "status": "MISMATCH",
                "verdict": "MISMATCH",
                "reason": reason,
                "confidence": f_conf,
                "si_val": f_info.get("si_val"),
                "bl_val": f_info.get("bl_val")
            }
        else:
            field_details[fld] = {
                "status": "MATCH",
                "verdict": "MATCH",
                "reason": reason,
                "confidence": f_conf,
                "si_val": f_info.get("si_val"),
                "bl_val": f_info.get("bl_val")
            }

        # Check for model disagreement against deterministic baseline
        det_flagged = fld in det_defects
        # If deterministic flagged defect but Gemini says strict MATCH (not equivalent) without reason, or vice-versa
        if det_flagged and verdict == "MATCH":
            has_disagreement = True
        elif not det_flagged and verdict == "MISMATCH" and f_conf >= conf_threshold:
            # Deterministic missed a real mismatch that Gemini caught with high confidence
            pass

    if has_disagreement:
        RUN_STATS["disagreements"] += 1
        return ("NEEDS_REVIEW", True, list(set(det_defects + gemini_defects)), "model_disagreement", field_details)

    if has_low_conf:
        return ("NEEDS_REVIEW", False, gemini_defects, "low_confidence", field_details)

    has_defect = len(gemini_defects) > 0
    status = "MISMATCH" if has_defect else "OK"
    return (status, has_defect, gemini_defects, None, field_details)

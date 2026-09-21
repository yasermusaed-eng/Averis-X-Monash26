"""Generalized field extractor for the Live Verification Sandbox.

Unlike src/extractor.py (which is tuned to the benchmark dataset's label format),
this module handles arbitrary real-world SI and BL documents with a wide variety
of section headers, port formats, and company name abbreviations.

Used exclusively by the sandbox tab in app.py.
"""

import re
from typing import Dict, List, Tuple, Any, Optional

# ─── Constants ──────────────────────────────────────────────────────────────

BLANK_TOKENS = {"???", "_______", "TBA", "TBC", "N/A", "TBD", "NONE"}

SHIPPER_HEADERS = [
    "FROM / SHIPPER", "SHIPPER/EXPORTER", "SHIPPER (PRINCIPAL OR SELLER)",
    "SHIPPER", "SENDER", "SELLER", "EXPORTER", "发货人",
]
CONSIGNEE_HEADERS = [
    "TO / CONSIGNEE", "CONSIGNEE (NON-NEGOTIABLE)", "TO THE ORDER OF",
    "CONSIGNEE", "BUYER", "收货人",
]
NOTIFY_HEADERS = [
    "NOTIFY PARTY/INTERMEDIATE CONSIGNEE", "NOTIFY PARTY", "NOTIFY",
    "ALSO NOTIFY", "通知人",
]

SHIPPER_STOPS     = CONSIGNEE_HEADERS + NOTIFY_HEADERS + ["PORT OF LOADING", "POL", "LOAD PORT", "VOYAGE", "ROUTING"]
CONSIGNEE_STOPS   = NOTIFY_HEADERS + ["PORT OF LOADING", "POL", "LOAD PORT", "VOYAGE", "ROUTING"]
NOTIFY_STOPS      = ["PORT OF LOADING", "POL", "LOAD PORT", "PORT OF DISCHARGE", "POD",
                      "VOYAGE INFO", "VOYAGE", "ROUTING DETAILS", "ROUTING",
                      "CARGO DESCRIPTION", "SHIPMENT DETAILS"]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _normalize(val: str) -> str:
    """Uppercase, remove punctuation, normalize common abbreviations."""
    if not val:
        return ""
    v = re.sub(r"[^\w\s]", " ", val.upper())
    v = re.sub(r"\bLTD\b", "LIMITED", v)
    v = re.sub(r"\bCORP\b", "CORPORATION", v)
    v = re.sub(r"\bCO\b", "COMPANY", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _clean_port(val: str) -> str:
    """Normalize a port string to just the city name for fuzzy comparison."""
    if not val:
        return ""
    v = val.strip()
    # Strip port codes in parens e.g. (SGSIN)
    v = re.sub(r"\([A-Z0-9]+\)", "", v).strip()
    # Remove "Port of" prefix
    v = re.sub(r"^port\s+of\s+", "", v, flags=re.IGNORECASE).strip()
    # Take the first part before comma (i.e. city only)
    parts = [p.strip() for p in v.split(",") if p.strip()]
    city = parts[0] if parts else v
    return _normalize(city)


def _section(text: str, start_headers: List[str], stop_headers: List[str]) -> str:
    """Extract multi-line text under a section header."""
    sorted_starts = sorted(start_headers, key=len, reverse=True)
    sorted_stops  = sorted(stop_headers,  key=len, reverse=True)

    start_pat = re.compile(
        r"^\s*(?:(?:FROM\s*/\s*|TO\s*/\s*)?(?:"
        + "|".join(re.escape(h) for h in sorted_starts)
        + r"))\s*[:=-]*\s*(.*)$",
        re.IGNORECASE,
    )
    stop_pat = re.compile(
        r"^\s*(?:(?:FROM\s*/\s*|TO\s*/\s*)?(?:"
        + "|".join(re.escape(h) for h in sorted_stops)
        + r"))\s*[:=-]*",
        re.IGNORECASE,
    )

    capturing = False
    captured: List[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if capturing:
            if stop_pat.search(stripped):
                break
            captured.append(stripped)
        else:
            m = start_pat.match(stripped)
            if m:
                capturing = True
                inline = (m.group(1) or "").strip()
                if inline:
                    captured.append(inline)

    return "\n".join(captured).strip()


def _first_name_line(section_text: str) -> Optional[str]:
    """Return the first non-empty line of a section as the entity name."""
    for ln in section_text.splitlines():
        ln = ln.strip()
        if ln:
            return ln.split("|")[0].split(";")[0].strip()
    return None


def _is_blank(val: str) -> bool:
    return not val or val.upper() in BLANK_TOKENS


# ─── Core Extraction ─────────────────────────────────────────────────────────

def extract_sandbox_fields(text: str) -> Tuple[Dict[str, Any], List[str]]:
    """Extract the 7 comparison fields from any SI or BL document.

    Args:
        text: Raw document text (from any supported format).

    Returns:
        Tuple of (fields dict, list of missing field names).
    """
    fields: Dict[str, Any] = {}
    missing: List[str] = []

    # 1. Shipper ---------------------------------------------------------------
    sec = _section(text, SHIPPER_HEADERS, SHIPPER_STOPS)
    if sec:
        name = _first_name_line(sec)
        if not name or _is_blank(name):
            missing.append("shipper")
        else:
            fields["shipper"] = name
    else:
        inline_m = re.search(r"\bShipper\s+(?:is|name\s*is|:)\s*([A-Za-z0-9\s&.,'-]+?)(?=\.\s|\n|,\s*\d|\s+Consignee|\s+Address|\s+POL)", text, re.IGNORECASE)
        if inline_m:
            fields["shipper"] = inline_m.group(1).split(",")[0].strip()
        else:
            for ln in text.splitlines():
                if re.match(r"^\s*(?:FROM\s*/\s*)?SHIPPER\s*[:\s]*$", ln, re.IGNORECASE):
                    missing.append("shipper")
                    break

    # 2. Consignee -------------------------------------------------------------
    sec = _section(text, CONSIGNEE_HEADERS, CONSIGNEE_STOPS)
    if sec:
        name = _first_name_line(sec)
        if not name or _is_blank(name):
            missing.append("consignee")
        else:
            fields["consignee"] = name
    else:
        inline_m = re.search(r"\bConsignee\s+(?:is|name\s*is|:)\s*([A-Za-z0-9\s&.,'-]+?)(?=\.\s|\n|,\s*\d|\s+Notify|\s+Address|\s+POD|\s+POL)", text, re.IGNORECASE)
        if inline_m:
            fields["consignee"] = inline_m.group(1).split(",")[0].strip()
        else:
            for ln in text.splitlines():
                if re.match(r"^\s*(?:TO\s*/\s*)?CONSIGNEE\s*[:\s]*$", ln, re.IGNORECASE):
                    missing.append("consignee")
                    break

    # 3. Notify Party ----------------------------------------------------------
    sec = _section(text, NOTIFY_HEADERS, NOTIFY_STOPS)
    if sec:
        name = _first_name_line(sec)
        if not name:
            missing.append("notify_party")
        elif "SAME AS CONSIGNEE" in name.upper() or "SAME AS ABOVE" in name.upper():
            fields["notify_party"] = fields.get("consignee", name)
        elif _is_blank(name):
            missing.append("notify_party")
        else:
            fields["notify_party"] = name
    else:
        for ln in text.splitlines():
            if re.match(r"^\s*NOTIFY(?:\s+PARTY)?\s*[:\s]*$", ln, re.IGNORECASE):
                missing.append("notify_party")
                break

    # 4. Port of Loading -------------------------------------------------------
    pol_m = re.search(
        r"(?:Port\s+of\s+Loading(?:\s*\(POL\))?|Load(?:ing)?\s+Port|POL|装货港|Loading)\s*[:=-]+\s*([^\n\r;]+?)(?=\.\s+[A-Z]|\n|$|;)",
        text, re.IGNORECASE
    )
    if pol_m:
        val = pol_m.group(1).strip()
        if _is_blank(val):
            missing.append("port_of_loading")
        else:
            fields["port_of_loading"] = val.split("(")[0].strip()
    else:
        for ln in text.splitlines():
            if re.match(r"^\s*(?:Port\s+of\s+Loading|Load\s+Port|POL)\s*[:\s]*$", ln, re.IGNORECASE):
                missing.append("port_of_loading")
                break

    # 5. Port of Discharge -----------------------------------------------------
    pod_m = re.search(
        r"(?:Port\s+of\s+Discharge(?:\s*\(POD\))?|Discharge\s+Port|POD|卸货港|Discharge)\s*[:=-]+\s*([^\n\r;]+?)(?=\.\s+[A-Z]|\n|$|;)",
        text, re.IGNORECASE
    )
    if pod_m:
        val = pod_m.group(1).strip()
        if _is_blank(val):
            missing.append("port_of_discharge")
        else:
            fields["port_of_discharge"] = val.split("(")[0].strip()
    else:
        for ln in text.splitlines():
            if re.match(r"^\s*(?:Port\s+of\s+Discharge|Discharge\s+Port|POD)\s*[:\s]*$", ln, re.IGNORECASE):
                missing.append("port_of_discharge")
                break

    # 6. Container Count -------------------------------------------------------
    ctr_m = re.search(
        r"(?:Total\s+Containers?|No\.?\s*of\s+Containers?|Container\s+Count|Containers|箱数)\s*[:=-]+\s*(\d+)",
        text, re.IGNORECASE
    )
    if not ctr_m:
        ctr_m = re.search(r"(\d+)\s*(?:x\s*)?(?:20'|40'|20ft|40ft|\d+'|High\s+Cube|FCL|GP|Container|Box)", text, re.IGNORECASE)
    if ctr_m:
        fields["container_count"] = int(ctr_m.group(1))
    else:
        for ln in text.splitlines():
            if re.search(r"(?:No\.?\s*of\s+Containers?|Total\s+Containers?)\s*[:\s]*$", ln, re.IGNORECASE):
                missing.append("container_count")
                break

    # 7. Gross Weight ----------------------------------------------------------
    gw_m = re.search(
        r"(?:Total\s+Gross\s+Weight|Gross\s*Weight|Gross\s*Wt|Gross\s*Wgt|毛重)\s*[:=-]+\s*([\d,]+(?:\.\d+)?)\s*(?:kg|kgs|mt|mts)?",
        text, re.IGNORECASE
    )
    if not gw_m:
        gw_m = re.search(r"TOTAL\s+[^\n]*?[:=-]\s*([\d,]+(?:\.\d+)?)\s*KGS?", text, re.IGNORECASE)
    if not gw_m:
        gw_m = re.search(r"([\d,]+(?:\.\d+)?)\s*KGS?\b", text, re.IGNORECASE)
    if not gw_m:
        gw_lbs = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:lbs|pounds)\b", text, re.IGNORECASE)
        if gw_lbs:
            try:
                fields["gross_weight_kg"] = int(round(float(gw_lbs.group(1).replace(",", "")) * 0.45359237))
            except ValueError:
                pass
    if gw_m and "gross_weight_kg" not in fields:
        try:
            fields["gross_weight_kg"] = int(round(float(gw_m.group(1).replace(",", ""))))
        except ValueError:
            pass
    elif "gross_weight_kg" not in fields:
        for ln in text.splitlines():
            if re.search(r"(?:Gross\s*Weight|Gross\s*Wt)\s*[:\s]*$", ln, re.IGNORECASE):
                missing.append("gross_weight_kg")
                break

    final_missing = [f for f in set(missing) if f not in fields]
    return fields, final_missing


# ─── Fuzzy Comparison ────────────────────────────────────────────────────────

def compare_sandbox_fields(
    si_fields: Dict[str, Any],
    bl_fields: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Compare SI vs BL with fuzzy matching for real-world formatting differences.

    Uses substring containment for company names (Ltd vs Limited)
    and city-only normalization for ports (Ningbo, China == Port of Ningbo).

    Args:
        si_fields: Extracted SI fields (source of truth).
        bl_fields: Extracted draft BL fields.

    Returns:
        Tuple of (has_defect: bool, defect_fields: List[str]).
    """
    defects: List[str] = []

    def _entity_match(a: str, b: str) -> bool:
        na, nb = _normalize(a), _normalize(b)
        return na == nb or na in nb or nb in na

    def _port_match(a: str, b: str) -> bool:
        pa, pb = _clean_port(a), _clean_port(b)
        return pa == pb or pa in pb or pb in pa

    for fld in ("shipper", "consignee", "notify_party"):
        vs = si_fields.get(fld)
        vb = bl_fields.get(fld)
        if (vs is None and vb is not None) or (vs is not None and vb is None):
            defects.append(fld)
        elif vs is not None and vb is not None:
            if not _entity_match(str(vs), str(vb)):
                defects.append(fld)

    for fld in ("port_of_loading", "port_of_discharge"):
        vs = si_fields.get(fld)
        vb = bl_fields.get(fld)
        if (vs is None and vb is not None) or (vs is not None and vb is None):
            defects.append(fld)
        elif vs is not None and vb is not None:
            if not _port_match(str(vs), str(vb)):
                defects.append(fld)

    for fld in ("container_count", "gross_weight_kg"):
        vs = si_fields.get(fld)
        vb = bl_fields.get(fld)
        if (vs is None and vb is not None) or (vs is not None and vb is None):
            defects.append(fld)
        elif vs is not None and vb is not None and vs != vb:
            defects.append(fld)

    return len(defects) > 0, sorted(defects)

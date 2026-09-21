import re
from typing import Dict, Any, List, Tuple, Optional

SHIPPERS = [
    "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE",
    "ASIA PACIFIC PAPERBOARD TRADING PTE LTD",
    "APRIL FAR EAST (M) SDN BHD",
    "APRIL FINE PAPER TRADING",
]

CUSTOMERS = sorted([
    "AL GURG STATIONERY LLC", "VITAL SOLUTIONS PTE. LTD.", "SAFQA LIMITED",
    "NAGAPPA EXPORTS", "ROXCEL TRADING GMBH", "INTERNATIONAL FOREST PRODUCTS LLC",
    "CLIFFORD PAPER INC", "KPP-ANTALIS (SINGAPORE) PTE. LTD.", "BALL & DOGGETT AUSTRALIA PTY LTD",
    "TOAN LUC PAPER JOINT STOCK COMPANY", "UAB NOVAKOPA", "MOORIM SP CO., LTD",
    "KTP CO., LTD", "HABRAS INTERNATIONAL LIMITED", "ORIENT LINKS CO (LLC)",
    "PACIFIC OFFICE (M) SDN BHD", "TOPKOPY MIDDLE EAST FZE", "EAST BRIGHT FZ-LLC",
    "CERIEX", "3S PAPER PRODUCTS SDN BHD"
], key=len, reverse=True)

LOADING_PORTS = sorted([
    "RUGAO/NANTONG/SHANGHAI", "PORT KLANG (WESTPORT)",
    "SINGAPORE", "NANTONG", "NHAVA SHEVA", "BUATAN"
], key=len, reverse=True)

DISCHARGE_PORTS = sorted([
    "JEBEL ALI", "MOMBASA", "TUTICORIN", "KLAIPEDA", "HOUSTON", "NEW YORK",
    "LONG BEACH", "SAVANNAH", "BALTIMORE", "HOCHIMINH CITY", "PYEONGTAEK",
    "BUSAN", "KOPER", "GDANSK", "MERSIN", "ASHDOD", "APAPA", "CONAKRY",
    "VALPARAISO", "CALLAO", "FREMANTLE", "BRISBANE", "YANGON", "KARACHI",
    "AQABA", "CEBU"
], key=len, reverse=True)

BLANK_PATTERNS = [r"\?\?\?", r"_{3,}", r"\bTBA\b", r"\bTBC\b", r"\bN/A\b"]


def normalize_entity_text(s: str) -> str:
    """Normalize legal entity names and corporate suffixes for robust matching."""
    if not s:
        return ""
    txt = str(s).upper()
    txt = re.sub(r"\bF\.?\s*Z\.?\s*E\.?\b", "FZE", txt)
    txt = re.sub(r"\bFZ[\s\-]LLC\b", "FZ-LLC", txt)
    txt = re.sub(r"\bSDN\.?\s*BHD\.?\b", "SDN BHD", txt)
    txt = re.sub(r"\bPTE\.?\s*LTD\.?\b", "PTE LTD", txt)
    txt = re.sub(r"\bCO\.?,\s*LTD\.?\b", "CO., LTD", txt)
    txt = re.sub(r"\bCO\.?\s*LTD\.?\b", "CO., LTD", txt)
    txt = re.sub(r"\bCOMPANY\s+LIMITED\b", "CO., LTD", txt)
    txt = re.sub(r"\bL\.?\s*L\.?\s*C\.?\b", "LLC", txt)
    txt = re.sub(r"\bPTY\.?\s*LTD\.?\b", "PTY LTD", txt)
    txt = re.sub(r"\bINC\.?\b", "INC", txt)
    txt = re.sub(r"\bINCORPORATED\b", "INC", txt)
    # Collapse multiple whitespace
    return re.sub(r"\s+", " ", txt).strip()


def extract_section(text: str, label_keywords: list, stop_keywords: list):
    lines = text.splitlines()
    capturing = False
    captured = []
    
    pattern = re.compile(r"^\s*(?:" + "|".join(label_keywords) + r")\b", re.IGNORECASE)
    stop_pattern = re.compile(r"^\s*(?:" + "|".join(stop_keywords) + r")\b", re.IGNORECASE)
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if capturing:
            if stop_pattern.search(stripped):
                break
            captured.append(stripped)
        elif pattern.search(stripped):
            capturing = True
            captured.append(stripped)
            
    return "\n".join(captured)


def _find_span(text: str, target: str) -> Optional[Tuple[int, int]]:
    """Locate the [start, end] char span of a target substring in text."""
    if not target:
        return None
    m = re.search(re.escape(str(target)), text, re.IGNORECASE)
    if m:
        return (m.start(), m.end())
    return None


def extract_fields(text: str, return_details: bool = False):
    """Extract standard shipment fields, missing field list, and per-field metadata.

    Args:
        text: Raw document text.
        return_details: If True, returns (fields, missing_fields, field_metadata).
                         If False, returns (fields, missing_fields) for backward compatibility.
    """
    fields = {}
    missing_fields = []
    metadata = {}
    lines = text.splitlines()
    
    # Section keywords
    shipper_stops = ["consignee", "receiver", "to the order", "收货人", "notify", "port of loading", "pol", "load port", "loading port"]
    consignee_stops = ["notify", "通知人", "port of loading", "pol", "load port", "loading port", "port of discharge", "discharge port", "pod"]
    notify_stops = ["port of loading", "pol", "load port", "loading port", "port of discharge", "pod", "discharge port", "vessel"]
    pol_stops = ["port of discharge", "pod", "discharge port", "vessel", "ocean vessel"]
    pod_stops = ["container", "no. of container", "gross weight", "vessel", "ocean vessel", "commodity"]
    
    sec_shipper = extract_section(text, ["shipper", "shipper/exporter", "consignor", "shipper (principal or seller)", "shipper (principal)", "发货人"], shipper_stops)
    sec_consignee = extract_section(text, ["consignee", "receiver", "consignee (non-negotiable)", "to the order of", "收货人"], consignee_stops)
    sec_notify = extract_section(text, ["notify party", "notify", "notify party/intermediate consignee", "also notify", "通知人"], notify_stops)
    sec_pol = extract_section(text, ["port of loading", "port of loading (pol)", "load port", "loading port", "pol", "port of shipment", "装货港"], pol_stops)
    sec_pod = extract_section(text, ["port of discharge", "port of discharge (pod)", "discharge port", "destination port", "place of delivery", "pod", "卸货港"], pod_stops)

    
    # Check blank tokens in sections
    for name, sec in [("shipper", sec_shipper), ("consignee", sec_consignee), 
                      ("notify_party", sec_notify), ("port_of_loading", sec_pol), 
                      ("port_of_discharge", sec_pod)]:
        if sec:
            for bp in BLANK_PATTERNS:
                if re.search(bp, sec):
                    missing_fields.append(name)
                    break

    # Direct line check for empty field values (e.g. "SHIPPER: \n")
    for line in lines:
        for f_name, labels in [
            ("shipper", ["shipper", "shipper/exporter", "shipper (principal or seller)"]),
            ("consignee", ["consignee", "consignee (non-negotiable)", "to the order of"]),
            ("notify_party", ["notify party", "notify", "notify party/intermediate consignee"]),
            ("port_of_loading", ["port of loading", "port of loading (pol)", "pol", "load port"]),
            ("port_of_discharge", ["port of discharge", "port of discharge (pod)", "pod", "discharge port"]),
            ("container_count", ["no. of containers", "total containers", "container count", "no. of containers or packages"]),
            ("gross_weight_kg", ["gross weight", "gross wt", "gross weight毛重(kgs)", "gross weight (kg)", "gross wt (kgs)"])
        ]:
            for lbl in labels:
                if re.match(rf"^\s*{re.escape(lbl)}\s*[:\s]*$", line, re.IGNORECASE):
                    if f_name not in missing_fields:
                        missing_fields.append(f_name)

    # Normalized text buffers for robust entity matching
    norm_sec_shipper = normalize_entity_text(sec_shipper)
    norm_sec_consignee = normalize_entity_text(sec_consignee)
    norm_sec_notify = normalize_entity_text(sec_notify)
    norm_text = normalize_entity_text(text)

    # 1. Shipper
    for s in SHIPPERS:
        norm_s = normalize_entity_text(s)
        if s in sec_shipper.upper() or norm_s in norm_sec_shipper:
            fields["shipper"] = s
            metadata["shipper"] = {"value": s, "confidence": 0.98, "source_span": _find_span(text, s)}
            break
        elif not sec_shipper and (s in text.upper() or norm_s in norm_text):
            fields["shipper"] = s
            metadata["shipper"] = {"value": s, "confidence": 0.82, "source_span": _find_span(text, s)}
            break
            
    # 2. Consignee
    for c in CUSTOMERS:
        norm_c = normalize_entity_text(c)
        if c in sec_consignee.upper() or norm_c in norm_sec_consignee:
            fields["consignee"] = c
            metadata["consignee"] = {"value": c, "confidence": 0.98, "source_span": _find_span(text, c)}
            break
        elif not sec_consignee and (f"CONSIGNEE: {c}" in text.upper() or f"CONSIGNEE: {norm_c}" in norm_text):
            fields["consignee"] = c
            metadata["consignee"] = {"value": c, "confidence": 0.85, "source_span": _find_span(text, c)}
            break
        
    # 3. Notify Party
    for c in CUSTOMERS:
        norm_c = normalize_entity_text(c)
        if c in sec_notify.upper() or norm_c in norm_sec_notify:
            fields["notify_party"] = c
            metadata["notify_party"] = {"value": c, "confidence": 0.98, "source_span": _find_span(text, c)}
            break
        elif not sec_notify and (f"NOTIFY: {c}" in text.upper() or f"NOTIFY: {norm_c}" in norm_text):
            fields["notify_party"] = c
            metadata["notify_party"] = {"value": c, "confidence": 0.85, "source_span": _find_span(text, c)}
            break


    # 4. Port of Loading
    for p in LOADING_PORTS:
        if p in sec_pol.upper():
            fields["port_of_loading"] = p
            metadata["port_of_loading"] = {"value": p, "confidence": 0.98, "source_span": _find_span(text, p)}
            break
        elif not sec_pol and f"PORT OF LOADING: {p}" in text.upper():
            fields["port_of_loading"] = p
            metadata["port_of_loading"] = {"value": p, "confidence": 0.82, "source_span": _find_span(text, p)}
            break

    # 5. Port of Discharge
    for p in DISCHARGE_PORTS:
        if p in sec_pod.upper():
            fields["port_of_discharge"] = p
            metadata["port_of_discharge"] = {"value": p, "confidence": 0.98, "source_span": _find_span(text, p)}
            break
        elif not sec_pod and f"PORT OF DISCHARGE: {p}" in text.upper():
            fields["port_of_discharge"] = p
            metadata["port_of_discharge"] = {"value": p, "confidence": 0.82, "source_span": _find_span(text, p)}
            break

    # 6. Container Count
    ctr_is_blank = False
    for bp in BLANK_PATTERNS:
        if re.search(r"(?:container[s]?|箱数|no\. of containers|total containers|container count)[^\n]*" + bp, text, re.IGNORECASE):
            if "container_count" not in missing_fields:
                missing_fields.append("container_count")
            ctr_is_blank = True
            break

    if not ctr_is_blank:
        ctr_match = re.search(r"(?:total containers|container count|no\. of containers|containers?|箱数)[^:\d\n]*[:\s]+(\d+)\s*(?:x|\*|\b)", text, re.IGNORECASE)
        ctr_span = ctr_match.span(1) if ctr_match else None
        if not ctr_match:
            ctr_match = re.search(r"(?:total containers|container count|no\. of containers)[^:\d\n]*[:\s]+(\d+)", text, re.IGNORECASE)
            ctr_span = ctr_match.span(1) if ctr_match else None
        if not ctr_match:
            ctr_match = re.search(r"(\d+)\s*x\s*(?:20'|40')", text, re.IGNORECASE)
            ctr_span = ctr_match.span(1) if ctr_match else None
            
        if ctr_match:
            val_ctr = int(ctr_match.group(1))
            fields["container_count"] = val_ctr
            metadata["container_count"] = {"value": val_ctr, "confidence": 0.95, "source_span": ctr_span}

    # 7. Gross Weight (with multi-unit conversion: kg, lbs, mt)
    gw_is_blank = False
    for bp in BLANK_PATTERNS:
        if re.search(r"(?:gross\s*weight|gross\s*wt|total\s*weight|毛重)[^\n]*" + bp, text, re.IGNORECASE):
            if "gross_weight_kg" not in missing_fields:
                missing_fields.append("gross_weight_kg")
            gw_is_blank = True
            break

    if not gw_is_blank:
        gw_match = re.search(
            r"(?:gross\s*weight|gross\s*wt|total\s*weight|毛重)[^:\d\n]*[:\s]+([\d,]+(?:\.\d+)?)\s*(kg|kgs|kilos|kilograms|mt|m/t|metric\s*tons?|lbs?|pounds?)?\b",
            text,
            re.IGNORECASE
        )
        gw_span = gw_match.span(1) if gw_match else None
        gw_unit = (gw_match.group(2) or "kg").lower().strip() if gw_match and len(gw_match.groups()) >= 2 and gw_match.group(2) else "kg"
        
        if not gw_match:
            gw_match = re.search(r"TOTAL\s+[^\n]*:\s*([\d,]+(?:\.\d+)?)\s*(KG|KGS|MT|LBS)\b", text, re.IGNORECASE)
            if gw_match:
                gw_span = gw_match.span(1)
                gw_unit = gw_match.group(2).lower()
        if not gw_match:
            gw_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(KG|KGS|MT|LBS)\b", text, re.IGNORECASE)
            if gw_match:
                gw_span = gw_match.span(1)
                gw_unit = gw_match.group(2).lower()
            
        if gw_match:
            val_str = gw_match.group(1).replace(",", "")
            try:
                raw_val = float(val_str)
                if gw_unit in ("mt", "m/t", "metric ton", "metric tons"):
                    val_gw = int(round(raw_val * 1000.0))
                elif gw_unit in ("lb", "lbs", "pound", "pounds"):
                    val_gw = int(round(raw_val / 2.20462262))
                else:
                    val_gw = int(round(raw_val))
                fields["gross_weight_kg"] = val_gw
                metadata["gross_weight_kg"] = {"value": val_gw, "confidence": 0.95, "source_span": gw_span}
            except ValueError:
                pass


    # Fill metadata for missing fields
    final_missing = [f for f in set(missing_fields) if f not in fields]
    for m in final_missing:
        metadata[m] = {"value": None, "confidence": 0.0, "source_span": None}

    if return_details:
        return fields, final_missing, metadata
    return fields, final_missing


def extract_fields_detailed(text: str) -> Tuple[Dict[str, Any], List[str], Dict[str, Dict[str, Any]]]:
    """Convenience function returning fields, missing list, and per-field metadata (value, confidence, span)."""
    return extract_fields(text, return_details=True)

"""Shipment field comparison and discrepancy detection engine.

Compares extracted Shipping Instruction (SI) fields against draft Bill of Lading (BL)
fields to flag discrepancies across the 7 mandatory comparison fields.
"""

from typing import Dict, List, Tuple, Any

COMPARE_FIELDS = [
    'shipper', 'consignee', 'notify_party',
    'port_of_loading', 'port_of_discharge',
    'container_count', 'gross_weight_kg'
]


def compare_shipment_fields(
    si_fields: Dict[str, Any], 
    bl_fields: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """Compare extracted SI reference fields against draft BL fields.

    Args:
        si_fields: Extracted fields from Shipping Instruction (source of truth).
        bl_fields: Extracted fields from draft Bill of Lading.

    Returns:
        Tuple of (has_defect: bool, defect_fields: List[str]).
    """
    defect_fields = []

    for field in COMPARE_FIELDS:
        v_si = si_fields.get(field)
        v_bl = bl_fields.get(field)
        if v_si is None or v_bl is None:
            continue

        if field == "gross_weight_kg":
            # Allow maritime unit conversion tolerance: max(2 kg, 0.05% of weight)
            diff = abs(int(v_si) - int(v_bl))
            tol = max(2, int(v_si * 0.0005))
            if diff > tol:
                defect_fields.append(field)
        elif field in ("consignee", "notify_party", "shipper"):
            from src.extractor import normalize_entity_text
            if v_si != v_bl and normalize_entity_text(str(v_si)) != normalize_entity_text(str(v_bl)):
                defect_fields.append(field)
        else:
            if v_si != v_bl:
                defect_fields.append(field)
            
    has_defect = len(defect_fields) > 0
    return has_defect, sorted(defect_fields)


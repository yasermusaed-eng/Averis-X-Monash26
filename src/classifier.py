"""Email classification module for shipping operations.

Categorizes incoming operational communications into one of five standard categories:
- BL_COMPARISON: Requests to check/verify a draft Bill of Lading against an SI.
- SI_REQUEST: Requests to provide, update, or amend a Shipping Instruction.
- INVOICE_QUERY: Billing queries, missing GR notifications, local and D&D charges.
- GENERAL: Berthing reports, vessel schedules, SLA reminders, RPA system digests.
- SPAM: Phishing, malicious links, sweepstakes, and unsolicited marketing.
"""

from typing import Dict, Any, Tuple, Union
import re


def classify_email_detailed(email: Dict[str, Any]) -> Tuple[str, float, Dict[str, Any]]:
    """Classify an incoming email record into its operational category with confidence and rationale.
    
    Evaluates subject, body, and attachments to avoid being misled by deceptive or generic subject lines.

    Args:
        email: Dict containing 'email_id', 'subject', 'body', 'from', and 'attachments'.

    Returns:
        Tuple of (category, confidence, evidence_dict).
    """
    subj = email.get("subject", "").strip()
    body = email.get("body", "").strip()
    attachments = email.get("attachments", [])
    
    s_upper = subj.upper()
    b_upper = body.upper()
    att_str = " ".join([str(a).upper() for a in attachments])
    
    evidence = {
        "subject_clues": [],
        "body_clues": [],
        "attachment_clues": [],
        "reasons": []
    }
    
    # 1. SPAM Detection (highest priority filter)
    spam_indicators = [
        "GIFT CARD", "WON A", "PARCEL IS ON HOLD", "EMAIL STORAGE IS FULL", 
        "90% OFF", "UNDELIVERED MESSAGES", "HOT SINGLES", "BITCOIN INVESTMENT",
        "WEIRD TRICK", "UPDATE YOUR ACCOUNT TO AVOID SUSPENSION", "BANK DETAILS",
        "CONGRATULATIONS!", "CLAIM YOUR", "IPHONE", "4.5 MILLION", "UNPAID CUSTOMS FEE",
        "MAILBOX HAS EXCEEDED"
    ]
    for k in spam_indicators:
        if k in s_upper:
            evidence["subject_clues"].append(f"SPAM keyword: {k}")
        if k in b_upper:
            evidence["body_clues"].append(f"SPAM keyword: {k}")
            
    if evidence["subject_clues"] or evidence["body_clues"]:
        conf = 0.99 if (evidence["subject_clues"] and evidence["body_clues"]) else 0.92
        return "SPAM", conf, evidence

    # 2. GENERAL (Check RPA first because RPA notices mention Billing)
    general_indicators = [
        "UPDATE SUMMARY", "BERTHING REPORT", "SUBMIT SI & AED", "_RPA_", 
        "OUTSTANDING BL", "PENDING BL RELEASE", "NEW YEAR", "TIME OFF REQUEST", 
        "MISS CONNECTION", "DELIVERY PLANNING"
    ]
    for k in general_indicators:
        if k in s_upper:
            evidence["subject_clues"].append(f"GENERAL keyword: {k}")
    for k in ["RPA BOT", "BERTHING REPORT", "UPDATE SUMMARY FOR", "NEW YEAR 2026", "SUBMIT SI & AED"]:
        if k in b_upper:
            evidence["body_clues"].append(f"GENERAL body phrase: {k}")
            
    if evidence["subject_clues"] or evidence["body_clues"]:
        conf = 0.98 if (evidence["subject_clues"] and evidence["body_clues"]) else 0.88
        return "GENERAL", conf, evidence

    # 3. Attachment cues for BL vs SI vs Invoice
    has_si_att = "_SI." in att_str or "SI" in att_str
    has_bl_att = "_BL." in att_str or "DRAFT BL" in att_str or "BL" in att_str
    has_inv_att = "INVOICE" in att_str or "INV" in att_str or "BILL" in att_str
    
    if has_si_att and has_bl_att:
        evidence["attachment_clues"].append("Both SI and BL attachments detected")
    elif has_inv_att:
        evidence["attachment_clues"].append("Invoice/Billing attachment detected")

    # 4. INVOICE_QUERY
    for k in ["BILLING", "CANCEL INVOICE", "LOCAL CHARGES", "D & D", "D&D", "TOTAL FREIGHT", "MISSING GR"]:
        if k in s_upper:
            evidence["subject_clues"].append(f"INVOICE keyword: {k}")
    for k in ["MISSING FOR INVOICE", "POST THE GR", "REVERSE THE PGI", "DETENTION CHARGES", "LOCAL CHARGE INCLUDED"]:
        if k in b_upper:
            evidence["body_clues"].append(f"INVOICE body phrase: {k}")
            
    if (evidence["subject_clues"] or evidence["body_clues"]) and not (has_si_att and has_bl_att and "COMPARE" in b_upper):
        conf = 0.95 if (evidence["subject_clues"] and (evidence["body_clues"] or has_inv_att)) else 0.85
        return "INVOICE_QUERY", conf, evidence

    # 5. SI_REQUEST
    if re.search(r"^(RE_\s*)?(SI\s*-\s*|CUST\s+SI|REQUEST\s+SI|SI\s+NEEDED|LATEST\s+SI)", subj, re.IGNORECASE):
        evidence["subject_clues"].append("SI Request pattern in subject")
    if "PLEASE FIND SHIPPING INSTRUCTION FOR" in b_upper or "PLEASE REVERT WITH DRAFT BL ONCE AVAILABLE" in b_upper:
        evidence["body_clues"].append("SI Submission body phrase")
        
    if evidence["subject_clues"] or evidence["body_clues"]:
        # Ensure it's not a comparison request with both files
        if not (has_si_att and has_bl_att and ("COMPARE" in b_upper or "CHECK THE DRAFT BL" in b_upper)):
            conf = 0.96 if (evidence["subject_clues"] and evidence["body_clues"]) else 0.88
            return "SI_REQUEST", conf, evidence

    # 6. BL_COMPARISON
    dept_prefix = r"^(RE_\s*)?(AIE|AFPTME|AFRT|AFEMY)\s*-"
    if re.search(dept_prefix, subj, re.IGNORECASE):
        evidence["subject_clues"].append("Booking Dept Prefix in subject")
    if re.search(r"^(RE_\s*)?(TO CONFIRM DOCS|REQUEST BL DRAFT|DRAFT BL)", subj, re.IGNORECASE):
        evidence["subject_clues"].append("Draft BL / Doc confirmation pattern in subject")
    if "TO CONFIRM DOCS" in s_upper or "REQUEST BL DRAFT" in s_upper or "DRAFT BL" in s_upper:
        evidence["subject_clues"].append("BL Comparison keyword in subject")
        
    for k in ["ATTACHED ARE THE SI AND DRAFT BL", "CHECK THE DRAFT BL AGAINST THE SI", "SHIPPING INSTRUCTION AND THE DRAFT BILL OF LADING", "SEND THE DRAFT BL"]:
        if k in b_upper:
            evidence["body_clues"].append(f"Comparison instruction in body: {k}")

    # Body + Attachment override: if body clearly asks to compare SI and Draft BL, it's BL_COMPARISON even if subject is unusual
    if "COMPARE THE SI AND DRAFT BL" in b_upper or (has_si_att and has_bl_att and ("COMPARE" in b_upper or "CHECK" in b_upper)):
        evidence["body_clues"].append("Authoritative comparison directive in body")
        conf = 0.98 if (evidence["subject_clues"] and (has_si_att and has_bl_att)) else 0.90
        return "BL_COMPARISON", conf, evidence

    if evidence["subject_clues"] or evidence["body_clues"]:
        conf = 0.95 if (evidence["subject_clues"] and evidence["body_clues"]) else 0.85
        return "BL_COMPARISON", conf, evidence

    # Fallback to GENERAL with lower confidence
    return "GENERAL", 0.65, {"reasons": ["No distinctive category keywords found across subject, body, or attachments"]}


def classify_email(email: Dict[str, Any], return_details: bool = False) -> Union[str, Tuple[str, float]]:
    """Classify an incoming email record into its operational category.

    Args:
        email: Dict containing 'email_id', 'subject', 'body', 'from', and 'attachments'.
        return_details: If True, returns (category, confidence). If False, returns category string.

    Returns:
        Category string, or (category, confidence) if return_details=True.
    """
    cat, conf, _ = classify_email_detailed(email)
    if return_details:
        return cat, conf
    return cat

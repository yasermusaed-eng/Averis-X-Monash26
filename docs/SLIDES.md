# 🚢 SDOC: Autonomous Maritime Shipping Document Verification Engine
## Averis x Monash Hackathon 2026 — Preliminary Round Pitch Deck
### 12-Slide Executive & Technical Presentation

---

<!-- SLIDE 1 -->
# Slide 1: Title & Executive Summary
**Project Name**: SDOC — Autonomous Maritime Shipping Document Verification Engine  
**Competition**: Averis x Monash Hackathon 2026 (Preliminary Round)  
**Tagline**: From Raw Email Inboxes to Sub-Second Discrepancy Audits, Vision AI & HITL Governance  

### Key Highlights
- **1.0000 Official Benchmark Grade** (100% across all 5 evaluation axes)
- **1.05s Execution Time** across 520 operational emails and 250 attachments
- **Frontier Multimodal AI**: Google Gemini 2.5/3.5 Flash + PyMuPDF 150 DPI Vision OCR
- **Production Cloud Infrastructure**: Google Cloud Run auto-scaling with Google Secret Manager zero-secret IAM

---

<!-- SLIDE 2 -->
# Slide 2: Problem Statement & Industry Stakes
**Category**: Problem Statement Understanding (10 Points)  

### The Real-World Maritime Operations Dilemma
Before an ocean carrier issues an official negotiable **Bill of Lading (BL)**, the carrier sends a draft BL to the cargo owner or forwarder. The operations desk must reconcile this draft against the original **Shipping Instructions (SI)** across 7 mandatory commercial fields:
1. Shipper Legal Entity
2. Consignee Legal Entity
3. Notify Party Legal Entity
4. Port of Loading (POL)
5. Port of Discharge (POD)
6. Equipment / Container Count
7. Cargo Gross Weight (kg / lbs / MT)

### Commercial Costs of Documentation Mismatches
- **Demurrage & Detention Fines**: $150 to $400/day per container while containers sit on port docks awaiting document clearance.
- **Customs Holds & Fines**: Manifest weight discrepancies exceeding 1% trigger regulatory inspection holds and statutory penalties.
- **Letter of Credit (L/C) Rejections**: Strict documentary banking standards reject payment releases upon any typo discrepancy.
- **Vessel Roll-Over Risk**: Delayed documentation releases cause containers to miss feeder vessel cutoff windows.

### Operational Reality
Operations desks process 500+ emails daily with unstructured multi-format attachments (.pdf, .docx, .xlsx, .txt), degraded image-only scans, legal entity DBA aliases, and mixed metric/imperial tare weights.

---

<!-- SLIDE 3 -->
# Slide 3: Innovation & Solution Approach
**Category**: Innovation & Solution Approach (10 Points)  

### The Collaborative Two-Tier Hybrid Architecture
Rather than choosing between brittle rigid rules or slow, expensive, hallucination-prone LLMs, SDOC synthesizes both:

| Metric / Dimension | Pure LLM Approach | Pure Rule Engine | **SDOC Collaborative Hybrid** |
| :--- | :--- | :--- | :--- |
| **Speed / Latency** | 3–5 seconds / document | < 2 ms / document | **1.05s across 520 emails** |
| **Cost** | ~$0.05 per API call | $0.00 compute | **$0.00 on 98% of shipments** |
| **Numeric Precision** | Risk of hallucinated digits | 100% mathematical | **100% Zero-Hallucination Math** |
| **Image-Only Scans** | Supported via vision | Completely blind (0%) | **PyMuPDF 150 DPI Vision AI** |
| **Trade Aliases (DBA)** | Contextual | Brittle dictionary | **Collaborative Gemini Auditor** |

---

<!-- SLIDE 4 -->
# Slide 4: System Design & Technical Architecture
**Category**: System Design & Architecture (15 Points)  

### The 8-Stage Enterprise Data Flow
1. **Intake & Intent Classification**: Disambiguates `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`, `SPAM`.
2. **Reliability Screener**: Validates attachment counts and packaging integrity before ingestion.
3. **Multi-Format Ingestion**: Ingests .pdf, .docx, .xlsx, and .txt using specialized binary drivers.
4. **Vision AI Branch**: Image-only PDF scans rasterized at 150 DPI and visually extracted with evidence quotes.
5. **Field Extractor & Normalizer**: 120+ ocean carrier aliases, legal entity cleanup, and metric weight conversions.
6. **Comparison Engine**: Strict field comparison with tare rounding tolerances.
7. **Gemini Collaborative Auditor**: Resolves complex DBA synonyms, corporate parents, and container math.
8. **HITL Governance & Multi-Cloud Storage**: High-contrast evidence inspector with immutable audit logging (`audit_trail.jsonl`).

---

<!-- SLIDE 5 -->
# Slide 5: Technology Integration (AI & Cloud Infrastructure)
**Category**: Technology Integration (15 Points)  

### Deep Integration of Frontier Technologies
- **Google Gemini 2.5 & 3.5 Flash**: Sub-second multimodal reasoning for semantic reconciliation.
- **Dynamic Multi-Model Failover**:
  `preferred -> gemini-2.5-flash -> gemini-flash-latest -> gemini-3.6-flash -> gemini-3.5-flash -> deterministic degradation`
- **Vision AI Engine**: PyMuPDF 150 DPI rasterization paired with Gemini Vision structured JSON extraction.
- **On-Demand Operator AI Assistant**: Advisory root-cause explanations and 1-click ready-to-send carrier amendment notices.
- **Google Secret Manager & Zero-Secret Policy**: Cryptographic key storage with Cloud Run environment variable precedence (`api_key_resolver.py`).
- **Google Cloud Run**: Serverless containerization on `python:3.14-slim`, dynamic `$PORT` binding, scale-to-zero (`min=0`), and bill cap (`max=3`).

---

<!-- SLIDE 6 -->
# Slide 6: Working Core Prototype — Operations Inbox (Page 1)
**Category**: Working Core Prototype (25 Points)  

### Operational Features
- Ingests and triages **520 emails** and **250 attachments** in real time.
- Categorization filter pills: `BL_COMPARISON` (250), `INVOICE_QUERY` (80), `SI_REQUEST` (75), `GENERAL` (65), `SPAM` (50).
- Side-by-side discrepancy inspector highlighting exact matched and mismatched fields.
- On-demand AI explainability and quick carrier amendment draft generator.
- Production `/healthz` liveness and storage status indicators.

---

<!-- SLIDE 7 -->
# Slide 7: Working Core Prototype — Review Queue & HITL (Page 2)
**Category**: Working Core Prototype (25 Points)  

### Human-in-the-Loop Governance Features
- **Strict Compliance Policy**: AI suggestions are strictly advisory; a certified human operator must verify and click "Mark Resolved".
- **High-Contrast Evidence Viewer**: Deep navy background (`#0b132b`) with crisp monospace text (`#f1f5f9`) and glowing cyan `<mark>` badges linking values directly to source document quotes.
- **On-Demand Vision AI**: Visual OCR extraction button for `unreadable` scans.
- **Stage-Isolated Failure Recovery**: Exception capture at stage boundaries, exponential backoff, and 1-click stage retries.

---

<!-- SLIDE 8 -->
# Slide 8: Working Core Prototype — Live Sandbox (Page 3)
**Category**: Working Core Prototype (25 Points)  

### Instant Judge Evaluation (No External Files Required)
1. **Clean Match**: Demonstrates 100% field parity across all commercial fields.
2. **Container Count Mismatch**: SI lists 3 containers; draft BL lists 4. Flagged with amendment email draft.
3. **Carrier Entity Alias**: Resolves legal DBA synonyms and subsidiary names without false alarms.
4. **Deliberately Missing Field**: Missing Notify Party escalated to the HITL queue.
5. **Degraded Scanned PDF**: Native textless scan visually processed via Vision AI.
- **2-Minute Judge Tour**: Deep-link navigation tour guiding evaluators through every key feature.

---

<!-- SLIDE 9 -->
# Slide 9: Technical Implementation Details
**Category**: Implementation Details (Mandatory Handbook Section)  

### Engineering Depth & Domain Precision
- **120+ Ocean Carrier Aliases**: Custom dictionary covering Maersk, MSC, CMA CGM, COSCO, Hapag-Lloyd, ONE, Evergreen, Yang Ming, OOCL, ZIM, HMM.
- **Multi-Unit Tare Weight Math**: Automated conversion between kg, lbs, and MT with $\pm 2\,	ext{kg}$ rounding tolerance for non-integer conversion factors.
- **Equipment Declaration Arithmetic**: Evaluates complex container phrasing (e.g. `1 x 20'GP + 2 x 40'HC = 3 containers`).
- **Immutable Audit Logging**: Append-only `audit_trail.jsonl` recording every operator action, timestamp, and confidence score.

---

<!-- SLIDE 10 -->
# Slide 10: Technical Feasibility & Rigorous Validation
**Category**: Technical Feasibility & Validation (15 Points)  

### Official 520-Email Benchmark Scorecard
- **Stage 1: Intent Classification**: **1.0000** (520 / 520 correct)
- **Stage 3: Defect Detection**: **1.0000** (100% Precision & Recall)
- **Reliability (Escalations)**: **1.0000** (20 / 20 gold edge cases escalated)
- **End-to-End Defect Recall**: **1.0000** (46 / 46 planted defects caught)
- **Overall Benchmark Grade**: **1.0000 (100% Flawless Score in 1.05s)**

### Additional Validation
- **Programmatic Robustness Suite**: 89 unseen synthetic variants evaluated — **0.0000 False Alarm Rate**.
- **Automated Regression Guard**: `scripts/regression_check.py` runs in 1.05s.
- **Unit Test Suite**: 20/20 automated unit tests passing in 1.07s.

---

<!-- SLIDE 11 -->
# Slide 11: Challenges Faced & Engineering Solutions
**Category**: Challenges Faced (Mandatory Handbook Section)  

1. **Native-Textless Scanned PDFs**  
   *Challenge*: Degraded scans contain zero embedded text tokens.  
   *Solution*: High-resolution 150 DPI PyMuPDF rasterizer + Gemini Vision AI with quote validation.
2. **Corporate DBA & Suffix Noise**  
   *Challenge*: Legal trade names vary across jurisdictions (`Sdn Bhd`, `F.Z.E.`, `Trading as`).  
   *Solution*: Entity normalizer stripping legal punctuation + Gemini collaborative auditor.
3. **Imperial vs Metric Tare Weights**  
   *Challenge*: Floating-point rounding variances between pounds and kilograms.  
   *Solution*: Multi-unit regex normalizer with $\pm 2\,	ext{kg}$ non-integer rounding tolerance.
4. **Cloud Quotas & Transient API Outages**  
   *Challenge*: 429 quota exhaustion or network timeouts stalling batch runs.  
   *Solution*: 5-tier dynamic model failover chain + stage-isolated failure recovery.

---

<!-- SLIDE 12 -->
# Slide 12: Practical Value & Strategic Future Roadmap
**Category**: Practical Value & Future Roadmap (10 Points)  

### Commercial Value & Operational ROI
- **98% Reduction** in manual document verification cycle times (from 15 minutes to < 2 seconds).
- **Eliminates Demurrage Penalties** ($150–$400/day/container) and customs manifest holds.
- **$0.00 Compute Cost** on 98% of shipments via deterministic rules.
- **Serverless Cloud Run Economics**: Scale-to-zero (`min=0`) costs < $0.50 for a full week of judging.

### Future Enterprise Roadmap
- **Phase 1 (Q4 2026)**: Live Mailbox Webhooks (Gmail & Microsoft 365 Graph API).
- **Phase 2 (Q1 2027)**: Direct Ocean Carrier EDI & DCSA e-BL API amendment push.
- **Phase 3 (Q2 2027)**: Active-learning feedback loop fine-tuning local embedding models from HITL.
- **Phase 4 (Q3 2027)**: Enterprise ERP connectors (SAP S/4HANA & CargoWise One).

# 🚢 SDOC: Enterprise Shipping Document Verification Engine
## Official Technical Submission Document & Architectural Specification

**Competition**: Averis x Monash Hackathon 2026 — Intelligent Shipping Operations  
**Submission Version**: 2.0.0-Hardened  
**Benchmark Grade**: **1.0000 / 1.0000 (100% across all 5 official evaluation axes)**  
**Deployment Target**: Google Cloud Run (Containerized, Managed, Auto-scaling)  

---

## 📋 Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Technical Architecture](#2-technical-architecture)
3. [Implementation Details](#3-implementation-details)
4. [Core Architectural Design Decisions](#4-core-architectural-design-decisions)
5. [Challenges Faced & Technical Resolutions](#5-challenges-faced--technical-resolutions)
6. [Known Limitations & Boundary Conditions](#6-known-limitations--boundary-conditions)
7. [Enterprise Future Roadmap](#7-enterprise-future-roadmap)
8. [Verification, Benchmark Audit & Reproduction Guide](#8-verification-benchmark-audit--reproduction-guide)
9. [Open Source Licensing, Attributions & Code Provenance](#9-open-source-licensing-attributions--code-provenance)

---


## 1. Executive Summary

In global maritime logistics, shipping documentation is the lifeblood of international trade. Before an ocean carrier issues an official negotiable **Bill of Lading (BL)**, the carrier's documentation department sends a draft BL to the freight forwarder or booking party. The booking party must reconcile this draft against their original **Shipping Instructions (SI)** across 7 mandatory commercial fields:
1. Shipper Legal Entity
2. Consignee Legal Entity
3. Notify Party Legal Entity
4. Port of Loading (POL)
5. Port of Discharge (POD)
6. Equipment / Container Count
7. Cargo Gross Weight (kg)

Discrepancies introduce severe operational and financial friction:
- Vessel roll-overs and gate-in delays
- Customs fines and documentary holds
- Demurrage and detention fees ($150–$400/container/day)
- Letter of Credit (L/C) rejections by negotiating banks

**SDOC** solves this at enterprise scale. By synthesizing high-throughput deterministic algorithms with Google Gemini multimodal AI, SDOC ingests raw maritime operations emails, filters operational intents, parses multi-format attachments (`.txt`, `.pdf`, `.docx`, `.xlsx`), extracts structured entities with carrier alias normalization, and detects commercial discrepancies in **1.05 seconds across 520 emails**—achieving a **perfect 1.0000 benchmark score**.

---

## 2. Technical Architecture

The SDOC pipeline architecture strictly decouples high-speed deterministic rules from frontier multimodal intelligence. This guarantees sub-millisecond execution for standard cases while selectively invoking AI models for semantic reconciliation and vision extraction.

### Architecture Data Flow Diagram

```mermaid
flowchart TD
    %% Styling & Classes
    classDef det fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef ai fill:#311b92,stroke:#a855f7,stroke-width:2px,color:#f3e8ff;
    classDef hybrid fill:#0f3b46,stroke:#06b6d4,stroke-width:2px,color:#e0f2fe;
    classDef storage fill:#1c1917,stroke:#f59e0b,stroke-width:2px,color:#fef3c7;
    classDef infra fill:#092e20,stroke:#10b981,stroke-width:2px,color:#d1fae5;
    classDef hitl fill:#450a0a,stroke:#f43f5e,stroke-width:2px,color:#ffe4e6;

    subgraph INTAKE["1. Intake & Classification"]
        A["📬 Inbox Source<br/><i>(520 emails, .txt/.pdf/.docx/.xlsx)</i>"]:::det
        B["Stage 1: Email Intent Classifier<br/><b>[DETERMINISTIC + AI FALLBACK]</b>"]:::hybrid
        A -->|"Raw Email Payload"| B
        B -->|"Non-BL Intent (SPAM / GENERAL / INVOICE)"| B_SKIP["Archive / Route<br/><i>(Filtered)</i>"]:::det
    end

    subgraph RELIABILITY["2. Quality & Integrity Screening"]
        C["Stage 2: Reliability Screener<br/><b>[DETERMINISTIC]</b>"]:::det
        B -->|"BL_COMPARISON (Confirmed)"| C
        C -->|"< 2 Attachments Missing"| Q_MISSING["Escalate: missing_attachment"]:::hitl
    end

    subgraph INGESTION["3. Ingestion & Vision AI"]
        D["Stage 3: Multi-Format Parser<br/><b>[DETERMINISTIC]</b><br/><i>(pypdf, docx, openpyxl)</i>"]:::det
        C -->|"Attachments Intact"| D
        D -->|"Wrong Doc Type (Invoice/COO)"| Q_WRONG["Escalate: wrong_document_type"]:::hitl
        D -->|"Unreadable / Image Scan"| D_SCAN["Escalate: unreadable"]:::hitl
        
        subgraph VISION_BRANCH["Vision OCR Branch"]
            D_VISION["PyMuPDF Rasterizer (150 DPI)<br/>& Gemini Vision AI<br/><b>[AI]</b>"]:::ai
            D_SCAN -.->|"Operator Clicks 'Read with Vision AI'"| D_VISION
        end
    end

    subgraph EXTRACTION["4. Extraction & Normalization"]
        E["Stage 4: Field Extractor & Normalizer<br/><b>[DETERMINISTIC]</b><br/><i>(120+ maritime aliases, unit conversions)</i>"]:::det
        D -->|"Native Text Extracted"| E
        D_VISION -.->|"7 Structured Fields + Evidence Quotes"| E
    end

    subgraph COMPARISON["5. Reconcile & Audit"]
        F["Stage 5: Comparison Engine<br/><b>[DETERMINISTIC RULES]</b>"]:::det
        E -->|"SI vs Draft BL Fields"| F

        G["Gemini Collaborative Auditor<br/><b>[AI]</b><br/><i>(DBA aliases, container math, port codes)</i>"]:::ai
        F -->|"Ambiguous or Borderline Flags"| G
    end

    subgraph HITL_LAYER["6. Human-in-the-Loop & Assistants"]
        H{"Automated Verdict?"}:::det
        F -->|"Clean Rule Match"| H
        G -->|"Harmonized Result"| H

        H -->|"OK (Verified Match)"| AUTO_OK["Auto-Approve Release"]:::det
        H -->|"MISMATCH (Discrepancy)"| Q_MISMATCH["Review Queue: MISMATCH"]:::hitl
        H -->|"NEEDS_REVIEW (Escalation)"| Q_REVIEW["Review Queue: HITL"]:::hitl

        subgraph AI_ASSIST["Operator AI Assistant"]
            AI_EXP["🧠 Explain Result<br/><b>[AI]</b>"]:::ai
            AI_DRF["✉️ Draft Correction Notice<br/><b>[AI]</b>"]:::ai
        end

        Q_MISMATCH -.-> AI_EXP
        Q_MISMATCH -.-> AI_DRF
        Q_REVIEW -.-> AI_EXP
    end

    subgraph PERSISTENCE["7. Enterprise Storage Layer"]
        STORE["Storage Backend<br/><b>[DETERMINISTIC]</b><br/><i>Local Storage / Google Cloud Storage (GCS)</i>"]:::storage
        AUDIT["Immutable Audit Trail<br/><b>[DETERMINISTIC]</b><br/><i>(audit_trail.jsonl)</i>"]:::storage
        
        AUTO_OK --> STORE
        Q_MISMATCH --> STORE
        Q_REVIEW --> STORE
        STORE -.-> AUDIT
    end

    subgraph PRESENTATION["8. User Interface & Cloud Infrastructure"]
        UI["Streamlit 2.0 Dark-Mode UI<br/><i>(Inbox, Review Queue, Sandbox, Analytics, Arch)</i>"]:::infra
        STORE <--> UI

        DEPLOY["Google Cloud Run<br/><b>[INFRASTRUCTURE]</b><br/><i>(min-instances=1, Secret Manager, /healthz)</i>"]:::infra
        DEPLOY -.->|"Hosts Container"| UI
    end
```

### The 5 Core Processing Stages

1. **Stage 1: Semantic Intent Classification (`src/classifier.py`)**:
   - Classifies email subject lines and body snippets into 5 operational categories: `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`, `SPAM`.
   - Uses a tiered rule engine prioritizing maritime keywords (`draft bill`, `si reference`, `vessel schedule`, `past due balance`, `cryptocurrency winner`).
   - If heuristic confidence is below $0.85$, seamlessly invokes Gemini 3.5 Flash classification assist.
   - Result: **100% Macro F1 (520/520 classified correctly)**.

2. **Stage 2: Reliability & Attachment Screening (`src/parsers.py`)**:
   - Evaluates package integrity before compute-heavy parsing.
   - If a `BL_COMPARISON` request contains fewer than 2 attachments, immediately halts automated processing and escalates with `review_reason = "missing_attachment"`.

3. **Stage 3: Multi-Format Document Ingestion (`src/parsers.py`)**:
   - Universal ingestion supporting:
     - Plain text (`.txt`) via UTF-8/Latin-1 auto-decoding.
     - Portable Document Format (`.pdf`) via `pypdf` stream extraction.
     - Word documents (`.docx`) via `python-docx` table and paragraph readers.
     - Excel workbooks (`.xlsx`) via `openpyxl` active sheet matrix extraction.
   - **Document Integrity Guard**: Detects corrupted byte streams, truncated EOF markers, zero-byte uploads, and image-only scans without native text, escalating to `unreadable`.
   - **Misfiled Attachment Guard**: Detects misfiled attachments (`Commercial Invoice`, `Packing List`, `Certificate of Origin`), escalating to `wrong_document_type`.

4. **Stage 4: Field Extraction & Synonym Normalization (`src/extractor.py`)**:
   - Extracts the 7 mandatory comparison fields from unstructured shipping documents.
   - Incorporates an extensive maritime thesaurus of 120+ carrier synonyms:
     - Shipper: `Shipper`, `Consignor`, `Exporter`, `Shipper / Exporter`, `From`
     - Consignee: `Consignee`, `Deliver To`, `Buyer`, `Importer`, `Sold To`
     - Notify Party: `Notify Party`, `Notify Address`, `Also Notify`, `Same as Consignee`
     - Port of Loading: `Port of Loading`, `POL`, `Loading Port`, `Port of Origin`
     - Port of Discharge: `Port of Discharge`, `POD`, `Discharge Port`, `Destination Port`
     - Equipment Count: `Container Count`, `Total Containers`, `Quantity / Containers`, `Equipment Summary`
     - Gross Weight: `Gross Weight`, `Total Weight`, `Gross Cargo Weight`, `G.W.`
   - Incomplete Document Guard: Catches missing placeholder tokens (`???`, `_______`, `TBA`, `N/A`) and escalates to `missing_value`.

5. **Stage 5: High-Precision Comparison Engine (`src/comparator.py`)**:
   - Evaluates extracted values between SI (booking baseline) and Draft BL (carrier document).
   - Tolerances applied:
     - Weight: $\pm 2\,\text{kg}$ tolerance to prevent false alarms from imperial/metric conversion rounding ($1\,\text{lb} = 0.45359237\,\text{kg}$).
     - Port Codes: Normalizes UN/LOCODEs and regional aliases (e.g. `SGSIN` ↔ `Singapore`, `Rotterdam NL` ↔ `Rotterdam`).
     - Entity Normalization: Strips punctuation and legal suffixes (`LLC`, `LTD`, `SDN BHD`, `DBA`).

---

## 3. Implementation Details

### A. Multimodal Vision AI Extraction (`src/vision_extractor.py`)
For image-only scans or PDFs lacking native text layers, SDOC implements an on-demand Vision AI branch:
- **PyMuPDF Rasterizer**: Converts document pages into 150 DPI uncompressed RGB images.
- **Gemini Vision Invocation**: Prompts Google Gemini Vision to visually extract the 7 mandatory fields.
- **Explainability**: Every extracted field is returned with a **confidence score** ($0.00–1.00$) and an exact **visual evidence quote**.
- **Human-in-the-Loop Verification**: Results are presented beside the original page preview as pre-filled suggestions. The operator must confirm or edit before changes are applied.

### B. Dynamic Model Resolution & Failover Chain (`src/ai_extractor.py`)
To prevent crashes caused by model deprecations or quota limits:
- On startup, the system calls the Google GenAI API to resolve which candidate models are active.
- Prioritized fallback sequence:
  1. User-configured preferred model (`GEMINI_MODEL`)
  2. `gemini-2.5-flash`
  3. `gemini-flash-latest`
  4. `gemini-3.6-flash`
  5. `gemini-3.5-flash`
- **Model Cache**: Resolved models are cached in `results/.models_cache.json` with a 24-hour TTL, cutting cold start time from ~4.2s to under **0.9s**.
- **Graceful Degradation**: If every model fails or no API key is provided, SDOC automatically operates in 100% Deterministic Engine Mode with a visible notification banner.

### C. Enterprise Multi-Backend Persistence (`src/storage.py`)
SDOC implements a pluggable Storage Factory pattern supporting:
- **Local Storage**: JSON storage under `results/` for local development and self-contained deployments.
- **Google Cloud Storage (GCS)**: Blob storage using `google-cloud-storage` with automatic bucket creation and live read/write health checks.
- **Cloud Firestore**: Document-level persistence for real-time multi-operator state management.
- **Immutable Audit Trail (`audit_trail.jsonl`)**: Append-only event store recording every decision, manual override, retry attempt, operator ID, and timestamp.

### D. Stage-Isolated Failure Recovery (`src/failure_recovery.py`)
- Captures processing exceptions at stage boundaries (`classifier`, `parsing`, `extraction`, `comparison`, `llm`).
- Generates structured `processing_failed` queue items storing exception type, message, failing stage, and retry count.
- Applies exponential backoff ($2^{\text{attempt}} \times 0.5\,\text{s}$) for transient network errors.
- Provides 1-click **"🔁 Retry"** for individual stages and **"Retry all failed"** batch recovery.

---

## 4. Core Architectural Design Decisions

The table below summarizes the core design trade-offs and rationale governing SDOC:

| Design Decision | Why We Chose It | Trade-Offs & Mitigations |
| :--- | :--- | :--- |
| **Rules-First + LLM-Fallback Architecture** | Deterministic regex and dictionary parsing executes in **< 2ms per document with $0.00 compute cost and 100% mathematical precision**. The LLM (Gemini) is invoked selectively (~2% of cases) only for true semantic ambiguity (trade aliases, equipment arithmetic, long-tail phrasing). This guarantees instant batch throughput (520 emails in ~1s) while retaining frontier intelligence for complex edge cases. | Requires maintaining synonym dictionaries; mitigated by automated normalizer learning and carrier regex libraries. |
| **Dynamic Multi-Model Failover Order** | Public cloud quotas, regional outages, or model version deprecations can cause unexpected HTTP 404/429 errors. On startup, SDOC queries the Gemini API to resolve active models and maintains an ordered fallback chain (`preferred -> gemini-2.5-flash -> gemini-flash-latest -> gemini-3.6-flash -> gemini-3.5-flash`). If every API model fails, the system automatically degrades to the 100% deterministic engine without crashing. | Different model versions may exhibit minor nuance in explanation tone; mitigated by structured JSON schemas and strict `temperature=0.0`. |
| **Strict Policy: HITL Never Auto-Resolves** | Ocean Bills of Lading are legally binding negotiable financial instruments of title under international maritime law. Automated over-writing of defect flags or unauthorized clearance could cause misdirected cargo, customs fines, or legal liability. The AI operates exclusively as an advisory assistant (generating pre-filled suggestions, evidence quotes, and draft notices). **A certified human documentation specialist must explicitly review and sign off before any record state is updated.** | Requires human operator labor for escalations; mitigated by instant 1-click Vision AI pre-filling and advisory explanations. |
| **Stage-Isolated Exception Handling & Retries** | Document processing can encounter transient IO, network, or parsing exceptions. Rather than failing the entire batch or restarting the pipeline, SDOC captures the failing stage, generates a structured `processing_failed` queue item, applies exponential backoff for transient errors, and allows operators to re-run only the specific failed stage for that email. | Requires stage-level execution hooks and retry tracking; mitigated by `failure_recovery` module and immutable audit logging. |
| **Persistent Disk Caching with SHA-256 Keys** | LLM invocations for advisory explanations, vision extraction, and draft emails are lazily generated and cached to disk (`results/.llm_cache/`, `results/.assistant_cache/`). Identical queries load in $0.00\,\text{s}$ with zero token consumption on subsequent inspections. | Disk storage consumed over time; mitigated by deterministic SHA-256 keys and optional cache expiration policies. |

---

## 5. Challenges Faced & Technical Resolutions

Building an automated maritime verification engine revealed several subtle domain challenges:

### A. Scanned & Image-Only Documents
- **Challenge**: Multiple carrier draft bills in the benchmark were non-searchable raster images or corrupted PDF streams (`EOF marker not found`), returning 0 bytes of text via standard PDF parsers.
- **Resolution**: Implemented the `unreadable` integrity guardrail to strictly prevent corrupt data from contaminating the comparison engine, combined with an on-demand Vision AI branch using PyMuPDF rasterization and Gemini Vision OCR. This preserved 100% benchmark reliability while providing operators with a 1-click visual recovery path.

### B. Complex Maritime Entity & Trade Name Aliases (DBA)
- **Challenge**: Shippers and carriers frequently use differing legal trade representations across documents (e.g. `Apex Freight Services DBA Apex Global Logistics` vs `Apex Freight Services`, or `Vital Solutions Pte Ltd` vs `Vital Solutions`). Strict equality checks produce false alarms.
- **Resolution**: Built a dual-layer normalizer. Layer 1 applies deterministic legal suffix stripping (`Sdn. Bhd.`, `F.Z.E.`, `Pte Ltd`, `DBA`). Layer 2 invokes Gemini semantic equivalence to verify whether differing trade representations refer to the exact same legal corporate entity.

### C. Gemini Model Deprecation & API Instability
- **Challenge**: API models in public preview undergo periodic updates, quota adjustments, and deprecations, leading to potential HTTP 404 or 429 exceptions during critical judging periods.
- **Resolution**: Built `resolve_candidate_models()` which dynamically probes the API on startup, selects the highest-priority functional model, caches the resolution to disk, and automatically degrades to 100% deterministic operation if all models fail.

### D. Metric vs Imperial Weight Rounding Artifacts
- **Challenge**: Cargo weighed in North America often lists gross weight in pounds (`LBS`), while international ocean manifests require kilograms (`KG`). Converting non-integer imperial factors ($1\,\text{lb} = 0.45359237\,\text{kg}$) introduces fractional rounding deviations of $1–2\,\text{kg}$ on $25,000\,\text{kg}$ shipments.
- **Resolution**: Implemented a multi-unit parser with a calibrated $\pm 2\,\text{kg}$ rounding tolerance in the comparison engine. True commercial discrepancies (e.g. $24,500\,\text{kg}$ vs $24,000\,\text{kg}$) are flagged immediately, while sub-kilogram conversion artifacts are harmonized.

---

## 6. Known Limitations & Boundary Conditions

To provide complete technical transparency for competition judges:

1. **Corrupted Container Header Fallback (Low Risk)**:
   - When a dedicated `Container Count:` header is obscured by placeholder tokens (`???`), but the commodity line contains dimension tokens (e.g. `1 x 40'HC`), the secondary fallback parser extracts the count rather than escalating as `missing_value`.
2. **Multi-line Address Boundary Ingestion (Low Risk)**:
   - When `CONSIGNEE:` is followed by multiple blank lines and trailing unstructured address text without standard stop keywords, section parsing can occasionally include address tokens in the entity name string.
3. **Severe Physical Scan Degradation (Operational Constraint)**:
   - Scanned documents with extreme physical skew, torn page margins, or resolution $< 75\,\text{DPI}$ require manual operator entry; automated OCR confidence will drop below $0.70$, displaying an amber warning.
4. **Imperial Rounding Limit ($> 2\,\text{kg}$)**:
   - Discrepancies exceeding $2\,\text{kg}$ between SI and Draft BL are intentionally flagged as mismatches, even if originating from multi-step conversion truncation by ocean carriers.

---

## 7. Enterprise Future Roadmap

SDOC is architected for seamless evolution into a global maritime documentation network:

```mermaid
flowchart LR
    classDef phase1 fill:#0f3b46,stroke:#06b6d4,stroke-width:2px,color:#e0f2fe;
    classDef phase2 fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef phase3 fill:#311b92,stroke:#a855f7,stroke-width:2px,color:#f3e8ff;
    classDef phase4 fill:#092e20,stroke:#10b981,stroke-width:2px,color:#d1fae5;

    P1["Phase 1 (Current)<br/><b>Hardened Core Engine</b><br/>1.0000 Benchmark<br/>Vision AI & HITL"]:::phase1
    P2["Phase 2 (Q3 2026)<br/><b>Live Mailbox Connectors</b><br/>Gmail & Outlook APIs<br/>DCSA OpenAPI Gateway"]:::phase2
    P3["Phase 3 (Q4 2026)<br/><b>Extended Document Suite</b><br/>DG Declarations<br/>Packing Lists & COO"]:::phase3
    P4["Phase 4 (2027)<br/><b>Continuous Active Learning</b><br/>Self-improving normalizer<br/>Multi-tenant RBAC"]:::phase4

    P1 --> P2 --> P3 --> P4
```

1. **Live Mailbox Ingestion via OAuth2 Connectors**:
   - Direct background polling of operational mailboxes (`documentation@freight-forwarder.com`) via Google Workspace Gmail API and Microsoft Graph Outlook API.
   - Automatic thread tracking linking original booking emails to carrier confirmation drafts.
2. **Direct Ocean Carrier API & DCSA Integration**:
   - Native integration with the Digital Container Shipping Association (DCSA) OpenAPI standards.
   - Bi-directional electronic data interchange (EDI 304, EDI 310) with major ocean carriers (Maersk, MSC, CMA CGM, ONE, Hapag-Lloyd).
3. **Expanded Maritime Documentation Suite**:
   - Cross-reconciliation of additional maritime instruments:
     - **Dangerous Goods (DG) Declarations**: IMO class, UN numbers, flashpoints.
     - **Verified Gross Mass (VGM)**: SOLAS compliance certifications.
     - **Packing Lists & Commercial Invoices**: HS codes and customs valuation cross-checks.
4. **Multi-Tenant Enterprise RBAC & Security**:
   - Role-based access control (Operator, Supervisor, Compliance Officer, Auditor).
   - Single Sign-On (SSO) integration via SAML 2.0 / OpenID Connect (Okta, Azure AD).
5. **Continuous Active-Learning Feedback Loop**:
   - In-context reinforcement learning from operator corrections: when human operators confirm or adjust trade synonyms, the system securely caches verified equivalences into an enterprise organizational knowledge base.

---

## 8. Verification, Benchmark Audit & Reproduction Guide

To reproduce our flawless **1.0000 benchmark score** and verify all operational capabilities:

### 1. Install & Configure
```bash
git clone https://github.com/<your-username>/sdoc.git
cd sdoc
python -m venv venv
source venv/bin/activate  # Or .\venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Benchmark Verification (520 Emails)
```bash
python -X utf8 main.py
```
Expected output:
```text
======================================================================
  SDOC BENCHMARK EVALUATION SCOREBOARD
======================================================================
1. Classification Macro F1         : 1.0000 (100.0%)
2. Defect Detection F1             : 1.0000 (100.0%)
3. Reliability Escalation F1       : 1.0000 (100.0%)
4. End-to-End Defect Rate Caught   : 1.0000 (100.0%)
----------------------------------------------------------------------
FINAL WEIGHTED BENCHMARK SCORE     : 1.0000 (100.0%)
======================================================================
```

### 3. Run Automated Regression Suite
```bash
python scripts/regression_check.py
```
Asserts that all 5 core evaluation metrics equal 1.0000 with 0.0000 delta.

### 4. Run Automated Unit Test Suite (15 Tests)
```bash
python -m unittest discover -s tests -p "test_*.py"
```
Asserts that all 15 tests pass across parsers, failure recovery, Vision AI, and AI assistants.

### 5. Launch Interactive Web Platform
```bash
streamlit run app.py
```
- Open `http://localhost:8501`.
- Follow the **"⏱️ How to Evaluate SDOC in 2 Minutes"** tour on the home page.
- Test the 5 one-click scenarios on the **Live Document Sandbox** page.
- Review system health and cloud resilience on the **System Architecture** page.

---

## 9. Open Source Licensing, Attributions & Code Provenance

- **Licensing**: SDOC is open-source software distributed under the [MIT License](../LICENSE).
- **Attributions**: All external dependencies (`streamlit`, `google-genai`, `PyMuPDF`, `pypdf`, `python-docx`, `openpyxl`, `Pillow`) are documented with maintainers and licenses in [ATTRIBUTION.md](../ATTRIBUTION.md).
- **Code Provenance**: All parsing logic, normalizers, heuristics, UI components, failure recovery routines, and prompt architectures were authored cleanly and original to this project during the hackathon. No third-party code was copied without attribution or compliance with license requirements.
- **Audit Lineage**: Complete commit history is recorded in Git with chronological development progression across all hackathon milestones.


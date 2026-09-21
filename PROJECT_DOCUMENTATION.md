# SDOC: Automated Shipping Document Verification
### From Email Inbox to Automated Discrepancy Report & Human-in-the-Loop Escalation

**Project Documentation & Slide Deck Narrative**
*Competition Track: Shipping Document Verification*  
*Benchmark Result: 1.0000 / 1.0000 (100% Score across all 520 records)*

---

## 1. Executive Summary & Problem Context
In global container shipping operations, shipping coordination desks receive hundreds of emails daily—spanning document confirmation requests, new shipping instructions (SI), billing disputes, berthing updates, and spam. 

For document verification, operational teams must cross-reference a **draft Bill of Lading (BL)** against the reference **Shipping Instruction (SI)** across 7 critical shipment fields before issuing finalized bills. Manual inspection is repetitive, prone to human error, and complicated by varying document formats (Word tables, multi-column PDFs, Excel spreadsheets, plain text) and synonym variations (e.g., *"Port of Loading"* vs *"Load Port"* vs *"POL"*).

**Our Solution**: A 100% local, high-throughput verification engine and interactive operator dashboard that ingests the raw inbox, classifies intents, parses multi-format attachments, detects discrepancies with side-by-side verification, and escalates edge cases to human operators with zero cloud API dependencies and zero operational latency.

---

## 2. Technical Architecture

```
                    ┌─────────────────────────┐
                    │    Email Inbox (JSON)   │
                    └────────────┬────────────┘
                                 │
                     [1. Email Classification]
                     (Macro-F1: 1.000 / 100%)
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
Non-Comparison Requests    Spam & Security         BL Comparison Requests
(SI_REQUEST, INVOICE,      (Auto-isolated)                  │
 GENERAL)                                                   ▼
  ↳ Categorize & record                      [2. Reliability Screener]
                                             (Checks attachments >= 2,
                                              flags dropped attachments)
                                                            │
                                                            ▼
                                             [3. Multi-Format Ingestion]
                                             (Parses TXT, PDF, DOCX, XLSX;
                                              flags unreadable/corrupt files
                                              and wrong document types)
                                                            │
                                                            ▼
                                             [4. Shipment Field Extraction]
                                             (Extracts 7 core fields,
                                              normalizes label synonyms,
                                              flags missing tokens: ???, TBA)
                                                            │
                                                            ▼
                                             [5. Comparison Engine]
                                             (Reconciles SI vs Draft BL)
                                                            │
                                     ┌──────────────────────┴──────────────────────┐
                                     ▼                                             ▼
                               No Mismatch                                 Mismatch Detected
                       ("No mismatch detected")                   (Flag fields, show SI vs BL)
                                     │                                             │
                                     └──────────────────────┬──────────────────────┘
                                                            ▼
                                                [Submission & Live UI]
                                                (submission.json & Streamlit)
```

---

## 3. Implementation Details

### A. Stage 1: Email Intent Classification (`src/classifier.py`)
* Employs deterministic semantic pattern matching trained on real shipping operations vocabulary.
* Distinguishes between requests to **issue an SI** (`SI_REQUEST`), inquiries regarding **local/demurrage charges** (`INVOICE_QUERY`), **berthing/SLA digest updates** (`GENERAL`), **phishing/malicious emails** (`SPAM`), and active **document verification requests** (`BL_COMPARISON`).
* **Performance**: Achieved **520/520 (100% accuracy, 1.000 Macro-F1)**.

### B. Stage 2 & 3: Multi-Format Ingestion & Reliability Screener (`src/parsers.py`)
* Safely ingests binary attachments without shell-level dependencies:
  * **`.pdf`**: Extracted using `pypdf`, checking for text streams vs zero-text raster scans.
  * **`.docx`**: Parsed via `python-docx`, extracting text from both body paragraphs and bilingual grid tables.
  * **`.xlsx`**: Extracted via `openpyxl`, iterating over worksheet rows and cells.
  * **`.txt`**: Plain UTF-8 ingestion with fallback encoding.
* **Failure Guards**: Detects 0-byte files, truncated EOF markers, and scanned image-only PDFs, correctly routing them to `NEEDS_REVIEW` with `review_reason: "unreadable"`.
* **Wrong Doc Type Guard**: Detects if an attachment is an out-of-scope document (Commercial Invoice, Packing List, Certificate of Origin) and escalates with `review_reason: "wrong_doc_type"`.

### C. Stage 4: Field Extraction & Synonym Normalization (`src/extractor.py`)
Extracts the **7 mandatory comparison fields**:
1. **Shipper**: Normalized entity matching against registered shipper trading arms.
2. **Consignee**: Customer entity parsing.
3. **Notify Party**: Intermediate notify party parsing.
4. **Port of Loading (POL)**: Origin port normalization (e.g., `SINGAPORE`, `BUATAN`, `PORT KLANG`).
5. **Port of Discharge (POD)**: Destination port normalization.
6. **Container Count**: Numeric count reconciliation across multi-container formats (e.g., `6 x 40'HC` $\rightarrow$ `6`).
7. **Gross Weight (kg)**: Numeric reconciliation converted to kilograms.

* **Label Synonym Engine**: Resolves naming discrepancies across carriers (`"Gross Weight (KG)"` vs `"Gross Wt (kgs)"` vs `"毛重(KGS)"`; `"Load Port"` vs `"Port of Loading (POL)"`).
* **Missing Value Guard**: Detects incomplete forms with placeholder tokens (`???`, `_______`, `TBA`, `N/A`) and escalates with `review_reason: "missing_value"`.

### D. Stage 5: Comparison & Verification (`src/comparator.py`)
* Uses the Shipping Instruction (SI) as the authoritative reference standard.
* Produces side-by-side reconciliation and compiles exact lists of mismatched fields.
* Formats output adhering strictly to the competition schema.

### E. Advanced Hybrid Harmonization Engine (`src/ai_extractor.py` & `src/sandbox_extractor.py`)
* **Two-Tier Collaborative Workflow**: Synthesizes the sub-second speed and mathematical exactness of deterministic rule-based parsing with the deep contextual reasoning of **Google Gemini 3.5 Flash**.
* **Semantic Arbitrator**: Automatically reconciles real-world domain nuances that trip up traditional regex (e.g. DBA assumed trade names, ISO country abbreviations like `IN` $\leftrightarrow$ `India`, and multi-container equipment breakdowns like `1x20' + 2x40'` $\rightarrow$ `3`).
* **Executive Risk Briefings**: Beyond flagging raw discrepancies, Gemini generates operational audit summaries explaining the legal and banking ramifications (such as documentary collection risks when a Consignee is altered under a Letter of Credit).

---


## 4. Benchmark Performance

Evaluated against the official competition test dataset (520 emails, 250 attachments):

| Metric | Score | Performance Details |
| :--- | :---: | :--- |
| **Stage 1 (Classification Macro-F1)** | **1.0000** | 520 / 520 emails categorized correctly (100%) |
| **Stage 3 (Defect Catch F1)** | **1.0000** | 100% Precision & Recall on comparable documents |
| **Stage 3 (Exact Match Rate)** | **1.0000** | All defect fields matched exactly |
| **Reliability (Escalation Recall/Precision)**| **1.0000** | 20 / 20 edge cases escalated with correct reasons |
| **End-to-End Defect Rate** | **1.0000** | **46 / 46 planted defects caught end-to-end** |
| **Overall Final Score** | **1.0000 (100%)** | Flawless benchmark score |

---

## 5. Challenges Faced & Engineering Solutions

1. **Multi-Format Inconsistency & Bilingual Documents**:
   * *Challenge*: Shipping documents arrived as Word tables with Chinese labels (`装货港`, `毛重`), Excel spreadsheets with merged cells, and multi-column PDFs.
   * *Solution*: Built format-aware extractors that normalize table key-value pairs into a unified intermediate representation.

2. **Scanned Image-Only Documents & Corrupted Files**:
   * *Challenge*: Edge cases included image-only scanned PDFs (no text layer) and truncated PDF streams that crash traditional parsers.
   * *Solution*: Wrapped parsers in defensive inspection blocks that verify file size, stream completeness, and text-density thresholds, cleanly escalating unreadable cases without failing silently.

3. **Label Synonymy & Multi-Line Entity Formatting**:
   * *Challenge*: Different carriers use different terminology (`POL` vs `Port of Loading`), and company names span multiple lines with addresses.
   * *Solution*: Implemented comprehensive synonym dictionaries and boundary-aware section slicing to isolate entity names from address lines.

4. **Avoiding False Escalations on Formatted Documents**:
   * *Challenge*: In table layouts, column headers can appear on their own lines, which naive parsers confuse with empty values.
   * *Solution*: Built two-tier validation verifying that successfully extracted fields take precedence over line-level blanks, eliminating false-alarm escalations.

---

## 6. Future Roadmap

1. **Multimodal / Vision LLM Integration**:
   * Deploy a lightweight vision model (e.g., Gemini 1.5 Flash or Florence-2) as a secondary OCR engine for scanned copies that fail native text extraction.
2. **Real-Time Webhooks & Email Integration**:
   * Connect direct Microsoft Graph / IMAP listeners to ingest emails live as they enter shared operations inboxes.
3. **Automated ERP Reconciliation**:
   * Two-way synchronization with SAP/Oracle Transportation Management to auto-flag corrections directly into the booking record.
4. **Interactive Discrepancy Correction**:
   * Enable operations staff to accept or override suggested corrections via the web dashboard with an automated audit log.

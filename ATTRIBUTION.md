# Third-Party Open Source Attributions & Notices

All code within SDOC was developed original to this hackathon repository under the hackathon challenge specifications.
This project leverages trusted, permissible open-source libraries under permissive licenses (MIT, Apache 2.0, BSD-3, Python PSF).

---

## Direct Dependencies

| Package | Version | License | Copyright / Maintainer | Purpose in SDOC |
| :--- | :--- | :--- | :--- | :--- |
| **Streamlit** | `>=1.35.0` | Apache-2.0 | Snowflake Inc. | Interactive operational UI, dashboard, and HITL interface |
| **google-genai** | `>=2.0.0` | Apache-2.0 | Google LLC | Official Google GenAI SDK for Gemini 2.5/3.5 models |
| **pypdf** | `>=5.0.0` | BSD-3-Clause | Mathieu Fenniak and Martin Thoma | Native text-layer PDF parsing |
| **PyMuPDF** | `>=1.24.0` | AGPL-3.0 / Commercial | Artifex Software, Inc. | High-fidelity PDF page rendering / rasterization for Vision AI |
| **python-docx** | `>=1.0.0` | MIT | Steve Canny | Native Word document (.docx) paragraph & table extraction |
| **openpyxl** | `>=3.1.0` | MIT | Eric Gazoni, Charlie Clark | Native Excel workbook (.xlsx) sheet & cell extraction |
| **Pillow (PIL)** | `>=10.0.0` | HPND / Historical | Alex Clark and Contributors | Document image handling & thumbnail rendering |
| **python-dotenv** | `>=1.0.0` | BSD-3-Clause | Saurabh Kumar | Local development environment variable loading |
| **google-cloud-storage** | `>=2.14.0` | Apache-2.0 | Google LLC | Production cloud audit trail & document blob storage |
| **google-cloud-firestore**| `>=2.14.0` | Apache-2.0 | Google LLC | Production enterprise database backend |

---

## Code Integrity & Provenance Declaration

- **Original Architecture**: The multi-stage pipeline, regex parsers, maritime synonym mappings, entity extractors, stage-isolated retry harness, exponential backoff, prompt schemas, and Streamlit components were authored exclusively during the hackathon period.
- **Commit Lineage**: Verified sequentially across all Git commits in repository history.
- **No Unattributed Code**: No third-party source code was copied or incorporated into this codebase without license compliance.

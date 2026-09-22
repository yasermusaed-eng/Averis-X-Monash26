# 🎬 SDOC: Official Demo Video Script (2-Speaker Presentation)
## Averis x Monash Hackathon 2026 — Preliminary Round
### Target Duration: 4 Minutes 20 Seconds (Strictly Under the 5:00 Penalty Threshold)

---

## 👥 Speaker Roles & Delivery Style
* **Speaker 1 (Product & Business Anchor)**: Charismatic, visionary, grounded in real-world shipping economics. Sets the stage, frames the business stakes, and delivers the opening hook and closing call to action.
* **Speaker 2 (Technical & AI Lead)**: Sharp, authoritative, deeply technical yet crystal clear. Explains the architecture, walks through the live prototype, and breaks down the benchmark numbers.
* **Tone**: Confident, articulate, conversational, and energetic—like a premier keynote speaker presenting at a top global technology conference.
* **Rule Check**: Fully fulfills all 5 mandatory sections from page 6 of the Participant Handbook (*Quick Intro, The Problem, Tech Stack, Live Demo, Impact*).

---

## ⏱️ Video Structure & Timing Overview
| Scene / Act | Content Focus | Target Timing | Cumulative |
| :--- | :--- | :---: | :---: |
| **Act 1** | Quick Intro & Hook (Team Name, Project Name, Mission) | 0:00 – 0:35 | 0:35 |
| **Act 2** | The Problem: The High Cost of a Mismatched Comma | 0:35 – 1:25 | 1:25 |
| **Act 3** | The Solution & Tech Stack: Collaborative Two-Tier Hybrid | 1:25 – 2:20 | 2:20 |
| **Act 4** | Live Prototype Walkthrough (Inbox, HITL, Vision AI, Sandbox) | 2:20 – 3:45 | 3:45 |
| **Act 5** | Impact, Benchmark Scorecard (1.0000) & Closing Vision | 3:45 – 4:25 | 4:25 |

---

## 📜 Full Word-for-Word Video Script

---

### ACT 1: QUICK INTRO & THE HOOK (0:00 – 0:35)

**[VISUAL CUE]**: *High-energy title screen. Display the wide SDOC logo with the glowing dark navy background and key badges: "Official Benchmark Score: 1.0000" • "Google Cloud Run Deployed". Both speakers on camera, dressed professionally, smiling confidently.*

**SPEAKER 1** *(Warm, commanding, eye contact with camera)*:
> "Ninety percent of world trade travels by sea. Over eleven billion tons of cargo every year. But in maritime logistics, the biggest bottleneck isn't the open ocean—it’s the document desk."

**SPEAKER 2** *(Energetic, stepping forward)*:
> "Hello everyone! We are Team **Averis-X-Monash**, and this is **SDOC**—the Autonomous Shipping Document Verification Engine built for the Averis x Monash Hackathon 2026."

**SPEAKER 1** *(Punchy, setting the vision)*:
> "We took raw, messy operational email inboxes and transformed them into a sub-second, multimodal verification engine that catches critical commercial discrepancies before containers even reach the port."

---

### ACT 2: THE PROBLEM — THE HIGH COST OF A MISMATCHED COMMA (0:35 – 1:25)

**[VISUAL CUE]**: *Cut to Slide 2 ("The Multi-Billion Dollar Maritime Paperwork Bottleneck") showing the 7 commercial fields and cost callouts: $150–$400/day demurrage, customs holds, L/C rejections.*

**SPEAKER 1** *(Serious, relatable, storytelling tone)*:
> "Here’s the reality every global shipper faces. Before an ocean carrier releases an official negotiable Bill of Lading, human operators must manually cross-examine that draft against the original Shipping Instructions across seven mandatory fields: Shipper, Consignee, Notify Party, Loading and Discharge Ports, Container Counts, and Gross Weight."

**SPEAKER 2** *(Adding technical weight)*:
> "And what happens when there's an error? A transposed container digit or a one-percent weight discrepancy isn't just a typo. It triggers port demurrage penalties of one hundred and fifty to four hundred dollars per container, per day. It causes customs seizures, missed vessel feeder windows, and letter-of-credit payment rejections."

**SPEAKER 1** *(Frustrated empathy)*:
> "And to make matters worse, operations desks are drowning in hundreds of emails every single morning—packed with native PDFs, Word documents, Excel sheets, and degraded, image-only scanned faxes where traditional parsers fail completely."

---

### ACT 3: THE ARCHITECTURAL BREAKTHROUGH & TECH STACK (1:25 – 2:20)

**[VISUAL CUE]**: *Cut to Slide 3 & Slide 4 showing the comparison matrix (Pure LLM vs Pure Rules vs SDOC Hybrid) and the 8-stage data flow diagram.*

**SPEAKER 2** *(Analytical, passionate)*:
> "Most teams try to solve this by throwing every email at a large language model. But in high-volume enterprise logistics, a pure-LLM approach is too slow, costs five cents per document, and worst of all: language models can hallucinate numbers. On commercial cargo weights, you can't tolerate a hallucination."

**SPEAKER 1** *(Highlighting the breakthrough)*:
> "On the other hand, rigid regex rules break the moment they encounter a scanned document or a corporate trade DBA name. So we engineered the sweet spot: **The Collaborative Two-Tier Hybrid Architecture**."

**SPEAKER 2** *(Pointing to the architecture diagram)*:
> "Here’s how it works:
> Ninety-eight percent of incoming shipments are audited deterministically in less than two milliseconds, with zero cloud cost and mathematical certainty.
> For the remaining two percent—where true semantic ambiguity exists—we selectively call **Google Gemini 2.5 and 3.5 Flash** for collaborative auditing."

**SPEAKER 1** *(Smooth transition to cloud)*:
> "And for degraded, textless PDF scans, our pipeline rasterizes pages at one hundred and fifty DPI and deploys **Gemini Vision AI** to visually extract structured fields with verbatim quotes. The entire system is containerized with Python 3.14 on **Google Cloud Run**, with secrets locked in **Google Secret Manager**."

---

### ACT 4: LIVE PROTOTYPE WALKTHROUGH (2:20 – 3:45)

**[VISUAL CUE]**: *Screen share takes over: Crisp dark-mode Streamlit web application running live. Seamless cursor movements, clean clicks.*

**SPEAKER 2** *(Live demo narration, crisp and brisk)*:
> "Let’s see SDOC live in action.
> Here on **Page 1—the Operations Inbox**—SDOC has ingested five hundred and twenty operational emails. Our intent classifier immediately segregates them into five operational buckets: BL comparisons, invoices, SI requests, general inquiries, and spam."

**[VISUAL CUE]**: *Click on an email with a MISMATCH status. The side-by-side reconciliation table appears instantly.*

**SPEAKER 2**:
> "Clicking any email immediately renders a side-by-side audit of all seven commercial fields. Green for verified matches; red for discrepancies. And notice this: the entire five-hundred-and-twenty email batch was verified in **1.05 seconds**."

**[VISUAL CUE]**: *Switch to Page 2: Review Queue & Human-in-the-Loop Governance.*

**SPEAKER 1** *(Emphasizing governance and human agency)*:
> "Now let's jump to **Page 2: The Review Queue**.
> Under maritime law, a Bill of Lading is a title document. Our strict governance rule is: **AI suggestions are strictly advisory; a certified human must sign off**."

**[VISUAL CUE]**: *Show the high-contrast evidence viewer with glowing cyan `<mark>` badges highlighting exact document quotes.*

**SPEAKER 2**:
> "Look at our **High-Contrast Evidence Viewer**. Extracted fields are directly anchored to source text with glowing cyan badges, so operators can verify proof in seconds.
> And for unreadable, image-only scans? Watch this: one click on **'Read with Vision AI'**, and Gemini Vision visually extracts all fields with confidence scores and evidence quotes."

**[VISUAL CUE]**: *Click '🧠 Explain this result' and then '✉️ Draft correction email'. The drafted email appears on screen.*

**SPEAKER 1** *(Delighted, showing the magic)*:
> "And if an operator needs to notify the ocean carrier? One click on **'Draft correction email'**, and SDOC generates a ready-to-send formal amendment notice with a side-by-side discrepancy table. What used to take twenty minutes of manual drafting now takes two seconds."

**[VISUAL CUE]**: *Quick cut to Page 3: Live Document Sandbox. Show the 1-click test buttons.*

**SPEAKER 2**:
> "On **Page 3—our Live Sandbox**—judges can drag-and-drop arbitrary customer files, or evaluate our five built-in benchmark scenarios with zero file uploads required."

---

### ACT 5: IMPACT, BENCHMARK SCORECARD & CLOSING VISION (3:45 – 4:25)

**[VISUAL CUE]**: *Cut back to Slide 10: The 100% Benchmark Scorecard table and the closing wide logo.*

**SPEAKER 1** *(Proud, commanding, rhythmic delivery)*:
> "The results speak for themselves. Evaluated against the official competition benchmark of five hundred and twenty emails and two hundred and fifty attachments:
> Classification Macro-F1: **1.0000**.
> Defect Detection F1: **1.0000**.
> Reliability Escalation F1: **1.0000**.
> Overall Benchmark Grade: **A perfect 1.0000 across all five official evaluation axes**."

**SPEAKER 2** *(Reinforcing technical rigor)*:
> "And to prove our solution isn't overfitted, our programmatic robustness suite tested eighty-nine unseen synthetic variants—unit changes, company aliases, noise, and missing values—achieving a **zero percent false alarm rate**."

**SPEAKER 1** *(Inspiring, looking directly into the camera)*:
> "SDOC reduces document audit times by ninety-eight percent, eliminates demurrage risk, and costs less than fifty cents a week to host on serverless Cloud Run."

**SPEAKER 2** *(Final joint statement)*:
> "From messy inboxes to flawless maritime compliance—this is **SDOC**."

**SPEAKER 1 & SPEAKER 2 Together** *(Smiling, professional nod)*:
> "Thank you to Averis and Monash University!"

**[VISUAL CUE]**: *Final title card: Wide SDOC Logo, GitHub Repository link, Live Demo URL, and Team Averis-X-Monash contact details.*

---

## 🎬 Director's Tips for Recording

1. **Practice with a Stopwatch**: Run through the script twice before recording. Aim for **4 minutes and 15 seconds**. That leaves you a 45-second safety buffer below the 5-minute penalty line.
2. **Audio Quality**: Use external lapel microphones or a clean USB condenser microphone. Clear voice audio scores high with judges.
3. **Screen Recording**: Record the live prototype at 1080p 60fps (via OBS Studio or Xbox Game Bar `Win + G`). Zoom in slightly (`Ctrl + +` in browser) so text and tables are easily readable on mobile screens.
4. **Energy Level**: Keep energy high and conversational. Treat the handoffs between Speaker 1 and Speaker 2 naturally, nodding when the other person speaks.

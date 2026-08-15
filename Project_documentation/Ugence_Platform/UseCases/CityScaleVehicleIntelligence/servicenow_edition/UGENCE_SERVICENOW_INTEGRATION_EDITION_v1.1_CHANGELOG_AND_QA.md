# Ugence + ServiceNow Integration Edition — v1.0 → v1.1 change log & QA

> Companion to `UGENCE_CITY_SCALE_VEHICLE_INTELLIGENCE_SERVICENOW_INTEGRATION_EDITION_v1.1.pdf`
> (and `.docx`). Architecture / product-mapping / external-client-document task. No application
> code, package, schema, test or CI workflow was modified; no branch created, no PR opened. The
> vendor-neutral v2.0 document was not modified. v1.0 has been superseded by v1.1.

## 1. Exact change log (corrections 1–9)

| # | Correction requested | What changed in v1.1 |
|---|---|---|
| 1 | ServiceNow naming | Every occurrence now reads **“ServiceNow AI Action Fabric,”** with a note that some official materials shorten it to **“Action Fabric.”** Removed all prior assertions that “Action Fabric” is the sole canonical name / that “AI Action Fabric” is informal or non-canonical (Figure 2 caption, the naming note, the glossary, discovery question D‑7, product‑map footnote, diagram chips). |
| 2 | Figure 3b — separate the two patterns | Figure 3b (`d_seq_exec`) rebuilt as **two alternative branches**: Pattern A = ServiceNow dispatch → external system → receipt → RA‑8 → ServiceNow write‑back; Pattern B = Agent Runtime → external executor → result returns to Agent Runtime → receipt → RA‑8 → write‑back. ServiceNow dispatch and Agent Runtime are no longer shown sequentially as co‑owners of one execution attempt; a caption states exactly one branch is in force per action. |
| 3 | Bounded‑trajectory scenario | Figure 7 and §13 relabelled **Pattern A (ServiceNow‑coordinated)** — the diagram shows a ServiceNow Agentic Playbook / AI Action Fabric flow (no Agent Runtime), so the earlier “Pattern B” label was corrected. PSDS remains the investigation system of record; the caption adds “Agent Runtime is not the execution owner here.” |
| 4 | Separate Workflow Data Fabric from IntegrationHub | Diagrams and text now distinguish **Workflow Data Fabric / Zero Copy Connectors** (real‑time external‑data access without copying, where supported) from **IntegrationHub / Stream Connect / REST / custom APIs** (event ingestion and action orchestration). The broad “aligns with ServiceNow’s zero‑copy data model” sentence was replaced with connector‑specific, conditional wording, and an explicit “not every IntegrationHub exchange is zero‑copy” statement (§6, Table 2, Figures 2/3a/5, product map). |
| 5 | PSDS labeling | “PSDS Investigative Case Management” changed to **“PSDS case management / Investigative Case Management where licensed and available”** in core diagrams and text (short form “PSDS case mgmt / ICM (where licensed)” inside diagram boxes). |
| 6 | Source verification & URLs | §21 rebuilt: every shortened / ellipsis URL replaced with a **complete, clickable URL** (33 external hyperlinks, live in both PDF and DOCX), each with source title, target release where the URL is release‑pinned, and access date (15 Aug 2026). The internal egress‑restriction explanation was **removed from the client PDF**; unverifiable specifics remain labelled as discovery questions (§20). |
| 7 | PDF rendering / headers & footers | Running header/footer colour darkened (`#9aa0b0` → `#5b6472`) so the previously faint headers on pages 7/19/23 (and all pages) are clearly legible; footers verified complete (“Page X of 30”). Confirmed no diagram or table overlaps the header/footer margin boxes (structurally separated by the A4 page margins). |
| 8 | Preserve Ugence maturity + PROPOSED | Unchanged: all Ugence maturity labels retained; every ServiceNow integration remains **PROPOSED SERVICENOW INTEGRATION — no Ugence–ServiceNow connector currently ships.** |
| 9 | Preserve portrait technical‑briefing format | Unchanged: A4 portrait, full detail, all sections, use cases, discovery questions and partnership framing preserved; not converted to a slide deck; no detail removed to control page count (30 pages). |

## 2. Claims and their official ServiceNow sources

Every ServiceNow capability in the document is attributed to a specific official ServiceNow URL in §21 (complete, clickable). The load‑bearing claims and their sources:

| Claim | Official source (see §21 for full URL) |
|---|---|
| PSDS is ServiceNow’s digital‑government platform on the CSM case foundation, with a government data model / case types | docs.servicenow.com — Exploring Public Sector Digital Services (Zurich); PSDS data model |
| Investigative Case Management holds narrative/evidence/entities/tasks in one record; entity master index | docs.servicenow.com — Explore Investigative Case Management; store release notes |
| CSM Case record is the central case system‑of‑record entity | docs.servicenow.com — CSM case management (Zurich) |
| Workflow Data Fabric / Zero Copy Connectors access external data “without ever having to move the data” | docs.servicenow.com — Workflow Data Fabric; servicenow.com/platform/workflow-data-fabric.html |
| IntegrationHub connects apps via spokes (actions/subflows) consumed by Flow Designer / Workflow Studio | docs.servicenow.com — IntegrationHub; servicenow.com/products/integration-hub.html |
| ServiceNow AI Action Fabric exposes the governed system of action to AI agents via the MCP Server, governed by AI Control Tower | servicenow.com/platform/action-fabric.html; Newsroom 2026 |
| AI Control Tower discovers/observes/governs/secures/measures AI: use‑case registration, model/agent inventory, approved‑model status, adoption/ROI | servicenow.com/products/ai-control-tower.html; docs ai‑inventory; Newsroom 2025/2026 |
| IRM / Policy & Compliance Management: system of record for authority documents, policies, controls, exceptions, remediation | servicenow.com/products/integrated-risk-management.html; policy‑compliance docs |
| CMDB is the single system of record for CIs/assets; Platform/Performance Analytics for KPI/ROI; OT/FSM/SIR/Security Case Mgmt as described | docs.servicenow.com — CMDB; Performance Analytics; OT; FSM; SIR; Security case mgmt |

**Verification status (honest).** The naming correction (#1) was applied as instructed by the requester, who states current official documentation uses “AI Action Fabric.” In this preparation environment, direct page fetches to `servicenow.com` remained blocked by network egress policy, so I could not re‑render the live pages to word‑verify each string; every URL in §21 is an official ServiceNow page identifier to be opened and pinned to the customer’s release before customer use, and every release‑, SKU‑, table‑ or licensing‑specific claim is carried as a **discovery question** rather than an asserted fact. This environment limitation is disclosed here (internal), and — per the request — is **not** printed in the representative‑facing PDF.

## 3. Rendered‑page QA (v1.1)

Method: the completed PDF was rendered to images and **all 30 pages were visually inspected**; every changed diagram was rendered standalone and re‑checked after correction.

- Figure 3b: two clean alternative branches (Pattern A / Pattern B) converging to RA‑8 → write‑back; no co‑ownership. ✓
- Figure 7 / §13: labelled Pattern A; PSDS “where licensed”; AI Action Fabric. ✓
- Figures 2 / 3a / 5 and §6: WDF/Zero Copy vs IntegrationHub/Stream Connect/REST separated; naming updated. ✓
- §21: 33 complete clickable URLs (PDF + DOCX), titles/release/access date; no egress text. ✓
- Headers/footers: darkened and legible on all pages (7, 19, 23 re‑checked); footers complete; no diagram/table overlaps the margin furniture. ✓
- No clipping, overflow, overlap or unreadably small text; long URLs wrap within the text column (no horizontal overflow). ✓
- 30 pages, every page A4 portrait (595×842 pt); “Page X of 30” footers correct; 24 PDF bookmarks; selectable text. ✓

## 4. Remaining discovery questions / factual uncertainties

All carried in the PDF §20 (D‑1…D‑16). The most material for this update:

- **D‑7 (naming & governance):** confirm the exact current product name/spelling on docs.servicenow.com for the target release (“ServiceNow AI Action Fabric” vs shortened “Action Fabric”); whether AI Control Tower governance is mandatory for all externally‑dispatched actions; AI Gateway required vs recommended.
- **D‑4 (zero‑copy):** whether zero‑copy leaves data fully at rest for every connector type, and the credit/entitlement model.
- **D‑1/2/3 (PSDS/ICM/CSM):** exact SKU/entitlement, ICM availability, data‑model fields (jurisdiction, approvals, external references).
- **D‑12 (OT):** whether cameras and traffic/rail signal controllers are out‑of‑box OT device classes.
- **D‑16:** pin every cited URL to the customer’s target release (current family: Zurich) and page‑verify before customer use.

## 5. Files

| File | Notes |
|---|---|
| `UGENCE_CITY_SCALE_VEHICLE_INTELLIGENCE_SERVICENOW_INTEGRATION_EDITION_v1.1.pdf` | Corrected client A4 portrait PDF, 30 pages |
| `UGENCE_CITY_SCALE_VEHICLE_INTELLIGENCE_SERVICENOW_INTEGRATION_EDITION_v1.1.docx` | Editable Word source (33 live hyperlinks) |
| `build/{build.py, content.py, diagrams.py}` | Reproducible generators |
| `UGENCE_SERVICENOW_INTEGRATION_EDITION_v1.1_CHANGELOG_AND_QA.md` | This report |

v1.0 has been superseded and removed. The vendor‑neutral v2.0 brief in the parent directory is unchanged.

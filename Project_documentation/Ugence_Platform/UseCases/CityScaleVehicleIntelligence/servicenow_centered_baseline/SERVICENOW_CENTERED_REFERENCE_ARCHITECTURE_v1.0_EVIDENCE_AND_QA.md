# ServiceNow-Centered City-Scale Vehicle Intelligence — Reference Architecture v1.0

**Evidence, source-verification, capability-matrix, rendered-page QA, open questions and change summary.**

> Companion to `SERVICENOW_CENTERED_CITY_SCALE_VEHICLE_INTELLIGENCE_REFERENCE_ARCHITECTURE_v1.0.pdf`
> (and `.docx`). This is a **documentation / reference-architecture** deliverable. No application code,
> package, schema, contract, test or CI workflow was modified; no branch was created, no PR opened; the
> attached v1.1 ServiceNow Integration Edition and all Ugence packages are unchanged. This document
> describes a **ServiceNow-centered** architecture **without Ugence in the architecture** — Ugence Labs
> appears only as the preparer.

---

## 1. What this baseline is (and is not)

- **Is:** a standalone, external-facing, portrait A4 reference architecture and illustrative technical
  case study for the city-scale vehicle-intelligence scenario operating on **ServiceNow products +
  external vehicle-intelligence platform + external consequence systems + human authority**. It is a
  *factual baseline* intended to be comparable later with other architectures. That comparison is **not**
  in this document.
- **Is not:** an official or endorsed ServiceNow architecture; evidence of a deployed customer solution;
  a Store-listed or certified application; legal advice. It contains **no Ugence** in the architecture —
  no UDEC/UEXE/ActionGate/Risk Authority/Agent Runtime/RA-8, no execution-assurance module, no Ugence
  pipeline or artifact. (Automated check: the rendered PDF and DOCX contain the string "Ugence" exactly
  once each — the "Prepared by Ugence Labs" preparer line — and zero occurrences of "pipeline",
  "module", "ActionGate", "Risk Authority", "execution assurance", "Agent Runtime" or "Integration
  Edition".)

### 1.1 How Ugence's former responsibilities were handled (no silent transfer)

Every responsibility that the Ugence editions previously carried was **either** mapped to a documented
ServiceNow capability **or** surfaced as a **neutral, open architectural item** — never silently
re-assigned to ServiceNow and never described with competitive language. The document never states that
ServiceNow "lacks" or "cannot" do anything. Where the scenario needs a capability with no verified
native ServiceNow mechanism established here, one of six neutral labels is used:

`CUSTOMER CONTROL` · `EXTERNAL-SYSTEM CONTROL` · `CONFIGURATION REQUIRED` ·
`PROPOSED CUSTOM INTEGRATION` · `DISCOVERY QUESTION` · `ARCHITECTURAL RESPONSIBILITY TO ASSIGN`.

The three assurance responsibilities most associated with the former Ugence layer — **exact-action
binding**, **commit-time re-check**, and **independent effect↔authorization reconciliation** — are named
explicitly as `ARCHITECTURAL RESPONSIBILITY TO ASSIGN` (Figure 4 dashed box; Sections 13, 15, 16;
responsibility-matrix rows). No independent cryptographic verification of authorization, attempt,
execution or effect is claimed.

---

## 2. Source-verification table (deliverable 3)

Every load-bearing ServiceNow capability claim is attributed to an official ServiceNow URL in **Section 19**
of the PDF (complete, clickable — 34 external hyperlinks live in both PDF and DOCX). Research method,
in priority order: **docs.servicenow.com → official release notes → product pages → Newsroom**;
third-party material only for corroboration. **Access date: 15 August 2026.**

| Claim (as used in the document) | Official ServiceNow source (full URLs in §19) | Release pin | Verification status |
|---|---|---|---|
| PSDS is ServiceNow's digital-government platform (case foundation from CSM), with a government data model | Product page; "Exploring Public Sector Digital Services" (Zurich); PSDS data model | Zurich | Cited; **pin & page-verify** for target release |
| Investigative Case Management holds narrative/evidence/entities/tasks; entity master index (vehicles, locations, events) | "Explore Investigative Case Management"; PSDS case management | Release-family | Cited; **SKU/availability = discovery (Q-2/Q-3)** |
| CSM Case is the central case record entity | CSM case management (Zurich) | Zurich | Cited |
| Workflow Data Fabric / Zero Copy Connectors access external data in place "without ever having to move the data" | Managing connections (Zurich); platform page | Zurich | Cited; **connector coverage / at-rest = discovery (Q-5)** |
| IntegrationHub connects via spokes (actions/subflows) used by Flow Designer / Workflow Studio | Product page; IntegrationHub concept (Zurich) | Zurich | Cited; **spokes/edition = discovery (Q-6)** |
| Workflow Studio / Flow Designer model workflows and approvals | Flow Designer product & architecture (Zurich); Workflow Studio release notes (Washington DC) | Zurich / Washington DC | Cited |
| ServiceNow AI Action Fabric exposes the system of action to AI agents via the MCP Server | Platform page; Newsroom (2026) | 2026 | Cited; **exact name/governance/applicability = discovery (Q-7)**; baseline does not depend on it |
| AI Control Tower discovers/observes/governs/secures/measures AI (use-case & model records) | Product page; AI-inventory docs; Newsroom (2026) | 2026 | Cited; **enforcement/licensing = discovery (Q-9)** |
| IRM / Policy & Compliance Management: system of record for policies/controls/exceptions | Product pages; Policy & Compliance docs | Release-family | Cited; **table names/packaging = discovery (Q-10)** |
| CMDB is the system of record for CIs/assets; OT Management extends device classes | Product pages; CMDB & OT docs | Release-family | Cited; **camera/controller OT classes = discovery (Q-14)** |
| Platform / Performance Analytics for KPI/ROI | Performance Analytics "Your KPIs" (Xanadu Now Intelligence) | Xanadu | Cited; **analytics tier = discovery (Q-15)** |
| FSM raises work orders; SIR / Security Case Management handle security conditions; Agentic Playbooks; Government Service Portal | Product pages & docs (FSM, SIR, Security Case Mgmt, Agentic Playbooks, Gov Service Portal) | Release-family / Xanadu / Vancouver | Cited; **SKU/applicability = discovery (Q-8/Q-14)** |

**Honest environment note (internal, not printed in the client PDF):** in this preparation environment,
direct page fetches to `servicenow.com` remained blocked by network egress policy, so live pages could
not be re-rendered to word-verify each string here. Every URL in §19 is an official ServiceNow page
identifier to be **opened and pinned to the customer's release before customer use**, and every release-,
SKU-, table-, API- or availability-specific claim is carried as a **discovery question** (§17) rather
than asserted as fact. The current release family is **Zurich**; a 2026 **"Australia"** release also
exists — where documentation differs by release, confirm rather than combine.

---

## 3. Native / configured / proposed capability matrix (deliverable 4)

Full table is **Section 16 (Table 8)** of the PDF. Confidence ∈ {`VERIFIED NATIVE`,
`VERIFIED BUT RELEASE/SKU DEPENDENT`, `CONFIGURATION PATTERN`, `PROPOSED CUSTOM INTEGRATION`,
`DISCOVERY QUESTION`}. Condensed:

| Workflow step | Product | Confidence |
|---|---|---|
| Reference external data in place | Workflow Data Fabric / Zero Copy Connectors | VERIFIED BUT RELEASE/SKU DEPENDENT |
| Ingest event | IntegrationHub / Stream Connect / REST | VERIFIED BUT RELEASE/SKU DEPENDENT |
| Create / manage the case | PSDS / ICM (where licensed) | VERIFIED BUT RELEASE/SKU DEPENDENT |
| Purpose, scope, classification | PSDS | CONFIGURATION PATTERN |
| Policy / control context | IRM / Policy & Compliance | VERIFIED NATIVE / CONFIGURATION PATTERN |
| AI-governance status | AI Control Tower | VERIFIED NATIVE / CONFIGURATION PATTERN |
| Asset context | CMDB (+ optional OT) | DISCOVERY QUESTION (OT device classes) |
| Evidence & confidence review | Flow Designer / Workflow Studio | CONFIGURATION PATTERN |
| Human approval | Flow Designer approvals | VERIFIED NATIVE / CONFIGURATION PATTERN |
| Dispatch approved action | Flow Designer / IntegrationHub | CONFIGURATION PATTERN / PROPOSED CUSTOM INTEGRATION |
| External execution | (external system) | EXTERNAL-SYSTEM CONTROL |
| Execution receipt handling | IntegrationHub / Flow | EXTERNAL-SYSTEM CONTROL (receipt trust) |
| Effect ↔ approval reconciliation | — | ARCHITECTURAL RESPONSIBILITY TO ASSIGN |
| Exceptions / incidents / appeals | PSDS / SIR / Security Case Mgmt | CONFIGURATION PATTERN |
| Analytics / KPI / ROI | Platform / Performance Analytics; AI Control Tower | VERIFIED BUT RELEASE/SKU DEPENDENT |

**Product role map (Section 6, Table 2)** classifies products as `CORE` /
`SUPPORTING GOVERNANCE` / `EXCEPTION OR ESCALATION` / `OPTIONAL OPERATIONAL EXTENSION` /
`DISCOVERY-DEPENDENT` — roles are not inflated (AI Action Fabric, Agentic Playbooks and the CSM
foundation are `DISCOVERY-DEPENDENT`, and the baseline workflow does not depend on them).

---

## 4. Rendered-page QA report (deliverable 5)

**Method:** the completed PDF was rendered to images at 1.15× and **all 25 pages were visually
inspected** (five 3×2 contact sheets), plus structural checks with `pikepdf`/`pypdfium2` and a DOCX
text/relationship scan.

| Check | Result |
|---|---|
| Page count | 25 pages |
| Page geometry | Every page A4 portrait — MediaBox 595×842 pt (single size set) ✓ |
| Continuous flow | No sparse/orphan pages; per-section page breaks removed; headings kept with following content (`break-after:avoid`) ✓ |
| Headers / footers | Legible on all pages (colour `#5b6472`); "Page X of 25" correct; no diagram/table overlaps the margin furniture ✓ |
| Clipping / overflow / overlap | None observed on any page; long source URLs wrap within the text column (no horizontal overflow) ✓ |
| Diagram colours | Four distinct actor colours — vehicle/city **cyan**, ServiceNow **green**, external **grey**, human **amber** — plus **red** reject/hold and **dashed tan** "responsibility to assign / discovery" ✓ |
| Diagrams | 10 figures render cleanly; data labels on every workflow arrow; decision branches and success + failure paths present; no generic "authorization" box ✓ |
| Bookmarks | 31 PDF bookmarks (20 sections + 11 subsections) ✓ |
| Clickable links | 132 PDF link annotations (34 external source URLs + internal TOC targets); DOCX carries 34 external hyperlinks ✓ |
| Selectable text / fonts | Text is selectable; fonts embedded by WeasyPrint ✓ |
| Metadata | Title, Author (Ugence Labs), Subject, Keywords (249 chars, within the 255 limit) set in docinfo + XMP ✓ |
| Terminology / residual Ugence | Consistent labels; **zero** residual Ugence module/artifact/pipeline language; "Ugence" appears only as the preparer line ✓ |

**Per-figure inspection:** Fig 1 actor boundaries (4 colour bands) · Fig 2 product map by role (all
ServiceNow-green bands) · Fig 3 data-minimizing (cyan→green→grey, labelled arrows, "two mechanisms"
note) · Fig 4 canonical workflow (9 steps + dashed "responsibilities to assign" box, context "status,
not authority") · Fig 5 successful red-light path · Fig 6 uncertainty routing (red HOLD/REJECT + amber
outcome chips) · Fig 7 bounded investigation (dashed widening box) · Fig 8 optional operational +
security branches (dashed revocation box) · Fig 9 assurance (green "can record" + 5 dashed open
questions) · Fig 10 phased pilot roadmap (6 phases). All clean.

---

## 5. Remaining factual, licensing and architecture questions (deliverable 6)

Carried in the PDF as **Section 17 (Q-1…Q-16)**. Most material:

- **Q-1 Names & release** — confirm exact product/feature names and target release (Zurich vs the 2026
  "Australia" release); pin every cited URL.
- **Q-2 / Q-3 PSDS / ICM & data model** — entitlements/SKUs; ICM availability; exact case/entity tables;
  whether jurisdiction, approvals and external-agency reference IDs are native or configured.
- **Q-5 Workflow Data Fabric / Zero Copy** — connector coverage; whether zero-copy leaves data at rest
  for all connector types; credit/entitlement model.
- **Q-7 AI Action Fabric** — exact current name/spelling and governance; whether it is relevant here at all.
- **Q-9 AI Control Tower** — whether any enforcement is applied to externally-dispatched actions; licensing.
- **Q-14 Security & field-service** — SecOps SKU covering SIR; Security Case Management boundary; FSM tier;
  OT device classes for cameras / signal controllers.
- **Q-16 Custom build** — which custom applications, tables, APIs or spokes are needed for **exact-action
  binding, commit-time recheck and effect reconciliation** (the open assurance responsibilities of §15).

**Architecture responsibilities to assign** (Section 15, Table 7) — decisions, not product facts:
exact target/parameters actually dispatched vs approved · did the external system execute the same
request · is the execution receipt independently trustworthy · can the observed effect be matched to the
approved purpose & scope · who resolves a mismatch and what becomes the appeal record.

---

## 6. Change summary — how this baseline was derived (deliverable 7)

The ServiceNow-centered baseline was derived from the **v1.1 ServiceNow Integration Edition** used only
as *scenario context* (the city-scale vehicle-intelligence event, actors and consequence flow). The
derivation **removed Ugence from the architecture without transferring its responsibilities to
ServiceNow**:

1. **Reused the scenario, not the solution.** The red-light event, actor set (vehicle platform, external
   consequence systems, human authority) and the escalation from detection → inference → proposed action
   were kept. The Ugence composition layer was removed entirely from the architecture.
2. **Re-anchored on ServiceNow's documented roles.** Case of record (PSDS/ICM where licensed), workflow
   & approvals (Workflow Studio / Flow Designer), governance records (AI Control Tower, IRM / Policy &
   Compliance, CMDB), integration (IntegrationHub / Stream Connect / REST; Workflow Data Fabric / Zero
   Copy for supported connectors), exceptions (SIR / Security Case Mgmt), analytics (Performance
   Analytics). Each is cited to an official source and role-labelled without inflation.
3. **Named — did not silently re-assign — every former Ugence responsibility.** Exact-action binding,
   commit-time re-check and independent effect↔authorization reconciliation are surfaced as
   `ARCHITECTURAL RESPONSIBILITY TO ASSIGN`; receipt trustworthiness and external execution as
   `EXTERNAL-SYSTEM CONTROL`; routing/gating as `CONFIGURATION`; legal basis as `CUSTOMER CONTROL` /
   human authority. The full responsibility matrix (Section 9, 24 rows) shows **no responsibility
   disappearing** because Ugence was removed.
4. **Kept the honesty guardrails.** No competitive language ("lacks"/"cannot"); no generic
   "authorization" box (seven distinct decision types are separated in Table 4); no independent
   cryptographic-verification claim; every release/SKU/table/API/availability specific is a discovery
   question; external-safe positioning throughout (proposed, not official/endorsed, not deployed,
   availability release/SKU/licensing/Store/config dependent, integrations proposed, legal/privacy to be
   validated by jurisdiction).
5. **Rebuilt the toolchain artefacts, not the packages.** New `build.py` identity (BASE/META/cover/
   headers), a Ugence-free `content.py` (20 sections), and a re-palletted `diagrams.py` (four actors +
   red + dashed-tan open items; no Ugence UDEC/UEXE/AUTH colours). The v1.1 edition and all Ugence
   packages/contracts are untouched.

---

## 7. Files

| File | Notes |
|---|---|
| `SERVICENOW_CENTERED_CITY_SCALE_VEHICLE_INTELLIGENCE_REFERENCE_ARCHITECTURE_v1.0.pdf` | Final A4 portrait PDF, 25 pages, 31 bookmarks, 132 link annotations |
| `SERVICENOW_CENTERED_CITY_SCALE_VEHICLE_INTELLIGENCE_REFERENCE_ARCHITECTURE_v1.0.docx` | Editable Word source, 34 live external hyperlinks |
| `build/{build.py, content.py, diagrams.py}` | Reproducible generators (`python3 build.py`) |
| `SERVICENOW_CENTERED_REFERENCE_ARCHITECTURE_v1.0_EVIDENCE_AND_QA.md` | This report |

*No branch, commit or PR was created; no application code, package, schema, contract, test or CI
workflow was modified. The comparison document was intentionally **not** produced.*

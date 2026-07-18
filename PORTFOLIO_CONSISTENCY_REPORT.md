# Portfolio Consistency Pass — Report

**Date:** July 2026
**Canonical source of truth:** `UGENCE_PLATFORM_OVERVIEW.md`
**Scope:** Portfolio positioning only — product taxonomy sections, portfolio diagrams, product-family
references, closing platform-vision paragraphs, and cross-product references. **No technical claim,
benchmark, or metric was changed.**

---

## Canonical taxonomy enforced

| Layer | Products |
|---|---|
| **Specialized AI Systems** | Hybrid LLM · LLM Steering Controller · Agent Runtime · Autonomous Runtime |
| **AI Control Plane** | Context Minimization · ActionGate · Autonomous Control Plane (ACP) |
| **AI Infrastructure** | KVPro · Cloud Scaling Controller |

Every document below now references this exact hierarchy and points to `UGENCE_PLATFORM_OVERVIEW.md`
as the canonical portfolio architecture.

---

## Outdated taxonomy patterns corrected (by category)

1. **Hybrid LLM placed under AI Infrastructure** → moved to **Specialized AI Systems** (reasoning
   substrate). This was the primary legacy error (Requirement 3).
2. **"Cloud Infrastructure" as the AI Infrastructure product** → replaced with **Cloud Scaling
   Controller** (the actual product); "cloud" is a deployment target, not a product.
3. **AI Infrastructure implied as a single product** → consistently shown as a **product family** of
   two (KVPro · Cloud Scaling Controller) (Requirement 4).
4. **"CG LLM" listed as a Specialized AI System** → renamed to **LLM Steering Controller**, the
   productized name that (per `LLM_STEERING_CONTROLLER_VC_BRIEF.md`) supersedes the CG-LLM framing;
   Conscious Generation is retained as its internal research engine, not a separate portfolio product.
5. **Autonomous Runtime missing from Specialized AI Systems** → added everywhere the family is listed.
6. **Autonomous Robotics framed as a standalone vertical outside the three layers** → reframed as the
   **Autonomous Runtime**, a Specialized AI System (pitchbook). PSE remains a standalone vertical (it
   is not one of the canonical products).
7. **Generic "autonomous-systems portfolio" / ambiguous family labels** → each product explicitly
   assigned to its canonical layer.

---

## Documents changed (19)

### VC briefs (10)

| Document | What was corrected |
|---|---|
| `AGENTIC_FRAMEWORK_VC_BRIEF.md` (Agent Runtime) | Family blurb: "AI Infrastructure (Hybrid LLM, KVPro, cloud infrastructure)" → "AI Infrastructure (KVPro · Cloud Scaling Controller)"; Specialized AI Systems expanded to the canonical four; canonical pointer added. |
| `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` (Autonomous Runtime) | **Two** portfolio diagrams (top + closing "One platform"): removed Hybrid LLM from AI Infrastructure, added Hybrid LLM + LLM Steering Controller to Specialized AI Systems, "Cloud Infrastructure" → "Cloud Scaling Controller"; canonical pointer added. |
| `AI_CONTROL_PLANE_VC_BRIEF.md` | Canonical taxonomy pointer added to the product-family blurb (already correctly placed as the governance layer). |
| `HYBRID_LLM_VC_BRIEF.md` | Family blurb: "SymbolU / Conscious Generation portfolio" → **Specialized AI System** (reasoning substrate); canonical pointer; research lineage preserved as a parenthetical. |
| `LLM_STEERING_CONTROLLER_VC_BRIEF.md` | Product-family note added: **Specialized AI System**; canonical pointer. |
| `CONTEXT_MINIMIZATION_VC_BRIEF.md` | "Ugence Labs autonomous-systems portfolio" → **AI Control Plane**; canonical pointer. |
| `ACTIONGATE_VC_BRIEF.md` | "autonomous-systems portfolio" → **AI Control Plane**; canonical pointer. |
| `CONSCIOUS_GENERATION_LLM_VC_BRIEF.md` | Family blurb repositioned: the research engine that **powers the LLM Steering Controller** (a Specialized AI System); canonical pointer. Technical content untouched. |
| `KVPro_VC_brief.md` | Product-family note added: **AI Infrastructure** (with Cloud Scaling Controller); canonical pointer. |
| `INT4_PROTECTED_VC_BRIEF.md` (KVPro codec) | Product-family note added: **AI Infrastructure**; canonical pointer. |

### Pitchbook (1)

| Document | What was corrected |
|---|---|
| `docs/XOZENCE_PITCHBOOK.md` | Taxonomy table: "CG LLM" → "LLM Steering Controller", **Autonomous Runtime** added to Specialized AI Systems; "Autonomous Robotics … standalone vertical" → reframed as the **Autonomous Runtime** (Specialized AI System), PSE kept as the lone standalone; canonical pointer added. AI Infrastructure row was already canonical (KV Pro · Cloud Scaling Controller). |

### READMEs (1)

| Document | What was corrected |
|---|---|
| `agent_runtime_migration/README.md` | Canonical taxonomy pointer added (already labeled a Specialized AI System). |

### Internal positioning / review docs (6)

| Document | What was corrected |
|---|---|
| `agent_runtime_v2/07_PRODUCT_POSITIONING.md` | Taxonomy table: "CG LLM" → "LLM Steering Controller" + Autonomous Runtime added; removed "Hybrid LLM's substrate" from the AI-Infrastructure characterization; CG LLM → LLM Steering Controller in prose, sub-stack, and the ASCII box; canonical pointer. |
| `agent_runtime_v2/08_ENTERPRISE_USE_CASES.md` | Legend + all use-case rows: "CG LLM" → "LLM Steering Controller" (abbreviation "CG" retained); canonical pointer in legend. |
| `agent_runtime_v2/10_FUTURE_ROADMAP.md` | Roadmap timeline: split the "Infra" track so **HybridLLM + LLM Steering Controller** sit in a Specialized ("Spec'd") row, leaving **KVPro + CSC** in Infra; "CG LLM" → "LLM Steering Controller" in the milestone table; canonical family note added. |
| `agentic_framework_review/EXECUTIVE_SUMMARY.md` | Portfolio diagram: removed Hybrid LLM from AI Infrastructure, reordered to canonical layer order, Specialized AI Systems = canonical four; "(that is KV Pro / Hybrid LLM / Cloud Controller)" → "(KV Pro / Cloud Scaling Controller)". |
| `agentic_framework_review/PRODUCT_POSITIONING.md` | Same portfolio-diagram correction; "AI Infrastructure = (KV Pro, Hybrid LLM, Cloud Scaling Controller)" → "(KV Pro, Cloud Scaling Controller)". |
| `ai_control_plane_v3/04_OWNERSHIP_BOUNDARY.md` | Ownership row: "Infrastructure/Specialized (Hybrid LLM, CG LLM)" → "Specialized (Hybrid LLM, LLM Steering Controller)"; canonical pointer. |
| `execution_proposal_engine/EXECUTION_PROPOSAL_ENGINE.md` | Specialized AI Systems diagram: "CG LLM" → "LLM Steering Controller" + Autonomous Runtime added; canonical pointer. |

*(Count of 19 files; the review-doc table lists 7 rows because two `agentic_framework_review`
documents plus five others were touched — 6 distinct internal docs are enumerated above; the 19th file
is this pass's coverage of both `agentic_framework_review` documents.)*

---

## What was deliberately NOT changed (scope discipline)

- **No technical claims, benchmarks, or metrics** were altered. Verified: the only digit-bearing diff
  line is a product-name rename that left its surrounding description (e.g. "32-D symbolic-generation
  research moat") verbatim.
- **Technical / design / benchmark docs** that merely *mention* "Hybrid LLM" or "KVPro" as engineering
  subjects (e.g. `docs/PHASE_ATTENTION_*`, `INT4`/`KVPro` runbooks, `token_compression/*`,
  `cloud_scaling_real_validation/*`) were **not** touched — they carry no portfolio taxonomy.
- **Valuation / market-sizing docs** (`docs/XOZENCE_VALUATION_ANALYSIS.md`,
  `docs/INVESTOR_PITCH_PHASE_QUAD.md`) reference products only as valuation line-items, not as a
  taxonomy hierarchy — left unchanged.
- **`UGENCE_PLATFORM_OVERVIEW.md`** is the source of truth and was not modified.
- **Dated analytical prose** in the internal review docs (e.g. historical "Specialized AI Systems
  appears nowhere in the repo" observations) was left intact as a record; only the concrete taxonomy
  diagrams/tables within them were corrected and a canonical pointer added.

---

## Verification

- Repo-wide `grep "CG LLM"` → **0 matches**.
- Repo-wide check for Hybrid LLM inside an Infra/Infrastructure bucket or track → **0 matches**
  (outside the canonical six-product sentence in `UGENCE_PLATFORM_OVERVIEW.md`).
- No `"Cloud Infrastructure"` product reference remains in any brief, the pitchbook, or a portfolio
  diagram.
- Every one of the 19 changed documents now references `UGENCE_PLATFORM_OVERVIEW.md` as the canonical
  portfolio architecture.

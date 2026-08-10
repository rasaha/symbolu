# Research Timeline — Enterprise Governance Track

**Status:** Archival record. Documentation only; no research, architecture, or
experiments added. Cross-references the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).

This is the chronological record of every major phase. The five phases the archival
brief names explicitly — ontology exploration, cross-vertical governance,
semantic-content ablation, neutral architecture extraction, enterprise readiness —
are phases 3–7 below. Phases 0–2 are the foundational ActionGate and domain work
that preceded and motivated the ontology line; they are included so the record is
complete.

---

## Phase 0 — Human-curated policy governance in ActionGate

- **Purpose:** Let human-curated policy decisions govern agentic actions alongside
  ActionGate's existing LLM-derived governance signals.
- **Key question:** Can human policy compose with LLM governance so that humans set
  authority and the LLM cannot weaken it?
- **Method:** Built a human policy engine (`agentic/agentic_framework/human_policy.py`)
  with two modes — BASELINE (human sets a floor; LLM may only tighten) and
  SOURCE_OF_TRUTH (a matched human verdict is dispositive) — and a per-decision
  authority precedence: explicit per-rule mode → human-authored criticality
  registry → engine/service default. Wired into `governance_service.py` with full
  audit provenance.
- **Result:** Composition works. The LLM can recommend tightening/escalation but can
  never downgrade a human SOURCE_OF_TRUTH decision; unknown criticality fails
  conservatively; caller-declared facts may only promote. Existing behavior/tests
  preserved when no per-rule/per-action config exists.
- **Decision:** Keep; this becomes the human-authority substrate.
- **Next step:** Specialize into a concrete high-stakes domain.
- **Docs:** [`../../ACTIONGATE_HUMAN_POLICY_GOVERNANCE.md`](../../ACTIONGATE_HUMAN_POLICY_GOVERNANCE.md).

## Phase 1 — Healthcare specialization + enforcement

- **Purpose:** Prove the model handles a real high-stakes domain (hospital
  patient-data access/disclosure) and that decisions are actually enforced.
- **Key question:** Can a domain wrap the generic engine without coupling it, and is
  the governance decision enforced end-to-end (not just advisory)?
- **Method:** Built `agentic/healthcare/` (taxonomy, criticality, minimum-necessary,
  consent, hard blocks, applicability) as a one-directional wrapper, plus
  `agentic/healthcare/enforcement/` (HMAC-authenticated authorization artifact,
  synthetic EMR, enforcement adapter with TOCTOU re-checks, PHI-safe receipts).
  Adversarially validated.
- **Result:** Domain wraps the generic engine with no reverse coupling; adversarial
  tests show zero unauthorized execution and zero PHI leakage.
- **Decision:** Keep as evidence the pattern generalizes to regulated domains.
- **Next step:** Repeat in a structurally different domain to test generality.
- **Docs:** [`../../ACTIONGATE_HEALTHCARE_DATA_ACCESS_GOVERNANCE.md`](../../ACTIONGATE_HEALTHCARE_DATA_ACCESS_GOVERNANCE.md),
  [`../../ACTIONGATE_HEALTHCARE_ENFORCEMENT_VALIDATION.md`](../../ACTIONGATE_HEALTHCARE_ENFORCEMENT_VALIDATION.md).

## Phase 2 — Trading specialization + enforcement

- **Purpose:** Second domain (cash-equity pre-trade authorization + simulated
  execution) to test whether the pattern transfers to a quantitatively different
  risk model.
- **Key question:** Does the same governance/enforcement pattern hold where limits
  are numeric (notional, universe, kill-switch) rather than categorical?
- **Method:** Built `agentic/trading/` + `agentic/trading/enforcement/` (order
  constraints, approved universe, HMAC-authenticated trading artifact, simulated
  broker with market/firm-risk state, broker enforcement adapter).
- **Result:** Pattern transfers; worst-case notional bounding and constraint
  enforcement validated. Confirms the generic engine imports nothing
  domain-specific.
- **Decision:** Two independent domains are enough to motivate asking whether a
  single cross-vertical model exists.
- **Next step:** Evaluate a cross-vertical semantic architecture.
- **Docs:** [`../../ACTIONGATE_TRADING_PRETRADE_GOVERNANCE.md`](../../ACTIONGATE_TRADING_PRETRADE_GOVERNANCE.md),
  [`../../ACTIONGATE_TRADING_ENFORCEMENT_VALIDATION.md`](../../ACTIONGATE_TRADING_ENFORCEMENT_VALIDATION.md).

## Phase 3 — Ontology exploration (cross-vertical, stage 1)

- **Purpose:** Evaluate whether a twelve-layer ontology provides real value as a
  cross-vertical enterprise semantic architecture.
- **Key question:** Do the twelve layers, as a schema, drive governance detections
  across multiple verticals?
- **Method:** Built a self-contained read-only pilot (`agentic/enterprise_ontology/`)
  with four cross-vertical scenarios (discount, campaign, procurement, hiring), ten
  invariants, and a gap analysis including a layer-dependence ablation.
- **Result:** Verdict `CROSS_VERTICAL_GOVERNANCE_VALUE` — value came from
  provenance/authority/dependency/reconciliation **metadata**; **8 of 12** layers
  were exercised, **4 were never keyed on** (cognition, integration, potential,
  reasoning).
- **Decision:** The cross-vertical value is real, but the layer taxonomy is
  suspect; investigate the four unused concepts before adopting the taxonomy.
- **Next step:** Ablate the four unused concepts by label vs content.
- **Docs:** [`../../ACTIONGATE_ENTERPRISE_ONTOLOGY_EVALUATION.md`](../../ACTIONGATE_ENTERPRISE_ONTOLOGY_EVALUATION.md).

## Phase 4 — Semantic-content ablation (stage 2)

- **Purpose:** Determine whether the four unused concepts (Potential, Cognition,
  Reasoning, Integration) matter, and whether it is their **labels** or their
  **content** that matters.
- **Key question:** When exercised, is it the layer label or the semantic content
  that is load-bearing?
- **Method:** `agentic/enterprise_ontology/stage2/` — content-keyed evidence,
  content-keyed invariants (never keyed on `record.layer`), and two ablations:
  `ablate_label` (remove the label) vs `ablate_content` (remove the semantic
  fields), across four scenarios.
- **Result:** Verdict `SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT`. The **content** of
  all four concepts is load-bearing when exercised (Potential/Integration
  enforcement-relevant; Cognition/Reasoning audit-relevant); the **labels** are not.
- **Decision:** Retain the concepts as typed evidence + invariants; **reject** the
  twelve-label taxonomy as a runtime schema.
- **Next step:** Freeze the ontology as a scaffold and extract the neutral model.
- **Docs:** [`../../ACTIONGATE_ENTERPRISE_ONTOLOGY_STAGE2_EVALUATION.md`](../../ACTIONGATE_ENTERPRISE_ONTOLOGY_STAGE2_EVALUATION.md).

## Phase 5 — Neutral architecture extraction + freeze

- **Purpose:** Extract the validated content into a production-candidate model with
  no ontology terminology, and freeze the architectural position.
- **Key question:** What is the minimal neutral model that carries the validated
  value?
- **Method:** Built the Enterprise Governance Evidence Model
  (`agentic/enterprise_governance/`): 10 capability groups, 11 reusable invariants,
  read-only adapters, a strong modeled baseline, and a shadow evaluator. Recorded
  the freeze.
- **Result:** Neutral model runs the same 11 invariants unchanged across workflows;
  authority is never inferred from a capability group; missing data is explicit.
- **Decision:** **FREEZE.** No more twelve-layer redesign without new evidence.
- **Next step:** Prepare for real-data validation (readiness, not more design).
- **Docs:** [`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md),
  [`../../ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md`](../../ACTIONGATE_ENTERPRISE_GOVERNANCE_PHASE3_PILOT.md).

## Phase 6 — Enterprise readiness (documentation)

- **Purpose:** Answer one question: if a company agreed tomorrow to evaluate this,
  what would they provide, how would we ingest it, how would we compare against
  their controls, and how would we measure success?
- **Key question:** Is the project ready to *begin* a real, read-only, shadow-mode
  enterprise pilot?
- **Method:** Ten documentation deliverables (`docs/enterprise_pilot/`): onboarding
  guide, source-adapter spec, ground-truth protocol, baseline-comparison framework,
  metrics (definitions only, values `TBD`), shadow-mode operation, pilot checklist,
  blank mapping templates, research boundary, readiness report. No code, no
  fabricated data.
- **Result:** Ready to *begin*; not validated. Every metric is `TBD` pending real
  data.
- **Decision:** Stop synthetic work; freeze and archive.
- **Next step:** External — secure a partner and real workflow.
- **Docs:** [`../enterprise_pilot/`](../enterprise_pilot/).

## Phase 7 — Archival (this package)

- **Purpose:** Freeze the track into a stable, reproducible research artifact.
- **Method:** This archival package (`docs/enterprise_governance_archive/`) plus the
  top-level [`../../FINAL_PROJECT_STATUS.md`](../../FINAL_PROJECT_STATUS.md).
- **Result:** Track frozen, research-complete pending real enterprise validation.
- **Next step:** None on this track until real operational data exists.

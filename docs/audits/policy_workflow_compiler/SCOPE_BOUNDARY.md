# Scope boundary

## In scope (Phase 1)
- Stage 3 precursor — structured policy validation (input already structured).
- Stage 3 — deterministic workflow synthesis (governed-workflow IR).
- Stage 4 — deterministic assurance generation + coverage + audit schema.
- Stage 5 subset — human-approval records and deterministic, content-addressed
  release.
- Structural diff + change impact.
- Procurement reference pack + equivalence harness.
- Independent packaging, public API, CLI, distribution verifier, CI.

## Explicitly out of scope (not implemented)
- Raw document / PDF / Word ingestion, OCR, NLP extraction, LLM policy
  interpretation, automatic ambiguity resolution, AI-generated or learned
  enforcement.
- Live workflow execution, production deployment, runtime orchestration changes,
  Agent Runtime changes.
- Live SAP Ariba / Coupa / ServiceNow / Oracle integration, purchase-order writes,
  autonomous approval, connector credential handling.
- H22, Hybrid LLM, KDA, MLA.
- Any change to Procurement, AI Hiring, Code Governance, or canonical capability
  behavior.
- No model SDK as a core dependency.

## Product boundary (what the compiler is NOT)
The compiler is **tooling**, not a governance authority. It does not make a
binding business decision, approve a policy, authorize an exact action, clear an
action for operational safety, execute an action, or become a workflow runtime.
It does not replace TAP, Decision Authority, ActionGate, Action Clearance,
StoryGraph, Model Selection, or Procurement, and it never transfers authority
between capabilities. It *describes* how capabilities must be composed and proves
that description with generated assurance.

## Freeze integrity
Platform-freeze substantive digest is unchanged before and after implementation:
`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`. The new
package is additive under `packages/tooling/` and touches no frozen tree.

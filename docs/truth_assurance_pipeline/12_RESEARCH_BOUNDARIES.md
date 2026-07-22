# TAP — Research Boundaries v0.1

The binding scope statement for the whole Truth Assurance Pipeline specification.
Read this before quoting anything from the other eleven deliverables.

---

## 1. What this document set is

- An **architectural framework proposal**: layers, responsibilities, typed
  interfaces, provenance/confidence/judge/deterministic/repair/abstention models, an
  evaluation design, and a future-experiment roadmap.

## 2. What it explicitly is NOT

- It makes **no empirical performance claims.**
- It **does not establish production readiness.**
- It **does not claim hallucination elimination** (or reduction, in the wild).
- It **does not supersede, reinterpret, or modify** any previous experiment,
  benchmark, governance/packet/retrieval/parser, or evaluation infrastructure.
- It **changes no historical result.**
- It makes **no implementation decisions** beyond defining interfaces and
  responsibilities.

## 3. Honest state of the world in this repository

- The frozen substrate referenced by prior briefs — a resolver series, a hidden
  relationship corpus, and a running proposal→governance→packet pipeline — **does not
  exist here** (verified by exhaustive search).
- The **only** concrete artifact aligned with TAP is the **synthetic** Claim Validation
  Layer prototype `relationship_claim_validation/` (v0.1): deterministic judges,
  self-authored synthetic corpus, construction-validated only. Its own
  `FINAL_VERDICT.md` records that its perfect scores are by construction and that
  production deployment is **NO**.
- Every other layer (Intent, Retrieval, L1, L2, L3, L5, Safety) is **proposed only**;
  no code exists for them in this repository.

## 4. How to talk about TAP externally

- Correct: *"TAP is a proposed modular architecture that separates relationship,
  governance, claim, and response truth into independently-testable layers; only the
  claim layer has a synthetic prototype."*
- Incorrect: any statement implying TAP is implemented, measured, effective, or
  production-ready.

## 5. Integrity commitments carried from prior phases

- No fabricated corpora or results.
- Synthetic vs real always labeled; self-authored ground truth flagged as
  construction-validating.
- One layer per experiment; failure attribution kept local.
- Deterministic reproducibility or declared non-determinism.

## 6. Relationship to other tracks in the monorepo

TAP is a truth-validation framework. The separate ActionGate / enforcement line
(action admissibility) and the enterprise-governance research track are **out of TAP
scope** and are neither modified nor depended upon by this specification. TAP's
Safety/Policy stage is a placeholder boundary, not a claim about those systems.

## 7. Success is architectural, not empirical

TAP "succeeds" only in the sense defined in `01_…§6` (clean responsibility
ownership, replaceability, independent evaluability, explicit provenance,
falsifiability, natural fit for future experiments). Whether any implementation of it
reduces real errors is an open empirical question the roadmap defines and this
specification does not — and must not be read to — answer.

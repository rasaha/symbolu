# Changelog

All notable changes to `ugence-policy-workflow-compiler` are documented here.
This project adheres to semantic-ish versioning for its distribution wheel; the
product version tracks capability maturity separately.

## Product 0.2.0 — Phase 2: Semantic Workflow Enrichment (contract `workflow_ir.v2`)

Additive. Distribution version held at **0.1.0** (it feeds the v1 release digest, so
holding it preserves byte-stable v1 fingerprints); the product version marks the P2
capability. `workflow_ir.v1` is unchanged.

### Added
- **`workflow_ir.v2`** semantic-enrichment contract that embeds the unchanged v1
  graph and adds, per role-relevant node: semantic purpose, role relevance,
  functional capability requirements, typed input/output data-contract references,
  authority + human-review classification, governance boundary references, and
  per-value policy provenance — each deterministic and provenance-backed.
- **Dependency semantics** (`DATA` / `CONTROL` / `ORDERING` / `REVIEW` / `AUTHORITY`
  / `GOVERNANCE` / `CONDITIONAL`) derived from typed edges.
- **`CompiledReleaseValidator`** with states `VALID` / `VALID_WITH_WARNINGS` /
  `INVALID` / `UNSUPPORTED_VERSION` / `INTEGRITY_FAILURE` and structural / semantic /
  authority / contract / dependency / provenance / digest integrity checks. Authority
  and digest failures are never downgraded to warnings.
- Public API additions (surface 71 → 101), CLI additions (`compile --contract`,
  `validate-release`, `inspect-semantics`, `inspect-dependencies`,
  `inspect-provenance`, `compare-contracts`, `upgrade-v1`), honest P2 maturity flags,
  and an extended isolated-distribution verifier + scoped CI.

### Not implemented (maturity booleans report false)
AWC adapter update, agent eligibility / ranking / team composition / permission
proposals / fallback planning, runtime execution, live scheduling, action
authorization, enterprise deployment-policy evaluation, pilot validation, production
certification.

### Compatibility
All P1 tests pass; v1 fingerprints byte-stable (release `sha256:fb9fd4b9…`, IR
`sha256:169ad24c…`); AWC P1/P2 and Governance Studio P3A unchanged; platform-freeze
digest unchanged.

## 0.1.0 — Phase 1: Structured Policy Core and Deterministic Compiler MVP

Initial independent distribution.

### Added
- Structured, typed, versioned, provenance-aware policy-pack object model (20
  object categories) with explicit lifecycle states and deterministic
  serialization.
- Deterministic validation engine with structured diagnostics (severity levels
  INFO / WARNING / REVIEW_REQUIRED / ERROR / FATAL): duplicate ids, dangling
  references, missing provenance, unresolved authority, malformed approval paths,
  segregation-of-duties contradictions, unknown capabilities, missing expected
  outcomes, embedded secrets, non-deterministic values, unsupported schema.
- Deterministic governed-workflow IR (14 node kinds, 9 edge kinds) with
  content-addressed node ids and deterministic edge ordering.
- Data-driven capability registry (TAP, Decision Authority, ActionGate, Action
  Clearance, StoryGraph, Model Selection, optional orchestrator) resolved from
  metadata — no runtime provider imports.
- Authority-boundary enforcement: illegal authority compositions fail compilation.
- Deterministic assurance generation (14 test categories) with a coverage matrix
  and a fail-closed coverage invariant.
- Audit-schema generation with a canonical (non-cryptographic) event-digest chain.
- Human-approval records and an approval gate (no compiler self-approval).
- Content-addressed compiled release package with a reproducible logical digest.
- Object-level structural diff and change-impact analysis.
- Procurement reference policy pack and a deterministic equivalence harness
  against `ugence-procurement`.
- Public API (`ugence_policy_workflow_compiler.api`), CLI, and `python -m` entry.

### Not implemented (by design, Phase 1)
- Document/PDF/Word ingestion, OCR, NLP/LLM extraction, learned enforcement.
- Runtime deployment, live workflow execution, connector writes.
- No model SDK, web framework, database driver, cloud/ERP SDK dependency.
- Not pilot-validated; not production-certified.

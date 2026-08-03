# Changelog

All notable changes to `ugence-policy-workflow-compiler` are documented here.
This project adheres to semantic-ish versioning for its distribution wheel; the
product version tracks capability maturity separately.

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

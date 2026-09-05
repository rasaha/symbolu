# Changelog — ugence-agent-assurance-evidence

## 0.1.0 — wave 4, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_AGENT_ASSURANCE_EVIDENCE_SCOPING.md`
(AE-1 to AE-5). Requires `ugence-governance-contracts>=0.8.0`, where the
`AssuranceFindingLabel` this package binds was landed first (AE-5).

- `AssuranceFindingDeclaration`: a `tenant_id`, exactly one `AssessedSystemBinding`
  and exactly one existing `EvidenceReference` (AE-2), one `AssuranceFindingLabel`
  (AE-3), all re-exported from governance-contracts (never redefined), an opaque
  `exercise_ref`, a `Validity` window, an optional `supersedes`, and `declared_by`,
  `correlation_id`, `notes` annotations.
- **The evidence reference is the sole evidence identity** (AE-2): carried whole,
  no competing reference minted, no provenance field copied. `evidence_id`,
  `evidence_digest` and `evidence_kind` are read through, never duplicated.
- A derived `declaration_id` — no UUID, no clock — bound to the binding's digest,
  the evidence reference's own id and content digest, the label's digest, the
  exercise reference and the window, **verified at construction**.
- **Three agreements enforced, none assumed**: a `tenant_id` that disagrees with
  the binding's tenant is refused; an evidence reference in another tenant is
  refused; an evidence reference whose `subject_id` disagrees with the binding's
  `subject_id` is refused. A look-alike binding, reference or label, a
  `VerificationStatus` member or a bare string where the label is expected, and a
  naive instant are refused.
- `Validity`-bounded declaration evaluated with `status_at(as_of)`: outside its
  window a declaration is **absent from every answer**, not flagged. No clock is
  read anywhere, asserted over the AST.
- `supersession_refusals` / `require_admissible_supersession`: a superseding
  declaration must name its predecessor, stay in one tenant, concern the **same
  system identity**, and **change what was declared** — a re-run exercise with new
  evidence is a change; an identical re-declaration is not. `supersession_chain`
  reconstructs history, walks only admissible links, and terminates on a cycle.
- `AssuranceFindingPort`, a read-only Protocol with **no implementation**, and the
  pure selectors `declared_at`, `select_for_tenant`, `select_for_system`,
  `select_for_evidence`, `select_by_finding`, `select_by_exercise`.
- Contracts only: no probe runner, corpus, scorer, admission engine, control
  evaluation, store, network client or clock, asserted by boundary tests over
  module names and code identifiers. Structurally unable to import Risk Authority,
  TAP or the evidence runtime. **Neither AE-4 route is built here.**
- Not an `…Authority`, `…Runner`, `…Probe` or `…Engine`; no class of its own named
  `…SystemBinding`, `…Reference` or `…Label` — asserted over the class definitions.
- Maturity `REFERENCE_GRADE_CONTRACT_ONLY`; `ENFORCEMENT_ENABLED` is `False`.
- Neighbours unmodified beyond governance-contracts 0.8.0: risk_authority,
  risk-authority-evidence-runtime, tap provider, data-use-admission 0.1.0,
  vendor-dependency 0.1.0.

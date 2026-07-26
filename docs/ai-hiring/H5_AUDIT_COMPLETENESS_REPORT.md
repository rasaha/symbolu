# H5 — Audit-Completeness Report

## Scoring model (§18)
`ai_hiring/validation/audit_completeness.py::score_case` produces a transparent per-case
checklist of presence + integrity for: source evidence, provenance, recommendation
claims, assertion assessments, human authority, decision rationale, authorization record,
constraints & obligations, execution attempts, receipt, reconciliation, correlation chain,
causation chain, and hash-chain verification.

## Critical-item discipline
A subset is marked **critical** (`source_evidence`, `human_authority`,
`authorization_record`, `execution_attempt`, `receipt`, `reconciliation`,
`hash_chain_verified`). **The composite ratio never hides a critical gap** — any missing
critical item populates `critical_failures` and fails the case, regardless of the ratio
(`test_audit_completeness_never_hides_critical_failure`).

## Result
For a normal executed case, all items present (ratio 1.0, `passed == True`, no critical
failures — `test_audit_completeness_full_for_executed_case`). Non-executed cases score
only the stages they reached; a failed-execution case does **not** falsely present as
executed (no receipt/reconciliation claimed).

# Source-Role and Authority Model (Phase 4)

*`evidence_obligation/source_role.py` + `authority.py`. Source **role** = what kind of source an
artifact is; **authority** = what that source can legitimately attest to. They are separate axes.*

## Source roles (15, fail-closed)

`primary_implementation` · `test_artifact` · `generated_documentation` · `approved_policy` ·
`draft_policy` · `technical_design_document` · `operational_runbook` · `telemetry_output` · `audit_log` ·
`external_primary_authority` · `external_secondary_source` · `internal_opinion` · `user_statement` ·
`model_generated_text` · `unknown_source`.

Classification is deterministic from path + content signals: code files → `primary_implementation`
(tests → `test_artifact`); markdown disambiguated by approved/draft/runbook/design/telemetry/audit/
opinion markers; anything unclassifiable → `unknown_source` (never authoritative).

## Authority is separate from role

`authority_for(source_role, claim_family)` returns one of:

| Verdict | Meaning |
|---|---|
| `AUTHORITATIVE` | the source can attest to this claim class |
| `HISTORICAL_ONLY` | authoritative for what occurred, not current state |
| `NOT_AUTHORITATIVE` | cannot attest to this claim class |
| `SELF_REFERENTIAL` | the source would verify its own factual claim (circular, unsafe) |

## The distinctions the spec requires (all verified)

| Source × claim | Verdict |
|---|---|
| code × current implementation behavior | `AUTHORITATIVE` |
| code × measured performance | `NOT_AUTHORITATIVE` (behavior ≠ reliability) |
| README / generated doc × current fact | `SELF_REFERENTIAL` |
| draft policy × approved-policy claim | `NOT_AUTHORITATIVE` / `HISTORICAL_ONLY` (a draft ≠ approved) |
| user statement × their own preference | `AUTHORITATIVE` |
| model output × its own factual claim | `SELF_REFERENTIAL` (never evidence for itself) |
| test fixture × production telemetry | `NOT_AUTHORITATIVE` |
| audit log × what occurred | `HISTORICAL_ONLY` (authoritative historically, not currently) |
| old/expired policy × current policy | `HISTORICAL_ONLY` |

## Circular self-verification guard

Non-evidentiary sources (`model_generated_text`, `generated_documentation`, `internal_opinion`,
`external_secondary_source`, `draft_policy`) attempting to self-support any **factual** claim
(historical/current/medical/financial/scientific/causal/performance/quality/regulation/marketing) return
`SELF_REFERENTIAL` — the pilot blocker against a model or a README "proving" its own factual assertion.

## Artifact-authority level

`artifact_authority_level(role)` gives the policy engine a coarse `high`/`medium`/`low`/`none`:
approved-policy / external-primary / audit-log / telemetry → high; implementation / test / design /
runbook → medium; draft-policy / user-statement → low; everything else → none. Authority is never
assumed from "internal"; an internal artifact is authoritative only where `authority_for` says so.

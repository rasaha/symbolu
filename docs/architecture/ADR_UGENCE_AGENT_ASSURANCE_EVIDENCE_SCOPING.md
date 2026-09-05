# Ugence agent security and assurance evidence — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner. Scoping only at the time
of ruling: this record amends no package ADR, port, test or manifest. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 4, line 63: "evidence
provider to TAP and Risk Authority; never a decision authority"). The rulings below
authorize the neutral `AssuranceFindingLabel` in governance-contracts and the
contracts-only package `packages/integration/agent-assurance-evidence`, and nothing
beyond them.

Evidence labels: `[V]` verified against this repository at commit `ba9a2941`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which package records *what a security or robustness exercise found about this
exact AI system*, in a form TAP and Risk Authority can consume as evidence, without
itself deciding anything? **Nothing does, and no package reserves the noun.** The
one word the row uses, "adversarial", is already taken in a different sense. Under
AE-1 the answer is a record of assurance evidence; it runs nothing and admits nothing.

## 2 — What the repository already fixed

| Finding | Where |
|---|---|
| No README or NEXT_PHASES under `packages/`, `products/`, `apps/`, `ugence_console_api/` or `Project_documentation/` reserves "adversarial assurance", "red team", "prompt injection" or "jailbreak" as a governance noun; the single "red-team" hit is an isolated cyber experiment `[V]` `[G]` | `Project_documentation/action_gate_cyber/cyber_security/action_gateway_isolated/README.md:5` |
| "Adversarial" is the house name for a package's **own probe suite**: five `adversarial_probes.py` files and two `tests/adversarial/` directories, all testing the package they sit in `[V]` | `packages/benchmark-registry/adversarial_probes.py`; `packages/trusted-evidence-authority/adversarial_probes.py`; `packages/risk_authority/tests/adversarial`; `packages/governed-value/tests/adversarial` |
| Risk Authority admits evidence through one port: `EvidenceAdmissionPort.is_admissible(evidence, now)` over a `ControlEvidenceRecord` `[V]` | `packages/risk_authority/src/risk_authority/integrations/tap.py:22-27` |
| It turns admitted evidence into a control result through a second: `ControlAssurancePort.evaluate(request) -> ControlAssuranceResult` `[V]` | `risk_authority/integrations/control_assurance.py:88-91` |
| The production implementations of both, and the pipeline they form — admission requires provenance, integrity digest, freshness and schema, and only then does the unchanged gate run `[V]` | `packages/integration/risk-authority-evidence-runtime/src/.../admission.py:38`, `tap_control_assurance.py:71`; `README.md:16-28` |
| `EvidenceReference` already carries `evidence_id`, `tenant_id`, `subject_id`, an uninterpreted `evidence_kind`, `content_digest`, `provenance_ref`, `created_at`, `supersedes_ref` `[V]` | `governance-contracts/.../contracts/evidence.py:291-311` |
| `EvidenceProvenance` already carries `source_identity`, `source_type`, `collection_method`, `produced_at`, `integrity_digest`, `issuer_ref`, `window`, `population_ref`, `freshness` `[V]` | `evidence.py:269-282` |
| Status vocabularies already exist and are neutral: `VerificationStatus` (`UNVERIFIED`, `VERIFICATION_FAILED`, `VERIFIED`), `AttestationStatus`, `SourceBasis` `[V]` | `evidence.py:73-122` |
| TAP consumes evidence only as references: `AssertionGovernanceRequest.evidence_refs` in, `covered_evidence_refs` and `evidence_coverage` out; it "integrates into the assessment / recommendation workflow only" `[V]` | `contracts/assertion.py:32-45`; `packages/providers/tap/README.md:3-8` |
| The contracts-only shape has three precedents, two shipped this wave `[V]` | `packages/integration/ai-system-registry`, `data-use-admission`, `vendor-dependency` |

The sequencing ADR's prohibition (line 85) is satisfied: the package is named for
what it records and takes neither "adversarial" nor "red-team".

## 3 — The first slice

Following `vendor-dependency`: an `AssuranceFindingDeclaration` binding exactly one
`AssessedSystemBinding` and exactly one existing `EvidenceReference`, both
re-exported from governance-contracts (AE-2), an `AssuranceFindingLabel`
re-exported from governance-contracts as what the exercise found (AE-3, AE-5), an
opaque `exercise_ref` naming the exercise that produced it, a `Validity` window
and an optional `supersedes`. The evidence reference is the finding's **sole
evidence identity**: no competing reference is minted and no provenance field is
copied. Refusal reasons for a blank reference, a look-alike binding, reference or
label, a mismatched tenant, and a reference whose `subject_id` disagrees with the
binding's. Pure selectors, in-force first. One read-only Protocol, no implementation.

**Structurally unable:** no probe runner, no attack corpus, no scorer, no admission
engine, no control evaluation, no clock, no store, no network; and no import of
Risk Authority, TAP or the evidence runtime. A finding is an *input* to
`EvidenceAdmissionPort` and a citation for TAP; the package calls neither.

## 4 — Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| AE-1 | The noun and package name, avoiding "adversarial" | **`packages/integration/agent-assurance-evidence`**, distribution `ugence-agent-assurance-evidence`, namespace `ugence_agent_assurance_evidence`. It records assurance evidence; it is neither a probe runner nor an authority. |
| AE-2 | Is a finding a new record type, or an `EvidenceReference` with provenance? | **`NEW_RECORD_TYPE`.** `AssuranceFindingDeclaration` binds exactly one canonical `AssessedSystemBinding` to exactly one existing `EvidenceReference`. The evidence reference remains the finding's sole evidence identity; no competing reference is minted and no provenance field is copied. |
| AE-3 | Does a finding carry an uninterpreted label, or reuse `VerificationStatus`? | **`UNINTERPRETED_LABEL`.** `AssuranceFindingLabel`: an immutable, non-empty opaque label with no taxonomy, severity, score, ordering or implied verification. `VerificationStatus` remains an independent statement about whether a claim was checked and must not represent what the exercise found. |
| AE-4 | How does a finding reach Risk Authority without the package importing it? | **`BOTH`.** TAP may cite the declaration's existing `EvidenceReference`; separately, a composition root may construct Risk Authority's `ControlEvidenceRecord` from the declaration and submit it through `EvidenceAdmissionPort`. Both routes preserve the same evidence identity. A TAP citation is not Risk Authority admission, and neither route upgrades the other. |
| AE-5 | Does any neutral type land in governance-contracts first? | **Yes — `AssuranceFindingLabel`.** Landed first in `packages/governance-contracts` as a neutral structural contract. It grants no authority and performs no verification or risk interpretation. |

## 5 — Maturity ceiling, stated once

**`REFERENCE_GRADE_CONTRACT_ONLY`.** The package records what a declarer asserted
an exercise found. Nothing here runs a probe, holds a corpus, scores a finding,
admits evidence, evaluates a control, or proves that the referenced evidence exists,
that the exercise was sound, or that the named system was the one exercised.
Neither consumer route is built in this slice: no composition root constructs a
`ControlEvidenceRecord`, and no TAP request is issued. `ENFORCEMENT_ENABLED` is
`False` and stays so until a further ruling authorizes a route. A finding is a
record, not a verdict.

## 6 — Next step

Implement `packages/integration/agent-assurance-evidence` 0.1.0 under the decisions
above, after `AssuranceFindingLabel` lands in governance-contracts.

# Ugence agent security and assurance evidence — scoping record

**Status: SCOPED, NOT RULED — nothing here is implemented.** This record authorizes
no code change, creates no package, adds no dependency and amends no package ADR,
port, test or manifest. Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(wave 4, line 63: "evidence provider to TAP and Risk Authority; never a decision
authority"). It maps how evidence already reaches the two consumers, what the
neutral evidence contracts already carry, and the five owner decisions to rule
before any code.

Evidence labels: `[V]` verified against this repository at commit `ba9a2941`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Which package records *what a security or robustness exercise found about this
exact AI system*, in a form TAP and Risk Authority can consume as evidence, without
itself deciding anything? **Nothing does, and no package reserves the noun.** The
one word the row uses, "adversarial", is already taken in a different sense.

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

The sequencing ADR's prohibition (line 85) is satisfied only if the package is
**not** named "adversarial": that word names every package's own probe suite.

## 3 — A first slice, by analogy `[I]`

Following `vendor-dependency`: an `AssuranceFindingDeclaration` binding one
`AssessedSystemBinding` re-exported from governance-contracts, one
`EvidenceReference` re-exported the same way (so the finding *is* evidence, with an
`evidence_kind` the declarer chose), an opaque `exercise_ref` naming the exercise
that produced it, a `Validity` window and an optional `supersedes`. Refusal reasons
for a blank reference, a look-alike binding or reference, a subject that disagrees
with the binding, and a mismatched tenant. Pure selectors, in-force first. One
read-only Protocol, no implementation.

**Structurally unable:** no probe runner, no attack corpus, no scorer, no admission
engine, no control evaluation, no clock; and no import of Risk Authority, TAP, or
the evidence runtime. The finding is an *input* to `EvidenceAdmissionPort`; the
package never calls it.

## 4 — Decisions to rule `[R]`

| # | Decision | What turns on it |
|---|---|---|
| **AE-1** | The noun and package name, avoiding "adversarial". | "assurance-finding" or "agent-assurance-evidence" name what is recorded; "adversarial" and "red-team" name how it was produced, and the first already means a probe suite here. |
| **AE-2** | Is a finding a new record type, or an `EvidenceReference` with provenance? | Reuse means TAP and the evidence runtime consume it with no new adapter; a new type needs a mapping before either can see it. |
| **AE-3** | Does a finding carry an uninterpreted label, or reuse `VerificationStatus`? | An uninterpreted label follows DE-3 and VR-3; `VerificationStatus` is already neutral but says whether a claim was checked, not what was found. |
| **AE-4** | How does a finding reach Risk Authority without the package importing it? | As a `ControlEvidenceRecord` built by a composition root from the finding, through `EvidenceAdmissionPort`; or as an `EvidenceReference` TAP cites. Either keeps admission on Risk Authority's side. |
| **AE-5** | Does any neutral type land in governance-contracts first? | No new type if AE-2 reuses `EvidenceReference`; a neutral `AssuranceFindingLabel` if AE-3 chooses a label, following DE-5 and VR-5. |

## 5 — Next step

Rule AE-1 to AE-5. Nothing is implemented by this record.

# Cloud Scaling Phase 5B-2 — the trusted instant, ratified

**Status:** ratified 2026-09-04 by the repository owner. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1, cloud-scaling
ladder). Amends no package ADR, port, digest, partition or test; the only
repository changes it authorizes are the three documentation corrections it
names. Read-only for package code.

## The question

Is there a Phase 5B-2 "trusted time source" left to build? **No.** 5B-2 ran in two
parts and closed the residual it was named for, and the trusted clock already
exists as a ratified injection in Risk Authority. What remains is Risk Authority
Phase 5 signed envelope issuance, which is where the instant gets bound.

## What the record establishes `[V]`

| Finding | Where |
|---|---|
| 5B-2 part 1 closed R-9 and R-11; part 2 closed R-2 and R-7 | `ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`, "Phase 5B-2 part 1", "part 2" |
| R-2 "was a different defect than its name": the instant was already type-checked, round-tripped, and unable to resurrect a revoked or out-of-window policy; what was open was that no gate compared it to the candidate's six carried timestamps. Gate 13 closed that under four typed refusals, later re-sourced from the digest-bound decision snapshot (R-12b) | same, "R-2 was a different defect than its name" |
| Risk Authority owns the trusted clock: the application takes a clock callable from the composition root; the production evaluation seam refuses a caller-supplied instant with `CALLER_SUPPLIED_EVALUATION_TIME` and stamps the refusal with the trusted clock | `packages/risk_authority/README.md`, "Evaluation-time authority"; `api/dependencies.py` |
| Phase 4C's contract: risk evaluation happens once, in Risk Authority, "under its own trusted clock" | `ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md` §2 |
| Platform precedent for an authoritative clock: one injected clock, zero skew, no future dating, caller-supplied instants only on historical inspection paths | Benchmark Registry ruling D-11, `ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md` |
| Every leaf on the path reads no clock and proves it over the AST: policy authenticity, producer attestation, authorization contracts, Policy Authority, Trusted Evidence Authority, execution reservation | each package's no-clock test |
| Envelope issuance reads the Risk Authority clock once and then refuses in production mode with `ProductionContainmentError`; the envelope already carries `issued_at`, `not_before`, `expires_at` | `api/dependencies.py:719`, `domain` envelope dataclass |

## What was stale `[G]`, corrected under decision D-5

The policy-authenticity README section "the open residual you must read before
deploying", the `resolved_as_of_fact` comments in `verified.py` and the "No
clock" docstring in `verification.py`, and Appendix B row 30 of
`docs/UGENCE_ENTERPRISE_AI_GOVERNANCE_CAPABILITY_PIPELINE.md` all still said R-2
was open pending a trusted time source. Committed ADRs outrank explanatory
documents, and the code comments sat beside a partition whose membership is
correct: the fact stays recorded because it is still caller-injected, only now
bounded. Test docstrings that narrate R-2's history are left as history.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Scope of 5B-2 | **The standalone "trusted time source" reading is retired.** The trusted clock is Risk Authority's composition-root-injected clock. 5B-2's remaining "envelope-issuance work" is Risk Authority Phase 5 signed envelope issuance, scoped separately. No new package, port or clock service is created for time. |
| D-2 | `resolved_as_of_fact` | **Stays in the recorded half.** The 5B-0B artifact records the instant it was handed; no leaf can attest an instant, so promotion would move the frozen digest and the profile version under the D-5B1-3 ratchet for a fact that would still be caller-injected. The envelope binds the instant by issuer signature instead. |
| D-3 | Clock rules for envelopes | **D-11's rules apply**: one injected authoritative clock, zero skew tolerance, no future-dated issuance, and envelope issuance takes no caller-supplied instant. The reference seam remains the only place an explicit instant may be injected, exactly as the Risk Authority README already states. |
| D-4 | Issuance cross-check | **Envelope `issued_at` must equal the policy-authenticity artifact's `resolved_as_of_fact`.** Risk Authority Phase 5 issuance reads its clock once, passes that instant as `as_of` to the verifier, and refuses issuance with a typed refusal if the artifact's recorded instant differs. The single-read invariant becomes a Risk Authority test, mirroring Policy Authority's "read exactly once". |
| D-5 | Documentation | **Correct the three stale documents** to: R-2 closed as narrowed by gate 13; the instant stays recorded; binding is Phase 5 issuance. Applied in the same commit as this record. |

## What this does not decide

Risk Authority Phase 5 envelope issuance itself: envelope schema beyond the
existing fields, what an envelope binds beyond the candidate digest, signing key
custody, and ActionGate admission (5C). Those are the Phase 5 ADR §7 deferred
list and are scoped separately.

## Next step

Scope Risk Authority Phase 5 signed envelope issuance, read-only, against
`packages/risk_authority/src/risk_authority/api/dependencies.py` `issue_envelope`
and the Phase 5 ADR §7 deferred list.

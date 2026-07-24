# Falsification Plan (Phase 14)

*Preregistered before outcome-bearing review. Frozen by `EVALUATION_PROTOCOL.md` (Phase 15). Each null is
resolved only from **real** reviewer data; with no real reviewers every human-dependent null is
**NOT EVALUATED**, and the calibration/pilot decisions return NOT ENOUGH HUMAN EVIDENCE.*

## Endpoints

- **Human agreement:** acceptable-obligation, exact, risk, source-authority, clean-allow,
  evidence-satisfaction, qualification, review-required, native-ActionGate agreement.
- **Safety:** unsafe-allow disagreement, high-risk unsafe-allow disagreement.
- **Operational:** review time (p50/p90), override rate + direction, adjudication/unresolved rate,
  explanation usefulness, artifacts/hour.

## Preregistered nulls

| Null | Statement | Experiment | Rejection threshold | Consequence |
|---|---|---|---|---|
| H0-1 | Real reviewers cannot agree on evidence obligations | acceptable-obligation agreement | ≥ 0.70 | reject → agreement adequate |
| H0-2 | Agreement is no better than the prior simulated 0.50 | vs prior proxy | > 0.50 by a margin | reject → real > proxy |
| H0-3 | Reviewers frequently identify unsafe system allows | unsafe-allow disagreement | < 2% | reject → few unsafe allows |
| H0-4 | High-risk agreement is inadequate | high-risk obligation agreement | ≥ 0.80 | retain → high-risk gate |
| H0-5 | Source authority cannot be assessed reliably | source-authority agreement | ≥ 0.70 | retain → fix authority metadata |
| H0-6 | Explanations do not improve agreement | post-reveal vs blinded agreement | post-reveal higher | reject → explanations help |
| H0-7 | Explanations do not reduce review time | time with vs without trace | trace faster | reject → explanations help |
| H0-8 | Most overrides move stricter | override direction | stricter < 0.40 | retain → policy too permissive |
| H0-9 | 50% clean allow is not operationally useful | reviewer-accepted clean allows | material workload reduction | reject → useful |
| H0-10 | Review burden is excessive | artifacts/hour, review-required rate | within frozen limits | retain → burden excessive |
| H0-11 | The six-level vocabulary is still too complex | reviewer confusion / guide-ambiguity rate | low | retain → simplify vocabulary |
| H0-12 | The policy requires frequent exceptions | exception rate | low | retain → policy brittle |
| H0-13 | The internal pilot remains too conservative | clean-allow acceptance | useful | retain → too conservative |
| H0-14 | The policy is not ready for external shadow use | full safety+agreement gate | all pass | **retain** unless fully cleared |
| H0-15 | Only low-risk external pilot use is justified | risk-stratified readiness | high-risk cleared | context |
| H0-16 | Another internal calibration round is required | residual disagreement | low | context |

## Resolution in this environment

Every null above depends on **real reviewer data**, which does not exist here. Therefore:

- **H0-1..H0-13, H0-15, H0-16: NOT EVALUATED.**
- **H0-14 (not ready for external shadow use): RETAINED** — external readiness requires human validation,
  which is absent, so the policy is not cleared for external use.

## Freeze rule

Nulls, endpoints, and thresholds are frozen before outcome-bearing review and not altered after it
begins. Because no outcome-bearing review runs (no reviewers), the honest terminus is **NOT ENOUGH HUMAN
EVIDENCE** — the plan is complete and ready, the evidence is absent, and none is fabricated.

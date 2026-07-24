# Falsification Plan (Phase 5)

*Preregistered before final outcome-bearing evaluation. Each null is a claim the study tries to support;
the frozen final evaluation (Phase 23) rejects or retains it. A retained null is an honest negative
result, not a failure of the study. This plan is frozen by `EVALUATION_PROTOCOL.md` (Phase 22).*

## Endpoints (shared)

- **Safety (co-primary):** unsafe assertion allow, unsafe action allow, high-risk unsafe allow.
- **Utility (co-primary):** clean allow, over-qualification, false withholding, unnecessary escalation.
- **Secondary:** obligation accuracy, source-role accuracy, authority accuracy, reviewer agreement,
  unresolved rate, human-review rate, latency, metadata burden.

## Preregistered null hypotheses

| Null | Statement | Experiment | Primary endpoint | Rejection threshold | Kill / consequence |
|---|---|---|---|---|---|
| **H0-1** | Uniform evidence requirements perform as well as contextual obligations | baseline A/B vs Q on held-out | clean allow @ equal safety | contextual ≥ +20pp clean allow, no safety loss | reject → contextual justified |
| **H0-2** | Risk tier alone performs as well as full policy | baseline C vs Q | clean allow & unsafe | Q beats C by ≥10pp clean allow at ≤ C unsafe | retain → collapse to risk-tier (decision 4) |
| **H0-3** | Claim type alone performs as well | baseline E vs Q | clean allow & unsafe | Q beats E by ≥10pp or lower unsafe | retain → reduce to claim-type policy |
| **H0-4** | Source role adds no value | ablate source role (Phase 18) | clean allow & unsafe | ablation loses ≥5pp or gains unsafe | reject → source role load-bearing |
| **H0-5** | Artifact authority cannot be classified reliably | authority accuracy vs gold | authority accuracy | accuracy ≥ 0.80 | retain → authority unreliable (fix first) |
| **H0-6** | Implementation evidence creates unsafe self-verification | contextual-authority + adversarial set | circular self-verification rate | self-verification = 0 on adversarial | retain → implementation evidence unsafe |
| **H0-7** | Internal authoritative artifacts are not reliable enough | internal-authoritative subgroup | clean allow & unsafe | clean allow ↑, unsafe = 0 | retain → internal authority insufficient |
| **H0-8** | A no-evidence-required class increases unsafe allows | NO_FACTUAL_EVIDENCE_GATE subgroup + adversarial | unsafe allow on disguised claims | 0 high-risk factual in no-gate | retain → no-gate unsafe (remove class) |
| **H0-9** | Contextual obligations do not materially improve clean allow | Q vs prior 0% | clean allow | clean allow ≥ +20pp over prior 0% | retain → utility not improved |
| **H0-10** | Contextual obligations do not reduce over-qualification | Q vs prior 85.5% | over-qualification | over-qual ≤ 65% (≥20pp drop) | retain → no over-qual reduction |
| **H0-11** | Contextual obligations weaken high-risk safety | high-risk subgroup Q vs baseline | high-risk unsafe allow | high-risk unsafe = 0 | retain → safety weakened (STOP) |
| **H0-12** | EvidenceAssurance already captures obligation differences implicitly | derivation-only vs obligation-fed EA | clean allow delta | obligation-fed ≥ +15pp | retain → EA already captures it |
| **H0-13** | Simple rule-based assignment performs as well as the richer component | Simple-4 (Phase 19) vs Q | clean allow & unsafe & accuracy | Q beats Simple-4 by ≥5pp or lower unsafe | retain → prefer simple comparator |
| **H0-14** | Human reviewers disagree too much on obligations | dual-rubric agreement (Phase 20) | obligation agreement | agreement ≥ 0.70 | retain → labels unstable |
| **H0-15** | The utility failure is caused by natural-artifact derivation, not obligation | derivation-only vs obligation policy holding derivation fixed | clean allow delta | obligation policy improves at fixed derivation | retain → derivation is the cause |
| **H0-16** | A global threshold change performs equally well | baseline K (global threshold reduction) vs Q | unsafe allow at matched clean allow | K raises unsafe at matched clean allow | reject → global change unsafe |
| **H0-17** | A distinct EvidenceObligation stage is unnecessary | merged-adapter vs distinct-stage | clean allow, unsafe, explainability | distinct stage strictly better/safer | retain → merge into EA adapter |
| **H0-18** | External customer shadow-pilot readiness remains blocked after calibration | post-calibration safety+utility gate | pilot readiness gate | all gates pass | retain → still blocked (pilot decision) |

## Decision links

- H0-2 / H0-3 / H0-13 / H0-17 retained → simplify or merge the component (architectural decision 3/4/5/6).
- H0-5 / H0-6 / H0-8 / H0-11 retained → a safety fix is required first (pilot decision D/E, or STOP).
- H0-9 / H0-10 retained → utility not improved (architectural decision 9/10; pilot decision G/H).
- H0-14 retained → obligation labels unstable (human-review fallback, decision 7).
- H0-1 / H0-4 / H0-12 / H0-16 rejected AND H0-9 / H0-10 rejected AND safety nulls retained-safe →
  contextual obligation justified (architectural decision 1/2).

## Freeze rule

These nulls, their thresholds, and their endpoints are frozen before the final evaluation begins
(Phase 22 `verify_evaluation_freeze.py`). No threshold is altered after the final evaluation starts.

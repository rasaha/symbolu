# Prior Results and Scope (Phase 1)

*Contextual Evidence Obligation and Utility Calibration Study. Begins from the completed **Bounded
Governed Inference Natural-Artifact Shadow Pilot**. Consumes all prior components **read-only**;
enforced by `evidence_obligation/verify_prior_artifacts.py` (32 guarded artifacts, fails on drift).*

## What this track must not touch

Read-only, never modified: EvidenceAssurance, AssertionGate, ActionGate, ClaimIntegrity, ScopeIntegrity,
ExecutionGate, ModelPolicy, `governed_inference_pilot`, `customer_shadow_readiness`,
`bounded_shadow_pilot`, prior corpora, prior ground truth, prior thresholds, prior frozen manifests, and
prior outcome-bearing artifacts. All new work lives under `evidence_obligation/` and
`docs/evidence_obligation/`. The 32-artifact guard is the mechanical proof of that boundary (the 22
pinned by the bounded_shadow_pilot guard + the 10 bounded_shadow_pilot outcome-bearing artifacts).

## Prior result recorded exactly (bounded_shadow_pilot, n = 857)

| Fact | Value |
|---|---|
| Natural artifacts evaluated | **857** (naturally occurring repository text, not built for governance) |
| Unsafe permits | **0** |
| Fail-closed / deterministic replay / native ActionGate | all held |
| Mandatory stop condition fired | **none** |
| Clean allow (`WOULD_ALLOW`) | **0.0%** |
| Over-qualification (`WOULD_QUALIFY` on benign) | **~85.5%** |
| Remainder | withheld or sent to review |
| Reviewer burden | 11.6% |
| Decision | Option 4 — do not proceed externally yet; gate on utility calibration |

**Evidence sensitivity result:** ordinary evidence derivation produced ~0% clean allow, while an
optimistic `VERIFIED` base restored ~83.3% clean allow — proving the runtime is **not generally broken**
and that the **evidence-obligation / evidence-derivation assumptions were too blunt for natural text.**

## Why this is a calibration study, not threshold-lowering

The prior pilot showed the utility failure is concentrated **upstream of final delivery**: natural
artifacts were assigned uniform evidence states (typically `VERIFIED_WITH_LIMITATIONS`), and
EvidenceAssurance and the downstream gates then behaved **conservatively and correctly** relative to
those inputs. The gates are not miscalibrated — the **evidence obligation applied to each claim is**.

This track therefore does **not** lower EvidenceAssurance thresholds or relax any gate. It asks a
different question: *when does a claim actually require external corroboration, internal authoritative
evidence, implementation evidence, policy evidence, logical verification, attribution verification, or
no factual evidence gate at all?* The objective is to assign each claim an **appropriate** evidence
obligation, increasing clean allow only where the lower obligation is genuinely justified — never by
weakening safety.

## Scope

- **Shadow-only, non-enforcing.** No enforcement, no external action, no live provider calls, no
  unrestricted network.
- **Read-only composition.** EvidenceObligation is a new stage *upstream* of Evidence binding; it never
  modifies or bypasses EvidenceAssurance or any gate.
- **Falsification-first.** 18 preregistered nulls (Phase 5); a NOT-ENOUGH-EVIDENCE or REJECT outcome is
  a legitimate success.
- **New data.** The prior final 857-artifact set is **not** reused for tuning; new development,
  held-out-natural, and adversarial partitions are built (Phase 6), with an honest NOT ENOUGH EVIDENCE
  return if natural supply is insufficient.

## Primary research question

> Can a contextual evidence-obligation policy materially improve natural-artifact utility (higher clean
> allow, lower over-qualification) **without weakening safety** (no increase in unsafe assertion or
> action permits, no high-risk safety degradation)?

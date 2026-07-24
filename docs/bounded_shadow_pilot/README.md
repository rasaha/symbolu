# Bounded Governed Inference Natural-Artifact Shadow Pilot — Completion Report

*A pilot-execution track. Begins where the completed **Customer Shadow Pilot Readiness** track ended and
asks one falsifiable question: does the governed inference runtime remain **safe, useful, auditable, and
understandable** on naturally occurring artifacts never designed for its structured corpora? Consumes
all completed components and `customer_shadow_readiness` **read-only**; rebuilds/modifies/re-evaluates
none of them. Shadow-only, non-enforcing, single-tenant, de-identified, fully audited, immediately
stoppable.*

## Answer

> On naturally occurring artifacts the governed runtime is **safe and auditable and preserves native
> ActionGate semantics with zero loss**, but — as configured for evidence-grounded structured inputs —
> it is **not yet useful** on evidence-free natural text, over-qualifying 85.5% of benign documentation.
> The effect is proven **evidence-driven, not a safety regression**. The pilot completed with **no stop
> condition triggered**. Decision: **do not proceed to an external single-customer shadow pilot yet —
> gate it on utility calibration** (Option 4 of 11).

## The mandatory task — native ActionGate semantics (Phase 5)

The readiness track's adapter collapsed the gate's six native outcomes into four (25% tracked loss).
This pilot's **native contract** (`actiongate_contract.py`) invokes the real frozen gate read-only and
preserves **all six** outcomes verbatim — `ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY`, `ESCALATE_TO_HUMAN`,
`REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY` — with constraints, approvals, evidence requirements,
simulation, retry, reason codes, policy references, and action/policy hashes. Conformance 6/6, native
semantic loss **0%**, no safety-relevant outcome collapsed, and 28 real derived actions decided natively
in execution. **No pilot blocker.**

## Findings by dimension

| Dimension | Verdict | Basis |
|---|---|---|
| **Safe** | **YES — transfers** | 0 fully-supported unsafe permits; all fail-closed; non-enforcing |
| **Useful** | **NO — does not transfer** | 0% clean allow; 85.5% over-qualified; 13.8% withheld |
| **Auditable** | **YES — transfers** | full-stack determinism + stable replay signatures; audit completeness 1.0 |
| **Understandable** | **PARTIAL** | reason codes + native outcome + provenance, but explanations are uniform/low-information |
| **Native ActionGate** | **PRESERVED** | 6/6 outcomes, 0% loss, no blocker |

The over-qualification is the pilot's central negative transfer result. Its cause is honest and
disclosed: an **evidence-grounded** runtime applied to **evidence-free** natural text (no gold evidence
bundles), conditioned on `natural_derivation_v1`. The adversarial derivation-sensitivity probe confirms
it — flipping the derived evidence base to optimistic `VERIFIED` restores an **83.3%** clean-allow rate,
proving the runtime is not broken.

## Pilot execution (single scored run, n = 857)

Prior-artifact guard (22) and eval freeze (7) verified before scoring. Full frozen set run once.
Final distribution `WOULD_QUALIFY` 735 / `EVIDENCE_UNAVAILABLE` 67 / `WOULD_ESCALATE` 27 /
`WOULD_CONSTRAIN_ACTION` 25 / `INDETERMINATE` 3 (**zero `WOULD_ALLOW`**). `unsafe_permit=0`, all
non-enforcing. All six stop conditions PASS → **`COMPLETED_NO_STOP`**. Governance sub-ms, ~$0; reviewer
burden 11.6%.

## Falsification

Six preregistered nulls, all rejected: safety, native-ActionGate-preservation, determinism, evidence-
sufficiency (857 ≥ 200), non-contamination stand; the utility-transfer null is rejected in the
**negative** direction (utility does not transfer). Stress-tested by the derivation-sensitivity probe.

## Decision (Phase 21 — 1 of 11)

**Option 4 — do not proceed to the external single-customer pilot yet; gate it on utility calibration.**
No safety blocker exists (options 5–11 excluded), but external exposure to a near-zero-clean-allow
runtime would be low value. Constructive next step: **Option 3**, an internal single-tenant natural
shadow pilot to calibrate the evidence stage for evidence-free text, then re-gate
(`SINGLE_CUSTOMER_PILOT_PLAN.md`).

## Milestones

| M | Deliverable | Phases | Commit |
|---|---|---|---|
| M1 | freeze + scope + exclusions + 22-artifact guard | 1 | `5714f6d` |
| M2 | natural-artifact intake protocol | 2 | `fb19719` |
| M3 | natural corpus (857, SUFFICIENT) | 3 | `7ec3e8a` |
| M4 | blinded ground truth | 4 | `b933926` |
| M5 | native ActionGate contract (MANDATORY) | 5 | `45ab457` |
| M6 | orchestrator wrapper + audit extension | 6–7 | `27c2e81` |
| M7 | review workflow + stop conditions + dry run | 8–10 | `20d6f68` |
| M8 | baselines A–O + metrics | 11–12 | `b35f87e` |
| M9 | natural failure taxonomy + transfer analysis | 13–14 | `a38eac9` |
| M10 | latency + cost + reviewer burden | 15–16 | `40fd87a` |
| M11 | falsification plan + eval freeze | 17–18 | `1572ef9` |
| M12 | pilot execution + evaluation report | 19–20 | `0bd6313` |
| M13 | decision + single-customer plan + this report | 21–22 | — |

## Final tallies

- **Files:** 19 Python modules under `bounded_shadow_pilot/`, 16 docs under `docs/bounded_shadow_pilot/`,
  8 eval artifacts + 1 frozen natural corpus + 1 ground-truth file.
- **Prior artifacts:** 22 guarded, byte-identical (17 research-track + 4 GIP frozen + 1 CSR study). No
  frozen logic or artifact modified. Prior suites unaffected (spot-checked green).
- **Tests:** 45 pilot tests passed; deterministic; non-enforcing.
- **ActionGate:** 6/6 native outcomes preserved, 0% loss, no blocker.
- **Safety:** 0 unsafe permits; all stop conditions pass; `COMPLETED_NO_STOP`.
- **Honesty:** over-qualification reported as the headline negative result and stress-tested; the
  derived-input limitation is disclosed and conditioned throughout.

## Reproduce

```bash
python -m bounded_shadow_pilot.verify_prior_artifacts     # 22 prior artifacts intact
python -m bounded_shadow_pilot.harvest                    # natural corpus (857)
python -m bounded_shadow_pilot.actiongate_contract        # 6/6 native outcomes, 0 loss
python -m bounded_shadow_pilot.baselines                  # A-O
python -m bounded_shadow_pilot.transfer_analysis          # transfer verdicts
python -m bounded_shadow_pilot.falsification              # 6/6 nulls rejected + probe
python -m bounded_shadow_pilot.eval_freeze                # freeze the evaluation
python -m bounded_shadow_pilot.pilot_execution            # single scored run
python -m bounded_shadow_pilot.architectural_decision     # 1 of 11
python -m pytest bounded_shadow_pilot/tests -q            # 45 passed
```

## Document index

`PILOT_SCOPE.md` · `PRIOR_ARTIFACTS_AND_SCOPE.md` · `PILOT_ASSUMPTIONS_AND_EXCLUSIONS.md` ·
`INTAKE_PROTOCOL.md` · `NATURAL_CORPUS.md` · `GROUND_TRUTH.md` · `NATIVE_ACTIONGATE_CONTRACT.md` ·
`ORCHESTRATOR_WRAPPER_AND_AUDIT.md` · `REVIEW_STOP_DRYRUN.md` · `BASELINES_AND_METRICS.md` ·
`FAILURE_TAXONOMY_AND_TRANSFER.md` · `LATENCY_COST_BURDEN.md` · `FALSIFICATION_AND_EVAL_FREEZE.md` ·
`EVALUATION_REPORT.md` · `ARCHITECTURAL_DECISION.md` · `SINGLE_CUSTOMER_PILOT_PLAN.md`.

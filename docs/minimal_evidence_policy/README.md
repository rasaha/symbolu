# Minimal Evidence Obligation Policy and Internal Utility Pilot — Completion Report

*A simplification-and-validation track. Begins from the completed Contextual Evidence Obligation study,
which showed the concept works but the rich 90-rule component does not earn its complexity. This track
builds the **minimal** policy the prior study recommended — small, explicit, monotonic, invariant-based —
validates it on new natural artifacts, and prepares an internal pilot. Consumes all prior components
**read-only**; shadow-only, non-enforcing, no external onboarding.*

## Answer

> A **minimal, monotonic, 12-rule** evidence-obligation policy restores natural-artifact utility (clean
> allow **0% → 50%**, over-qualification **85.5% → 0%**) while holding **0 unsafe high-risk allows, 0
> unsafe action allows, and 0 self-verification escapes** — **safer than both risk-only (52 unsafe) and
> the rich component (85 unsafe)**. It passes **10/10 frozen technical criteria**. Decision: **keep it as
> a distinct stage; proceed to an internal single-tenant pilot.** An external pilot stays **blocked**
> until **real human validation** (currently NOT EVALUATED) is done.

## The policy

Six ordered outcomes `E0 < E1 < E2 < E3 < E4 < ER`; a non-negotiable **risk floor** (low→E1 … critical→E4,
unknown→ER); **upward-only** modifiers (regulated→E4, measured/current→E3, internal/impl→E2, temporal/
action escalation); and **12 structural invariants** as hard rules (anti-self-verification, no circular
corroboration, internal≠authoritative, doc≠impl, fixture≠telemetry, impl≠operational, stale authority,
attribution≠truth, unknown→ER, action authority, no high-risk E0). Every decision is explainable in one
trace. The downstream contract preserves "standard met ≠ truth" and touches no frozen threshold.

## Findings

| Property | Result |
|---|---|
| Clean allow | 0% → **50%** |
| Over-qualification | 85.5% → **0%** |
| High-risk unsafe allows | **0** |
| Action unsafe allows | **0** |
| Self-verification escapes | **0 / 13** |
| Monotonicity violations | **0 / 528** |
| vs risk-only (52 unsafe) / rich (85 unsafe) | **safer (0)** |
| Complexity | 12 policy-logic rules (≤ 20), 6 outcomes, no learned model |
| Review burden | 9.6% |
| Native ActionGate vocabulary | preserved, 0% loss |
| Annotator agreement (6-level vs prior 14-type) | **0.640 vs 0.316** |

**Subgroups (conservative shape):** low-risk clean allow 0.875, medium 0.171, high **0.000**.

## Falsification (17 nulls: 12 rejected, 4 retained, 1 NOT EVALUATED)

Rejected: risk-only adequacy, claim-type utility, monotonicity safety, clean/over-qual improvement,
high-risk/action safety, review burden, minimal-vs-rich, global threshold, complexity budget, pilot
usefulness. Retained (honest): source-role no utility; **anti-self-verification 0 marginal on this data**
(the modifiers already catch the traps — retained as classification-independent insurance; a cleaner
adversarial isolation is future work); review-fallback no marginal; external readiness blocked. **NOT
EVALUATED:** real-reviewer agreement (no real reviewers).

## Decisions

- **Architectural (1 of 9): Option 1 — KEEP MINIMAL EVIDENCE POLICY AS A DISTINCT STAGE.** Claim-type is
  safety-critical, so risk-floor+anti-self-verification alone (Option 2) is insufficient; the distinct
  ~12-rule stage is the safe policy. Documented reduction: the minimum viable safe policy is
  risk+claim+temporal+action.
- **Pilot (A–I): B — PROCEED TO INTERNAL SINGLE-TENANT PILOT.** External is blocked until real human
  validation; the internal pilot is the vehicle to produce it.

## Milestones

| M | Deliverable | Phases | Commit |
|---|---|---|---|
| M1 | freeze + scope + simplification rationale | 1 | `b4e289b` |
| M2–M3 | schema + policy + precedence + invariants | 2–3 | `6f48eaa` |
| M4 | anti-self-verification study | 4 | `0b62785` |
| M5 | new dataset + ground-truth protocol | 5–6 | `d0da7ef` |
| M7 | minimal reference policy implementation | 8 | `1caad5b` |
| M8 | downstream frozen-component contract | 9 | `1e19fe7` |
| M6 | baselines A–O + metrics | 7 | `eb05091` |
| M9 | internal natural-artifact utility pilot | 10 | `0bd9170` |
| M10 | human-review protocol + reviewer guide | 12–13 | `23abdff` |
| M11 | error propagation + monotonicity | 14–15 | `40cbb0f` |
| M12 | safety-utility frontier | 16 | `cc9671f` |
| M13 | ablation + complexity challenge | 17–18 | `2e708f4` |
| M14 | falsification plan | 19 | `882e426` |
| M15 | consolidated test suite | 25 | `4a40c5f` |
| M16 | evaluation protocol freeze | 20 | `d2dd13e` |
| M17 | final evaluation | 21 | `acc742c` |
| M18 | falsification + architectural decision | 22–23 | `d155bcd` |
| M19 | internal pilot plan | 24 | `deca64b` |
| M20 | this completion report | — | — |

## Final tallies

- **Files:** 42 Python files under `minimal_evidence_policy/` (incl. `internal_pilot/` + tests), 19 docs,
  9 eval artifacts + 5 dataset files.
- **Prior artifacts verified unchanged:** 45 (32 evidence_obligation guard + 13 evidence_obligation
  outcome-bearing), byte-identical; no frozen logic touched.
- **Dataset:** 475 items — DEVELOPMENT 100, HELD_OUT_NATURAL 250, ADVERSARIAL_INVARIANTS 75,
  HUMAN_REVIEW_SET 50; 676 new natural available (SUFFICIENT). Vocabulary `minimal_evidence_policy_v1`; 6
  levels; 7 modifiers; 12 invariants; 16 baselines.
- **Tests:** 64 minimal_evidence_policy + 244 prior = **308 passed**; prior suites unchanged.
- **Clean allow 50% · over-qualification 0% · false-withholding 31.6% · unsafe assertion allow 0 · unsafe
  action allow 0 · high-risk unsafe 0 · self-verification escape 0 · circular-evidence escape 0.**
- **Review-required rate 9.6% · reviewer agreement (proxy) 0.50 · human validation NOT EVALUATED.**
- **Policy latency sub-ms · metadata burden: risk + claim-type load-bearing.**

## Unresolved blockers (before any external pilot)

1. **Real human validation** (currently NOT EVALUATED) — the internal pilot's primary purpose.
2. **Cleaner adversarial isolation** of the invariants' marginal safety (H0-4 could not be cleanly
   rejected).
3. Real evidence sources / real traffic (the clean-allow ceiling is conditioned on a modelled
   available-evidence set).

**Not production-ready.** Shadow-only, read-only, de-identified, single window, single internal tenant.

## Reproduce

```bash
python -m minimal_evidence_policy.verify_prior_artifacts    # 45 prior artifacts intact
python -m minimal_evidence_policy.dataset                   # 475-item dataset
python -m minimal_evidence_policy.self_verification         # 0 escapes
python -m minimal_evidence_policy.baselines                 # A-O
python -m minimal_evidence_policy.monotonicity              # 0 violations / 528
python -m minimal_evidence_policy.frontier                  # safety-utility frontier
python -m minimal_evidence_policy.ablation                  # minimum viable safe policy
python -m minimal_evidence_policy.internal_pilot.pilot      # internal pilot
python -m minimal_evidence_policy.verify_evaluation_freeze  # freeze the evaluation
python -m minimal_evidence_policy.final_evaluation          # 10/10 frozen criteria
python -m minimal_evidence_policy.architectural_decision    # 17 nulls + decision
python -m pytest minimal_evidence_policy/tests -q           # 64 passed
```

## Document index

`PRIOR_RESULTS_AND_SCOPE.md` · `SIMPLIFICATION_RATIONALE.md` · `MINIMAL_POLICY_SPEC.md` ·
`POLICY_PRECEDENCE.md` · `ANTI_SELF_VERIFICATION_PROTOCOL.md` · `GROUND_TRUTH_PROTOCOL.md` ·
`BASELINES.md` · `DOWNSTREAM_CONTRACT.md` · `HUMAN_REVIEW_PROTOCOL.md` · `REVIEWER_GUIDE.md` ·
`MONOTONICITY_REPORT.md` · `SAFETY_UTILITY_FRONTIER.md` · `ABLATION_AND_COMPLEXITY.md` ·
`FALSIFICATION_PLAN.md` · `EVALUATION_PROTOCOL.md` · `EVALUATION_REPORT.md` ·
`LIMITATIONS_AND_FALSIFICATION.md` · `ARCHITECTURAL_DECISION.md` · `INTERNAL_PILOT_PLAN.md`.

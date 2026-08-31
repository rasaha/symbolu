# Reviewer Qualification Protocol (Phase 7)

*How a candidate reviewer qualifies to join the pilot, using the training set (Phase 6) only. No real
reviewer has been qualified in this track — this is the protocol and the scorer that will run when real
candidates arrive. `qualification.py` **scores** responses a real person submits; it never invents them.*

## Purpose

Qualification checks that a candidate can apply the frozen minimal evidence-obligation policy's *reasoning
discipline* — not that they memorise answers. It gates who may submit final-set labels. It does **not**
change any policy rule, and it is never run on the final review set.

## What the candidate receives

- `REVIEWER_GUIDE.md`, `REVIEWER_QUICK_REFERENCE.md`, `COMMON_REVIEW_ERRORS.md`, `REVIEW_DECISION_TREE.md`.
- The training set `data/training_v1/training.json`: 16 natural artifacts + 8 trap types, each with the
  frozen policy's obligation label and a short explanation, so the candidate can study intended reasoning.

## The qualification quiz

Qualification reuses the trap families and a held-back handful of training-style items (the administrator
draws them from the *training* set — never the final set). For each item the candidate submits:

- `obligation` — one of `E0 E1 E2 E3 E4 ER`.
- `risk_floor` — the risk level they read (`low medium high critical unknown`).
- `trap_detected` — the safety trap they believe is present, or `none`.
- `action_requires_approval` — boolean, for action-bearing items.
- `reason` — free text (recorded, not auto-scored).

## Scoring criteria (all must pass)

A candidate qualifies only if every criterion below is met on the quiz. These test the habits the guide
teaches; they are deliberately conservative (safe errors are tolerated, unsafe errors are not).

1. **No high-risk downgrade.** The candidate never assigns `E0` to a high/critical-risk factual item, and
   never labels below the risk floor. A single unsafe downgrade fails qualification.
2. **Risk-floor agreement.** Reads the risk level correctly on ≥ 80% of items (off-by-one *upward* is
   tolerated as conservative; downward is not).
3. **Trap detection.** Correctly flags ≥ 7 of the 8 trap families (self-verification, circular evidence,
   stale authority, fixture-as-telemetry, impl-as-operational, action-without-approval,
   attribution-as-truth, high-risk-opinion). Missing a trap by staying *at or above* the trap's required
   level still counts as safe; assigning *below* it does not.
4. **Self-verification / circularity.** On self-verification and circular-evidence items the candidate
   assigns ≥ `E3`. No exceptions — these are the policy's defining invariants (INV-1, INV-2).
5. **Authority ≠ truth.** On attribution-as-truth items the candidate does not treat "X said it" as proof;
   obligation stays at the item's independent requirement.
6. **Action → approval.** On every action-bearing item, `action_requires_approval` is `true` and
   obligation is ≥ `E3`.
7. **ER on unknown.** On items with unknown risk/authority/type, the candidate chooses `ER` (not a guess).
8. **E2-vs-E3 discrimination.** Distinguishes implementation-supported behaviour claims (`E2`) from
   performance/telemetry claims (`E3`) on ≥ 70% of the relevant items.

## Outcome

`qualification.py` returns, per candidate: `qualified: bool`, the per-criterion pass/fail, and the raw
score breakdown. A candidate who fails may re-study and re-take with a fresh draw. Results are recorded
pseudonymously (Phase 3). **No candidate has taken this quiz in this track; the scorer has been exercised
only against constructed illustrative response sets that are explicitly flagged `is_mock=True` and are
excluded from any real result.**

## Honesty constraints (binding)

- The scorer **grades** submitted responses; it must never **generate** a reviewer's answers.
- Qualification uses the training set only; the final review set is never shown before or during
  qualification and is never used to coach.
- Passing qualification is a statement about a candidate's *readiness to review*, not about the policy's
  correctness and not about human agreement with the policy. Human validation remains **NOT EVALUATED**.

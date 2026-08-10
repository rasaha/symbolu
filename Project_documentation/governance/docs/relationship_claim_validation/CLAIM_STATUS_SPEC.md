# Claim Status Spec (v0.1)

The six statuses, their actions, and the frozen decision function
(`validator.ClaimValidationLayer._status_from_verdicts`).

> Scope: synthetic, self-contained, deterministic.

---

## 1. Statuses → actions

| Status | Action | Effect on retained graph |
|---|---|---|
| SUPPORTED | retain | kept |
| PARTIALLY_SUPPORTED | narrow | kept (narrowed) |
| CONTRADICTED | remove | dropped |
| UNSUPPORTED | remove | dropped |
| INSUFFICIENT_EVIDENCE | abstain | dropped |
| UNKNOWN | manual_review | dropped (flagged) |

"Retained" = action ∈ {retain, narrow}.

## 2. Decision function (evaluated in order)

1. Any predicate resolved **UNKNOWN** (equally-explicit A/B conflict) → **UNKNOWN**.
2. Any predicate **contradicted** → **CONTRADICTED**.
3. Relationship affirmatively supported (wording ∧ direction ∧ provenance) →
   **SUPPORTED** if all narrowing predicates (scope, temporal, authority) hold,
   else **PARTIALLY_SUPPORTED**.
4. Entities established but the relation between them not asserted → **UNSUPPORTED**
   (evidence present but does not support the claim).
5. Evidence does not even establish the entities → **INSUFFICIENT_EVIDENCE**.

Deterministic terminal statuses (§`DETERMINISTIC_VALIDATION.md`) bypass this
function.

## 3. Measured status distribution per ablation (from the run)

| Status | Gold | V0 | V1 | V2 | V3 | V4 |
|---|--:|--:|--:|--:|--:|--:|
| SUPPORTED | 12 | 48 | 0 | 24 | 16 | 12 |
| PARTIALLY_SUPPORTED | 8 | 0 | 0 | 8 | 8 | 8 |
| CONTRADICTED | 8 | 0 | 0 | 0 | 8 | 8 |
| UNSUPPORTED | 8 | 0 | 2 | 8 | 8 | 8 |
| INSUFFICIENT_EVIDENCE | 8 | 0 | 46 | 8 | 8 | 8 |
| UNKNOWN | 4 | 0 | 0 | 0 | 0 | 4 |

V4 reproduces the gold status distribution exactly (status accuracy 1.0). This is
**by construction** — the deterministic judges implement the grounding logic the
gold encodes — and must be read as mechanism validation, not real-world accuracy
(`FINAL_VERDICT.md`).

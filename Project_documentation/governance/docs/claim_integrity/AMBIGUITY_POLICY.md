# Ambiguity Policy (Phase 20)

*`claim_integrity/ambiguity.py`. Real text often permits more than one valid decomposition. Forcing a
single "atomic" answer where the text is genuinely ambiguous manufactures false precision — and, on
scope-spanning conjunctions, actively causes drift. This policy defines when to commit, when to offer
alternates, and when to abstain.*

## The decisions

| Situation | Action | Disposition |
|---|---|---|
| Single clear decomposition | commit | `VALID` |
| Annotators accepted >1 granularity | emit both; don't force one | `VALID_WITH_ALTERNATIVES` |
| Borderline conjunction / dependency, off gold by one, not clearly wrong | flag, don't guess | `AMBIGUOUS` |
| Scope-bearing modifier spans a conjunction (splitting would detach it) | preserve whole + flag | `INDETERMINATE` / `ESCALATE` |
| No parseable claim | abstain | `INDETERMINATE` |
| High-risk + irreducible ambiguity | route to human | `ESCALATE` |

## Preserving ambiguity beats forcing precision — measured

The 78 ADVERSARIAL_SCOPE cases carry an exception that attaches to only the second clause
("… is approved, but not during pregnancy unless monitored"). There are two ways to handle them:

- **Force precision (split the conjunction):** detaches "unless monitored" from its clause →
  `SCOPE_ERROR` → the exception-free fragment is delivered as supported. `O_aggressive_split` does
  exactly this and reaches **0.568 unsafe delivery**.
- **Preserve + flag (keep the conjunction whole):** the exception stays attached; the unit is
  under-split but nothing is dropped. The component does this and reaches **0.068 unsafe delivery**.

**Preserving the ambiguous unit is ~8× safer than forcing a split** on these cases. The component's
78 "under-splits" (Phase 12/18) are therefore not simply errors — they are the ambiguity policy
choosing preservation over false precision. The residual cost is that those claims are governed as one
coarse unit rather than two, which the policy surfaces as `INDETERMINATE` (a flag for review), not as a
silent pass.

## Why not always preserve, then?

Because preserve-whole is unsafe for a *different* reason: on genuinely multi-claim text it leaves
claims ungoverned (`A_preserve_whole` → 0.454 unsafe delivery, Phase 18). The policy is therefore
**conditional**, not "always split" or "always preserve":

- split when both sides are independently evaluable **and** no scope-bearing modifier spans them;
- preserve + flag when a modifier spans the boundary;
- emit alternates when annotators legitimately disagreed on granularity;
- abstain when no reliable decomposition exists.

This conditional policy is what distinguishes the component from both extremes (aggressive splitting and
preserve-whole), each of which is unsafe in its own direction.

## Honest limit

The policy reduces unsafe delivery on the spanning-modifier cases by *withholding precision*, not by
*achieving* it. The oracle still does better (0.000) by correctly splitting into two units that each
retain the exception — a decomposition the deterministic component cannot reliably produce from surface
text. So the ambiguity policy is a safe fallback, not a solution: it converts a potential silent unsafe
delivery into a flagged coarse unit. Closing the gap to the oracle requires deeper structural parsing
than this study's deterministic component attempts, and is left to the follow-up.

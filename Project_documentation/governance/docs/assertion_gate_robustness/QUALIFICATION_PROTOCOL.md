# Qualification Protocol

*Phase 10. Qualification is evaluated **separately** from disposition. A QUALIFY disposition is only
useful if the rewrite preserves the supported claim, removes unsupported certainty, and adds no new
facts. Implemented in `assertion_gate_robustness/qualification.py`.*

## What a qualification must do

| Requirement | Rule / check |
|---|---|
| preserve the supported portion of the claim | `semantic_preservation` ≥ threshold (claim tokens retained) |
| remove unsupported certainty | `removes_unsupported_certainty` — a hedge is prepended |
| disclose uncertainty | hedge band reflects support level (strong/moderate/weak) |
| add no new facts | `new_claim_introduced` == 0 (no content tokens beyond claim + hedge vocab) |
| not reverse meaning | hedge weakens, never negates (no "not"/negation inserted) |
| not become vacuous | `usefulness` — qualified text still asserts the (scoped) claim |
| be risk-appropriate | weaker support ⇒ stronger hedge |

## Rule-based transform (thin, deterministic)

`qualify_text(claim, support)` prepends one of three hedges by support band:
- support ≥ 0.5 → "The available evidence indicates that …"
- 0.3 ≤ support < 0.5 → "Limited evidence suggests that …"
- support < 0.3 → "There is only weak, preliminary evidence that …"

and scopes with "(in the studied context)." It never inserts new entities or negations, so
`new_claim_introduced` is structurally 0 and meaning cannot reverse.

## Metrics (Phase 11)

- semantic_preservation (claim-token retention)
- unsupported-content removal (hedge added)
- new-claim-introduction rate (must be ~0)
- usefulness (not vacuous)
- qualification precision (of predicted QUALIFY, fraction gold QUALIFY)
- overqualification rate (gold ALLOW predicted QUALIFY)
- underqualification rate (gold QUALIFY predicted ALLOW — an escape)

## Robustness angle

Under noisy evidence, the *disposition* may be wrong (that is the disposition metric's job). The
*qualification transform itself* is evidence-content-agnostic (it hedges by support band and scopes
the existing claim), so it is structurally safe regardless of noise: it cannot invent facts or
reverse meaning even when the support scalar is corrupted. The risk under noise is therefore
**wrong disposition** (qualifying when should allow, or vice versa), not **unsafe qualification
text** — a distinction the evaluation keeps separate (Phase 18).

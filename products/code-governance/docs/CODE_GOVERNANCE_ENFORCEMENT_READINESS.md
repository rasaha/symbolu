# Enforcement Readiness

> A deterministic decision framework, NOT an automatic enforcement switch. No
> verdict enables execution. Machine-readable companion:
> `docs/pilot_readiness_verdicts.json`.

## Verdicts

- `SAFETY_OR_INTEGRITY_BLOCKED` — any credential leak, write-boundary violation,
  integrity failure, unresolved safety adverse case, or incomplete audit
  reconstruction. Dominates all other considerations.
- `INSUFFICIENT_LIVE_EVIDENCE` — no live evaluations, or reviewer-feedback coverage
  below the configured minimum.
- `PILOT_CALIBRATION_REQUIRED` — unresolved serious possible-false-CLEAR cases or
  recurring policy defects.
- `PRODUCT_VALUE_NOT_PROVEN` — no demonstrated incremental value beyond CI.
- `READY_FOR_ENFORCEMENT_DESIGN` — only when safety/integrity is clean, live
  evidence + coverage exist, no unresolved serious possible false CLEAR, remaining
  disagreements are understood and bounded, credible incremental value is
  demonstrated, and limitations are explicitly recorded.

There is no single numerical score, and every verdict carries evidence references,
reasons, and limitations. **No verdict enables execution** — a `READY_...` verdict
authorizes *design work*, not enforcement.

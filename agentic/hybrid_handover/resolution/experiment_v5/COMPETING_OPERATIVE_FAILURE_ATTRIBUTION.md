# COMPETING_OPERATIVE_FAILURE_ATTRIBUTION — Competing Operative Resolution Experiment v0.1

Residual C4 errors attributed to exactly one primary stage. The Competing Operative
layer is blamed only for errors it owns (conflict classification, conflict resolution,
governance abstention). It introduced **no** new incorrect answers (0 breaks), so its
own attribution count is 0.

## Table 16 — failure attribution (C4)

| primary stage | incorrect C4 cases |
|---|---|
| proposal generation (missing edge; frozen) | inherited from C0 |
| frozen governing set / operative selection (G3) | inherited from C0 |
| frozen packet realization | inherited from C0 |
| competing-operative resolution (this layer) | 0 |
| governance abstention (this layer) | 0 false abstentions |

All 35 residual incorrect cases are unchanged from C0 (they were already
incorrect under G3, owned by frozen proposal generation, the frozen governing set, or
the frozen packet). The Competing Operative layer neither fixed nor broke any of them,
because none contained a genuine unresolved conflict for it to act on.

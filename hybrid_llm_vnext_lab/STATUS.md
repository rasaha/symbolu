# Hybrid LLM vNext Lab — Status

**Phase:** bounded binding-slot incubation & reproduction.
**Created from:** live default branch `claude/setup-symbolu-monorepo-…` @ `8b4ec6e7` (post-merge of audit PR #1294).

## Bounded binding-slot maturity

```
SLOT_MATURITY = HISTORICAL_RESULT_ONLY  ->  (target this phase) REPRODUCED
```

Maturity vocabulary (in order): `HISTORICAL_RESULT_ONLY` → `REPRODUCED` →
`WORKING_BUT_UNSTABLE` → `MULTI_SEED_VALIDATED` → `RELATIONAL_MEMORY_VALIDATED` →
`READY_FOR_COMPOSITION` → `READY_FOR_PACKAGING_REVIEW`.

**Current state at the close of this PR:** the slot subsystem is isolated with full provenance,
its discrete mechanics are reproduced and probed **deterministically** by a stdlib reference,
and its no-N×N / bounded-state / no-Phase properties are enforced by runnable tests. The
**neural** reproduction of the phase_lc positive result (learned addressing under training) is
`RESOURCE_BLOCKED` in this environment (no PyTorch), so the overall corrected status is:

```
INTERNALLY_SUPPORTED_WORKING_CANDIDATE_AT_TESTED_SCALE
  discrete mechanics ........ REPRODUCED (stdlib, deterministic, runs in CI)
  neural training result ..... RESOURCE_BLOCKED (torch unavailable; exact command provided)
  multi-seed stability ....... NOT_YET_RUN (pre-registered; after parity)
  relational memory .......... NOT_YET_DEMONSTRATED
```

Do **not** describe slots as failed/decorative/unsupported, and do **not** describe them as
validated/production-ready/package-ready.

## Gate to leave the lab (move toward packages/)
All must be true (none are yet):
1. provenance + source hashes complete ✅ (this PR)
2. legacy positive result reproduced (neural) — ⛔ RESOURCE_BLOCKED here
3. isolated slot tests pass ✅ (stdlib; torch tests blocked)
4. no Phase dependency ✅ (boundary test)
5. no N×N sequence tensor in slot layers ✅ (declarative audit + reference by construction)
6. true incremental state demonstrated ✅ (reference) / ⛔ torch module (blocked)
7. multi-seed results meet the pre-registered threshold — ⛔ not yet
8. causal ablations attribute the gain to slots — historical evidence present; re-run ⛔
9. source/version/supersession meets its gate if claimed — reference ✅ / neural ⛔
10. KDA-MLA backbone passes its own experiment — ⛔ separate later phase
11. combined KDA-MLA-slots beats matched controls — ⛔ separate later phase
12. package API/dependency boundary review — ⛔ later

Until 1–12 hold, nothing is created under `packages/`, no wheel is built, and this is not a
distribution.

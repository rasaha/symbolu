# KVPro V3 Step-0 — Part E: FROZEN decision thresholds

These rules decide which kernel project (if any) the profile justifies. They are **frozen here, before any
GPU profile is viewed** — same pre-registration discipline as the quality gate. The decision matrix
(`05_decision_matrix.py`) uses exactly these constants; changing them after seeing results is disallowed.

## What the profile measures
`04_parse_profile.py` attributes decode-**kernel** time to stages: gather, staging, splice, dequant,
protect, attention, other. The two *removable* buckets are:
- **gather+staging** = `gather% + staging% + splice%` (host gather, temp-buffer write/reread, partial-tail splice — implementation artifacts).
- **protected** = `protect%` (scattered protected-channel reads — a layout artifact).
`attention%` and `dequant%` are treated as fixed (query-dependent / intrinsic to the int4 format).

## Frozen thresholds

| Constant | Value | Meaning | Rationale |
|---|---|---|---|
| `MIN_JUSTIFY_PCT` | **8%** | a removable bucket below this % of decode-kernel time cannot justify a kernel project on its own | see the end-to-end bound below |
| `COMBINED_SPREAD_PCT` | **8%** | if BOTH removable buckets exceed this, prefer a combined redesign | two independently-worthwhile targets → do them together, not serially |
| `REALIZABLE_FRACTION_CAP` | **0.5** | fraction of a removable slice a fused kernel can actually recover | the ~0.27–0.30× decode-recovery ceiling means fusion recovers *part* of a removable stage, never all of it; 0.5 is a deliberately generous upper cap |
| `Z_MIN_PROJECTED_END_TO_END_PCT` | **3%** | below this projected end-to-end gain, no kernel project is justified | a multi-week specialized-kernel effort needs ≥~3% end-to-end to be worth it against maintenance + risk |

## Why `MIN_JUSTIFY_PCT = 8%`
Projected end-to-end gain is **bounded below** the removable-% of decode-kernel time:

```
end_to_end_gain  ≈  removable%  ×  decode_kernel_share_of_step  ×  realizable_fraction
                 ≤  removable%  ×  1.0                          ×  REALIZABLE_FRACTION_CAP (0.5)
```

So a removable bucket at the 8% floor projects to **≤ 4%** end-to-end (upper bound; the true decode-kernel
share of a step is < 1, so the real number is smaller). That clears the **Z = 3%** end-to-end floor with a
small margin — i.e. 8% is the smallest decode-kernel-time slice that can plausibly return ≥3% end-to-end.
The matrix reports `projected_end_to_end_pct_upper` alongside every measured recommendation so the Z check
is visible, not implicit.

## Decision rule (as implemented, frozen)
1. **No measured profile** → `FIX_PREREQUISITES_FIRST` (nothing profilable) or `INCONCLUSIVE` (profilable, not run). Never a guess.
2. `max(gather+staging, protected) < MIN_JUSTIFY_PCT` → **`NO_KERNEL_PROJECT_JUSTIFIED`** (time dominated by attention proper).
3. Both removable buckets ≥ `COMBINED_SPREAD_PCT` → **`BUILD_COMBINED_KERNEL`**.
4. `protected ≥ gather+staging` (and ≥ floor) → **`BUILD_PROTECT_STREAM_FIRST`** (int8 iff P8prod quality PASS, else bf16 dense).
5. Otherwise → **`BUILD_GATHER_FIRST`** (in-kernel gather + store-as-consumed; route-A Triton is the starting point).

## Explicitly NOT inputs to the decision
- Prior expectation that "gather is ~25%" — **must be re-measured**; the profile overrides it.
- The modeled byte ceilings (`cost_accounting.py`) — those bound the *format-change* upside (xmin/prot-int8) and are reported for context, but the **kernel-project** decision is driven by measured decode-kernel-time shares, not modeled bytes.
- Diagnostic-only ablation timings (protection-disabled, artificially-contiguous) — used for cost *separation*, never as production-achievable numbers.

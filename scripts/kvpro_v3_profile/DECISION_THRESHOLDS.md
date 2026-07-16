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

---

# Part H — FROZEN thresholds for the two-half-kernel unzip-bound probe

`07_unzip_bound_probe.sh` (→ `unzip_bound_probe.py`) times three specialisations of the *same* INT4
unzip inner loop — **FETCH**-only (loads+unpack, no affine), **MATH**-only (affine+select on
register-resident operands, no per-token HBM), **FULL** (fetch+affine) — because `ncu` is blocked
(`ERR_NVGPUCTRPERM`) and cannot separate the two. `08_classify_unzip_bound.py` classifies from the three
times **f, m, F** at the decision context (the largest measured — least launch/timer noise). These
constants are **frozen here before any GPU number is viewed**.

| Constant | Value | Meaning | Rationale |
|---|---|---|---|
| `OVR` | **1.5** | one side must be ≥ 1.5× the other to "dominate" | below 1.5× the two costs are comparable → not a clean memory/compute call |
| `HIDE` | **1.25** | `F ≤ 1.25·max(f,m)` ⇒ the smaller op is **hidden** under the larger (overlapped) | 25% slack for launch/measurement noise; if the full time barely exceeds the larger half, the smaller half is latency-hidden |
| `ADD` | **0.75** | `F ≥ 0.75·(f+m)` ⇒ times roughly **add** (serial; neither hidden) | if the full time approaches the sum, fetch and math are both on the critical path |
| `SAT_HI` | **0.60** | achieved read BW ≥ 60% of peak HBM ⇒ **bandwidth-saturated** | ≥60% of peak is near the practical achievable ceiling for a streaming kernel → faster HBM is the only lever |
| `SAT_LO` | **0.40** | achieved read BW ≤ 40% of peak HBM ⇒ **under-utilised** | well below peak ⇒ scattered/uncoalesced access is wasting the bus → coalescing/compaction is the lever |

**Decision rule (frozen, `classify_times`):** HIDDEN is tested *before* SERIAL (when one half is tiny,
`F ≈ larger` **and** `F > ADD·(f+m)` hold at once because `f+m ≈ larger`; the hidden regime is the correct
memory/compute-bound signal, so it must win). Then:
1. `F ≤ HIDE·max(f,m)` → **hidden**: `MEMORY-BOUND` if `f ≥ OVR·m`, `COMPUTE-BOUND` if `m ≥ OVR·f`, else `BALANCED-OVERLAPPED`.
2. else `F ≥ ADD·(f+m)` → **serial**: `BOTH-TIGHTENABLE` (a software-pipelined fused read kernel can overlap them).
3. else → **partial**: `MEMORY/COMPUTE-BOUND` if one dominates, else `PARTIALLY-OVERLAPPED`.

**Roofline cross-check (secondary, needs peak assumptions — the three-times verdict does not):** achieved
read GB/s = `fetch_bytes / f`; util = achieved / peak HBM. A `MEMORY-BOUND` verdict that is **SATURATED**
(≥ `SAT_HI`) ⇒ the lever is faster HBM (H100/H200), **not** layout; **UNDER-UTILISED** (≤ `SAT_LO`) ⇒ the
lever is coalescing/compacting the streams (a 6F-style compact-protect read kernel) *before* buying hardware.

**Scope / honesty:** the probe measures only the **unzip** (unpack + dequant + protect-overlay). The
attention matmuls (`tl.dot`) are deliberately excluded — they run at bf16 speed regardless of the format,
so they are not the format's tax. `MATH` is an **upper bound** on the true dequant compute (it re-fabricates
a per-row perturbation the real kernel gets for free from its loads), so a `MEMORY-BOUND` verdict is robust
(math is, if anything, over-counted). The compact/production path is the primary verdict; the single
route-A full-fp16-K ablation (`FULL_full − FULL_compact`) quantifies the fp16-pool penalty a compact-protect
read kernel would remove. Correctness of the kernel's addressing + arithmetic is anchored on CPU by
`validate_kernel_interp.py` (Triton interpreter mode, exact match vs a numpy reference) — no GPU needed for
the correctness half; the pod supplies only timing.

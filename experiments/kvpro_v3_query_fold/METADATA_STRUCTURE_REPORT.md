# KVPro V3 — K Metadata Natural-Structure Report (pre-gate)

**Discovery + falsification study.** *Before* forcing the production K `scale` / `xmin`
into any rank model, ask the neutral question: **what structure do they actually have?**
low-rank · clustered · temporally stable · low-entropy · or effectively unstructured.
No end-to-end quality here; no kernel; no rank assumed in advance.

> **Status: TOOLING COMMITTED + CPU-verified on synthetic ground truth. No real capture
> yet → no verdict.** Fill this in from the pod run (`run_both_models_structure.sh`).

## Why a pre-gate

The full query-fold study (`decide.py`) assumes a rank factorization is the fold. This
gate tests that assumption *neutrally*: if the metadata's natural structure isn't a
**work-reducing, input-stable** one, the whole line closes cheaply — before attention
or quality. The load-bearing distinction is:

- **reduces per-element hot-path work** (rank / template folds the affine off the
  per-element path) — the only kind of structure query-folding can exploit; vs
- **byte-compression only** (piecewise / codebook / delta / sparse) — saves storage but
  still reconstructs per element. **Not sufficient** (hard constraint).

## Methods compared (Phase F — none privileged)

`compare_structure_methods.py` runs all ten and reports, per (layer,head), the median
**and worst** reconstruction error, worst block, metadata bytes saved, and — critically —
`reduces_per_element_work`:

| # | Method | reduces work? |
|---|---|---|
| 1 | rank-1 multiplicative (linear SVD) | ✅ |
| 2 | rank-1 log-additive (α_d·β_b) | ✅ |
| 3–4 | rank-2 / rank-4 SVD | ✅ |
| 5 | piecewise-constant block segmentation | ❌ (compress) |
| 6 | k-means / VQ of block vectors | ❌ |
| 7 | per-head template + block scalar | ✅ |
| 8 | per-layer template + block scalar | ✅ |
| 9 | per-channel baseline + sparse residual | ❌ |
| 10 | low-entropy codebook / delta-from-prev | ❌ |

## FROZEN stop rules (pre-registered, `decide_structure.py`)

CLOSE the query-fold line before quality if **any** holds on the observed data:
- no **work-reducing** method reconstructs within `rel_frob_worst ≤ 0.10` on **both** models;
- the best representation is **prompt-dependent** (not offline-calibratable — Phase E);
- worst-layer/head error exceeds the tolerance;
- the only accurate representation retains **nearly all** per-(block,channel) metadata
  (`metadata_bytes_saved_pct < 40`);
- modeled hot-path reduction `< 10%`.

Continue to the existing attention/quality gate **only** if a natural, work-reducing,
input-stable structure exists on **both** Qwen and Llama.

## Verdict (Phase G — one) / Recommendation (Phase H — one)

`STRUCTURE_LOW_RANK · STRUCTURE_CLUSTERED · STRUCTURE_TEMPORALLY_STABLE ·
STRUCTURE_LOW_ENTROPY · STRUCTURE_MIXED · STRUCTURE_WEAK · INCONCLUSIVE`
→ `ADVANCE_EXISTING_QUERY_FOLD · REVISE_QUERY_FOLD_CANDIDATES · ADVANCE_NON_RANK_STRUCTURE ·
CLOSE_QUERY_FOLD_NO_STRUCTURE · INCONCLUSIVE`

## Phase H recommendation table (FILL IN from the pod run)

| Natural structure | Evidence (rel_frob worst / bytes / calibratable) | Work reduction | Stability | Worst-case risk | Recommendation |
|---|---|---|---|---|---|
| _pending_ | | | | | |

Then answer: (1) what structure exists; (2) shared across Qwen & Llama?; (3) stable
enough for offline calibration?; (4) reduces real decode work or only storage?; (5) which
one representation, if any, enters the existing attention gate; (6) retain / revise /
abandon QF1–QF3.

## Commands (pod)

```bash
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
# One model (capture + all analyzers, scale & xmin):
./run_metadata_explore.sh --model Qwen/Qwen2.5-7B-Instruct --mask $PROTECT_MASK_PATH --tag qwen
# Both models + the natural-structure verdict:
./run_both_models_structure.sh --qwen-mask <qwen_mask.pt> --llama-mask <llama_mask.pt>
# -> out/structure_verdict.json ; commit with: git add -f experiments/kvpro_v3_query_fold/out
```

Runtime: the CPU analysis (all 5 analyzers × scale+xmin) is **~1–2 min per model** on the
full 28–32-layer capture, with a progress line every 200 (layer,head) pairs; the GPU
capture is a handful of short forward passes. (The analyzers were vectorized after a
pre-run audit found the naive per-channel loops took ~25 min — see git history.)

## CPU self-checks (no GPU)

```bash
python tests/test_explore_cpu.py            # entropy/temporal/clustering/variance detectors 10/10
python tests/test_decide_structure_cpu.py   # verdict precedence + stop rules 9/9
python compare_structure_methods.py --synthetic low_rank --kind scale   # rank wins
python analyze_variance_sources.py --synthetic stable --kind scale       # calibratable
```

## What is NOT done / NOT claimed
- No real capture → no entropy/temporal/clustering/variance/method numbers, **no verdict**.
- No attention, no quality, no kernel, no TPS.
- A byte-compression-only structure is recorded honestly and does **not** advance the fold.

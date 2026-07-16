# KVPro V3 — K Metadata Natural-Structure Report (pre-gate)

**Discovery + falsification study.** *Before* forcing the production K `scale` / `xmin`
into any rank model, ask the neutral question: **what structure do they actually have?**
low-rank · clustered · temporally stable · low-entropy · or effectively unstructured.
No end-to-end quality here; no kernel; no rank assumed in advance.

> **RESULT (measured, Qwen2.5-7B + Llama-3.1-8B, 8 captures each):
> `STRUCTURE_LOW_ENTROPY` → `CLOSE_QUERY_FOLD_NO_STRUCTURE`.** Query-folding is
> falsified on real data — on BOTH models, for scale AND xmin. No work-reducing
> (foldable) representation clears the frozen `rel_frob_worst ≤ 0.10` gate; only
> per-element byte-compression reconstructs accurately, which is not a hot-path win.
> Raw artifacts live in `out/` on the run pod (not committed — pod push failed); the
> decisive numbers are recorded below.

### Measured method comparison — worst-case rel-Frobenius (frozen gate ≤ 0.10)

| Representation | reduces work? | Qwen scale | Llama scale | Qwen xmin | Llama xmin |
|---|:--:|--:|--:|--:|--:|
| rank-1 `α_d·β_b` (QF1) | ✅ | 0.200 | 0.209 | 0.381 | 0.431 |
| rank-2 SVD (QF3) | ✅ | 0.159 | 0.174 | 0.336 | 0.386 |
| rank-4 SVD (4× fold, not clean) | ✅ | 0.140 | 0.149 | 0.274 | 0.324 |
| per-head template | ✅ | 0.208 | 0.219 | 0.378 | 0.436 |
| per-layer template | ✅ | 0.602 | 0.676 | **10.63** | 0.826 |
| codebook (compress) | ❌ | 0.096 | 0.122 | 0.262 | 0.199 |
| delta-from-prev (compress) | ❌ | 0.000 | 0.000 | 0.000 | 0.000 |

**No `reduces_work=True` method clears 0.10 worst-case on either model, for either
tensor.** The clean rank-1 fold is 20% worst on scale, 38–43% on xmin. Even rank-4
(no longer a single Q-transform) fails. The only accurate methods are `delta`/`piecewise`
— lossless per-element storage (≈18–22% byte saving), NOT a fold. Both models fail
identically → it is a property of the int4-protected format, not a model quirk.

### Answers (Phase H)
1. **What structure exists?** Scale has a strongly *shared per-channel profile*
   (cross-head cosine **0.95**, identity variance **79%**, `calibratable=True`) but a
   per-block×per-channel residual too rich for rank ≤ 4. xmin is weaker (cosine 0.47–0.54).
   Moderate entropy (8.4 / 9.66 bits); losslessly delta/piecewise-representable, not
   rank-foldable.
2. **Shared across Qwen & Llama?** Yes — near-identical failure.
3. **Stable enough for offline calibration?** Yes (cross-prompt corr 0.85–0.96) — but
   irrelevant, because it is not foldable.
4. **Reduces real decode work or only storage?** Only storage.
5. **Which representation enters the attention gate?** None — CLOSE before it.
6. **Retain / revise / abandon QF1–QF3?** **Abandon all three.**

Original template (kept for method reference):

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

# KVPro V3 Structural Gate — Query-Folded Affine K Metadata

**Falsification study.** Question: does KVPro's per-block, per-channel affine K
metadata (`scale`, `xmin`) have enough stable low-rank structure that most of it can
be moved to a **query-side transform**, leaving only a cheap per-block residual at
decode — *without* losing quality on **both** Qwen and Llama?

Do not assume it works. The structural gate (Phase C/D) comes first: if the real
`scale`/`xmin` tensors don't factor, we stop before any attention or quality run.
**No production kernel is implemented in this study.**

> **Run the neutral PRE-GATE first.** `METADATA_STRUCTURE_REPORT.md` +
> `run_both_models_structure.sh` ask *what structure the metadata naturally has*
> (low-rank / clustered / temporally-stable / low-entropy / unstructured) WITHOUT
> assuming rank — and CLOSE the whole line cheaply if the structure isn't a
> work-reducing, input-stable one. Only advance to the rank-based gate below
> (`run_all.sh`) if the pre-gate recommends `ADVANCE_EXISTING_QUERY_FOLD`. The pre-gate
> adds: `metadata_explore.py`, `analyze_{entropy,temporal_stability,clustering,
> variance_sources}.py`, `compare_structure_methods.py`, `decide_structure.py`.

---

## Phase A — production K format (verified in source, not from summaries)

From `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py`:

| Property | Value | Source |
|---|---|---|
| Quant equation | `code = round((x − xmin)/scale).clamp(0,15)`; `x̂ = code·scale + xmin` | `:18`, `:1109-1113` |
| Code range | unsigned 4-bit `[0,15]`, low nibble of the packed byte | `:18`, `fused_decode_write_k.cu` |
| Divisor | `_ASYM_DIV = 15.0` | `:35` |
| Scale | `((amax − amin)/15).clamp(1e-8)`, amax/amin over the block's tokens | `:1109-1111` |
| Scale granularity | **per-block, per-channel** → `k_scale_ext (NB, H, D)` bf16 | `:1304`, `:1124-1132` |
| xmin granularity | **per-block, per-channel** → `k_xmin_ext (NB, H, D)` bf16 | `:1304`, `:1131` |
| Block size | `BS = 32` tokens | writer geom |
| Head/layer geom | per KV-head `H`, per layer; `D = 128`; Qwen `H_kv=4`, Llama `H_kv=8` | writer asserts |
| Protected channels | `protect_slot (H,D) int8` (slot or −1) + `k_protect_ext (NB,BS,H,n_protect)` bf16, per-token dense; n_protect ≈ round(0.04·D) = 5 | `:1300`, `:784`, `:1081-1082` |
| Protected semantics | protected channels overlay the int4 dequant with their exact bf16 value at decode | `:1128-1132`, decode overlay |
| dtypes | codes uint8 (nibble); scale/xmin bf16; protected bf16 (int8 optional, 6N, default off) | `:1304`, `:730-746` |
| Partial blocks | metadata committed **only on block-fill** (`full_mask_ext`); an un-filled block stays in the bf16 stage pool and is re-quantized on read | `:1128-1132`, stage pool |

The faithful CPU replica is `quant_ref.production_k_metadata` (mirrors the writer and
`experiments/kvpro_v3_symmetric_residual/quantizers.affine_int4`, self-contained).

## The fold (why this could reduce decode work)

For query token with (post-RoPE) `Q`, block `b`, and `K̂[s,d] = q[s,d]·s[b,d] + xmin[b,d]`:

```
QK[s] = Σ_d Q_d·(q[s,d]·s[b,d] + xmin[b,d])
```

If `s[b,d] ≈ α_d·β_b` (rank-1 multiplicative) and we fold `Q'_d = Q_d·α_d` (once per
decode token):

```
QK[s] = β_b·(Σ_d Q'_d·q[s,d])  +  (Q·xmin_b)
        └ scale-FREE int·dot ┘    └ one dot/block ┘
```

So a **rank-1** scale folds as *one* Q-transform + *one* per-block scalar; a linear
**rank-2** folds as two; xmin factored as `u_d + v_b` folds the same way. **Honesty:**
a fit that still needs the full per-(b,d) residual is a *lossless rearrangement* — it
saves nothing and is scored `NO_GO_SYSTEMS_VALUE`, not a win.

## Candidates (pre-registered, ≤4)

| id | K scale | K xmin | folds as |
|---|---|---|---|
| `affine` (QF4) | production | production | reference arm |
| `QF1` | `α_d·β_b` (rank-1) | production | 1 Q-transform + 1 scalar/block |
| `QF2` | `α_d·β_b` (rank-1) | `u_d + v_b` (additive) | fully-folded scale + xmin |
| `QF3` | rank-2 linear SVD | production | 2 Q-transforms + 2 scalars/block |

V is production affine and protected K channels are exact bf16 for **every** candidate —
the sole variable is the K scale/xmin representation.

## Pre-registered gates (frozen BEFORE viewing any real capture)

These do **not** reuse the earlier study's discredited *absolute* offline thresholds.

**Structural gate** (per candidate's decomposition, on the required metadata, both models):
- `rel_frob_worst ≤ 0.10` (worst layer/head reconstruction error of the factored grid)
- `var_explained_median ≥ 0.95`
- `max_rel_channel_bias_worst ≤ 0.05` (no channel systematically mis-reconstructed)

**Attention gate** (baseline-RELATIVE to the current-affine arm, both models):
- `attn_out_cos(QF) ≥ attn_out_cos(affine) − 0.005`
- `softmax_kl(QF) ≤ 1.5 × softmax_kl(affine)`
- `topk_overlap(QF) ≥ topk_overlap(affine) − 0.02`

**Systems-value gate** (MODELED bytes/ops, never measured TPS):
- `metadata_bytes_saved_pct ≥ 25` (per-block scale+xmin)
- per-element affine scale-mul removed (rank-1/low-rank)
- replacement cost is O(D) once/token + O(1..R)/block, not per-element (does not cancel)
- `modeled_kpath_reduction_pct ≥ 12` (of the K reconstruct/dequant sub-path — MODELED)

**Quality gate** (Phase H, only for candidates that pass C–G, both models): standard
needle, hard-needle, 2000-Q MMLU, token-agreement — must hold vs current affine KVPro
on **both** Qwen and Llama. No threshold is weakened after seeing results.

## Verdicts (Phase I — exactly one)

`GO_QUERY_FOLD_KERNEL_PROTOTYPE` (authorizes a *prototype kernel only*, not a
throughput claim) · `GO_WITH_MODIFICATION` · `NO_GO_STRUCTURE` ·
`NO_GO_ATTENTION_ERROR` · `NO_GO_QUALITY` · `NO_GO_SYSTEMS_VALUE` · `INCONCLUSIVE`

## Files

```
factorize.py          rank-1-mult / additive / low-rank SVD + channel-bias (pure math)
quant_ref.py          production-faithful K affine quant (self-contained)
candidates.py         QF1–QF3 + affine reconstruction (K-only; V & protected fixed)
structure.py          Phase C/D shared audit
analyze_scale_structure.py / analyze_xmin_structure.py   Phase C / D CLIs
accounting.py         systems-value model (bytes/ops, MODELED)
evaluate_attention.py Phase F attention-level evaluator
capture_metadata.py   Phase B real-tensor capture (pod)
run_quality.py        Phase H fake-quant quality (reuses the symmetric-residual drivers)
decide.py             Phase G/I gates + verdict
synthetic.py          CPU ground-truth generators (factorable / random / capture)
run_capture.sh run_structure.sh run_quality.sh run_all.sh   RunPod drivers
tests/                CPU tests (no GPU)
```

## Commands

```bash
# CPU self-checks (no GPU):
python tests/test_query_fold_cpu.py
python tests/test_gates_cpu.py
python analyze_scale_structure.py --synthetic factorable      # detector sanity

# On the pod — structure only (the gate; cheapest, stop here if it fails):
./run_all.sh --model Qwen/Qwen2.5-7B-Instruct   --mask <qwen_mask.pt> --structure-only
./run_all.sh --model meta-llama/Llama-3.1-8B-Instruct --mask <llama_mask.pt> --structure-only

# Full (structure -> attention -> systems -> quality, only if gates pass), both models:
./run_all.sh --both-models --full
```

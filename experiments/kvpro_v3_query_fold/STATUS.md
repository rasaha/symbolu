# STATUS — KVPro V3 query-fold structural gate

> **FINAL (measured on Qwen2.5-7B + Llama-3.1-8B): NO-GO — query-fold CLOSED.**
> The neutral pre-gate ran on both models (8 captures each). Verdict
> `STRUCTURE_LOW_ENTROPY` → `CLOSE_QUERY_FOLD_NO_STRUCTURE`: no work-reducing
> (foldable) representation clears the frozen 0.10 worst-case gate on either model —
> rank-1 fold is 20% worst on scale, 38–43% on xmin; only per-element byte-compression
> reconstructs accurately (not a hot-path win). See METADATA_STRUCTURE_REPORT.md.
> The rank-based attention/quality gate below is now MOOT (do not run `run_all.sh`).
> Raw `out/` artifacts are on the run pod (pod push failed); numbers recorded in the report.

## Built + CPU-verified (no GPU)
- **Phase A** production K format verified in source → `README.md` (with `phase5b_4c_paged_writer.py` line refs).
- `factorize.py` — rank-1-multiplicative (log-additive), additive, low-rank SVD, channel-bias. Tested.
- `quant_ref.py` — production-faithful K affine quant + dequant. Tested (codes ∈ [0,15], round-trip).
- `candidates.py` — QF1/QF2/QF3 + affine reference; K-only, V & protected fixed. Tested (lossless equivalence on exactly-factorable metadata; protected-channel isolation).
- `structure.py` + `analyze_scale_structure.py` + `analyze_xmin_structure.py` — Phase C/D audit. Detector verified: factorable → rel_frob ~0 / var_exp 1.0; random → rejected.
- `synthetic.py` — factorable / random / full-capture CPU ground truth.
- Pre-registered gates frozen in `README.md` (structural / attention / systems / quality). **Not** the discredited absolute offline thresholds.

- `accounting.py` (systems value, MODELED), `attn_metrics.py`, `evaluate_attention.py` (Phase F), `decide.py` (Phase G/I verdict). Tested (`tests/test_gates_cpu.py` 11/11).
- Full pipeline plumbing verified on the synthetic manifest: capture → structure → attention → decide (correctly returns `NO_GO_STRUCTURE` on non-factorable synthetic data).

## Built, pod-pending execution (code done + CPU-verified where possible)
- `capture_metadata.py` — **pod** (loads Qwen/Llama, reuses the validated rotary-patch post-RoPE Q hook + FQ loader, derives production metadata via `quant_ref`). No external INT4 fork needed. `--synthetic` mode smoke-tested (no GPU).
- `run_quality.py` — **pod**; only runs for candidates that pass C–G. Monkey-patches `quantizers.reconstruct` to route QF candidates through the query-fold reconstruction, then reuses the frozen needle / hard-needle / 2000-Q MMLU drivers. Patch routing verified on CPU (folds K, protected exact, V=production, affine path intact).
- `run_all.sh` / `run_capture.sh` / `run_structure.sh` / `run_quality.sh` — RunPod drivers, `bash -n` clean.

## Exact commands (pod)
```bash
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
# Structure gate ONLY (cheapest; stop here if it fails) — one model:
./run_all.sh --model Qwen/Qwen2.5-7B-Instruct           --mask $PROTECT_MASK_PATH --structure-only
./run_all.sh --model meta-llama/Llama-3.1-8B-Instruct   --mask <llama_mask.pt>    --structure-only
# Full (structure -> attention -> systems -> quality for survivors), BOTH models:
./run_all.sh --both-models --full --qwen-mask <qwen_mask.pt> --llama-mask <llama_mask.pt>
# Verdict prints at the end and is written to out/verdict.json. Commit artifacts:
#   git add -f experiments/kvpro_v3_query_fold/out
```

## What is NOT done / NOT claimed
- No real capture → **no structural, attention, systems, or quality numbers**, and **no verdict**.
- No production/Triton kernel (out of scope by directive).
- No TPS/speedup claim. Systems value is MODELED bytes/ops only.

## Neutral metadata PRE-GATE (added; CPU-verified, pod-pending)
- `metadata_explore.py` (multi-prompt/seed, metadata-only), `analyze_entropy.py`,
  `analyze_temporal_stability.py`, `analyze_clustering.py`, `analyze_variance_sources.py`,
  `compare_structure_methods.py` (10 neutral methods, `reduces_per_element_work` flag),
  `decide_structure.py` (natural-structure verdict + frozen stop rules),
  `run_metadata_explore.sh`, `run_both_models_structure.sh`, `METADATA_STRUCTURE_REPORT.md`.
- Runs BEFORE the rank-based gate: asks what structure exists without assuming rank; CLOSEs
  cheaply if the structure isn't work-reducing + input-stable on both models.
- Discrimination verified on synthetic ground truth (low_rank/clustered/piecewise/random/
  stable). CPU tests: `test_explore_cpu.py` 10/10, `test_decide_structure_cpu.py` 9/9.
- Pod-pending: real capture → the natural-structure verdict (no verdict yet).

## Decision discipline (frozen)
Structure gate is the pre-filter; if scale (QF1/QF3) or xmin (QF2) fails the frozen
structural thresholds on **either** model, stop → `NO_GO_STRUCTURE` before attention/
quality. A lossless rearrangement that keeps the full per-(b,d) residual is **not** a
systems win. Both Qwen and Llama must pass every gate before a kernel prototype is
authorized.

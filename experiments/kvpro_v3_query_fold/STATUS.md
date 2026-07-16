# STATUS — KVPro V3 query-fold structural gate

> Honest running status. **No verdict yet — no real metadata has been captured.**
> The structural gate is the make-or-break and it needs the pod capture (Phase B).

## Built + CPU-verified (no GPU)
- **Phase A** production K format verified in source → `README.md` (with `phase5b_4c_paged_writer.py` line refs).
- `factorize.py` — rank-1-multiplicative (log-additive), additive, low-rank SVD, channel-bias. Tested.
- `quant_ref.py` — production-faithful K affine quant + dequant. Tested (codes ∈ [0,15], round-trip).
- `candidates.py` — QF1/QF2/QF3 + affine reference; K-only, V & protected fixed. Tested (lossless equivalence on exactly-factorable metadata; protected-channel isolation).
- `structure.py` + `analyze_scale_structure.py` + `analyze_xmin_structure.py` — Phase C/D audit. Detector verified: factorable → rel_frob ~0 / var_exp 1.0; random → rejected.
- `synthetic.py` — factorable / random / full-capture CPU ground truth.
- Pre-registered gates frozen in `README.md` (structural / attention / systems / quality). **Not** the discredited absolute offline thresholds.

## Pending
- `accounting.py`, `evaluate_attention.py`, `decide.py` — CPU-buildable; in progress.
- `capture_metadata.py` — **pod** (loads Qwen/Llama, hooks post-RoPE Q/K, derives production metadata). No external INT4 fork needed for the structural study.
- `run_quality.py` — **pod**; only runs for candidates that pass C–G. Reuses the symmetric-residual needle/hard-needle/MMLU/token-agreement drivers.
- RunPod shell drivers.

## What is NOT done / NOT claimed
- No real capture → **no structural, attention, systems, or quality numbers**, and **no verdict**.
- No production/Triton kernel (out of scope by directive).
- No TPS/speedup claim. Systems value is MODELED bytes/ops only.

## Decision discipline (frozen)
Structure gate is the pre-filter; if scale (QF1/QF3) or xmin (QF2) fails the frozen
structural thresholds on **either** model, stop → `NO_GO_STRUCTURE` before attention/
quality. A lossless rearrangement that keeps the full per-(b,d) residual is **not** a
systems win. Both Qwen and Llama must pass every gate before a kernel prototype is
authorized.

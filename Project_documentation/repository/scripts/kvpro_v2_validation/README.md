# KVPro v2 — RunPod validation harness

Copy-paste-runnable scripts to validate KVPro v2 on a GPU pod. They **orchestrate the existing
KVPro tooling**; they do not reimplement it. Honesty rules are enforced in the scripts themselves:

- A result is labeled **MEASURED** only when the script actually measured it on this run.
- A missing capability is labeled **INCOMPLETE / NOT-MEASURED** and the script prints the **exact
  integration point** — it never fabricates a number.
- Decode-throughput recovery has a **bounded ceiling (~0.27–0.30× of full precision, PROJECTED)** and
  **never reaches full-precision parity**. The scripts state this and never claim parity.
- The int4 flash-attn fork is gated **before** any decode test; if it is missing, decode tests refuse.

## Prerequisites (the pod)
- NVIDIA GPU; vLLM **0.7.3** (V0); torch matching the pod's CUDA driver (keep KVPro on its working
  torch/vLLM — do not upgrade it).
- The int4 `vllm-flash-attn` fork built so `from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache` works.
- A calibrated protect-mask at `$PROTECT_MASK_PATH` (see `01_calibrate_mask.sh`).
- Model weights cached (or HF reachable).

## Scripts
| Script | Purpose | Produces |
|---|---|---|
| `00_env_gate.sh` | Check nvidia-smi, CUDA/nvcc, torch-CUDA, vLLM 0.7.3 V0, the int4 fork import, `$PROTECT_MASK_PATH`. Exits non-zero on hard failure. | PASS/FAIL per check |
| `01_calibrate_mask.sh <MODEL> <OUT> [frac] [mml]` | Build a protect-mask via `calibrate_phase5b_protect_mask.py`; verify the file exists. | `<OUT>.pt` + how to export `$PROTECT_MASK_PATH` |
| `02_phase0_baseline.sh` | Reproduce baseline (Qwen2.5-7B first): quality (hard-needle), density (saturation→net), throughput (int4-vs-bf16 + sweep). | `runs/kvpro_v2/<ts>/SUMMARY_phase0.md` + logs/JSON |
| `03_phase6f_validate.sh` | Phase 6F read-fusion: CPU byte-eq (fused≡reference); GPU A/B **only if wired**, else INCOMPLETE + integration point. | `phase6f_summary.csv` |
| `04_warmtier_validate.sh` | Byte-clean gate; storage systems (bytes/token, reload p50/p95); serving TTFT/p99 **fails loud if the hook is incomplete**. | `SUMMARY_warmtier.md`, `warmtier_systems.json` |
| `05_tp_smoke.sh` | Multi-GPU only: TP=1 vs TP=2 correctness + sidecar-sharding signal. Skips if <2 GPUs. | `SUMMARY_tp.md`, `tp1.json`, `tp2.json` |
| `run_all.sh [--phase0-only\|--fusion-only\|--warmtier-only\|--tp-only]` | Drive the sequence; hard-stop on env gate failure. | one shared `runs/kvpro_v2/<ts>/` |

## Quick start
```bash
cd <repo-root>

# 1) calibrate a mask for the primary model and export it
bash scripts/kvpro_v2_validation/01_calibrate_mask.sh \
     Qwen/Qwen2.5-7B-Instruct /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt

# 2) gate the environment
bash scripts/kvpro_v2_validation/00_env_gate.sh

# 3) run everything (or a subset)
bash scripts/kvpro_v2_validation/run_all.sh
bash scripts/kvpro_v2_validation/run_all.sh --phase0-only
bash scripts/kvpro_v2_validation/run_all.sh --fusion-only     # CPU byte-eq runs even without a GPU
```
Artifacts land in `runs/kvpro_v2/<timestamp>/` (git-ignored). Read `SUMMARY_*.md` / `*_summary.csv`.

## What this harness can and cannot tell you today
- **MEASURES on a proper pod:** the Phase-0 quality/density/throughput baseline; the WarmTier
  byte-clean gate; WarmTier storage economics (bytes/token, encode/reload, p50/p95); Phase-6F CPU
  byte-equivalence (no GPU needed); a TP=1-vs-TP=2 smoke verdict.
- **Reports INCOMPLETE with the exact gap (no fake numbers):**
  - **Phase-6F GPU throughput A/B** — only meaningful once `fused_read_dequant_prep` is wired into
    `phase5b_backend_install._read_decode_packed_batched` and honors `PHASE6F_FUSED_READ`.
  - **WarmTier serving** (serve-over-restored-KV, cold-vs-reuse TTFT, p95/p99) — needs
    `tier5c_warmtier_serving.mark_prefix_computed` + `serve_with_warmtier_reuse` wired to the vLLM
    scheduler and the int4 decode kernel.
  - **Tensor parallelism** — `tensor_parallel_size` is not yet wired for int4_protected; `05` will
    surface a TP=2 failure as the honest, MEASURED negative (the sidecars/pools aren't sharded).

## Configuration (env vars)
`MODEL` (default `Qwen/Qwen2.5-7B-Instruct`), `PROTECT_MASK_PATH` (required), `QUALITY_MML` (8192),
`DENSITY_MML` (8192), `TPUT_MML` (4096), `TPUT_BATCHES` (`1,2,4,8`), and
`EXTRA_MODELS="id=/path/mask.pt,id2=/path/mask2.pt"` for additional models in `02`.

See `docs/KVPRO_V2_RUNPOD_PLAYBOOK.md` for the full step-by-step pod runbook.

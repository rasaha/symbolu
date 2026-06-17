# KVPro v2 — RunPod validation playbook

Step-by-step runbook for validating KVPro v2 on a GPU pod, using
`scripts/kvpro_v2_validation/`. This document is **operational only** — it states how to run and how
to read results. It does **not** describe the KVPro compression mechanism (proprietary/patent-pending).

**Honesty contract (enforced by the scripts):**
- A figure is **MEASURED** only if the run actually measured it. Missing capabilities are reported
  **INCOMPLETE** with the exact integration point — never a fabricated number.
- Decode-throughput recovery has a **bounded ceiling (~0.27–0.30× of full precision, PROJECTED)** and
  **does not reach full-precision parity**. Do not report parity.
- The int4 flash-attn fork is gated **before** any decode test.

---

## 0. Provision the pod
- A CUDA GPU (≥A100/H100-class for the larger models). For TP, ≥2 GPUs.
- Install/activate the **KVPro venv** with **vLLM 0.7.3 (V0)** and torch matched to the pod's CUDA
  driver. **Do not upgrade** torch/vLLM (a cu130-vs-driver-12.8 mismatch broke an isolated venv;
  keep KVPro on its working stack). Ensure `VLLM_USE_V1` is **not** set to `1`.
- Build the int4 `vllm-flash-attn` fork (the ~720c948 + int4 path) so this import works:
  ```bash
  python3 -c "from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache; print('int4 kernel OK')"
  ```
  If this fails, decode/serving will not work (only prefill) — build the fork first.
- Clone the repo and `cd` to its root. All commands below are run from the repo root.

---

## 1. Calibrate a protect-mask (per model)
`Int4ProtectedLLM` reads `$PROTECT_MASK_PATH`. Build one per model:
```bash
bash scripts/kvpro_v2_validation/01_calibrate_mask.sh \
     Qwen/Qwen2.5-7B-Instruct /workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
export PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
```
(Under the hood: `CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py --model <M> --output <P>
--protect-fraction 0.04`. For Mistral/Llama, calibrate a mask for each and point `PROTECT_MASK_PATH`
at the right one before running that model.)

---

## 2. Gate the environment
```bash
bash scripts/kvpro_v2_validation/00_env_gate.sh
```
Checks nvidia-smi, CUDA/nvcc, torch-CUDA, vLLM 0.7.3 V0, the int4 fork import, and
`$PROTECT_MASK_PATH`. **Fix every `[FAIL]` before proceeding.** If `PROTECT_MASK_PATH` is missing it
prints the exact `01_calibrate_mask.sh` command to create it.

---

## 3. Run the phases
All phases share one timestamped run dir `runs/kvpro_v2/<ts>/` (git-ignored). Use `run_all.sh`:
```bash
bash scripts/kvpro_v2_validation/run_all.sh                 # gate -> phase0 -> fusion -> warmtier -> tp
bash scripts/kvpro_v2_validation/run_all.sh --phase0-only
bash scripts/kvpro_v2_validation/run_all.sh --fusion-only   # CPU byte-eq runs even without a GPU
bash scripts/kvpro_v2_validation/run_all.sh --warmtier-only
bash scripts/kvpro_v2_validation/run_all.sh --tp-only       # needs >= 2 GPUs
```
`run_all.sh` hard-stops on an environment-gate failure (except `--fusion-only`, whose CPU byte-eq is
GPU-independent and whose GPU A/B self-gates).

### Phase 0 — baseline (`02_phase0_baseline.sh`)
Reproduces, smallest first (Qwen2.5-7B):
- **quality** — hard-needle int4_protected vs bf16 (`phase6k12_hard_needle.py`). Reports
  `strict_accuracy` per cell. **Qwen2.5-7B is AT-THE-MARGIN under the 4% mask — report the exact
  figure (e.g. one seed 13/15), do not round to "parity".**
- **density** — saturation sweep (`phase6k14_saturation.py` → `phase6l_capacity_demo.py`): expect the
  ~2.0× raw / ~1.8× net class with a flat sidecar tax; confirm in the log.
- **throughput** — int4-vs-bf16 ratio (`bench_phase6_b4_throughput_gpu.py --cells eager,bf16`) plus an
  int4 batched sweep. Expect the **0.13–0.67×** class (below full precision). All MEASURED this run.

Add models: `EXTRA_MODELS="mistralai/Mistral-7B-v0.3=/path/mistral_mask.pt,..." bash ... 02_phase0_baseline.sh`.

### Phase 6F — read-fusion (`03_phase6f_validate.sh`)
- **CPU byte-equivalence** (`fused == reference`) runs always — MEASURED, no GPU needed.
- **GPU A/B throughput** runs **only if** the fusion is wired into the decode path. Until then the
  script prints **INCOMPLETE** with the exact integration point:
  > Wire `kv_policy.phase6f_read_fusion.fused_read_dequant_prep` into
  > `phase5b_backend_install._read_decode_packed_batched` (B=1: `_read_decode_packed_one`),
  > honoring `PHASE6F_FUSED_READ` (0=reference, 1=fused). The CPU test already pins fused≡reference.
- Output: `phase6f_summary.csv`. **Recovery ceiling stays ~0.27–0.30×; parity is never claimed.**

### WarmTier — (`04_warmtier_validate.sh`)
- **Byte-clean gate** (`verify_kvpro_snapshot_roundtrip.py`) — must PASS (MEASURED) before trusting reuse.
- **Storage systems** (`measure_kvpro_warmtier_snapshot.py`) — MEASURED bytes/token, encode/reload
  throughput, reload p50/p95.
- **Serving** (serve-over-restored-KV, cold-vs-reuse TTFT, p95/p99 under concurrency) — these need the
  serving hook. While it is incomplete the script **fails loudly** and prints the exact point:
  > Wire `tier5c_warmtier_serving.mark_prefix_computed` (scheduler "already-computed" signal via
  > `SequenceData.update_num_computed_tokens`) and `serve_with_warmtier_reuse`
  > (`plan_reuse → restore_prefix_into_blocks → mark_prefix_computed → generate` over the int4
  > decode kernel). It does **not** print TTFT/p99 numbers until this exists.

### TP smoke — (`05_tp_smoke.sh`)
- Skips clearly if `< 2` GPUs.
- Builds int4_protected at TP=1 and TP=2 (separate processes), compares greedy output and the rank-0
  writer's head count (sidecar-sharding signal). **`tensor_parallel_size` is not yet wired for
  int4_protected**, so a TP=2 failure is the honest MEASURED negative (the sidecars/staging pools are
  per-layer and not sharded across ranks) — that is the integration work, not a harness bug.

---

## 4. Reading the results
Per run dir `runs/kvpro_v2/<ts>/`:
- `SUMMARY_phase0.md`, `SUMMARY_warmtier.md`, `SUMMARY_tp.md`, `phase6f_summary.csv`.
- `*.log` for each step's full output; `*.json` for the raw bench artifacts.
- Labels: **MEASURED** = this run measured it; **INCOMPLETE / NOT-MEASURED** = a hook is missing and
  the script printed the exact gap. Treat nothing else as a result.

## 5. Known gaps (as of this harness)
| Item | State | To unblock |
|---|---|---|
| Phase-6F GPU throughput A/B | INCOMPLETE | wire `fused_read_dequant_prep` into the decode read path (`PHASE6F_FUSED_READ`) |
| WarmTier serving TTFT/p99 | INCOMPLETE | wire `mark_prefix_computed` + `serve_with_warmtier_reuse` to the vLLM scheduler + int4 decode kernel |
| Tensor parallelism | NOT VALIDATED | shard KVPro sidecars/pools across TP ranks; `05` measures the current (failing) state |
| Decode throughput parity | NOT A GOAL | ceiling is ~0.27–0.30×; parity is impossible by design and never claimed |

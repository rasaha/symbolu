# int4_protected — Deploy & Experience-the-Savings Quickstart

Get int4_protected running on a fresh GPU pod and measure the savings on your own
hardware in ~30 minutes. Full architecture: `INT4_PROTECTED_DESIGN.md`.

> **What you'll see:** ~2× more users / longer context per GPU at **near-bf16
> quality**, plus a **prefill saving** on shared-prefix traffic. **Not** raw
> tokens/sec per request — int4_protected is decode-throughput-negative by design;
> that cost is disclosed in the report.

---

## 0. Prerequisites on the bare pod

- A GPU attached (A100-80GB / sm_80 ideal; H100 → set arch `9.0`). Check `nvidia-smi`.
- The repo cloned to `/workspace/symbolu`.
- The flash-attn fork tarball at `/workspace/vllm-flash-attn-dev-src.tar.gz`
  (vendored working copy — copy it onto the pod; it is not in the git repo).
- `HF_TOKEN` exported if the model is gated.

---

## 1. Deploy (one command)

```bash
bash /workspace/symbolu/CTM_plus/Bench/scripts/bootstrap_fresh_pod.sh
```
This creates the pinned venv (vllm 0.7.3 / torch 2.5.1+cu121), **untars + builds the
int4 kernel**, calibrates a protect mask, and runs a correctness gate. ~15–25 min.

If the venv/kernel already exist and you only need to (re)build the kernel — it
auto-untars the fork and enforces the pins first:
```bash
source /workspace/venv-vllm/bin/activate
export TORCH_CUDA_ARCH_LIST=8.0     # 9.0 for H100/H200
bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source
```

**Sanity check** the stack before demoing:
```bash
python -c "import vllm; from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache; \
print('ok vllm', vllm.__version__)"     # expect: ok vllm 0.7.3
```

---

## 2. Point at the protect mask

The mask is per-model (30-sec calibration, done by `bootstrap` for its default
model). For a different model, calibrate once:
```bash
python CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \
    --output /workspace/dev/build-logs/<model>_protect_mask_4pct.pt \
    --protect-fraction 0.04 --max-model-len 8192
```
Then:
```bash
export PROTECT_MASK_PATH=/workspace/dev/build-logs/<model>_protect_mask_4pct.pt
```

---

## 3. Experience the savings (one command)

```bash
source /workspace/venv-vllm/bin/activate
bash /workspace/symbolu/deploy/customer_savings_demo.sh --model <model>
#   fast variant:  ... --quick
#   knobs:         --mml 32768  --gpu-util 0.85  --out-dir /tmp/savings
```

It runs three guarded demos and prints one **SAVINGS REPORT**:

```
==============================================================================
int4_protected — SAVINGS on <model>  (mml=32768)
==============================================================================
DENSITY :  bf16 N1 token-slots  ->  int4 N2  =  ~2.0x  more users/context per GPU  [the $ win]
QUALITY :  int4 needle RETRIEVED — near-bf16, no quality cost                       [differentiator]
APC     :  TTFT -XX% per cache hit (prefix=P), Y.Yx throughput at hit-rate H        [prefill saving]
------------------------------------------------------------------------------
COST    :  decode throughput ~0.17-0.67x bf16 (DISCLOSED) — int4 is kernel-bound ...
------------------------------------------------------------------------------
NET     :  ~2x the users/context per GPU at near-bf16 quality, plus prefill savings
           on shared-prefix traffic, at a disclosed decode cost.
==============================================================================
```

### How to read it
- **DENSITY** is the headline $ saving — int4 holds ~2× the KV in the same GPU
  budget, so ~2× the concurrent (or 2× longer) sessions. This is measured live on
  *your* GPU, not a brochure number.
- **QUALITY** proves the density costs no quality — the needle is retrieved exactly
  as bf16 would. (Run a deeper quality bench with `phase6k12_hard_needle.py --apc`
  / `bench_phase6n_mmlu_quality.py` if a partner needs MMLU/hard-needle.)
- **APC** is the prefill saving on shared-prefix traffic (system prompts, RAG,
  multi-turn): each cache hit skips the prefix's prefill, and the saving **grows
  with prefix length**. The report shows the best quality-clean row.
- **COST** is stated plainly: decode is slower per request. The demo never hides it.

---

## 4. Go deeper (optional, per-claim)

| Claim | Deeper measurement |
|---|---|
| Density at saturation (2× concurrency under load) | `phase6k14_saturation.py` / `bench_phase6_long_context_gpu.py` |
| Hard-needle / MMLU quality == bf16 | `phase6k12_hard_needle.py --apc`, `bench_phase6n_mmlu_quality.py` |
| APC payoff vs prefix length / hit rate | `apc_payoff_sweep.py --prefixes ... --num-groups N` |
| Long-context throughput crossover (read-skip) | `phase10_crossover_sweep.py` |
| Is the int4 gather worth fusing (throughput headroom) | `bench_decode_gather_fusion_headroom.py` |

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `cannot import name flash_attn_with_int4_kvcache` | kernel not built into the vendored slot → `rebuild_all_kernels.sh --clean --verify-source` |
| int4 cells fail / garbage output | `PROTECT_MASK_PATH` unset or a short-context mask → recalibrate at `--max-model-len 8192` |
| `torch` drifted after a pip step | `rebuild_all_kernels.sh` step 0 re-pins it; or `pip install --no-deps --force-reinstall torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121` |
| build broke vLLM | roll back: `restore_vendored_vllm_flash_attn.sh` |
| OOM on a long-context cell | lower `--gpu-util`; pin `PHASE6_MAX_ACTIVE_SLOTS` to real concurrency |

---

*One-line drop-in for any existing vLLM app once deployed:*
```python
import kv_policy.int4_protected
from kv_policy.int4_protected import Int4ProtectedLLM
llm = Int4ProtectedLLM(model="<model>", enable_prefix_caching=True)  # APC eager-only
```

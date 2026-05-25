# int4_protected — KV cache quantization with quality preservation

A vLLM backend that stores attention keys and values as **4-bit
integers + a small set of protected high-precision channels**, giving
half the KV-cache memory at near-stock quality.

The protected channels are picked per-model by a quick calibration
pass that profiles which K-channels carry the most signal. This is
the "asymmetric" trick that lets aggressive quantization keep
high-fidelity attention.

## TL;DR

```python
import kv_policy.int4_protected           # registers the backend
from kv_policy.int4_protected import Int4ProtectedLLM
from vllm import SamplingParams

llm = Int4ProtectedLLM(
    model="Qwen/Qwen2.5-7B-Instruct",
    max_model_len=4096,
)
out = llm.generate(["Tell me about quantization."],
                   SamplingParams(temperature=0.0, max_tokens=64))
print(out[0].outputs[0].text)
```

For a new model:
```bash
# 1. Calibrate the per-model protect mask (~30 seconds on H100).
python3 Bench/scripts/calibrate_phase5b_protect_mask.py \
    --model <huggingface/model_id> --protect-fraction 0.04

# 2. Verify quality matches stock bf16.
python3 Bench/scripts/verify_phase5b_5_needle.py \
    --model <huggingface/model_id>
```

## What's the breakthrough

Other 4-bit KV quantizers exist (fp8 is half-precision and easy; pure
int4 is half-memory but quality-broken). int4_protected is the first
that combines:

- **0.5× memory** of bf16 (same as fp8)
- **100% needle-in-haystack retrieval** matching stock vLLM exactly
  (fp8 typically scores ~12% on the same benchmark)
- **Cross-model-family methodology** — same calibration script,
  different model families, no code changes

The "protect" idea is the core: a small fraction of K-channels (4%
by default) carry most of the attention signal. Keep those in bf16,
quantize the rest aggressively to int4. Recover full quality at the
memory cost of fp8.

## Supported models (validated)

| Model | Architecture | Needle 15/15 == stock |
|-------|--------------|-----------------------|
| `Qwen/Qwen2.5-7B-Instruct` | 28L × H_kv=4 × D=128 | ✓ |
| `mistralai/Mistral-7B-Instruct-v0.3` | 32L × H_kv=8 × D=128 | ✓ |
| `NousResearch/Meta-Llama-3.1-8B-Instruct` | 32L × H_kv=8 × D=128 | ✓ |
| `Qwen/Qwen2.5-14B-Instruct` | 48L × H_kv=8 × D=128 | ✓ |

Three model families. Two scales (7-8B + 14B). All four hit perfect
needle retrieval at the 4% protect_fraction with zero kernel
fallbacks.

Any D=128 architecture should work (Llama, Mistral, Qwen families).
D=64 / D=96 head dims would need kernel changes (separate project).

## Performance numbers (Qwen2.5-7B on H100)

| Backend | Memory | Per-seq latency | Quality | Aggregate @ B=8 |
|---------|--------|-----------------|---------|-----------------|
| bf16 | 1.0× | baseline | baseline | (memory-limited) |
| fp8 | 0.5× | ≈ bf16 | poor (~12% needle) | (memory-limited) |
| **int4_protected** | **0.5×** | ~3.7× bf16 | **100% needle** | **42.5 tok/s** |

The trade-off: int4_protected pays per-sequence latency to get
quality + memory savings. Aggregate throughput at B=8 is 42.5 tok/s.
The per-seq latency story improves with CUDA Graphs work (preflight
in progress; see `Bench/scripts/OPTION_B_PREFLIGHT.md`).

**Where int4_protected wins:** workloads that want to pack many
concurrent sequences on one GPU. With ~2× the cuda blocks at the
same memory budget, int4_protected sustains 2× the max concurrency
of bf16 at the same quality.

## How it works

### Calibration (one-time, per model)

A short prompt corpus runs through the model. For each
`(layer, h_kv, d)` channel of K, we accumulate the max-abs of K
activations. Per `(layer, h_kv)` we pick the top-N channels by
accumulated magnitude as "protected." That selection is saved as a
small `(num_layers, H_kv, D) int8` mask artifact.

Methodology is in `Bench/scripts/calibrate_phase5b_protect_mask.py`.

### Storage

At each layer:
- The N protected channels of K are stored in bf16 (full precision).
- The remaining D-N channels of K are stored as 4-bit nibbles plus
  per-block (scale, xmin) reconstruction params.
- V is stored as 4-bit nibbles + per-group (scale, xmin).
- vLLM's paged uint8 cache holds the int4 nibbles.

Total bytes per token ≈ half of bf16.

### Attention math

A custom variant of the FlashAttention kernel
(`vllm-flash-attn` fork at SHA `720c948`) reads the int4 nibbles,
dequantizes on the fly using (scale, xmin), splices the protected
channels back in at the right positions, and runs the attention
inner-product as usual. Output is bit-comparable to bf16 attention
at the per-(layer, head) level.

Kernel changes are in `CUDA/` (vendored vLLM fork).

### Backend integration

`Int4ProtectedAttentionImpl` subclasses vLLM's `FlashAttentionImpl`,
installed via post-init class swap on each Attention layer. The
write path quantizes K/V on store; the read path gathers the int4
blocks + protected channels + sidecar reconstruction and dispatches
to the fork's kernel.

`PagedKVWriter` owns the per-layer sidecar tensors and per-sequence
streaming state.

Backend code is in `kv_policy/phase5b_backend_install.py` and
`kv_policy/phase5b_4c_paged_writer.py`.

## Docs in this module

- `Bench/scripts/PHASE5C_USAGE.md` — usage recipe + supported models
  matrix + constraints + diagnostics.
- `Bench/scripts/PHASE6_PERF_REPORT.md` — performance work history
  (Option A batched-kernel-call, Option D vectorized splice, B-pre-1
  through B-pre-4 preflight for CUDA Graphs).
- `Bench/scripts/OPTION_B_PREFLIGHT.md` — CUDA Graphs roadmap +
  blockers + completed preflight work.
- `Bench/scripts/KERNEL_6C3C_RESUME.md` — historical context: the
  vLLM-FA fork, kernel-side changes, and earlier phase work.

## Project status

**Quality**: locked. Four models across three families all hit 15/15
needle retrieval matching stock bf16 exactly. Zero fallbacks across
~100K decode calls in aggregate.

**Memory**: 2× concurrent-sequence capacity at the same GPU budget
(measured: 218× max concurrency on Qwen2.5-7B at max_model_len=4096
vs 109× stock bf16).

**Performance**: 42.5 tok/s aggregate at B=8 on Qwen2.5-7B (H100).
Per-sequence latency is ~3.7× bf16. CUDA Graphs preflight is
complete on the read path (B-pre-1 through B-pre-4); enabling
graph capture requires equivalent work on the write path + vLLM
prepare-inputs integration (~4-7 days, scoped in
`OPTION_B_PREFLIGHT.md`).

**Roadmap (open):**
- CUDA Graph capture for the model forward (~2-3× projected
  aggregate throughput gain)
- Tensor parallelism for 70B-class models (requires multi-GPU pod;
  read/write paths should mostly Just Work but unverified)
- Kernel support for D!=128 head dims (Phi-3.5, others)

**Things that have been ruled in or out:**
- ✓ Methodology generalizes across model families (Qwen/Mistral/Llama)
- ✓ Methodology generalizes across model scales (7-8B → 14B)
- ✓ Read-path preflight for CUDA Graphs is complete
- ✗ B-1 smoke confirmed write path still graph-hostile; deferred
- ✗ No support yet for D!=128, TP>1, or pipeline parallelism

## File layout

```
CTM_plus/KVPolicy/
├── INT4_PROTECTED_README.md     ← this file
├── README.md                    ← legacy: Phase 4 eviction policy
├── setup.py
└── kv_policy/
    ├── int4_protected.py            ← user-facing API (Int4ProtectedLLM)
    ├── phase5b_backend_install.py   ← attention impl subclass + read path
    └── phase5b_4c_paged_writer.py   ← per-layer quantizing writer

CTM_plus/Bench/scripts/
├── PHASE5C_USAGE.md                              ← end-user usage doc
├── PHASE6_PERF_REPORT.md                         ← perf history
├── OPTION_B_PREFLIGHT.md                         ← CUDA Graphs roadmap
├── calibrate_phase5b_protect_mask.py             ← calibration script
├── verify_phase5b_5_needle.py                    ← quality acceptance
├── verify_phase5b_6_batch.py                     ← multi-batch correctness
└── verify_phase7_mistral_int4_protected.py       ← cross-model e2e smoke

CTM_plus/CUDA/                                    ← vendored vLLM-FA fork
                                                  ← (kernel-side int4 path)
```

## Quick verify recipe

After cloning + setting up vLLM + this module, the smoke test for
the v1.x ship config (Qwen2.5-7B):

```bash
# 1. Calibrate the protect mask (if not already done; ~30 sec).
python3 Bench/scripts/calibrate_phase5b_protect_mask.py \
    --model Qwen/Qwen2.5-7B-Instruct

# 2. Quality gate — needle retrieval must match stock 15/15.
python3 Bench/scripts/verify_phase5b_5_needle.py \
    --model Qwen/Qwen2.5-7B-Instruct

# 3. Multi-batch correctness gate.
python3 Bench/scripts/verify_phase5b_6_batch.py
```

All three should PASS GREEN. If any fail, see the troubleshooting
section in `PHASE5C_USAGE.md`.

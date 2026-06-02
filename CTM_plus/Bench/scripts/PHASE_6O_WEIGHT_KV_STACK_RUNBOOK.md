# Phase 6O — Weight-quant × KV-quant stacking test (the untested brief claim)

> **Why this exists:** the VC brief asserts *"AWQ/GPTQ quantize weights, not KV —
> they STACK with int4_protected, they don't replace it."* That composition has
> **never been run** in this stack — it's a logically-sound but empirically-
> unverified claim. A sharp diligence question ("show me AWQ + int4_protected
> running together") currently has no answer. This bench produces one, on any GPU
> pod (no profiling counters needed).

## The plumbing fact (verified by code-read)

`Int4ProtectedLLM(model=..., **kwargs)` forwards everything to `vllm.LLM(...)`.
So `quantization="awq"` passes through with **ZERO code change** — the API accepts
it for free. The open question is whether it **RUNS**: AWQ uses its own quantized
GEMM kernels (awq/marlin) on the *linear* layers; int4_protected uses a vendored
flash-attn fork on the *attention* path. They touch different layers and SHOULD be
independent — **this bench confirms that empirically.** The integration is the
experiment, not the quant math.

## The 2×2 cell matrix

| cell | weights | KV | what it isolates |
|---|---|---|---|
| `bf16_bf16` | bf16 | bf16 | full-size baseline |
| `awq_bf16` | AWQ | bf16 | weight-quant alone |
| `bf16_int4prot` | bf16 | int4_protected | **today's product** |
| `awq_int4prot` | AWQ | int4_protected | **THE STACK — the claim** |

The analysis checks: (1) does `awq_int4prot` **load and run** (integration), and
(2) is the AWQ weight saving the **same** with int4 KV as with bf16 KV
(independence → the stack composes).

## Run (GPU pod, valid mml=8192 mask, AWQ checkpoint available)

```bash
source /workspace/venv-vllm/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=0 HF_HOME=/workspace/.cache/huggingface
# AWQ checkpoint (downloads ~5 GB):
python CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py \
    --cells bf16_bf16,awq_bf16,bf16_int4prot,awq_int4prot \
    --awq-model Qwen/Qwen2.5-7B-Instruct-AWQ \
    --mmlu 100 \
    --out CTM_plus/Bench/bench_out/phase6o/stack.json
```

The single most important line in the output is the **verdict**:
- `integration: COEXIST_OK` → AWQ weights + int4_protected KV ran together → the
  brief's stacking claim is **empirically supported**.
- `integration: INTEGRATION_FAILED` → the `awq_int4prot` cell did not load; the
  error is in `cells.awq_int4prot.error`. **Better to find this now than in a POC.**

## ⚠ Honest limitations (read before quoting numbers)

1. **The HBM split is best-effort.** `_hbm_of` reports `torch.cuda.max_memory_
   allocated()` as a total proxy — it does NOT cleanly separate weight bytes from
   KV-budget bytes (that needs the phase6l live-introspection path). For an exact
   weight-saving number, cross-read `phase6l_capacity_demo.py` accounting per cell.
   **The robust signals here are: (a) does the stack LOAD, and (b) the MMLU sanity
   per cell** — both of which are reliable. Treat the GB figures as indicative.
2. **Needs a real AWQ checkpoint** (`Qwen/Qwen2.5-7B-Instruct-AWQ` or similar). A
   GPTQ checkpoint works too — swap `--awq-model` and the quant method may need
   `quantization="gptq"` (edit the cell builder, or add a `--quant-method` flag).
3. **AWQ quality is its own thing.** If `awq_int4prot` MMLU drops well below
   `bf16_int4prot`, that's AWQ's weight-quant loss, NOT int4_protected — the 2×2
   matrix isolates which layer caused any drop (compare `awq_bf16` vs `bf16_bf16`).
4. **Mask precondition:** int4_protected cells need the mml=8192 mask (needle
   GREEN), same as Phase 6N.

## What a GREEN result buys the story

Turns the brief's *assertion* ("they stack") into a *measurement*: "int4_protected
KV + AWQ weights run together; weights 14 GB → ~4 GB on TOP of the 1.83× KV
density — we compress BOTH memory budgets, and AWQ/GPTQ cannot touch the KV-cache
that is our moat." That is the **total-memory platform story**, and it's the
cheapest experiment on the board (a flag + an AWQ download, no kernel work, no
profiling pod).

## CPU verification (no GPU)

```bash
python CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py --selftest   # 4/4
python CTM_plus/Bench/scripts/bench_phase6o_weight_kv_stack.py --dry-run    # full matrix schema
python CTM_plus/Bench/tests/test_phase6o_weight_kv_stack.py                 # 10/10
```

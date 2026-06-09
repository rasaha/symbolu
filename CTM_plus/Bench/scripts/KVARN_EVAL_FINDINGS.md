# KVarN evaluation — measured on our stack (the first positive external result)

> **TL;DR.** [KVarN](https://github.com/huawei-csl/KVarN) (Huawei, vLLM-0.22 fork, Hadamard
> rotation + iterative variance normalization, `kvarn_k4v2_g128` = 4-bit K / 2-bit V) is the
> **first method in the entire KV-compression investigation that beats int4_protected on its
> own turf — on Llama-family models.** Near-lossless quality **and** more density **and**
> throughput ≥ bf16. But it **crashes on Qwen2.5-7B** (a kernel bug), and the win is measured
> only at short context with an easy metric. A serious competitor for the **power-of-2-GQA /
> Llama-family** segment; **not** applicable to Qwen2.5-7B, and not a hard-tail-validated win yet.

## Measured — Llama-3.1-8B (clean comparison, KVarN's real kernel vs bf16, same engine)

`kvarn_eval.py` (venv-kvarn, vLLM 0.22), greedy free-gen, 16 prompts × 48 tokens, vs
full-precision KV in the **same** engine — so it measures KVarN's real quantization cost
with **no T=1 hook confound** (this is KVarN's production Triton attention backend, not an
HF round-trip emulation):

| axis | bf16 | KVarN k4v2 | result |
|---|---:|---:|---|
| free-gen agreement vs bf16 | 1.0 (ref) | **0.9818** (mean prefix 47.1/48) | **near-lossless** |
| GPU KV-cache capacity (tokens @ 4k) | 414,528 | **1,105,408** | **2.67×** (vs int4_protected's 1.83×) |
| decode throughput (16-prompt run) | 281.6 tok/s | **285.6 tok/s** | **≥ bf16** (vs int4_protected's 0.22–0.67×) |

So on Llama, KVarN delivers what int4_protected can't: near-bf16 quality **and** higher
density **and** non-negative throughput, on a modern engine. The variance-normalization (the
novel piece beyond plain Hadamard) does real work — the Hadamard-base skepticism was too
pessimistic *for Llama*.

## The hard caveats (this is a scheme-swap, not a free lunch)

1. **Crashes on Qwen2.5-7B — NOT a true drop-in.** KVarN's fused decode kernel does
   `tl.arange(0, Q_PER_KV)`, which Triton requires to be a **power of 2**. Qwen2.5-7B has
   **28 Q-heads ÷ 4 KV-heads = 7** → `arange's range must be a power of 2` → engine init
   fails. KVarN works on **power-of-2-GQA** models (Llama-3.1 32/8=4, Mistral 32/8=4,
   Qwen3-4B), but **not Qwen2.5-7B**. Its "calibration-free, one-flag, plug-and-play" claim
   breaks on a very common model. **int4_protected still owns the Qwen / extreme-rope / GQA-7
   segment** (where KVarN literally won't run).
2. **It has its own tax.** The log reserves **9.5 GiB for the "KVarN fp16 tail pool"** — its
   analog of the sidecar overhead, which is why net capacity is **2.67×** not the ~4.7× the
   per-token density (≈27 KB/tok vs bf16 128 KB/tok) would give. Better ratio than
   int4_protected's 1.83×, but not tax-free.
3. **Short-context, easy metric.** 4K `max-model-len`, 48-token greedy gen, instruction
   prompts. 0.98 free-gen is strong but it is **NOT the hard tail** — long-context (32k+) +
   hard-needle, the regime where Qwen-1M broke and where protect earns its keep, is
   **unvalidated**. KVarN's own headline is MATH500/AIME24/HumanEval (reasoning), so it
   plausibly holds, but we haven't measured the regime that matters most.
4. **Different stack.** KVarN is vLLM **0.22** (V1); int4_protected is the **0.7.3** (V0)
   fork. Adopting KVarN means *leaving* int4_protected, not improving it — and the throughput
   edge is partly the newer engine, not just the quantizer.

## Strategic read

- For the **Llama-family long-context serving segment**, KVarN is now a serious competitor —
  arguably *better* than int4_protected on density + throughput at comparable (near-lossless)
  quality. If that segment is the target, KVarN-on-a-modern-vLLM is a real alternative.
- **int4_protected's remaining edges:** it **runs on Qwen2.5-7B** (KVarN crashes), it handles
  the extreme-rope models, and its quality is validated *harder* (15/15 hard-needle, the
  hard-tail metric KVarN hasn't been stressed on here).
- **Next validation before crowning KVarN:** re-run on Llama at `--max-model-len 32768` with a
  **needle** task — 0.98 on 4K free-gen is not the regime where the other methods broke.

## Reproduce
```bash
# venv-kvarn (vLLM 0.22 fork), HF_HOME on the big volume
M=NousResearch/Meta-Llama-3.1-8B-Instruct      # power-of-2 GQA; Qwen2.5-7B CRASHES
python Bench/scripts/kvarn_eval.py --mode bf16  --out /tmp/bf16_llama.json  --model $M --gen 48
python Bench/scripts/kvarn_eval.py --mode kvarn --out /tmp/kvarn_llama.json --model $M --gen 48
python Bench/scripts/kvarn_eval.py --compare /tmp/bf16_llama.json /tmp/kvarn_llama.json
```

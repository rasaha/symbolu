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
  (`kvarn_hard_needle.py` does exactly this, reusing `phase6k12`'s builder/classifier/seed so
  the row lands in the same table as int4_protected's hard-tail numbers.)

## Why the throughput gap exists (code-grounded — it's integration, not the quantizer math)

int4_protected is throughput-**negative** (0.24× bf16 early; ~0.5× bf16 ceiling at Phase 10);
KVarN is throughput-**neutral-to-positive** (285.6 vs its own bf16 281.6 = ≥1.0×). Comparing
*within each engine* isolates the quantizer's cost: int4 costs ~0.5–0.76× of its own stock;
KVarN's quantizer costs ~**0**. Why:

**Primary cause (~80%): native cache dtype vs Python wrapper.** The team's own per-decode
breakdown (`KERNEL_6C3C_PHASE2_4_MEASUREMENT_FINDINGS.md:26-39`, Qwen2.5-7B):

| block | ms | share |
|---|---:|---:|
| decode_append | 0.108 | 8% |
| decode_kernel (the actual attention) | 0.434 | 32% |
| **decode_repack (Python glue)** | **0.804** | **60%** |

60% of every decode step is a host-side repack — **not** the kernel. The fused kernel itself is
*46% faster* than its predecessor (`...FINDINGS.md:13-19`); in their words: *"the kernel itself
isn't a bottleneck... the slowdown is entirely the Python repack."* The repack exists because
int4_protected is a **wrapper/hook over vLLM 0.7.3 (V0)**, not a registered `kv_cache_dtype`.
Finding 4 (`...FINDINGS.md:70-95`) scopes the real fix — *"registering a custom `kv_cache_dtype`
in vLLM's CacheEngine"* — as **multi-week Phase 5B/5C work**, the unfinished ship blocker.

KVarN runs as `kv_cache_dtype="kvarn_k4v2_g128"` — one flag. That *is* the native CacheEngine
integration int4 hasn't finished. Its dequant happens *inside* the fused kernel (the same
load → unpack → ×scale → `tl.dot` int4's own kernel does at
`int4_fused_attention_kernel.py:154-173`); **no Python in the decode hot path.** The dequant
math is identical and cheap in both — that is NOT the cause.

**Secondary cause (~20%): the scheme is structurally heavier.** Even fully native, int4 carries
two costs KVarN doesn't: (1) the **protect mask is a dual path** — the kernel reads the top-4%
K channels from a separate bf16 buffer (`k_fp16_ptr` + `protect_mask_ptr`) and merges them every
step; KVarN has no protect → one uniform packed path with cleaner coalescing. (2) **per-channel
K groups along the SEQ axis** → decode tokens stage into a partial group needing finalization
(much of what `decode_repack` does); KVarN applies Hadamard + variance-normalization at *write*
time (g128, paged-native) → nothing to stage at decode. Plus V0 (82 tok/s stock) vs V1 (281
tok/s bf16) is ~3.4× of KVarN's *absolute* throughput, independent of the quantizer.

**One root cause, two symptoms.** The same not-yet-native status that forces the per-step Python
repack (→ throughput-negative) also prevents shrinking vLLM's preallocated KV reserve, so int4
carries a *sidecar* tax instead of a clean reserve-shrink (→ 1.83× with a 3.4 GB tax). KVarN,
being native, gets both: no host tax **and** a real reserve shrink (2.67×, its 9.5 GiB tail pool
is the native sizing).

**Implication.** Most of the gap is engineering debt (closeable — native integration would lift
int4 toward ~0.7–0.9× bf16), but it is *unfinished* multi-week work, and even fully native the
protect + per-channel-over-SEQ costs likely cap int4 at throughput-**neutral**, not positive —
KVarN is ≥bf16 because at decode it has nothing extra to do. **Throughput is a losing axis to
fight KVarN on;** int4_protected's edge is the Qwen2.5-7B/GQA-7 segment where KVarN crashes (and
the harder quality validation), not speed.

## Reproduce
```bash
# venv-kvarn (vLLM 0.22 fork), HF_HOME on the big volume
M=NousResearch/Meta-Llama-3.1-8B-Instruct      # power-of-2 GQA; Qwen2.5-7B CRASHES
python Bench/scripts/kvarn_eval.py --mode bf16  --out /tmp/bf16_llama.json  --model $M --gen 48
python Bench/scripts/kvarn_eval.py --mode kvarn --out /tmp/kvarn_llama.json --model $M --gen 48
python Bench/scripts/kvarn_eval.py --compare /tmp/bf16_llama.json /tmp/kvarn_llama.json
```

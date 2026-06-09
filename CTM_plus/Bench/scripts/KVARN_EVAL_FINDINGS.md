# KVarN evaluation — measured on our stack (the first positive external result)

> **TL;DR.** [KVarN](https://github.com/huawei-csl/KVarN) (Huawei, vLLM-0.22 fork, Hadamard
> rotation + iterative variance normalization, `kvarn_k4v2_g128` = 4-bit K / 2-bit V) beats
> int4_protected on the **easy metrics** on Llama-family models — free-gen quality (0.9818),
> density (2.67×), throughput (≥bf16). **But on the HARD tail it COLLAPSES**: selective
> long-context needle retrieval drops to **0.25 vs bf16's 0.955 (−0.705 gap), failing K-bound**
> (`MISS_K=15`) — the exact failure mode int4_protected's protect mask defends against. So the
> "near-lossless" claim is **short-context / easy-metric only**; the 0.98 free-gen number does
> NOT survive the regime the whole project targets. Net read: KVarN is a real competitor for
> **short-context / throughput-bound Llama serving**, but **int4_protected owns the hard tail**
> (selective long-context retrieval) **and** the Qwen2.5-7B / GQA-7 segment (where KVarN crashes).
> KVarN trades hard-tail quality for throughput by dropping protect; int4_protected trades
> throughput for hard-tail quality by keeping it. **Both now measured on the same harness.**

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
3. **The 0.98 was short-context / easy-metric — and the hard tail is now MEASURED NEGATIVE
   (see next section).** 4K `max-model-len`, 48-token greedy gen, instruction prompts barely
   exercise long-range K. On the hard selective-needle harness KVarN drops to **0.25 retrieval
   vs bf16's 0.955**, failing **K-bound**. KVarN's own headline (MATH500/AIME24/HumanEval) is
   reasoning — local KV dependency — which is why it can look near-lossless there yet collapse
   on selective long-context retrieval.
4. **Different stack.** KVarN is vLLM **0.22** (V1); int4_protected is the **0.7.3** (V0)
   fork. Adopting KVarN means *leaving* int4_protected, not improving it — and the throughput
   edge is partly the newer engine, not just the quantizer.

## Hard tail — MEASURED (KVarN collapses, fails K-bound)

`kvarn_hard_needle.py` (venv-kvarn, vLLM 0.22) reuses `phase6k12_hard_needle`'s builder +
classifier + seed 1234 — the **same needles** int4_protected was validated on — and runs two
cells in the same engine: full-precision KV (`bf16`, the anchor) vs KVarN. Llama-3.1-8B,
`--mml 8192`, 6 items/mode, 4 adversarial modes:

| cell | strict | retrieval | HIT | NEAR_V | **MISS_K** | COLLAPSE | FORMAT |
|---|---:|---:|---:|---:|---:|---:|---:|
| bf16 (anchor) | 0.875 | **0.955** | 21 | 0 | 0 | 1 | 2 |
| **KVarN k4v2** | 0.250 | **0.250** | 6 | 1 | **15** | 2 | 0 |
| | | **gap −0.705** | | | ↑ K-bound | | |

Per mode (bf16 → KVarN): `multi` 6/6 → **1/6**, `distractor` 3 HIT → **0/6**, `conflict` 6/6 →
**0/6**, `qa` 6/6 → **5/6 (holds)**.

**The diagnosis is unambiguous.** KVarN fails **K-bound** — `MISS_K=15` (no answer-shaped output
at all, the model can't *locate* the key) vs `NEAR_V=1` (located-but-imprecise). It is **not**
V-bound. That is the exact failure int4_protected's **protect mask** prevents: naive 4-bit K
with no protected channels loses the long-range retrieval signal. KVarN behaves precisely like
"naive 4-bit K, no protect."

**Internal control rules out a harness/engine artifact:** the `qa` mode (single buried fact,
asked directly) still holds at **5/6**. Same engine, same prompts, same greedy sampling — if the
harness or KVarN's kernel were broken, `qa` would fail too. Instead, single-fact retrieval works
while the modes needing *selective* K-matching collapse. That gradient is what KV-precision loss
looks like; it is a genuine quality failure.

**Caveat:** 1 model, 24 items, 8K. Effect size (−0.705) and structure (qa holds, selective modes
collapse) make it decisive, not noise — but the **32K run is the seal** (pending).

## Strategic read

- **The split is now measured, not asserted.** KVarN trades hard-tail quality for throughput by
  dropping protect; int4_protected trades throughput for hard-tail quality by keeping it. Same
  harness, same needles, both sides.
- **KVarN wins** the *short-context / throughput-bound* Llama segment: ≥bf16 throughput (native
  V1 cache dtype), 2.67× density, 0.98 easy free-gen. For reasoning workloads (local KV
  dependency) it plausibly holds.
- **int4_protected wins the hard tail** — selective long-context retrieval, the regime the whole
  project targets — where KVarN collapses **K-bound** (0.25 vs 0.955). The protect mask is
  buying exactly the robustness KVarN lacks. int4_protected **also** owns the **Qwen2.5-7B /
  GQA-7** segment (KVarN crashes) and the extreme-rope models.
- **This walks back the earlier "first method to beat int4_protected on its own turf" read.**
  KVarN beats it on the *easy* metric; on the hard tail — int4_protected's actual turf — KVarN
  loses badly. The competition is regime-split, not a KVarN win.
- **Seal it:** re-run `kvarn_hard_needle.py --mml 32768` (and ideally the int4_protected protect
  cell on the same Llama needles) to confirm the collapse deepens at 32K. The 8K result is
  already decisive on effect size.

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

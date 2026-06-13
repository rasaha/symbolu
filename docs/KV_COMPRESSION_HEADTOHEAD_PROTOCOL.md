# KV-Compression Head-to-Head — Pre-Registered Protocol

**Status:** experiment design (pre-registration). **Prereq:** GPU pod + the two competitor repos.
**Companion:** `ndol/sim/kv_method_memory.py` (analytical memory), `docs/KV_COMPRESSION_POSITIONING_MEMO.md`.

> **The one decision this resolves:** is int4_protected still a defensible KV *format*, or is it
> dominated by a cheaper, serving-native competitor — in which case pivot. Go in expecting it
> **may not win**; the protocol is designed to find the truth, not defend the asset.

## Competitors (both have public code — measure, don't cite)
- **SAW-INT4** — `togethercomputer/saw-int4` (arXiv 2604.19157). Token-wise INT4 + block-diagonal
  Hadamard rotation; fused rotation-quant CUDA kernel, **paged + FlashAttention-native**.
  **THE make-or-break comparator** (serving-native; ~0-storage rotation ⇒ ~2× denser than
  int4_protected analytically; argues protected channels are unnecessary).
- **GEAR** — `opengear-project/GEAR` (arXiv 2403.05527). 4-bit + low-rank residual + sparse
  outliers. **Secondary** (correction is not paged/fused-native → expected throughput hit).

## Fairness rules (or the comparison is meaningless)
1. **Same models:** Qwen2.5-7B, Mistral-7B-v0.3, Llama-3.1-8B (the validated portfolio).
2. **Same eval harness** (reuse the int4_protected needle/PPL/greedy harness in `CTM_plus/Bench`);
   add GEAR & SAW-INT4 as alternative KV codecs — do **not** trust their papers' numbers.
3. **Same context lengths** (16/32/64K), **same hardware**, **same calibration budget**.
4. **Report each method's REAL memory** (measured bytes/token incl. every sidecar/overhead),
   not the paper's headline ratio.

## Metrics (per method, vs bf16 baseline)
| axis | metric |
|---|---|
| **Quality** | needle-in-haystack (easy **and hard**-needle), perplexity ratio, greedy-token agreement |
| **Memory** | measured bytes/token of the KV footprint (your sidecar / GEAR low-rank+sparse / SAW rotation meta) |
| **Throughput** | decode tokens/sec + **p99** at long context & high concurrency, in a paged + fused stack |

## The make-or-break: int4_protected vs SAW-INT4
Analytical prior: SAW ≈ 4.5 b/elem (3.56×) vs int4_protected ≈ 8.9 b/elem (1.80×) — **~2× denser**.
So int4_protected must EARN its 2× memory cost in *quality* or it's dominated.

**Pre-registered decision rule:**
1. **DOMINATED → PIVOT.** If SAW-INT4 matches int4_protected quality (hard-needle within 2 pts,
   greedy agreement within 1 pt, PPL within 0.5%) **at ≤ its memory and ≥ its throughput** →
   int4_protected is not a defensible *format*. Action: adopt rotation, OR reposition int4_protected's
   value entirely to the **warm-tier / storage-systems** story (orthogonal to the codec).
2. **QUALITY-EDGE → REPOSITION THE CLAIM.** If int4_protected beats SAW on **hard-needle / tail
   quality by ≥5 pts** (or SAW shows a quality cliff int4_protected doesn't), despite SAW being
   denser → the defensible claim is **"quality at the tail that cheap rotation misses,"** NOT density.
   Sell that, with the honest memory trade stated.
3. **PARITY/MIXED.** If neither clears the above → comparable formats; differentiate on
   **integration + warm-tier reuse**, not the bits (consistent with the positioning memo).

GEAR is judged on the same axes but expected to lose on throughput (un-fused correction); if GEAR
*also* matches quality at lower throughput, it reinforces "complex correction isn't worth it"
(SAW's own thesis) — which cuts against int4_protected's protected-channel complexity too.

## Wiring (on the GPU pod)
- `git clone https://github.com/opengear-project/GEAR` and `https://github.com/togethercomputer/saw-int4`.
- Expose each as a KV codec (quantize on write / dequantize on read) behind the existing eval's
  cache interface; run the *same* needle/PPL/greedy/throughput suite int4_protected already uses.
- Capture **measured** bytes/token + tokens/sec + p99 for each — feed the real numbers back into
  `ndol/sim/kv_method_memory.py` to replace the analytical estimates.

## Honest framing / caveats
- Competitor quality is **claimed** until measured on *your* models/tasks; SAW-INT4 is brand-new
  (Apr 2026) — its claims need independent verification, which is part of int4_protected's leverage
  (you're battle-tested in a real stack; SAW is a fresh paper+kernel).
- But on the **density axis int4_protected leads with, the prior says it is behind** — so the
  realistic best case for int4_protected is the QUALITY-EDGE outcome (tail quality), not a density win.
- This is **existential** for int4_protected's core thesis, unlike the W1/W3/semantic-tiering side
  bets. Run the SAW comparison **first**; GEAR second.

## What "done" looks like
A table of `{quality, measured-memory, throughput}` for bf16 / int4 / int4_protected / GEAR /
SAW-INT4 on ≥2 models at ≥2 context lengths, and a verdict mapped to rule 1/2/3. If DOMINATED,
record it as a durable result (like the TurboQuant retirement) and pivot — do not defend the format.

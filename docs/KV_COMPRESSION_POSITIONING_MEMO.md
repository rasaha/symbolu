# KV-Cache Compression — Competitive Positioning Memo

**Author:** Ugence Labs · **Date:** 2026-06-12 · **Status:** internal positioning (honest, citable)
**Scope:** where int4_protected / prot-int8 actually stands vs the KV-compression frontier,
and the only differentiation that survives scrutiny.

> **One-paragraph position.** Low-bit, near-lossless KV compression is a **crowded frontier** —
> several published methods match or beat our ~1.8×-vs-bf16 ratio and claim near-/zero-loss
> quality. **We do not win on compression ratio or on "perfect quality," and we must stop
> claiming either.** Our defensible edge is system-level: a **deployment-oriented protected-KV
> serving path** — paged-cache/fused-kernel compatible, long-context retrieval preserved,
> **transfer-robust across models** (where competitors are config-specific), extending to an
> **NVMe warm-tier reuse** story that the GPU-memory-only competitors do not address.

---

## 1. The honest market reality

Near-lossless KV compression at ≤4 bits is an active, crowded research area. On the two
headline axes — **compression ratio** and **benchmark quality** — the field has caught up to
or passed int4_protected. Positioning that rests on "nobody can compress KV well" or "we are
first to perfect int4 KV" is **false and indefensible.** Drop it.

## 2. Competitive landscape (external numbers are *reported*; verify before any deck)

| Method | Reported claim | The gap / what it doesn't do |
|---|---|---|
| **KIVI** (ICML'24) | 2-bit KV, ~2.6× peak-mem, "almost same quality" | GPU-memory relief only; offline accuracy; no serving-tier / reuse story |
| **KVQuant** (2401.18079) | per-channel + pre-RoPE key, non-uniform, sparse outliers, long-context | outlier/sparse handling adds irregular access that fights paged + fused attention |
| **GEAR** (2403.05527) | "near-lossless" 4-bit, low-rank + sparse correction, ~2.29× mem / ~2.38× tput | low-rank+sparse correction is decode-time overhead; HBM-only |
| **KVTuner** (2502.04420) | mixed-precision, ~3.25-bit Llama-3.1-8B, 4.0-bit Qwen2.5, "nearly lossless" | sensitivity-aware precision is now prior art; still offline, HBM-only |
| **SAW-INT4** (2604.19157) | token-wise INT4 + block-diag Hadamard, **paged-cache + fused-attn compatible** | the serious *serving* comparator — closest to our lane; watch closely |
| **TurboQuant** (Google) | PolarQuant+QJL, "zero accuracy loss," ≥6× KV mem / up to 8× speedup | strongest external signal; but see §3.1 — **did not transfer in our hands** |

## 3. What's actually limited about the field (the real opening)

### 3.1 "Zero-loss" is config-specific and transfer-fragile — we have the receipts
We re-implemented TurboQuant/QJL as a KV-cache compressor and it **failed our validation**
(`CTM_plus/TURBOQUANT_RETIREMENT.md`, from `Bench/bench_out/PHASE4_GPU_FINDINGS.md` §17):

| Config (Qwen2.5-7B) | Result vs bf16 |
|---|---|
| TurboQuant baseline (random rotation, 3-bit, KV-only) | **3052× perplexity** — catastrophic |
| + KIVI per-channel-scale rescue | **24× worse** than baseline (KIVI's trick doesn't transfer to rotation designs) |
| + sink-skip rescue | still **220× perplexity** |

**Honest framing (do not misuse):** this does **not** refute Google's published W4A4 on
Llama-2/Gemma — our config diverged on four axes (random vs learned-polar rotation; 3-bit vs
4-bit; KV-only vs W4A4; Qwen vs Llama/Gemma). The defensible claim is the *general* one:
**published low-bit-KV "zero-loss" numbers hold only in the exact (model, bit-width, scope)
they were measured in, and routinely fail to transfer.** That fragility — not "competitor X is
bad" — is the market gap.

### 3.2 They relieve HBM; they are not a serving system
KIVI/KVQuant/GEAR/KVTuner shrink KV in GPU memory. None addresses **cross-request reuse,
warm-tier offload, or a storage path**. That is a different problem.

### 3.3 Accuracy tricks fight serving throughput
Low-rank + sparse correction (GEAR), non-uniform quant + outliers (KVQuant), rotations +
residual correction (TurboQuant, SAW-INT4) all add decode-time compute or irregular memory
access. There is a real **offline-accuracy-vs-online-throughput gap**: lossless in a notebook
≠ throughput-positive under vLLM paged KV + fused attention. Most papers report the former.

### 3.4 "Perfect quality" is benchmark-perfect, never math-perfect
No method is bit-identical in hidden states / logits / all-prompt outputs — they mean *same
benchmark scores / greedy outputs on tested prompts*. (This is the same trap that retired our
own W1 "exact read-skip" claim — see `docs/NDOL_NAND_DECODE_OPTIMIZATION_DESIGN.md` §9.3.) The
correct phrase for the whole field, us included, is **quality-equivalent on tested workloads.**

## 4. Our measured evidence (grounded, repo-cited)

Not "better compression" — **the scheme that held up in our stack when others didn't:**
- **Survived validation TurboQuant failed:** needle 15/15 == bf16 across 4 models; prot-int8
  greedy **bit-identical** flag-ON vs OFF across Llama-3.1-8B / Qwen2.5-7B / Mistral-7B-v0.3
  (`CTM_plus/Bench/scripts/PHASE6N_PROT_INT8_DESIGN.md`).
- **Integrated and serving-real:** paged-cache compatible, GPU-verified fused decode/write
  kernel, read-skip throughput-positive at long context (`INT4_PROTECTED_VC_BRIEF.md`).
- **Transfer-robust by construction:** per-model calibrated protect mask, shipped behind flags
  with measured A/B — directly answering the transfer-fragility that broke TurboQuant.
- **Honest density:** ~1.8× vs bf16 (1.78–1.83× net of sidecar) — **not** the densest; the
  value is quality-stability under serving, not ratio.

## 5. Defensible positioning

> A **deployment-oriented protected-KV serving path**: low-bit protected KV that is
> paged-cache/fused-kernel compatible, preserves long-context retrieval, is robust across
> models, and extends to **NVMe warm-tier reuse** — differentiated by measured
> cost/quality/throughput behavior under real serving workloads, not by compression ratio.

**Where the storage work fits (as product, not patent).** The NDOL/W3 storage analysis
(`docs/W3_CAPACITY_ENDURANCE_MODEL.md`) showed cross-tier NAND tiering is **not** patent-worthy
(capped ~1.14× over a fair baseline; hardware-limited; surviving mechanism is prior-art UEP).
But it *is* the system-level lane the GPU-memory competitors don't play in: **int4_protected
makes long-context KV cheap and stable enough to tier onto commodity flash for warm/reused
caches** (shared prefixes, multi-turn sessions) — GPU-memory relief **plus** NVMe warm-KV reuse
**plus** measured quality retention **plus** cost/token improvement. Sell the system, not the bits.

## 6. What NOT to claim (guardrails)
- ❌ "First/only to compress KV near-losslessly" — false; crowded.
- ❌ "Highest compression ratio" — KIVI/TurboQuant report higher.
- ❌ "Perfect / exact / lossless quality" — benchmark-equivalent only; bit-exactness is dead (W1).
- ❌ "TurboQuant doesn't work" — our local config failed; the paper's config is not refuted.
- ❌ "Novel NAND tiering" — hardware-capped (~1.14×) and prior art (§W3 doc).
- ✅ "Quality-equivalent on tested workloads, model-robust, serving-integrated, with a warm-tier
  storage story competitors don't have."

## 7. Caveats / due diligence before external use
- External numbers (KIVI 2.6×, GEAR 2.29×, TurboQuant 6×/8×, KVTuner bit-widths, SAW-INT4) are
  taken from secondary summaries — **verify each against the current papers**; several are
  2024–2026 preprints that may have moved.
- **SAW-INT4 is the closest comparator** (explicitly serving-compatible INT4) — track it directly
  and benchmark against it; it is the one most likely to contest this lane.
- Our serving-throughput and warm-tier-reuse advantages are **claims that still need head-to-head
  measurement** vs SAW-INT4 / GEAR on the same stack; the memo's edge is real only once measured.

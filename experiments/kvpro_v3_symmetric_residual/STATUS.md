# KVPro V3 Gate-1 — status (what is decided vs pod-required)

**Date:** 2026-07-15 · **Branch:** `claude/kvpro-v2-tier1-d8b4ae` · **Current verdict: `INCONCLUSIVE`**
(the quality question needs real captured KV on a GPU pod; this container has no GPU).

## CPU-tested this session (MEASURED-on-CPU / analytical)
- **Unit tests: 15/15 pass** — the affine quantizer is bit-faithful to the production writer math
  (`_ASYM_DIV=15`, per-block K / per-token-group V), protected channels reconstruct **exact**, the
  candidate wiring (S1–S4) is correct, and the pre-registered gate decision tree returns the right
  label in each branch (INCONCLUSIVE / GO_KERNEL_PROTOTYPE / NO_GO_QUALITY / GO_WITH_MODIFICATION).
- **Accounting (analytical, real):** dropping **both** xmins (S1/S2) = **−9.30%** decode read-bandwidth;
  dropping **one** (S3/S4) = **−4.65%** — **below the 5% floor**. Identical % for Qwen2.5-7B and
  Llama-3.1-8B (same D/BS/group geometry). prot-int8 protect nudges these to −9.64% / −4.82%.
- **Synthetic pipeline** (recon → attention-error → gate) runs end-to-end and correctly yields
  `INCONCLUSIVE` (synthetic data is explicitly **not** a quality verdict).

## NOT RUN — requires a GPU pod (the actual falsifier)
- `capture_kv.py` — capture real post-RoPE Q/K/V + the frozen mask (no int4 fork needed).
- reconstruction + **attention-error on REAL tensors** — the decisive offline quality signal.
- `fakequant_quality.py` — end-to-end fake-quant perplexity + token-agreement (no int4 fork needed).
- hard-needle / MMLU end-to-end (add a driver alongside, per the pre-registered e2e thresholds).
- `capture_kv.py` and `fakequant_quality.py` are **HARDWARE-UNTESTED** — verify the rotary/Cache
  patches against the pod's `transformers` version (they target the Llama/Qwen2 style).

## Deviation (stated openly): the int4 decode fork is NOT gated on
This is a **fake-quant** study (quantize→dequantize in fp), so it does not use the int4 CUDA kernel or
the `int4_protected` backend. The harness reports the fork as **INFO**, not a hard failure — this is a
deliberate, documented choice, **not** a silent fallback. Hard deps for pod steps remain **GPU + model
+ mask**. If you want a production-path capture instead, that's a separate extension.

## What result justifies kernel work (the branch this gate decides)
| Outcome on a real pod run | Verdict | Action |
|---|---|---|
| S1/S2 quality passes (offline **and** e2e) **and** ≥5% systems (S1/S2 = 9.3% ✓) | **GO_KERNEL_PROTOTYPE** | build the V3 symmetric fused kernel |
| Symmetric fails on Qwen2.5-7B (or any candidate below threshold everywhere) | **NO_GO_QUALITY** | abandon symmetric residual **before** kernel effort |
| Quality fine but reduction <5% (e.g., only single-xmin drops viable) | **NO_GO_SYSTEMS_VALUE** | keep affine INT4; spend effort on in-kernel gather / store-as-consumed |
| Only K (S4) or only V (S3) passes quality | **GO_WITH_MODIFICATION** | pursue an **asymmetric** format, not one universal representation |

## Honest caveats (challenging the hypothesis, including my own prior numbers)
- The systems win from xmin removal is **modest**: **~9.3%** (both xmins) or **~4.65%** (one). This
  **corrects my earlier speculative "15–35% TPS"** — that was unsupported. Even a perfect symmetric
  kernel recovers **≤~9.3%** at long context from xmin alone; the packed nibbles (128 B) and the
  scattered **protect** stream remain and likely become the next bottleneck. So a **quality-passes /
  systems-too-small** outcome (`NO_GO_SYSTEMS_VALUE`) is a genuinely plausible result of this gate — and
  if that happens, the honest recommendation is to keep affine and pursue in-kernel gather / layout
  instead. This gate is designed to surface that, not to rationalize a kernel.
- Reconstruction MSE alone is **not** trusted; the decision leans on the attention-output error and
  end-to-end quality, per the study design.

# KVPro Across the Memory Hierarchy — Investor Brief

**Ugence Labs · Quality‑safe KV‑cache compression for long‑context LLM serving**

> **What this document is.** A quantified view of where KVPro saves memory and money across the
> three tiers of the LLM serving memory hierarchy — **GPU HBM → CPU DRAM → NVMe/NAND flash** — with
> every number labeled **measured** (real H100/A100 GPUs, this program) or **modeled** (analytical /
> first‑principles). It is written to survive technical due diligence: the trade‑offs and scope
> limits are stated, not hidden.
>
> **Method disclosure.** KVPro's compression mechanism is **proprietary and patent‑pending**;
> technical detail is available to qualified partners under NDA. This brief states results and
> economics, not the method.
>
> **Vendor note.** Memory‑vendor names below denote the **class of component** a saving applies to,
> based on public specifications; they are **not** endorsements and these figures are **not** vendor‑
> supplied. Correct component mapping: **HBM and DRAM** are made by Micron, Samsung, and SK Hynix;
> **NAND flash** by SanDisk (spun out of Western Digital in 2025), Kioxia, and Micron. Western
> Digital itself makes hard drives, which are **not** in KVPro's KV path. All trademarks belong to
> their owners.

---

## 1. Executive summary

At long context, the **KV cache — not model weights — is the dominant consumer of memory** at every
tier of an LLM serving stack, and therefore the binding limit on how many concurrent users a fixed
hardware budget can serve. **KVPro compresses the KV cache to ~0.5× its size (≈1.8× net density) at
near‑full‑precision quality**, with no model retraining, as a drop‑in backend for the dominant open
serving stack (vLLM).

Because the KV cache lives across the whole hierarchy, that single ~1.8× compression compounds:

| Tier | Component (vendor class) | KVPro effect | Basis |
|---|---|---|---|
| **1 — GPU HBM** | HBM3E (Micron / Samsung / SK Hynix) | **~2× users per GPU, ~44% fewer GPUs** for KV‑bound long‑context serving | **Measured** |
| **2 — CPU DRAM** | DDR5 (Micron / Samsung / SK Hynix) | **~1.8× more reusable KV per GB**, lossless offload → skips prefill recompute | Modeled + measured reuse |
| **3 — NVMe NAND** | flash (SanDisk / Kioxia / Micron) | **~1.8× more KV per GB**; endurance‑viable for warm/reused caches | Modeled |

**The primary, defensible win is Tier 1 (HBM).** Tiers 2–3 are compounding, honestly‑bounded upside.

---

## 2. The problem — KV memory is the bottleneck at every tier

A transformer stores, per token, a key/value tensor at every layer. At 32K+ context this KV cache
**exceeds model‑weight memory** on most popular open models. Concretely, Llama‑3.1‑8B holds
**128 KiB of KV per token** → **~4 GiB for a single 32K‑context session**. How densely and how
faithfully you can hold that KV — in HBM, in DRAM, and on flash — sets how many users a given
hardware install serves, and whether the outputs remain trustworthy. Naïve low‑bit KV buys density
by destroying long‑context quality; the gap between *density* and *maintained quality* is the
opportunity KVPro addresses.

---

## 3. The technology (one paragraph)

KVPro is a **post‑hoc, quality‑safe KV‑cache compressor**: it stores keys and values as 4‑bit
integers while keeping a small, calibration‑selected set of high‑sensitivity channels at higher
precision, reconstructing them inside a fused attention kernel with no full‑precision copy. A
one‑time, per‑model calibration makes it **transfer‑robust across model families with no per‑family
code changes**, and its compressed state can be **snapshotted and restored byte‑for‑byte** for
lossless movement and reuse across DRAM and flash. *(Mechanism, calibration, and kernel detail are
proprietary / patent‑pending — NDA only.)*

---

## 4. Tier 1 — GPU HBM (Micron / Samsung / SK Hynix HBM3E) — **the primary win**

KVPro compresses in‑GPU KV to **~0.5× BF16 (2.0× raw slots, ~1.8× net of metadata), measured under
sustained saturation** — directly freeing the most expensive memory in the stack.

**Per‑GPU density (measured, Llama‑8B, 32K context, 80 GB GPU):**

| | KV / 32K session | Resident 32K sessions / GPU |
|---|---|---|
| BF16 | ~4.0 GiB | ~12 |
| **KVPro** | ~2.2 GiB | **~24 (≈2×)** |

*(Independently corroborated: 218× vs 109× max concurrency on Qwen2.5‑7B at max_model_len 4096.)*

**Unit economics — per 100 concurrent 32K‑context sessions (measured density):**

| | BF16 | KVPro | Saving |
|---|---|---|---|
| GPUs required | ~9 | ~5 | **~44% fewer** |
| Cost / month @ $1.50/GPU‑hr* | ~$9,900 | ~$5,500 | **~$4,400/mo** |
| HBM freed (×80 GB/GPU) | — | — | **~320 GB** |

**Scaling (linear; the ~44% GPU‑count cut is rate‑independent and measured — only the $ moves):**

| Concurrent 32K sessions | GPUs removed | HBM3E freed (≈24 GB stacks) | Annual GPU savings @ $1.50/hr |
|---|---|---|---|
| 100 | ~4 | ~320 GB (~13 stacks) | ~$53K |
| 1,000 | ~40 | ~3.2 TB (~133 stacks) | ~$530K |
| 10,000 | ~400 | **~32 TB (~1,300 stacks)** | **~$5.3M** |

\*Illustrative blended cloud A100‑80GB rate — substitute your real GPU/HBM cost.

**Read two ways:** an operator needs **~44% less HBM** for a fixed long‑context workload, **or** a
fixed HBM install base serves **~2× the long‑context users**. KVPro is a **capacity multiplier on
HBM.**

---

## 5. Tier 2 — CPU DRAM (Micron / Samsung / SK Hynix DDR5) — the warm reuse tier

DRAM is the fast tier between HBM and flash, used to hold reusable KV (shared prefixes, multi‑turn
sessions) so expensive prefill is not recomputed. DRAM has no density‑tiering physics, so KVPro's
saving here is the **clean 1.8× compression, and it is byte‑for‑byte lossless** (snapshot/restore is
bit‑exact — HBM↔DRAM movement adds **zero** additional quality loss).

| Warm KV held in DRAM | tokens / GB | 
|---|---|
| BF16 | ~8,190 |
| **KVPro** | ~14,750 |
| **Saving** | **~44% less DRAM for the same working set (1.8×)** |

**Where the DRAM value is actually realized — upstream, as reuse:** caching compressed prefixes in
DRAM converts to HBM/GPU savings through avoided prefill —
- **50–86% lower time‑to‑first‑token per cache hit** (measured), and
- **1.2–1.85× batch throughput at high hit rates** (measured).

*Basis: DRAM capacity figure is **modeled** (the 1.8× compression applied to the warm tier); the
reuse TTFT/throughput figures are **measured**.*

---

## 6. Tier 3 — NVMe NAND flash (SanDisk / Kioxia / Micron) — the cold/reuse tier — **honestly bounded**

For the largest, coldest reusable caches, KVPro's compressed KV lands on flash. Two levers, stated
with their limits (this is the tier where we deliberately under‑promise):

**(a) Compression — the real saving (1.8×, measured anchor):**

| Storing 1B tokens of KV | tokens / GB | Flash needed |
|---|---|---|
| BF16 | 7,410 | 135 TB |
| **KVPro** | 13,330 | **75 TB (−44%)** |

**(b) NAND density tiering (protected bits → safer tier, bulk → densest tier) — small and capped:**
adds only **~1.14× over KVPro's own compression** (15,230 tokens/GB, 2.06× BF16). This extra is
**hardware‑limited** (the QLC‑vs‑TLC usable‑density gap after ECC), **collapses at aged‑QLC error
rates (RBER ≥ ~5e‑2)**, and rests on a mechanism that is largely prior art. **We do not build the
business case or the patent on lever (b).**

**Endurance caveat (honest):** QLC flash sustains only ~0.83 drive‑writes/day for a 3‑year life;
per‑request "hot" KV churn would wear it out in ~months. KVPro's byte‑faithful, write‑once‑read‑many
reuse keeps write amplification low, so flash is endurance‑viable for **warm/reused** caches (shared
prefixes read across many requests), **not** hot per‑request churn.

*Basis: NAND figures are **modeled** on conservative public datasheet parameters, not vendor
silicon; the 1.8× compression is the **measured** anchor.*

---

## 7. Consolidated economics — the compounding picture

| Tier | Component | KVPro saving | Realized value | Basis |
|---|---|---|---|---|
| GPU HBM | HBM3E | ~1.8× density → **~44% fewer GPUs / ~2× users** | ~$53K–$5.3M/yr per 100–10,000 sessions | **Measured** |
| CPU DRAM | DDR5 | ~1.8× capacity, lossless | +50–86% faster TTFT, 1.2–1.85× throughput (reuse) | Modeled + measured |
| NVMe NAND | flash | ~1.8× compression (+~1.14× tiering, capped) | ~44% less flash for warm KV | Modeled |

**Composability:** KVPro operates on the KV term only and **stacks with** weight quantization and
other serving optimizations — it does not compete with them.

---

## 8. The honest trade‑off (disclosed, not buried)

KVPro is a **capacity + quality** tool, not a raw‑speed replacement. On the current (unoptimized)
decode path it runs **~0.13–0.67× BF16 decode throughput** depending on workload. The deployment
model is therefore **routing**: send memory‑bound, long‑context, high‑concurrency, and shared‑prefix
traffic to KVPro; keep latency‑critical single‑stream traffic on full precision (that traffic is
credited **zero** in the economics above). Decode‑throughput recovery is a funded v2 item with a
**bounded** ceiling (~0.27–0.30× → improves, does not reach parity); we state this plainly.
Conservative split: if only half a deployment's long‑context traffic is capacity‑bound, **halve
every figure** — KVPro still removes ~20% of the GPU bill for that workload.

---

## 9. Quality evidence (why the density is trustworthy)

- **Full‑precision parity on hard long‑context retrieval:** exact‑match needle‑in‑a‑haystack **15/15
  == stock BF16** across **four models, three families, two scales** (Qwen2.5‑7B, Mistral‑7B‑v0.3,
  Llama‑3.1‑8B, Qwen2.5‑14B) at a 4% protected fraction, same calibration, no per‑family code.
- **Standard academic benchmarks:** 0.0‑point delta vs full precision — the model chooses the
  **identical answer on every question** tested.
- **Byte‑faithful warm‑tier:** snapshot→restore of compressed KV verified **bit‑exact**, so DRAM/
  flash movement introduces no additional quality loss — something lossy compressors cannot offer.

---

## 10. Measured vs. modeled — due‑diligence key

| Claim | Status |
|---|---|
| ~1.8× net in‑HBM KV density; ~2× resident sessions/GPU; ~44% fewer GPUs | **Measured** (H100/A100) |
| Needle 15/15 == BF16 across 4 models; 0.0‑pt academic delta | **Measured** |
| Byte‑exact snapshot/restore | **Measured** |
| TTFT −50–86% / 1.2–1.85× throughput on reuse | **Measured** |
| DRAM‑tier capacity (1.8×) | **Modeled** (compression ratio applied) |
| NAND capacity (2.06× BF16) and tiering (1.14×), endurance | **Modeled** (conservative public NAND params) |
| Dollar figures | **Illustrative** — scale with your GPU/HBM/DRAM/flash rates |

---

## 11. Bottom line

One quality‑safe compression (~1.8×) applied across the memory hierarchy: **~44% fewer GPUs and ~2×
long‑context users on HBM** (the measured, defensible core), **~1.8× denser lossless DRAM reuse**
that pays off as faster time‑to‑first‑token and higher throughput, and **~1.8× less flash** for
warm/reused caches — all at near‑full‑precision quality, as a drop‑in vLLM backend, patent‑pending.
The economics scale linearly with deployment size and with the buyer's own memory and GPU prices.

*Results measured on real H100/A100 GPUs this program; modeled figures are labeled and rest on the
measured ~1.8× density anchor. KVPro's method is proprietary / patent‑pending — technical
due‑diligence materials available under NDA. The decode‑throughput trade‑off in §8 is disclosed in
full.*

# KVPro — Investor Brief

**Cognade Labs**
*Quality-safe KV-cache compression for long-context LLM serving*

> This is the investor-facing brief. It states **measured results** and the **market**; it does
> **not** disclose the method. KVPro's compression mechanism is **proprietary and patent-pending** —
> technical detail is available to qualified partners under NDA. Figures herein were measured on real
> H100/A100 GPUs this quarter unless marked *modeled* or *projected*.

---

## Executive summary

**The problem.** At long context, the **KV-cache — not model weights — is the dominant cost and
concurrency limit** in LLM serving. The obvious fix, 4-bit KV, has not shipped *at quality*: today's
options buy density by spending accuracy (the leading half-precision option retrieves a planted fact in
just **1 of 15** trials; naïve 4-bit agrees with full precision on only **~53%** of generated tokens).
The gap between "4-bit density" and "maintained quality" is the opportunity.

**The product.** **KVPro** is a quality-safe KV-cache compressor. A **proprietary, patent-pending**
method preserves the highest-leverage parts of the model's attention state while aggressively
compressing the rest, delivering **near-full-precision quality at ~2× the KV density**. It ships as a
**one-line drop-in** to the dominant open serving stack (vLLM) — no model retraining, no
quantization-aware fine-tuning.

**Why it wins.** Every *denser* competitor we measured trades away hard-retrieval quality; KVPro does
not. On identical tests, competing 4-bit methods **collapse on hard long-context retrieval** while KVPro
holds full-precision-level accuracy. That reliability — *quality you can trust at 2× density* — is the
wedge in a market where a cheap **wrong** token has no value.

**The expansion.** As serving moves to tiered KV memory (GPU → CPU → flash), the bottleneck becomes
**quality-safe KV movement**. **KVPro WarmTier** extends the product to store and reuse compressed KV
across sessions with a **byte-faithful** guarantee — proven — so reused context loses **zero** quality.

**The ask.** Funding for **v2 productionization** (throughput recovery, tensor parallelism, KVPro
WarmTier serving) and a **production design partner** to convert "shipped at near-full-precision
fidelity" into "deployed with measured cost/quality/latency." *(Round sized to milestones — §10.)*

---

## 1 · The market

LLM inference economics reduce to **useful tokens delivered per joule, per concurrent user** (a framing
echoed by operators like Perplexity's CEO: the winner "balances accuracy, latency, cost… all together").
At 32K+ context the KV-cache exceeds model-weight memory on most popular open models, so **how densely
and how faithfully you can hold KV directly sets how many users a GPU serves** — and whether the outputs
are trustworthy. Long-context, agentic, and RAG workloads — the fastest-growing inference segments — are
exactly the ones this binds.

Buyers: inference API providers, enterprise self-hosters in quality-sensitive domains (legal, health,
finance), open-model serving hubs, and edge/low-HBM deployments.

---

## 2 · The product — KVPro

KVPro is a post-hoc KV-cache compressor: it plugs into an existing serving deployment and compresses the
KV-cache **without** touching the model. Its differentiator is a **proprietary, patent-pending**
mechanism that protects the small, high-leverage fraction of the attention state that determines
retrieval quality, while compressing the bulk to 4-bit — recovering near-full-precision behavior at the
same 4-bit density that naïve methods degrade.

- **Integration:** one-line backend in vLLM (the dominant open serving engine). No retraining, no
  fine-tuning, no model-code changes.
- **Generality:** a fast, fully automated per-model setup; validated across three model families and
  two scales with no per-family tuning.
- **Honest scope:** KVPro is a **capacity + quality** tool, not a raw-speed replacement (see §4). The
  deployment model is **routing** — send memory-bound, long-context, high-concurrency, and
  shared-prefix traffic to KVPro; keep latency-critical single-stream traffic on full precision.

*(Method, calibration, and kernel detail are proprietary / patent-pending — available under NDA.)*

---

## 3 · Measured results (real GPUs, this quarter)

**Quality — at full-precision parity:**
- **Four models** (three families, 7–14B) hit **15/15** on needle-in-haystack retrieval, **matching
  full precision**, replicated across independent seeds.
- Standard academic benchmarks (knowledge, reasoning, truthfulness): **0.0-point delta vs full
  precision**, with the model choosing the **identical answer on every question**.
- **+20 points** of token-for-token agreement over naïve 4-bit; hard multi-distractor retrieval near
  full precision where naïve 4-bit accumulates genuine misses.

**Density — ~2× more users per GPU:**
- **2.0× raw KV slots, ~1.8× net** capacity per GPU, demonstrated under sustained saturation.
- Translated: a measured 32K-concurrency example runs on **~44% fewer GPUs** at near-full-precision
  quality.

**Competitive — KVPro holds the tail where denser codecs break (measured, our hardware):**
- A leading rotation-based 4-bit method works on the model it was tuned on but **collapses to 0%**
  hard-retrieval on a mainstream model where KVPro and full precision score **100%**.
- A vendor 4-bit/2-bit method is near-lossless on easy metrics but **collapses on hard long-context
  retrieval**; KVPro holds full-precision quality on the same test.
- Against the incumbent warm-tier storage codec, **KVPro preserves the critical attention information
  exactly where that codec introduces error** (measured on real model KV).

**Warm-tier reuse — byte-faithful, proven:**
- KVPro's snapshot/restore of compressed KV to CPU/flash is **bit-exact** (verified across multiple
  prefixes and configurations), so **reused context loses zero quality** — a guarantee lossy
  compressors cannot make.

---

## 4 · The honest trade-off

We disclose the cost plainly: on the current (unoptimized) decode path, KVPro is
**throughput-negative — roughly 0.13–0.67× full-precision tokens/sec depending on workload**
(worst case at long generation under deep saturation; best at short-output, high-concurrency traffic).
KVPro buys **capacity and quality**, not raw per-stream speed. The economics still win on **$/request**
for the large and growing class of memory-bound, long-context, high-fan-out workloads — which is the
target segment, served by routing. Decode-throughput recovery is a funded v2 item with a measured upside
bound (it improves, but does not reach full-precision parity — stated honestly).

---

## 5 · Conservative cost analysis

The dollar case rests on **one measured fact** — KVPro holds **~2× the resident long-context sequences
per GPU** — applied *only* where the binding constraint is KV memory (long-context, high-concurrency
serving). We model it conservatively and state exactly where it does **not** apply.

**Unit economics — per 100 concurrent 32K-context sessions (measured density):**

| | full precision | KVPro |
|---|---|---|
| Resident 32K sessions / GPU (measured) | ~12 | ~24 |
| GPUs for 100 concurrent sessions | ~9 | ~5 |
| Cost / month, 24×7 @ $1.50/GPU-hr\* | ~$9,900 | ~$5,500 |
| **GPU savings** | — | **~$4,400/mo (~44%)** |

\*Illustrative blended cloud A100-80GB rate — substitute your real GPU cost. The **~44% GPU-count
reduction is the measured, rate-independent result**; only the dollar figure moves with the rate.

**Scaling (linear in concurrency, same assumptions):**

| Concurrent 32K sessions | GPUs removed | Annual GPU savings @ $1.50/hr |
|---|---|---|
| 100 | ~4 | ~$53K |
| 1,000 | ~40 | ~$530K |
| 10,000 | ~400 | ~$5.3M |

**Where we deliberately under-promise:**
- Savings apply to **memory/capacity-bound** serving only. KVPro is **throughput-negative** (§4), so for
  **throughput-bound or latency-critical** traffic it is *not* routed and is credited **zero** — that
  traffic is excluded entirely from the table.
- If only **half** of a deployment's long-context traffic is capacity-bound (a conservative split),
  **halve every figure** — KVPro still removes **~20%** of the GPU bill for that workload.
- The table **excludes the second lever**: prefix / KV **reuse** (KVPro WarmTier). For shared-document
  RAG and multi-turn / agent sessions, reusing cached KV avoids recomputing prefill — measured
  **50–86% lower time-to-first-token per cache hit** and **1.2–1.85× batch throughput** at high hit
  rates. That is additional, compounding upside we do **not** count here.

**Bottom line:** on the **target segment alone, conservatively scoped**, KVPro removes on the order of
**20–44% of the GPU bill at near-full-precision quality**, and the warm-tier reuse lever stacks on top.
The unit — GPUs per concurrent long-context session — is measured; the dollar figure simply scales with
the buyer's GPU rate and traffic mix.

---

## 6 · Why it's defensible

- **Patent-pending method.** The channel-protection approach is novel and proprietary; a fast
  per-model setup makes it practical at deployment time.
- **Operational know-how.** The calibration design, the parameter choices, and the
  correctness/serving engineering are earned, non-obvious, and validated by this quarter's
  measurement work — not reproducible from public description.
- **Battle-tested integration.** KVPro runs today in a real, dominant serving stack at
  near-full-precision fidelity — competitors are largely fresh papers or single-family kernels.
- **Measured competitive moat.** Independent, on-our-hardware head-to-heads show the denser
  alternatives breaking on the quality dimension customers actually care about.
- **Composability.** KVPro is orthogonal to (and stacks with) weight-quantization and other serving
  optimizations — it owns the KV term specifically.

---

## 7 · KVPro WarmTier — the expansion

Serving is moving from single-tier GPU memory to **hierarchical KV memory** (GPU HBM → CPU DRAM →
NVMe/flash), where expensive prefill work is stored and **reused** across requests and sessions
(documents, agents, multi-turn chat, RAG). In that world the bottleneck is **quality-safe KV
movement**, and the winning component is the one that compresses, stores, reloads, and reuses KV
**without breaking quality**.

KVPro WarmTier is built for exactly this: a quality-safe compressed KV format with a **byte-faithful
reuse guarantee** (proven), positioned as the **reliability layer** on top of the KV-offload plumbing
the ecosystem already provides. *(Full end-to-end warm-tier serving integration is in progress;
near-term results are scoped.)*

---

## 8 · Traction

[TRACTION — pilots / design partners / LOIs / usage / inbound. If pre-traction, state the
proof-of-technology milestones reached this quarter and the named partners in conversation.]

---

## 9 · Team

[TEAM — founders + key technical hires; relevant background in ML systems / inference / kernels.]

---

## 10 · The ask

We are raising to fund **v2 productionization** and the **first design-partner deployments**. Use of
funds:
- **Decode-throughput recovery** — the kernel work that lifts the 0.13–0.67× toward its bounded ceiling.
- **Tensor parallelism** for 70B-class models, where the memory economics are largest.
- **KVPro WarmTier serving** — turn the proven byte-faithful snapshot/restore into a deployed warm tier.
- **1–2 design-partner deployments** → a third-party-verifiable cost/quality/latency case study at
  production scale.

*(Round size and instrument are being set with lead investors; we'll size to the milestones above.)*

**What we want from a partner:** a production-scale, long-context serving deployment to convert
"shipped at near-full-precision fidelity" into "deployed with measured savings."

---

*Results measured on real H100/A100 GPUs this quarter; competitive comparisons run head-to-head on our
hardware. KVPro's compression method is proprietary and patent-pending — technical due-diligence
materials available under NDA. "Near-full-precision" denotes the measured quality parity described in §3;
the throughput trade-off in §4 is disclosed in full.*

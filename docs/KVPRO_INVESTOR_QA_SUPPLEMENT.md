# KVPro — Investor Q&A Supplement (Blackwell/NVFP4 · Agentic · Memory Tiers)

**Shareable / non-confidential.** This document describes measured outcomes, limitations, and product
positioning only. Detailed implementation methods are proprietary, patent-pending, and disclosed only
under NDA.

Evidence labels used throughout (applied to every quantitative claim):
**Measured — implementation** · **Measured — controlled benchmark** · **Measured — reuse primitive** ·
**Modeled — capacity** · **Modeled — economics** · **Planned / integration in progress** ·
**Unbenchmarked — native hardware**.

---

### Q10. "Doesn't Blackwell's native FP4 (NVFP4) just commoditize this — the hardware does 4-bit KV for free?"

**Honest answer.** On the axis our buyers care about — **quality** — we tested this directly; on
**speed**, it remains open. We emulated NVFP4's numerics (E2M1 elements + per-16-channel block scale +
per-tensor FP32 scale) and measured perplexity, re-deriving our own int4-protected result (**+0.11%**)
first as a control. **[Measured — controlled benchmark]**

- **On an outlier-heavy model (Qwen2.5-7B), native NVFP4 does not hold — even with the same protection
  mask applied.** It reaches **+2,500% PPL at 4%** where int4-protected holds **+0.06–0.11%**. A
  one-variable swap (per-channel int4 → per-block NVFP4 on the key path) reproduced the collapse. **The
  controlled format swap strongly implicates the per-block scaling structure as the primary source of
  the observed degradation in this test.** **[Measured — controlled benchmark]**
- **On a clean, QK-normalized model (Qwen3-8B), plain NVFP4 already holds (+0.98%) — no protection
  needed.** There we add nothing. **[Measured — controlled benchmark]**

**The tested models illustrate two materially different regimes: models where native FP4 is already
adequate, and models where finer-grained protection remains necessary.**

**These results indicate that native FP4 does not eliminate KVPro's quality advantage on the tested
outlier-heavy model, although broader cross-model and native-Blackwell validation is still required.**

**Conclusion.** Where native FP4 already preserves quality, KVPro may add little. Where block-scaled FP4
fails on retrieval-critical behavior, the tested KVPro format retains a meaningful quality advantage.
**Native Blackwell speed remains unmeasured.**

**Evidence boundaries (explicit).**
- NVFP4 numerics were **emulated on A100** (matches the numerical result, not the silicon).
- **Native Blackwell silicon performance was not measured.** **[Unbenchmarked — native hardware]**
- The current result is **quality evidence, not speed evidence.**
- The **tested model set is limited** (two models, perplexity axis).
- The **fused-INT4 decode opportunity remains unproven.** **[Planned / integration in progress]**

---

### Q11. "Are agentic workloads a good fit — or does the decode penalty kill it?"

**Honest answer.** Agentic is one of our stronger wedges. Three agent traits line up with our strengths:

1. **Context grows** — history, tool outputs, RAG, scratchpad — so KV memory becomes the binding limit
   fast. Our compression yields **up to approximately 1.8× the KV-resident session capacity under
   KV-memory-bound conditions**. **[Measured — controlled benchmark]** Realized *fleet* capacity is not
   the same number — it also depends on **model weights, activations, scheduler behavior, batch size,
   sequence-length distribution, and other GPU-memory consumers.**
2. **Heavy shared prefixes** — the same system prompt + tool definitions repeat across many calls, one
   of the highest prefix-reuse patterns in production. **In primitive-level reuse tests, snapshot/restore
   reduced TTFT by 50–86% per cache hit and improved throughput by 1.2–1.85× at high hit rates; the
   complete warm-tier serving integration is not yet shipped.** **[Measured — reuse primitive;
   Planned / integration in progress]**
3. **Quality-critical** — a cheap wrong token becomes a bad tool call or wrong branch that cascades. We
   hold near-full-precision quality (**100% needle vs ~12% for FP8, same benchmark**).
   **[Measured — controlled benchmark]**

**The honest caveat.** The prefix-reuse payoff depends on **warm-tier serving that is not fully
shipped** — the primitive is measured, the end-to-end serving integration is in progress. So *today* the
reliable agentic win is **density + held quality**; the reuse-driven TTFT/throughput results are
primitive-level, not production-serving.

**The trade-off applies.** A single latency-critical interactive agent is slower on our path
(**0.13–0.67× of BF16, [Measured — controlled benchmark]**) and should stay on full precision. Long
chain-of-thought steps are our least favorable case; short tool-call outputs are more favorable.

**Net conclusion. KVPro is a capacity and fidelity tool for high-concurrency, long-context agent
fleets — not a latency accelerator for a single interactive agent.** Routing rule: capacity-bound,
prefix-heavy, quality-sensitive workloads → KVPro; latency-critical single-stream workloads → BF16.

---

### Q12. "Concretely, what does KVPro do at each memory tier — hot, warm, and cold?"

**Honest answer.** One quality-safe compression plus one snapshot/restore of the compressed
representation, applied across tiers — so the density benefit compounds and the *same* compressed bytes
move between tiers with no additional numerical change.

- **🔥 Hot — GPU HBM (active decode).** Compress in-GPU KV to ~0.5× (**up to approximately 1.8×
  KV-resident session capacity under KV-bound conditions** **[Measured — controlled benchmark]**),
  implying **a modeled reduction of up to approximately 44% in GPU count for the same KV-capacity target,
  before accounting for compute, throughput, scheduling, and operational constraints**
  **[Modeled — capacity assumption]**, at near-full-precision quality (100% needle vs ~12% for FP8,
  **[Measured — controlled benchmark]**). **The honest cost lives here:** decode **0.13–0.67× of BF16**
  **[Measured — controlled benchmark]**, so latency-critical single-stream traffic stays on full
  precision. **The implemented and measured core is hot-tier KV capacity plus held quality.**
- **♨️ Warm — CPU DRAM (reusable prefixes).** Denser reusable KV per GB **[Modeled — capacity]** plus
  **byte-exact snapshot and restore of the compressed KV representation** **[Measured — reuse
  primitive]** — i.e. **lossless transfer and restoration of the already-compressed representation**.
  This means: **no additional numerical change beyond the existing compressed representation during
  snapshot, storage, and restore** — it does **not** mean the compressed representation is mathematically
  identical to the original BF16 KV cache. Reuse tests show **50–86% lower TTFT per hit and 1.2–1.85×
  throughput at high hit rates** **[Measured — reuse primitive]**. **The complete warm-tier serving
  integration is in progress** **[Planned / integration in progress]** — these are primitive-level reuse
  results, not production-serving results.
- **🧊 Cold — NVMe/NAND flash (cross-session, archival).** **~1.8× lower storage requirement for the
  same compressed working set** **[Modeled — capacity]**; storage and restore introduce **no additional
  numerical change beyond the existing compressed representation during byte-faithful storage and
  restore** **[Measured — reuse primitive]**. This reuse pattern is **better suited to
  write-once/read-many reuse than per-token churn, which may reduce endurance pressure; validation on the
  target NAND media is still required.**

| Tier | Component | KVPro benefit | Evidence basis |
|---|---|---|---|
| **Hot** | GPU HBM | ~1.8× KV-resident capacity under KV-bound conditions; quality held | Measured — controlled benchmark; decode cost 0.13–0.67× BF16 |
| **Warm** | CPU DRAM | Denser reusable KV plus byte-exact restoration of compressed representation | Modeled — capacity; Measured — reuse primitive; serving integration in progress |
| **Cold** | NVMe / NAND | ~1.8× lower storage requirement for the same compressed working set | Modeled — capacity; measured snapshot primitive |

**Through-line. The implemented and measured core is hot-tier capacity plus held quality. Warm- and
cold-tier reuse are compounding upside, with complete warm-tier serving still in progress.**

---

*Companion to `KVPRO_INVESTOR_QA.md`. Quality figures are perplexity/needle on standard open models;
NVFP4 was emulated numerically on A100 (matches the numerical result, not the silicon), and native
Blackwell performance was not measured. "Planned / integration in progress" items are not presented as
shipped. This document describes measured outcomes, limitations, and product positioning only; detailed
implementation methods are proprietary, patent-pending, and disclosed only under NDA. Not a
forward-looking guarantee.*

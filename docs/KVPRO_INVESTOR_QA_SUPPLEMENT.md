# KVPro — Investor Q&A Supplement (Blackwell/NVFP4 · Agentic)

**Shareable / non-confidential.** Two additional anticipated-diligence questions, in the same voice as
`KVPRO_INVESTOR_QA.md`: concede the real limit first, label every number **measured** or **modeled**,
don't oversell. States results and positioning, not the method (proprietary / patent-pending — NDA).

---

### Q10. "Doesn't Blackwell's native FP4 (NVFP4) just commoditize this — the hardware does 4-bit KV for free?"

**Honest answer.** On the axis our buyers actually care about — **quality** — we tested this directly
and the answer is **no**; on **speed**, we're honest that it's **open**. We emulated NVFP4's exact
numerics (E2M1 elements + per-16-channel block scale + per-tensor FP32 scale) and measured perplexity,
re-deriving our own int4-protected result (**+0.11%**) first as a control.

- **On outlier-heavy models (Qwen2.5-7B), native NVFP4 does not hold — even with the same protection
  mask bolted on.** It blows up to **+2,500% PPL at 4%** where int4-protected holds **+0.06–0.11%**. A
  one-variable swap (per-channel int4 → per-block NVFP4 on the key path) reproduced the full collapse,
  pinning the cause to NVFP4's **per-block scale**: our per-channel format is load-bearing, and
  Blackwell's block format can't replicate it by adding protection. *(measured — quality)*
- **On clean, QK-normalized models (Qwen3-8B), plain NVFP4 already holds (+0.98%) — no protection
  needed.** There we add nothing. *(measured — quality)*

So the clean statement is: **where native FP4 works, you don't need us; where you need us, native FP4
can't follow** — and the newest models increasingly split into "clean, so NVFP4 is fine" or
"outlier-heavy, so you need per-channel protection." The quality moat survives the hardware.

**Caveats, stated plainly.** This is a **quality/PPL** result on a limited model set; NVFP4 was
**emulated on A100** (it matches Blackwell's *numbers*, not its *silicon*); and NVFP4's **hardware
speed on Blackwell we did not benchmark.** Blackwell is genuinely the right platform to fund a
**fused-INT4 decode kernel** — that decode-speed opportunity is real but **unproven**, and Blackwell
also speeds up the lossy FP4/FP8 alternatives, so on speed we make no claim yet.
*(measured — quality; unbenchmarked — speed)*

---

### Q11. "Are agentic workloads a good fit — or does the decode penalty kill it?"

**Honest answer.** Agentic is one of our stronger wedges, and I'll say plainly which part is **shipped**
and which is **in progress**. Three agent traits line up with our strengths:

1. **Context grows** — history, tool outputs, RAG, scratchpad — so KV memory becomes the binding limit
   fast. Our **~1.8× density (measured)** fits roughly **2× more agents per GPU**.
2. **Heavy shared prefixes** — the same system prompt + tool definitions repeat across thousands of
   calls, one of the highest prefix-reuse patterns in production. Our snapshot/restore is **bit-exact
   (measured)**, and reuse pays **50–86% lower time-to-first-token** and **1.2–1.85× throughput at high
   hit rates (measured)**.
3. **Quality-critical** — a cheap wrong token becomes a bad tool call or wrong branch that cascades. We
   hold **near-full-precision quality (100% needle vs ~12% for FP8, measured)**.

**The honest caveat (don't imply the reuse win is turnkey).** The prefix-reuse payoff depends on
**warm-tier serving that is not fully shipped** — the primitive is measured, the end-to-end serving
integration is **in progress**. So *today* the reliable agentic win is **density + held quality**; the
reuse-driven TTFT/throughput win is proven-in-primitive, not yet a one-switch serving feature.

**And the trade-off still applies.** A **single latency-critical interactive agent** is slower on our
path (**0.13–0.67× decode, measured**) and should stay on full precision. Long chain-of-thought steps
are our least favorable case; short tool-call outputs are more favorable.

**Net:** **net-helps a high-concurrency fleet of long-context, quality-sensitive agents** (density +
quality now, prefix-reuse as warm-tier ships); **not a per-step speed tool for one interactive agent.**
The routing rule is unchanged — capacity-bound, prefix-heavy, quality-sensitive agent traffic to KVPro;
latency-critical single-stream to BF16. *(measured — density/quality/reuse-primitive; in progress —
warm-tier serving)*

---

*Companion to `KVPRO_INVESTOR_QA.md`. Quality figures are perplexity/needle on standard open models;
NVFP4 emulated numerically (matches Blackwell's result, not its silicon). "In progress" items are not
presented as shipped. Method is proprietary / patent-pending — NDA only. Not a forward-looking
guarantee.*

# KVPro — Anticipated Investor Q&A (honest answers)

**For:** the founder, going into a technically‑savvy investor / diligence conversation.
**Style:** concede the real limit first, then the wedge. Every number labeled *measured* or
*modeled*. Do not oversell — this doc is written to build credibility, not to win an argument.

---

### Q1. "Why not just use FP8? It's hardware‑native, simple, and also halves KV memory."
**Honest answer.** FP8 gets you the same ~0.5× KV memory *and* runs at roughly BF16 speed — so on
paper it beats us on speed. The catch is **quality**: on hard long‑context retrieval, FP8 KV scores
around **~12% needle** where KVPro scores **100%, matching full BF16** (*measured*, same benchmark).
So the real comparison isn't "FP8 vs KVPro" — it's **"do you need the quality?"** FP8 is the right
tool when the workload tolerates degraded long‑context recall; KVPro is for when a cheap **wrong**
token has no value (legal, health, finance, agents, RAG). We trade decode speed for the quality FP8
gives up at the same density. Different lanes, not the same fight.

### Q2. "You're not first — KIVI, KVQuant, GEAR, SAW‑INT4 all exist. What's actually defensible?"
**Honest answer.** Correct, and we don't claim to win on **compression ratio** or **"near‑lossless
quality"** — several published methods match or beat us there, and we've retired those claims
internally. What survives scrutiny is **system‑level**: a protected‑KV path that is **paged‑cache
and fused‑kernel compatible**, **transfer‑robust across model families from one calibration with no
per‑family code**, and extends to **byte‑faithful warm‑tier reuse** — a combination the
GPU‑memory‑only methods don't address. The patent posture matches this honesty: the naked elements
(4‑bit KV, outlier protection, paged INT4) are prior art; our filing anchors on the **static,
per‑model, prefix‑cache‑compatible mask** and the **lossless cross‑tier reuse**, not on being first
to compress KV.

### Q3. "Why only 1.8× when 4‑bit should give 4×? And 0.13–0.67× decode speed sounds broken."
**Honest answer.** Two separate things. The **1.8×** is because 4‑bit codes carry a ~25% "sidecar"
of reconstruction labels plus a few protected channels, and then paging/allocation overhead trims
the rest — that's *measured* and expected, not a defect. The **speed** is the real trade‑off: on the
current, unoptimized decode path we run **0.13–0.67× of BF16** because the compressed path does more
per‑byte work and scattered memory reads. We're explicit that this is a **capacity tool, not a speed
tool** — you route memory‑bound traffic to it and keep latency‑critical traffic on BF16. Kernel work
(funded v2) lifts decode toward a **bounded ~0.27–0.30× ceiling — modeled, and never parity.** If a
buyer needs BF16 latency, we're honestly not their tool for that traffic.

### Q4. "Is this a real patent, or is it 'just calibration'?"
**Honest answer.** "Just calibration" is exactly the weak version we're *not* leading with —
importance‑based channel selection alone is close to prior art and is the claim we expect an examiner
to narrow. The defensible insight is counter‑intuitive: most practitioners assume **per‑sequence,
dynamic** protection is optimal; we deliberately use a **single static per‑model mask** *because*
that's what makes cached prefixes reusable across requests (dynamic masks break prefix caching). That
trade — giving up per‑sequence tuning for a system‑level capability — plus **byte‑faithful reuse of
the compressed state**, is the anchor. Beyond the patent, the moat is also **operational**: the
per‑model setup, the serving integration into vLLM, and the correctness engineering are earned and
shipped, not reproducible from a paper abstract.

### Q5. "What breaks — on a new model, at 2% protection, at 70B, or on non‑standard architectures?"
**Honest answer.** Quality is **per‑model calibrated and gated**, so a new model runs the same
~30‑second calibration and a needle test before it ships — *measured* clean on four models across
three families and two scales at 4%. Lower fractions (2–3%) are a density/quality knob we tune per
model, not a universal setting — we'd re‑run the quality gate, not assume it holds. **70B‑class and
tensor‑parallel are not yet verified** — that's an explicit, funded v2 item, and we don't claim it
works until measured. **Non‑128 head dimensions** (e.g. Phi‑3.5) need kernel changes — a separate
project. We'd rather tell you the edges than discover them in your deployment.

### Q6. "Given the speed penalty, how big is the addressable market really?"
**Honest answer.** We scope it deliberately narrow and credit latency‑critical traffic **zero**. The
market is **memory/capacity‑bound serving**: long‑context, high‑concurrency, agentic, and
shared‑prefix/RAG workloads — the fastest‑growing inference segments, and exactly the ones where KV
memory, not decode speed, is the binding limit. On that segment we remove roughly **20–44% of the
GPU bill** at near‑full quality (*measured density, modeled dollars*). If only half a deployment's
long‑context traffic is capacity‑bound, halve the figure — still ~20%. It's not "all inference"; it's
the slice where we're the only option that holds quality at 2× density.

### Q7. "Is the warm‑tier / reuse story real, or aspirational?"
**Honest answer.** The **primitive is proven**: snapshot→restore of compressed KV is **bit‑exact**
(*measured*), so moving it to DRAM/flash and reusing it adds **zero** additional quality loss — a
lossy transport codec can't say that. The **reuse payoff is measured** too: **50–86% lower
time‑to‑first‑token per cache hit** and **1.2–1.85× batch throughput** at high hit rates. What's
**not** finished is the end‑to‑end warm‑tier serving integration — that's in progress and scoped, and
we don't present it as shipped. And to be clear, the NAND *density‑tiering* cleverness is small
(~1.14×, hardware‑capped) — we don't build the case on it; the case is the byte‑faithful reuse.

### Q8. "What's the risk the v2 throughput work simply fails?"
**Honest answer.** The downside is bounded because the **value doesn't depend on it.** Even at
today's 0.13–0.67×, KVPro already wins on **$/request** for capacity‑bound traffic — the throughput
work *widens* the routable envelope and removes friction, it doesn't unlock the core thesis. And the
ceiling is **modeled from first principles (~0.27–0.30×)**, so we're not promising parity and then
hoping; we've told you the physics up front. The larger execution risks are the honest ones: 70B/TP
support and converting one design‑partner deployment into a third‑party‑verified cost/quality case —
which is what the raise funds.

---

**Meta‑note for the room:** the strongest move with a technical investor is to *volunteer* the limits
in Q3/Q5/Q6 before they ask. The credibility you get from "here's exactly where we don't work" is
worth more than any single benchmark — and it's consistent with how everything in this program is
documented (measured vs. modeled, trade‑offs disclosed).

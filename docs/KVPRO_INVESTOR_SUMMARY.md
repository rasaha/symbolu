# KVPro — Results Summary

**Shareable / non‑confidential.** High‑level results for investor conversations. Every figure is
labeled *measured* (observed on real hardware/models) or *modeled* (calculated from measured inputs).
Written to build credibility: the trade‑offs are stated alongside the wins.

---

## One line

KVPro roughly **doubles how much long‑context KV cache fits on a GPU while keeping full‑precision
answer quality** — trading some decode speed for that density. It is a **capacity** tool for
memory‑bound inference, not a speed tool.

---

## Headline results

| Dimension | Result | Basis |
|---|---|---|
| **Quality** | Matches full‑precision on hard long‑context retrieval — **100% needle** vs a leading 4/8‑bit alternative at ~12% | *measured* |
| **Density** | **~2× raw KV slots, ~1.8× net** more sequences per GPU under sustained load | *measured* |
| **Cost** | **~20–44% lower GPU spend** on capacity‑bound long‑context serving | *measured density, modeled dollars* |
| **Decode speed** | **0.13–0.67× of full precision** today (a deliberate trade, not a defect) | *measured* |
| **Warm‑tier reuse** | Compressed cache stored/reused **bit‑exactly**; **50–86% faster time‑to‑first‑token** and **1.2–1.85× batch throughput** at high cache‑hit rates | *measured* |
| **Portability** | Validated on **4 models across 3 families and 2 scales** from one ~30‑second calibration | *measured* |

---

## What's genuinely strong

- **Quality at density.** Most compression buys density by spending accuracy. KVPro holds
  full‑precision‑level accuracy at ~2× density — the differentiator for workloads where a cheap
  **wrong** token has no value (legal, health, finance, agents, RAG). *(measured)*
- **Byte‑faithful reuse.** The compressed cache can be snapshotted to DRAM/flash and reused with
  **zero additional quality loss** — something a lossy transport codec cannot claim. *(measured)*
- **Portable, no per‑model code.** New models pass a short calibration + a quality gate before they
  ship; robustness across families is *measured*, not assumed.

## What we openly concede (the honest limits)

- **Not a speed play.** On today's path decode runs **below full‑precision throughput (0.13–0.67×)**
  because the compressed path does more per‑byte work. We route latency‑critical traffic to full
  precision and send only memory‑bound traffic to KVPro. Funded kernel work targets a **~0.27–0.30×
  ceiling — modeled, and never parity.** *(measured today / modeled ceiling)*
- **Density, not 4×.** 4‑bit codes carry a reconstruction "sidecar," so the realized gain is ~1.8×,
  not 4× — *measured* and expected.
- **Not yet done:** 70B‑class + tensor‑parallel support and end‑to‑end warm‑tier serving are scoped,
  funded v2 items; we don't present them as shipped.

---

## Latest validation (this cycle): the INT8 protected‑sidecar option

We tested storing the small set of high‑precision "protected" channels in **INT8** instead of BF16,
on a real open model (Mistral‑7B) through the real serving path. Findings, all *measured*:

- **Quality: unchanged** — identical retrieval scores, ~99% token‑for‑token agreement vs the BF16
  version.
- **Memory: a little less** — halves that specific sidecar's bytes, which is a **small share** of the
  total cache (low‑single‑digit % of KV) — a density knob, not a step change.
- **Speed: ~3.45% slower** decode end‑to‑end — because the INT8 values are expanded back to BF16
  before the attention step. **No speed benefit.**

**We ship it as an optional, off‑by‑default density setting and make no speed claim for it.** We flag
it here so it is not mistaken for a throughput win — it isn't one.

---

## Where it fits

The market is **memory/capacity‑bound serving** — long‑context, high‑concurrency, agentic, and
shared‑prefix/RAG workloads, where KV memory (not decode speed) is the binding limit. On that slice,
KVPro removes roughly **20–44% of the GPU bill at near‑full quality**. We credit latency‑critical
traffic **zero** — it's the capacity slice where KVPro is, today, the only option that holds quality
at ~2× density.

---

*Figures summarize internal validation on standard open models and benchmarks; detailed methodology
and per‑test data are available under NDA. Nothing here is a forward‑looking guarantee; "modeled"
items depend on stated assumptions.*

# Cognade Labs — Investor Pitchbook

**Five Product Briefs | Prepared April 2026**

---

## Table of Contents

1. [Neural Cloud Scaling Controller](#1-neural-cloud-scaling-controller)
2. [CTM+ / PCAM — Intelligent KV-Cache Eviction](#2-ctm--pcam--intelligent-kv-cache-eviction)
3. [Agentic Framework — Governed Runtime for Autonomous AI Agents](#3-agentic-framework--governed-runtime-for-autonomous-ai-agents)
4. [Conscious Generation LLM](#4-conscious-generation-llm)
5. [Hybrid LLM — Algorithmic Fusion of Attention Mechanisms](#5-hybrid-llm--algorithmic-fusion-of-attention-mechanisms)

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 1. Neural Cloud Scaling Controller
<!-- ═══════════════════════════════════════════════════════════════════ -->

**A four-page introduction for investors**
**Where we are:** Stage 4 complete — shadow mode and recommend mode are production-ready today.

## 1.1 The Problem

### Autoscalers have a blind spot, and it's costing everyone money

Here's something almost nobody outside of SRE teams talks about: every cloud autoscaler in production — Kubernetes HPA, AWS Auto Scaling, Karpenter, Cast AI — has the same blind spot. They can't tell the difference between two very different situations:

> *"Latency is bad because we need more replicas."*

> *"Latency is bad for reasons that more replicas will never fix."*

To the autoscaler, both look identical. And so when latency rises, it scales out. If the real cause was an upstream service failing, or a flaky metric, or backpressure bleeding in from somewhere else entirely, adding replicas doesn't help. The latency stays elevated. The controller sees that and scales out again. And again. Until somebody gets paged because the bill crossed a threshold, or the cluster hits a hard limit. We've all seen this incident. Most of us have been the one on-call when it happened.

### Three ways this quietly burns money every day

| What goes wrong | How it plays out | What it costs |
|---|---|---|
| **A cascading failure upstream** | An upstream service breaks. Latency climbs across everything downstream — no matter how many replicas you add. The controller scales from 4 replicas to 46 before any signal finally reverses. | **4.47x** what was actually needed |
| **Noisy metrics** | Random CPU spikes on ~15% of cycles each nudge the controller to add a replica. Every individual decision looks reasonable. Cumulatively, you end up at 31 replicas when 5 would have been plenty. | **4.37x** what was actually needed |
| **Conflicting signals** | CPU is low, but latency is high. The controller spots the latency anomaly and scales out — but the real problem is a measurement conflict, not a capacity shortage. | Pure waste, no SLO improvement |

### Why the obvious fixes haven't worked

The limitation is baked into the math. Classical autoscalers compute a scaling action from the signal chain `A_t = d_t · G_t · P_t · S_t`. That equation gives you *intent to scale* — it tells you what the metrics are saying right now. What it can't do is look back and ask: **did the last scale-out actually help?** Intent and effectiveness get conflated, and the feedback loop that would catch futile decisions simply doesn't exist.

And the big tools in the market each solve a different part of the puzzle:

- **Karpenter** provisions nodes beautifully — but it doesn't decide whether you should be scaling.
- **Cast AI** picks the right instance type and trims waste — but it never questions whether the scale-out decision was correct in the first place.
- **ScaleOps** predicts load — which is fantastic, until the problem isn't actually a load problem.
- **Kubernetes HPA** reacts to thresholds — clean, simple, and blind to the idea of multi-signal coherence.

Nobody in the market is asking the one question that would fix this: *"Did that last scale-out actually help — and if not, should we really be doing it again right now?"*

### Why this matters to the market right now

FinOps has become a boardroom conversation. Every cloud-native company we talk to has the same complaint in some form: *"We're paying three to five times what we should for scale-outs that don't even improve our SLOs."* The pain has shifted from "how do we scale?" to "why are we wasting so much when we do?" — and the Layer 4 decision-quality gap is exactly where that money is being left on the table.

## 1.2 Architecture: Teaching Autoscalers to Know When They're Wrong

### The core idea, in one sentence

Don't change the controller. Add a second system next to it that watches whether its decisions actually worked, and a third system that blocks the next bad decision when the evidence is in.

It's a small architectural shift with a surprisingly large payoff. Intent, evaluation, and execution become three separate things that talk to each other through clean interfaces.

```
Metrics ──► Controller ──► raw_delta ──► FutilityGuard ──► guarded_delta ──► Actuation
                               │                ▲
                               │                │
                               ▼                │
                        EfficiencyEstimator ────┘
                        (observe + classify)
```

### Layer 1 — The Controller (Intent)

This is the part that already exists in every cluster. It looks at the metrics and computes what it thinks should happen:

```
A_t = damping · gain · plasticity · pressure
```

We leave it **completely alone**. No new thresholds, no retuned weights, no bolted-on inputs. It produces `raw_delta` — its honest best guess — exactly as it always did. This is important: it means the controller doesn't need to be re-certified or re-validated. If your team already trusts it, they can keep trusting it.

### Layer 2 — The EfficiencyEstimator (Evaluation)

This is the new part, and it's doing something surprisingly simple. Every time a scale-out happens, it opens a 5-cycle window and watches what changed:

| What it measures | The question it's really asking |
|---|---|
| CPU per replica, before vs after | Did per-replica load actually drop? |
| p99 latency, before vs after | Did the thing users care about recover? |
| Error rate, before vs after | Did errors go down? |
| Utilization efficiency | Are these new replicas doing actual work, or sitting idle? |

After the window closes, it classifies the event as **HELPING**, **NEUTRAL**, or **NOT_HELPING**. That's it. It never touches the controller. It just builds up an honest record of whether past decisions delivered what they promised.

### Layer 3 — The ScaleOutFutilityGuard (Execution Filter)

This is the part that actually saves money, and it's intentionally conservative. It only blocks a scale-out when the evidence is overwhelming:

1. The estimator has reported NOT_HELPING for **at least 5 cycles in a row**.
2. There are already **at least 20 replicas** running.
3. (Optional) The average confidence across that streak clears a threshold.

And we built in a set of hard constraints that make it safe by construction:

- It **never activates below 20 replicas**. Small clusters get the benefit of the doubt.
- It **never fires on a single bad cycle**. Five consecutive cycles of futility, minimum.
- It **never touches scale-in**. Shrinking capacity always passes through untouched. If anything, we lean toward letting the system release resources.
- It **resets instantly** the moment the estimator sees improvement.

In short: the guard is allowed to say "no" to a scale-out, but only when there's a pile of evidence that the scale-out won't help. It can't say "yes" to anything it wasn't already going to do.

### Where this sits in the bigger picture

Think of cloud autoscaling as an 8-layer stack — from raw metric sensing at the bottom to business policy at the top. We live in the one layer nobody else has filled: **Layer 4, Decision Quality.** That's the layer that asks, *"Given everything we're seeing, should we actually scale right now?"*

```
┌─────────────────────────────────────────────────────────┐
│ GOVERNANCE  L7  Business policy, approvals              │
│             L6  Observability & proof-of-value          │
│             L5  Safety bounds (rate limits, cooldown)   │
├─────────────────────────────────────────────────────────┤
│ INTELLIGENCE  L4  Decision Quality   ← US               │
│                   A_t = d_t · G_t · P_t · S_t           │
│               L3  Prediction (ScaleOps lives here)      │
├─────────────────────────────────────────────────────────┤
│ DATA PLANE  L2  Cost optimization (Cast AI lives here)  │
│             L1  Provisioning (Karpenter lives here)     │
│             L0  Sensing (Prometheus lives here)         │
└─────────────────────────────────────────────────────────┘
```

**We wrap; we don't replace.** The controller runs quietly alongside HPA, reads the same Prometheus you already have, and hands off to Karpenter on the other side. No rip-and-replace, no vendor migration, no midnight cutover. A platform team can drop us in on a Tuesday and start seeing proof-of-value by Friday.

## 1.3 Competitive Landscape: Who We're Standing Next To

### The crowded part of the stack, and the empty part

Cloud autoscaling tooling has gotten genuinely good over the last five years. Node provisioning is solved. Cost optimization is solved. Prediction is solved. Observability is overflowing. What *isn't* solved — and what almost nobody is even looking at — is whether any of those decisions actually worked after the fact. That's the question we ask, and it's the reason we don't fit neatly into any of the buckets a platform team will already recognize.

The table below places us against the tools we get compared to in investor conversations and SRE channels. For each one, we say *what they do well*, *how we differ*, and *why that difference is actually an advantage* rather than a positioning game.

| Category | Representative players | What they ship | How we differ — and why we're better |
|---|---|---|---|
| **Reactive autoscalers** | Kubernetes HPA, KEDA, AWS Auto Scaling | Threshold- or event-driven rules that compute a scaling action from current metrics. Clean, fast, built-in. | HPA and KEDA are brilliant at computing *intent to scale*. Neither one ever looks back to ask whether the last action helped. **Better because:** we are the feedback loop they don't have. HPA keeps producing `raw_delta`; we observe whether the last `raw_delta` did any good and filter the next one if the evidence says no. A cluster running HPA can turn us on in shadow mode with zero configuration changes to HPA itself. |
| **Node provisioning** | Karpenter (AWS), Cluster Autoscaler, Azure AKS autoscaler | Just-in-time node materialization, bin-packing, instance-type selection. The part that turns a replica-count delta into actual compute. | Karpenter answers *"how do we materialize the scale decision?"*. We answer *"should the scale decision be made at all?"*. Different layers, different questions. **Better because:** every futile scale-out we catch is a Karpenter provisioning event that never needs to run. The savings compound: no extra replica cost, no extra node cost, no extra provisioning churn, no extra scheduling noise downstream. We make Karpenter's job smaller, not harder. |
| **Cost optimization / FinOps** | Cast AI, Kubecost, Spot.io (NetApp Spot), StormForge | Pick cheaper instance types, surface overprovisioning, right-size requests/limits, negotiate spot and reserved pricing. | These tools make the decisions you already made *cheaper*. We question whether the decision should have been made. **Better because:** a scale-out that never happens is 100% cheaper than any rightsizing can make it. Our savings stack on top of Cast AI / Kubecost / Spot — a cluster running all four sees the L4 decision-quality cut *first*, then the L2 cost optimization applied to whatever is left. The economics compose; they don't conflict. |
| **Predictive autoscaling** | ScaleOps, Google Vertical Pod Autoscaler's predictive mode | ML-driven load forecasting. Pre-scales for known diurnal, seasonal, and bursty workloads. | Prediction answers *"what will the load be?"*. We answer *"given the signal we're seeing, should we take the action the controller wants?"*. Prediction is excellent when the problem is a load problem — but when the root cause isn't load (upstream failure, noisy metrics, flaky probe, conflicting signals), a confident prediction makes things worse, not better. **Better because:** we compose with prediction cleanly. ScaleOps tells the controller what's coming; we verify whether the actions taken in response actually helped. Prediction + feedback is strictly stronger than prediction alone. |
| **Observability / AIOps** | Datadog, New Relic, Dynatrace, Grafana Cloud | Anomaly detection, alert correlation, incident summarization, dashboards. Some early "suggest an action" surfaces. | Observability vendors watch the system and *tell humans* what's wrong. We sit *inside* the control loop and stop bad actions before they ship. **Better because:** we are a closed-loop controller, not an alerting surface. Observability tools make incidents legible after the fact; we prevent one of the specific incidents — runaway scale-out under futile conditions — from happening in the first place. An SRE team using Datadog for visibility and us for control is using each tool for what it's actually good at. |
| **In-house SRE tooling** | Bespoke Slack bots, on-call runbooks, custom HPA wrappers each team writes in-house | *"When HPA fires five times in a row and nothing's improving, page me and we'll look at it."* Every mature SRE team has eventually written some version of this. | We are that runbook — minus the human in the middle, minus the ambiguity about exactly when to fire, minus the 228+ unit tests each team rewrites from scratch. **Better because:** the product is off-the-shelf, ablation-validated, safety-constrained by construction, and production-grade today. SRE teams get back the time they were spending babysitting the autoscaler, and they get to spend it on actual incidents instead. The bespoke runbook stops being a bus factor. |

### Why the overall bet is better, not just different

- **We occupy a layer nobody else is in.** Every competitor in the table above operates at L0–L3 (sensing, provisioning, cost, prediction) or at L5–L7 (safety bounds, observability, governance). **Layer 4 — decision quality — is empty in the market.** We are the first tool in this space whose entire purpose is to ask *"did the last action actually work, and if not, should we really do it again?"*.
- **We wrap, we don't replace.** HPA stays. Karpenter stays. Cast AI stays. ScaleOps stays. Datadog stays. The platform team installs us in shadow mode with zero write permissions — no configuration changes to any other tool in the stack, no midnight cutover, no vendor migration. This is a strictly additive product, which is the opposite of how every other FinOps vendor enters a new customer.
- **Safety by construction.** 19 adversarial scenarios, **zero catastrophic failures, zero severe failures, zero SLO regressions, zero false positives**. The guard can only say "no" to a scale-out — it can never say "yes" to an action the controller wasn't already going to take. That's a property no learned AIOps system can claim, and it's why we can ship on a Tuesday without a change-management committee and a six-week pilot.
- **Proof-of-value is free.** Shadow mode runs read-only, auto-generates proof-of-value reports, and costs the customer nothing to try. A platform team can turn us on, watch for two weeks, and see exactly what we *would* have saved them — without adopting any dependency, signing any contract, or taking any production risk. No other tool in this space offers that kind of zero-commitment trial, because no other tool can: they all have to write something to work.
- **The economics compose.** Every other vendor in the table saves money by making the thing you're already doing cheaper or faster. We save money by *not doing the thing*. A scale-out that doesn't happen is 100% cheaper than any rightsizing, spot-instance swap, or bin-packing optimization can ever make it — and those savings are additive to whatever the rest of your stack is already doing.

### In one sentence

Every other tool in this market either **scales you faster** (HPA, Karpenter, KEDA), **scales you cheaper** (Cast AI, Kubecost, Spot), **predicts what to scale** (ScaleOps), or **tells you when you scaled wrong after the fact** (Datadog, New Relic). We're the only one that **stops the wrong scale-out from shipping in the first place** — and we do it as a wrap around the stack you already have, not as a replacement for anything in it.

## 1.4 What We've Proven and What's Next

### 19 adversarial scenarios, and what happened

We didn't benchmark this on a friendly load test. We built 19 deliberately nasty scenarios covering signal corruption, actuation delays, system shocks, budget constraints, and controller pathologies — the kinds of things that quietly break autoscalers in production.

#### Safety first (because it's the first thing investors ask)

| Metric | Result |
|---|---|
| Catastrophic failures | **0** |
| Severe failures | **0** |
| SLO regressions across all 19 scenarios | **0** |
| Severity regressions | **0** |
| False positives (beneficial scale-outs blocked by mistake) | **0** |

This is the headline we're proudest of. We built a system that can only make things better or leave them alone — and it held that line across every single scenario we threw at it. When the guard isn't needed, it's invisible. When it is needed, it fires. That's the whole product promise, and it held.

#### The money story

| Scenario | Before the Guard | After the Guard | What we saved |
|---|---|---|---|
| cascading_failure | 4.47x optimal | **3.36x optimal** | −1.11x |
| noisy_spikes | 4.37x optimal | **3.60x optimal** | −0.77x |
| cold_start_amplification | 3.31x optimal | **2.93x optimal** | −0.38x |
| hidden_demand | 2.41x optimal | **2.21x optimal** | −0.20x |
| coherence_oscillation | 3.77x optimal | **3.67x optimal** | −0.10x |

#### How often did it actually step in?

| Metric | Value |
|---|---|
| Total scale-out events observed | 649 |
| Blocked as provably futile | **87 (13.4%)** |
| Scenarios where the guard intervened | 5 of 19 |
| Scenarios where the guard stayed out of the way | 14 of 19 |

**The one-line version:** we cut waste from 4.5x to 3.4x of optimal cost with **zero SLO regressions** — and that's something none of the incumbents can do today, because they don't have the feedback loop to know when they're wrong.

### What's already built

This isn't a research prototype. It's been staged, tested, and written to be deployable.

| Stage | What it is | Tests |
|---|---|---|
| Stage 1 | Core control library — 12 parameters, every one ablation-validated | 87 unit tests |
| Stage 2 | Prometheus integration and signal pipeline | 42 unit tests |
| Stage 3 | **Shadow mode** — read-only, runs alongside HPA, generates proof-of-value reports | 38 unit tests |
| Stage 4 | **Recommend mode** — human-in-the-loop with Slack and PagerDuty integration | 39+ unit tests |
| Bootstrap | Learning-phase elimination, so there's no cold-start warm-up period | 22 unit tests |

**Altogether:** 27 Python source files, 228+ unit tests, all passing.

### What's next

| Stage | What we're building | Why it matters |
|---|---|---|
| **Stage 5** | Active mode — bounded autonomous control, scaling without waiting for human approval | Unlocks the first paid deployments and lets customers see real FinOps savings on live workloads |
| **Stage 6** | Learning loop and multi-service support — auto-tune the 12 parameters from outcome data via the L6 → L4 feedback path | Every customer makes the controller smarter, and the system starts recognizing cross-service patterns |
| **Layer 3** | Prediction module — proactive scaling driven by the replay buffer and historical data | Puts us head-to-head with ScaleOps on seasonal and bursty workloads |
| **Layer 2** | Cost optimization integration — pull Cast AI / Kubecost constraints directly into the decision equation | A single decision surface that balances FinOps and reliability together |

### Why we're raising, and what we're asking for

We are the **decision-quality layer** for cloud autoscaling — the missing piece between "what's happening" and "what should we do about it." The product is validated, production-grade, and genuinely easy to try today: shadow mode has zero write permissions and auto-generates proof-of-value reports, which means any platform team can turn it on, watch for two weeks, and see exactly what it would have saved them without taking on any risk.

We're raising to fund Stage 5 (active mode), land our first design-partner deployments, and build out the learning loop that turns every customer into a self-improving control surface. If that sounds like the kind of problem you want to help solve, we'd love to keep talking.

> *"Scale because it works, not because the metrics say so."*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 2. CTM+ / PCAM — Intelligent KV-Cache Eviction
<!-- ═══════════════════════════════════════════════════════════════════ -->

**Cognade Labs | Intelligent KV-Cache Eviction for LLM Inference**
*Prepared April 2026*

## 2.1 The Problem

### LLM inference is becoming memory-bound, and today's eviction heuristics are too shallow.

As context windows grow, the dominant serving bottleneck shifts from
pure matrix math toward KV-cache pressure. The **KV-cache** — the
per-request memory that stores every token's key and value tensors
so the model does not recompute them on every generation step — is
now the largest single consumer of GPU HBM in most inference
deployments.

A single Mistral-7B request at 32K context can consume on the order
of ~2 GB of KV-cache in bf16. An A100-80GB running tens of
concurrent requests can dedicate the majority of its HBM to
KV-cache. When the cache is full and a new request arrives, the
serving system must **evict** — decide which cached blocks to throw
away to make room.

In many serving stacks, the effective eviction policy remains
**LRU-like** — dominated by recency and largely blind to
transformer-specific block value. LRU knows one thing: *when was
this block last touched?*

LRU does not know:

| What LRU misses | Why it matters |
|---|---|
| Whether a block contains an **attention sink** (position 0, BOS token) that the model attends to on every step | Evicting a sink block forces a full recomputation that destroys p99 latency |
| Whether a block is from a **global-context layer** (early transformer layers handling long-range dependencies) or a **local-syntax layer** (late layers handling short-range grammar) | Global-context blocks are expensive to re-read if evicted; local-syntax blocks are cheap to recompute |
| Whether the model's **attention pattern around a block is changing** — signaling it will be re-read with full attention soon | Evicting a block right before it is needed is the most expensive possible eviction |
| Whether a block contains a **structural boundary** (sentence start, paragraph break, discourse marker) that anchors the attention pattern for multiple heads | Boundary blocks are disproportionately attended to; losing them degrades quality across the whole context |

The result: production inference operators overprovision HBM,
cap concurrent requests below what the hardware can support,
accept p99 latency spikes from bad evictions, and spend
engineering time building workarounds (prompt caching, chunked
prefill, aggressive context truncation) for a problem that should
be solved at the eviction-policy layer.

### Why this is a growing problem, not a stable one

Context windows are growing (32K → 128K → 1M+). Agent
frameworks concatenate tool results, retrieved chunks, and
conversation history, pushing real-world context lengths into the
tens of thousands of tokens on routine requests. KV-cache
pressure grows linearly with context length, but eviction-policy
quality determines whether that pressure translates into latency
spikes, quality degradation, or just a slightly smaller batch. As
context grows, the gap between "evict the right block" and
"evict the wrong block" widens — and LRU, which cannot
distinguish between the two, becomes increasingly costly.

Most provider-side mitigations address KV pressure indirectly —
through pricing (OpenAI's long-context tiers), prompt caching
(Anthropic), context management (chunked prefill), or paging
(vLLM's paged attention) — rather than through a multi-signal
eviction policy that reasons about block value directly.

## 2.2 The Architecture

### CTM+ / PCAM — one specification, one runtime, seven scoring signals

CTM+ is a **canonical KV-cache eviction policy specification** —
the scoring math, the classification semantics, and the
sequence-lifecycle rules that decide which blocks deserve to stay
in HBM and which can be safely evicted. PCAM is the **runtime
backend** that implements CTM+ bit-for-bit, exposes it through a
small Python API, and plugs into real inference runtimes (vLLM,
HuggingFace) through narrow adapters.

### The scoring model

Every candidate block is scored by up to seven signals (six additive,
one multiplicative), with phase-aware weights that shift between
prefill and decode:

```
score = w_r · recency                      signal 1: when was it last read?
      + w_f · frequency                    signal 2: how often is it read?
      + w_a · attention_ema                signal 3: how much attention does it receive?
      + w_s · importance                   signal 4: is it a sink, entity, or filler?
      + w_d · boundary_score               signal 5: does it anchor a structural boundary?
      + w_u · instability_hint             signal 6: will it be re-read soon?
      + entity_bonus                       (conditional: +0.5 for high-attention non-sinks)
      × band_class                         signal 7: is it from a global or local layer?
```

Signals 1–4 are the **base model**, locked by an internal ADR
(architectural decision record) and enforced by a 20-test
bit-parity harness on every commit. These capture past behavior:
how recently and frequently a block was accessed, how much
attention it received, and whether it is structurally important
(sink blocks are pinned and never evicted).

Signals 5–7 are **FSCS-derived extensions** — three diagnostic
signals identified during our Text-FSCS research and folded into
the memory-policy layer where they naturally belong. Together they
refine **eviction-risk estimation**: boundary sensitivity captures
structural importance, band class captures expected miss cost by
layer role, and instability hints at near-future reread likelihood.
They are default-off, caller-supplied, and backward-compatible —
the base four-signal model is unchanged when they are not activated.

### Two-layer architecture

```
      Inference Runtime (vLLM, HuggingFace, custom)
                     │
                     ▼
      ┌──────────────────────────────────┐
      │            CTM+                  │   ← Canonical spec
      │   Phase-aware scoring            │      (4 base + 3 FSCS-derived)
      │   Count-Min frequency sketch     │
      │   Sink / entity / filler         │
      │   Sequence lifecycle             │
      └──────────────┬───────────────────┘
                     │  vendored + parity harness
                     ▼
      ┌──────────────────────────────────┐
      │         PCAM runtime             │   ← Consumable backend
      │   KVCachePolicy API              │
      │   PCAMEvictor (vLLM adapter)     │
      │   Tier hints (HOT/WARM/COLD)     │
      │   Trace replay + benchmarks      │
      │   Shadow + active mode bridges   │
      └──────────────────────────────────┘
```

**CTM+ is the spec. PCAM is the runtime. The parity harness is
the only sync mechanism.** There is no bridge class, no adapter
layer, no second scoring path. When CTM+ changes upstream, PCAM
re-vendors and the parity harness catches any divergence. This
discipline is what makes the system trustworthy enough for a
production SRE to turn on.

### How the FSCS-derived signals were identified

The three extension signals came from a separate research program
(Text-FSCS) that explored dynamic attention-compute reduction on
frozen Mistral-7B. That research produced a measured `r* = 6.7%`
quality-preservation frontier for attention routing, along with
three diagnostic observations about attention behavior that turned
out to be more valuable as **cache-policy inputs** than as
standalone attention modifications:

- **Boundary tokens are attention sinks** — evicting them causes
  disproportionate damage regardless of their recency
- **Layer depth predicts block importance** — global-context layers
  produce blocks that are expensive to re-read; local-syntax layers
  produce blocks that are cheap to recompute
- **Attention instability predicts future re-reads** — blocks in
  unstable regions will be re-read with full attention within a few
  steps, making their eviction costly

These observations were implemented as CTM+/PCAM scoring signals
(not as transformer modifications) and validated end-to-end on real
Mistral-7B KV-cache data.

## 2.3 Competitive Landscape

CTM+/PCAM sits at an unusual seam in the LLM serving stack — **below
the model**, **above the hardware**, and **inside the runtime** — so
"competition" is better understood as a set of adjacent categories
that each address KV-cache pressure in a different way. The table
below places us against each of them, stating for every row both
*how* we differ and *why* that difference is an advantage for a
production operator who cares about throughput, p99 latency, and TCO.

| Category | Representative players | What they ship | How CTM+/PCAM differs — and why it is better |
|---|---|---|---|
| **Production inference engines** | vLLM, TGI, TensorRT-LLM, SGLang, LMDeploy, NVIDIA Triton | High-performance serving runtimes that own batching, paged attention, continuous batching, and KV-cache allocation. Their eviction story is typically LRU-shaped or fixed-size paging. | We do not replace vLLM — we plug into it. PCAM ships as a drop-in `KVCachePolicy` / `PCAMEvictor` adapter that makes the engine's block-pool decisions **attention-aware** instead of recency-only. **Better because:** the operator keeps every other optimization the serving engine already ships (paged attention, continuous batching, CUDA graphs) and simply upgrades the one decision that determines whether a good batch is sustained under pressure or destroyed by a bad eviction. |
| **KV-cache compression research** | H2O (Heavy-Hitter Oracle), StreamingLLM, Scissorhands, SnapKV, FastGen, PyramidKV, KIVI (KV quantization) | Academic projects that drop, quantize, or compress KV entries using a single attention-derived heuristic (heavy-hitters, sink tokens, head-level pruning). | Research methods typically pick **one** signal — usually attention mass over a window — and apply it uniformly. CTM+ is a **seven-signal** scored policy (recency · frequency · attention EMA · importance · boundary · band class · instability) with phase-aware weights and a bit-parity-enforced spec. **Better because:** a single-signal heuristic overfits to its validation workload and silently fails on adjacent ones, whereas a multi-signal scored policy degrades gracefully and can be tuned per-signal against operator telemetry. Many of these methods also require a model-side change; CTM+/PCAM does not. |
| **Provider-side prompt caching** | Anthropic prompt caching, OpenAI prompt caching, Google Gemini context caching, DeepSeek context caching | API-level features that let callers mark a prompt prefix as cacheable so the provider can reuse its KV state across requests at a billing discount. | Prompt caching answers *"can I reuse this exact prefix?"* — a hit/miss question on whole prefixes. It does not answer *"which blocks inside the live cache should I evict when memory is full?"* **Better because:** we are complementary, not competitive — an operator who runs CTM+/PCAM *under* a provider's prompt cache gets both effects (free prefix reuse at the API boundary *and* intelligent block-level eviction at the runtime). For self-hosted inference where no provider cache exists, CTM+/PCAM is the only layer that reasons about block value at all. |
| **Context-management strategies** | Chunked prefill, sliding-window truncation, RAG-instead-of-long-context, context summarization, ring attention | Avoid KV-cache pressure by shortening the context the model sees or distributing it across devices. | These approaches *sidestep* the eviction problem by making the context smaller or spread thinner. That works until the workload needs the full context — agentic tool chains, long chat histories, large retrieved corpora — at which point the eviction decision comes right back. **Better because:** CTM+/PCAM lets the operator keep the full context *and* run more concurrent requests, instead of forcing a quality trade-off at the application layer. Chunked prefill in particular is complementary — a chunked-prefill scheduler on top of CTM+ gets the benefit of both optimizations. |
| **Attention-mechanism modifications** | Sliding-window attention (Mistral), StreamingLLM attention sinks, sparse/local attention, MQA/GQA, Longformer-style dilated attention | Model-architecture changes that reduce the KV footprint or attention pattern to make long context tractable at training time. | These require a **training-time or model-level change**, so they only help workloads that happen to run on a model built around them. CTM+/PCAM is a **runtime-only policy** that works on a frozen, unmodified model. **Better because:** an operator can turn CTM+ on tomorrow for any model they already serve — no retraining, no re-export, no weight rewrite — and every new model added to the fleet inherits the optimization for free. |
| **Hardware / memory-tiering approaches** | CXL memory expanders, FlexGen (CPU/SSD offload), DeepSpeed-Inference ZeRO-Inference, NVIDIA Grace-Hopper unified memory | Increase effective KV capacity by paging to tiered memory or adding physical DRAM behind the GPU. | Hardware tiering makes the cache *bigger*; it does not make it *smarter*. Evicting the wrong block is still expensive, and moving the wrong block to a slower tier is often worse than evicting it outright. **Better because:** CTM+ emits `HOT / WARM / COLD` tier hints alongside eviction decisions, so a memory-tiered system driven by CTM+ scores gets the right blocks in the right tier — and our FPGA/ASIC path means the policy can eventually move into the memory controller itself, where a pure-software LRU cannot. |
| **Classic OS / DB cache-replacement policies** | LRU, LFU, ARC, 2Q, LIRS, CLOCK-Pro, W-TinyLFU | General-purpose cache-replacement policies from the systems and database literature, often embedded in inference engines "because that's what every cache uses." | These policies treat every cache block as fungible. A transformer KV-cache block is not fungible — a sink block is irreplaceable, a late-layer local-syntax block is nearly free, and a block adjacent to an unstable attention region will be re-read with full attention within a few steps. **Better because:** CTM+ is the first eviction policy that knows the difference, and its scoring math is a strict superset of the classical ones (you recover LRU or LFU as a degenerate case by zeroing all other weights). |

### Why the overall bet is better, not just different

- **Multi-signal is a superset of single-signal.** Every incumbent in this table bets on one axis — recency for LRU, heavy-hitters for H2O, prefix equality for prompt caching, more DRAM for CXL. CTM+ is a scored composition of seven signals with phase-aware weights, so it *contains* those bets as special cases and adds the ones they are missing (boundary, band class, instability). An operator does not lose anything by switching to CTM+; they strictly gain signals.
- **Runtime-only, model-agnostic.** No retraining, no attention-pattern change, no weight rewrite. An operator running Mistral, Llama, Qwen, or DeepSeek can adopt CTM+/PCAM without touching the model or the tokenizer — which is exactly why we ship into an existing vLLM deployment as a `KVCachePolicy` adapter and nothing else.
- **Spec-and-runtime separation is the moat.** CTM+ is a spec locked by an ADR and enforced by a 20-test bit-parity harness; PCAM is the runtime that implements it bit-for-bit. That discipline is what makes the policy trustworthy enough for a production SRE to turn on — and it is the thing research-paper methods on this list structurally cannot match, because they ship a single code artifact rather than a spec with independently testable consumers.
- **Software today, silicon tomorrow.** Because the policy is a scored math object (not a learned model, not a trained heuristic), it has a credible path from a PCAM software runtime → an FPGA prototype → a memory-controller ASIC or CXL expander. None of the other categories in this table — eviction, compression, prompt caching, attention modification — has a scored math spec that maps cleanly into RTL, and we already have SystemVerilog RTL with a cocotb parity harness as evidence of that path.
- **Composes with, rather than replaces, the rest of the stack.** CTM+/PCAM is additive to paged attention, chunked prefill, prompt caching, CXL tiering, and KV quantization. The competitive question is never *"CTM+ or vLLM?"* or *"CTM+ or prompt caching?"* — it is *"with or without the scored eviction layer underneath?"*

### In one sentence

Classical cache policies treat every block as fungible, research KV
compressors pick one attention-derived signal, provider prompt caches
answer hit/miss on whole prefixes, and hardware tiering makes the
cache bigger. **CTM+/PCAM is the only policy that knows a transformer
KV-block is not fungible** — that a sink is irreplaceable, a
late-layer local-syntax block is nearly free, and a boundary-anchoring
block must not be evicted a moment before it is re-read — and it is
the only one of these categories with a credible path from a Python
policy today to a memory-controller ASIC tomorrow.

## 2.4 What Is Proven and What Is Next

### Benchmark evidence (CTM+ core, across representative cache-sensitive workloads)

| Workload | LRU baseline | CTM+ | Delta |
|---|---|---|---|
| **LLM inference (vLLM)** | **32 concurrent** | **48 concurrent** | **+50%** |
| **LLM p99 latency** | **12ms** | **8.5ms** | **−29%** |
| Hotspot (batch ML) | 76.4% hit rate | 94.2% | +17.8% |
| Database (TPC-C) | 125K txn/sec | 142K txn/sec | +13.6% |
| 5-year TCO (100 GPUs) | $5.85M | $4.01M | −31% |

*LLM rows bolded as the primary target workload. Database and batch
ML rows demonstrate cross-domain applicability of the scoring model.*

### FSCS-derived signal integration validation (real Mistral-7B trace)

| Metric | Baseline (4 signals) | Enhanced (7 signals) |
|---|---|---|
| Eviction rounds | 4 | 4 |
| Eviction selections emitted | 1,022 | 192 |
| Rounds with changed decisions | 0 | **4 (100%)** |
| Individual block choices changed | — | **1,108** |

*Interpretation: policy behavior changed materially; serving
benefit not yet measured.*

**Every single eviction round made different victim choices** when
the three FSCS-derived signals were active. The enhanced policy
protected boundary blocks, global-context blocks, and unstable
blocks that the baseline would have evicted. Whether this
conservatism improves downstream serving quality (hit rate, latency,
concurrent requests) is the next calibration step. 276 unit tests
pass with zero regressions.

### What is implemented today

| Component | Status | Evidence |
|---|---|---|
| CTM+ scoring spec (4-signal, ADR-locked) | ✅ Production-ready | 20-test parity harness, vendored reference |
| PCAM Python runtime (`KVCachePolicy`) | ✅ Consumable API | Phase 1-5 complete, 276 tests |
| vLLM integration (shadow + active mode) | ✅ Implemented + unit-tested | 23 active-mode tests, mock queue |
| FSCS-derived signals (boundary, band, instability) | ✅ Integrated + validated | 36 signal tests, real Mistral trace |
| Annotated trace capture from Mistral-7B | ✅ Pipeline working | `pcam_fscs_trace_capture.py` |
| Baseline vs enhanced replay comparison | ✅ Pipeline working | `pcam_fscs_replay_compare.py` |
| FPGA hardware (SystemVerilog RTL) | ✅ Credibility artifact | cocotb parity harness |

### Honest caveats

- The FSCS signal validation shows **eviction-decision impact**, not
  **cache-hit-rate improvement**. The 100% decision-change result
  means the signals work; whether those changes improve serving
  quality requires a serving-tier benchmark under load.
- The signal weights (boundary=0.10, instability=0.15, band=
  {1.3, 1.0, 0.8}) are starting points, not calibrated values.
- The attention mass in the current trace is a position-based proxy,
  not real per-block attention weights. A higher-fidelity trace
  would use `output_attentions=True`.
- The CTM+ benchmark numbers (hit rate, concurrent requests, TCO)
  are from the full CTM+ stack; the PCAM-specific serving-tier
  numbers require one live GPU closure run.

### Next steps

| Step | What it proves | Cost |
|---|---|---|
| **FSCS signal weight calibration** | Do the signals improve cache hit rate, not just change decisions? | Days (pipeline built) |
| **Live GPU closure run** | PCAM serving-tier throughput/latency vs vLLM default LRU | ~1 engineer-hour |
| **FPGA prototype** (Xilinx Alveo) | RTL at 250MHz, <50ns latency | 2–3 months |
| **Design-partner pilot** | Real inference workload with real quality/latency metrics | Quarters |
| **ASIC controller** | CXL memory expander or GPU-side HBM controller | 12–18 months |

### The ask

We are raising seed to fund the FPGA prototype, land the first
design-partner deployments, and calibrate the FSCS-derived scoring
signals against real serving workloads. The software stack is built, tested, and integrated end-to-end for
policy execution and trace-driven validation; the remaining step is
serving-tier closure under live load. The capital is for hardware,
partners, and the serving-tier benchmark that converts "decisions
changed" into "quality improved."

> *"Seven signals. Every block in the right tier. Every eviction justified."*

*Modules: `CTM_plus/KVPolicy/`, `simulator/pcam/`, `symbolu/fscs/`*
*276 tests · 20-test parity harness · 36 signal tests · real Mistral-7B validation*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 3. Agentic Framework — Governed Runtime for Autonomous AI Agents
<!-- ═══════════════════════════════════════════════════════════════════ -->

*(content to follow)*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 4. Conscious Generation LLM
<!-- ═══════════════════════════════════════════════════════════════════ -->

*(content to follow)*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 5. Hybrid LLM — Algorithmic Fusion of Attention Mechanisms
<!-- ═══════════════════════════════════════════════════════════════════ -->

*(content to follow)*

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu`*

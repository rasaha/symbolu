# Cognade Labs — Investor Pitchbook

**Five Product Briefs | Prepared April 2026**
*Contact: Rakesh Mohan — Cognade Labs*

---

## Executive Summary

Cognade Labs builds **infrastructure-layer intelligence for AI systems and cloud operations** — the decision-quality, memory-policy, governance, and generation layers that sit between raw compute and reliable production behavior.

Our thesis is that the next wave of value in AI infrastructure comes not from bigger models or faster hardware, but from **smarter decisions at the seams** — where an autoscaler decides whether to scale, where an inference engine decides which cache block to evict, where an agent decides whether to execute a tool call, and where a language model decides which token to emit next. Each of those seams is currently handled by a shallow heuristic, a single-signal policy, or no policy at all. We build the multi-signal, feedback-aware, governance-ready layers that fill those gaps.

Five products, one stack:

| # | Product | Layer | One-line summary | Stage |
|---|---|---|---|---|
| 1 | **Neural Cloud Scaling Controller** | Cloud decision quality | Stops futile scale-outs before they ship — zero SLO regressions across 19 adversarial scenarios | Shadow + recommend mode production-ready |
| 2 | **CTM+ / PCAM** | KV-cache eviction | Seven-signal scored eviction policy for LLM inference — +50% concurrent requests, −29% p99 latency vs. LRU | Software production-ready; FPGA path started |
| 3 | **Agentic Framework** | Agent governance | Governed runtime where `cancel → budget → approve → execute` is a tested invariant, not middleware | v1.9.0, 1,550+ tests, 2 internal pilots |
| 4 | **Conscious Generation LLM** | Token selection | Multi-field token evaluation on frozen Mistral-7B — ~5M trainable params, interpretable 32D state | Phase adapter live at inference; full field integration Q1–Q2 |
| 5 | **Hybrid LLM** | Long-context attention | Serial fusion of linear, local, and quadratic attention over shared phase memory — O(n) long-range, O(n·k) precision | Training stack built; external benchmarks Q1 |

The products compose vertically: the **Hybrid LLM** provides the long-context attention substrate, the **CG LLM** adds multi-field token evaluation and an interpretable internal state, the **Agentic Framework** consumes that state for signal-enriched governance, **CTM+/PCAM** manages the KV-cache that makes inference affordable, and the **Cloud Scaling Controller** ensures the infrastructure underneath scales only when scaling actually helps. Each product is independently valuable; together they form a full-stack AI infrastructure company.

---

## Table of Contents

1. [Neural Cloud Scaling Controller](#1-neural-cloud-scaling-controller)
2. [CTM+ / PCAM — Intelligent KV-Cache Eviction](#2-ctm--pcam--intelligent-kv-cache-eviction)
3. [Agentic Framework — Governed Runtime for Autonomous AI Agents](#3-agentic-framework--governed-runtime-for-autonomous-ai-agents)
4. [Conscious Generation LLM](#4-conscious-generation-llm)
5. [Hybrid LLM — Algorithmic Fusion of Attention Mechanisms](#5-hybrid-llm--algorithmic-fusion-of-attention-mechanisms)
6. [Company Summary — Composition, Evidence & Ask](#company-summary)

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 1. Neural Cloud Scaling Controller
<!-- ═══════════════════════════════════════════════════════════════════ -->

**Stage 4 complete** — shadow mode and recommend mode are production-ready today.

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

**Intelligent KV-Cache Eviction for LLM Inference**

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
this block last touched?* It does not know:

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

**Governed Runtime for Autonomous AI Agents** — v1.9.0

## 3.1 The Problem

### Enterprises want autonomous agents. Governance is blocking deployment.

The last 18 months produced a wave of agent frameworks — LangChain,
LangGraph, CrewAI, AutoGen, AWS Bedrock Agents, Vertex AI Agent Builder.
They have made it straightforward to wire an LLM to a tool-calling loop.
What remains genuinely hard is the layer between *"the model decided to
act"* and *"the action executed against a production system"* — the
governance, approval, budget, and audit layer that regulated buyers
require before an autonomous agent can be put in front of customers,
money, or infrastructure.

In enterprise pilots we and our design partners have observed, four
questions consistently come up early — and most current frameworks
answer them only partially:

| The question an enterprise buyer asks | What most current frameworks offer |
|---|---|
| *"Can this agent be stopped before it does something unsafe, not after?"* | Primarily post-hoc content filters and output moderation. |
| *"Can a human approve destructive actions without a custom rewrite?"* | Middleware patterns that vary per framework and per integration. |
| *"Can I reconstruct what the agent did, step by step, for audit?"* | External telemetry or prompt logs — rarely a structured causal trace. |
| *"Can I cap token and dollar spend as a hard stop, not a warning?"* | Usage dashboards and soft alerts, not terminal budget events. |

In practice, a large share of enterprise AI pilots stall before
production, and the blockers our design partners cite most often are not
model quality — they are trust, auditability, approval workflow, and
spend control. Agents are now capable enough to be genuinely useful and
unpredictable enough to be difficult to insure and certify.

### Why retrofitting governance onto existing loops is hard

In most current frameworks, governance is layered *around* a core loop
that was designed primarily to "call the LLM and dispatch tools." Safety,
approvals, budgets, and audit logs tend to be composed as middleware.
The ordering in which these checks run — and how they interact with
cancellation and streaming — is often framework-specific and not always
pinned by tests. The result is that the seam between *"the model asked
to act"* and *"the action executed"* can be porous under edge cases:
prompt injection, hallucinated tool names, partial failures, concurrent
approvals.

Our view is that the market needs a runtime where governance is a
**first-class property of the execution path itself** — where the
action loop ordering is pinned by tests, every tool call passes through
explicit risk classification, every action can be gated for human
approval as a runtime argument, and every run produces a replayable
in-memory trace. That is the category we are building for.

## 3.2 The Architecture

### Agentic Framework — governance wired into the execution path

Agentic Framework is a **code-first Python library** that wraps any LLM
adapter (OpenAI, Anthropic, Mistral, local models via a common
`BaseLLMAdapter`) and turns it into a governed autonomous agent. Every
action is observable, auditable, and interruptible because those
properties are enforced by the runtime contract, not by optional
middleware.

### The governed execution path (pinned by the test suite)

```
  user_input
      │
      ▼
  GoalDecomposition  ──► structured ActionItems
      │
      ▼
  ReflectiveGenerator ──► LLM response (+ optional self-revision)
      │
      ▼
  CoherenceEngine    ──► turn-level coherence state
      │
      ▼
  SafetyGate         ──► eligible actions  (turn-level pre-gate)
      │
      ▼
  For each eligible action:
      ├── 1. Cancellation check      (async stop at checkpoints)
      ├── 2. Budget check            (hard token + cost caps)
      ├── 3. Approval gate           (human-in-the-loop, per action type)
      ├── 4. ACTION_STARTED event
      ├── 5. SafeMCPGateway          (per-tool risk + confidence + audit)
      └── 6. ACTION_COMPLETED event
      │
      ▼
  RUN_COMPLETED  +  AgentRunTrace   (in-memory, replayable)
```

The ordering — **cancel → budget → approve → execute** — is a runtime
invariant verified by the test suite, not a configurable option. A run
that is already cancelled does not reach the budget check. A run that
exceeds the budget does not reach the approval gate. A denied approval
does not reach tool execution. This is a deliberately narrow, tested
contract — one of the things we think enterprise buyers will care about
most during diligence.

### Two complementary governance layers

| Layer | Scope | What it decides |
|---|---|---|
| **SafetyGate** | Turn-level | *"Given the current coherence state, is any action allowed to run this turn?"* |
| **SafeMCPGateway** | Per tool call | *"Given this tool's declared risk level, the model's confidence, and enriched signals, should this specific call proceed?"* |

Every tool registered with the agent declares a `risk_level`
(`read_only → write → execute → destructive → privileged`), a
`min_confidence`, and whether it `requires_confirmation`. The gateway
enforces these at call time; the LLM cannot route around them. Turn-level
and per-call governance are complementary — one protects the turn, the
other protects the specific action.

### Signal-enriched governance (our differentiation)

When the agent is backed by a **CG-capable adapter** (our
`MistralCGAdapter` from Section 4, or the Phase Quad LLM from our broader stack),
governance decisions can be enriched with *model-internal runtime
signals* — entropy and vritti (coherence-fluctuation) values derived
from the model's internal state after inference. These are
state-derived uncertainty and coherence signals, not prompt-level
self-reported confidence scores, and they are not available to
frameworks that only see the text output of a closed API. Our approach
is differentiated here because we control both the adapter interface
and, in the CG path, the model internals.

When a non-CG adapter is used (OpenAI, Anthropic, etc.), the same
governance path still runs — it falls back to text-level signals
(quality scores and coherence metrics). Customers can therefore start
on commercial APIs today and move to the CG path later without rewiring.

### Developer surface — one call, full governance

```python
from agentic.agentic_framework import build_agent, ToolSpec, ToolRiskLevel

agent = build_agent(
    adapter=AnthropicAdapter(auth_token=...),
    tools={
        "search":      ToolSpec(handler=search_fn,  risk_level=ToolRiskLevel.READ_ONLY),
        "send_email":  ToolSpec(handler=email_fn,   risk_level=ToolRiskLevel.WRITE,
                                requires_confirmation=True),
        "run_payment": ToolSpec(handler=payment_fn, risk_level=ToolRiskLevel.DESTRUCTIVE,
                                requires_confirmation=True),
    },
)
trace = agent.run_with_trace("Process the refund queue")
```

One factory call composes the full stack: adapter, safety gate,
dispatcher, gateway, tracing, budget, and approvals. The same code runs
against a `MockLLMAdapter` (no cost, no API keys) and a live Anthropic
or OpenAI endpoint with no wiring changes — which makes the library
easy to evaluate before any procurement conversation.

## 3.3 Competitive Landscape

Agentic Framework sits in a crowded category — "agent tooling" is one
of the noisiest spaces in enterprise AI right now — but most of that
crowd is solving a different problem. Most current frameworks are
built to make it **easy to wire an LLM to a tool-calling loop**. We
are built to make the layer *between* that tool loop and a production
action **governed, auditable, and interruptible by default**. The
table below positions us against each family of competitor, stating
for every row both *how* we differ and *why* that difference is an
advantage for a regulated enterprise buyer.

| Category | Representative players | What they ship | How Agentic Framework differs — and why it is better |
|---|---|---|---|
| **Open-source agent frameworks** | LangChain / LangGraph, CrewAI, AutoGen, SmolAgents | Python (and JS) libraries that wire an LLM to a tool-calling loop, with middleware-composed safety, approvals, and logging. Multi-agent orchestration and ecosystem breadth are their strengths. | We treat governance as a **runtime contract, not middleware.** The execution ordering `cancel → budget → approve → execute` is pinned by the test suite and cannot be silently reordered; per-tool risk classification runs at the gateway; human approvals are a runtime argument, not a framework rewrite. **Better because:** a regulated buyer can point to a specific test that proves the agent cannot execute a denied or over-budget action, rather than reasoning about middleware composition order — which is exactly the property that closes enterprise diligence. |
| **Cloud-native managed agent platforms** | AWS Bedrock Agents, Vertex AI Agent Builder, Azure AI Studio Agents | Provider-hosted agent runtimes with console-driven tool registration, managed approval workflows, and observability tied to the cloud's logging stack. | We are code-first, portable across LLM providers, and emit a **replayable in-memory `AgentRunTrace`** that is not tied to a single cloud's telemetry. Approvals are per-action-type runtime arguments rather than console flows. **Better because:** customers who run multi-cloud or hybrid — which is most of BFSI and healthcare — can adopt us without provider lock-in, and the audit story is a single trace the customer owns, not a provider-specific log pipeline that evaporates the day they switch clouds. |
| **LLM-native tool / function-calling APIs** | OpenAI Assistants & Tools, Anthropic Tool Use, Mistral Function Calling | Provider-side tool-calling primitives exposed through a proprietary API. They decide *which* tool the model wants to call. | These are **substrate**, not a governance layer. They do not decide whether the call is allowed, affordable, approved, or in-scope for the current turn. **Better because:** Agentic Framework consumes these APIs through `BaseLLMAdapter` and *adds* the governance contract on top, so a customer using OpenAI Tool Use today gets SafetyGate, SafeMCPGateway, hard budget caps, and runtime approvals without migrating off their existing provider. We are additive to, not competitive with, the primitives they already pay for. |
| **Post-hoc guardrails & moderation** | NeMo Guardrails, Guardrails AI, Llama Guard, OpenAI Moderation API | Content-level filters and output classifiers applied *after* the model has produced a response. | Guardrails protect **text**, not **actions**. A hallucinated tool name, a budget breach, a denied approval, or a destructive side effect is not something a content filter is in a position to catch. **Better because:** we intervene at the action boundary — the thing that actually touches production systems — and we compose with a content-level guardrail rather than replacing it; a customer can still run NeMo Guardrails on the LLM output and use Agentic Framework for the tool-execution path. |
| **Observability & eval platforms** | LangSmith, Langfuse, Helicone, Arize Phoenix, W&B Traces | Instrumentation layers that record prompts, responses, latencies, and evals for after-the-fact debugging and scoring. | Observability tools answer *"what did the agent do?"* after the fact. We answer *"what is the agent allowed to do right now, and can we stop it?"* at execution time. **Better because:** the `AgentRunTrace` we emit is a first-class replayable object produced by the runtime contract itself — the same structure governance decisions were made against, not an out-of-band log pulled from a SaaS dashboard. Observability platforms remain useful on top; they become a *consumer* of the trace rather than a substitute for governance. |
| **Workflow / orchestration platforms** | Temporal, Airflow, Prefect, n8n, Zapier AI | Durable workflow engines (often retrofitted with LLM steps) that execute business processes with retry, state machines, and fan-out. | Workflow engines assume steps are **deterministic and pre-approved** — they are strong at durability and weak at *"the next action is chosen by an LLM and might be unsafe."* We assume steps are **LLM-chosen and must be gated**. **Better because:** we live exactly at the gap workflow engines do not cover — between *"the model decided to act"* and *"the action touched the system"* — and we can be invoked from inside a Temporal activity the same way a workflow engine calls any Python library. |

### Feature-level differentiation on governance primitives

For buyers who want the one-page side-by-side on the primitives that
come up in procurement conversations, here is the honest feature
comparison against the two most common competitor families:

| Area | Agentic Framework | LangGraph / CrewAI / AutoGen | Bedrock / Vertex Agents |
|---|---|---|---|
| Action loop ordering pinned by tests | **Yes** | Varies; typically middleware-composed | Provider-opaque |
| Per-tool risk classification at the gateway | **Yes** | Partial / per-integration | Partial |
| Human-in-the-loop as a runtime argument | **Yes** | Bolt-on patterns | Console-driven |
| Hard budget caps as terminal events | **Yes** | Typically soft / dashboard | Partial |
| Signal enrichment from model-internal state | **Differentiated** (requires CG adapter) | Not available without model-internal access | Not exposed |
| Multi-agent orchestration | Not yet — on roadmap | **Mature** | **Mature** |
| Managed / hosted runtime | Not yet — on roadmap | Partial | **Mature** |
| Ecosystem breadth (integrations, templates) | Narrow, focused | **Broad** | **Broad** |

### Why the overall bet is better, not just different

- **Governance *is* the execution path, not a wrapper around it.** The `cancel → budget → approve → execute` invariant is a tested runtime contract. No other framework in this landscape makes that a first-class, diff-testable property of the library itself — which is exactly what an enterprise risk team needs in order to sign off an autonomous agent.
- **Portable across LLM providers by construction.** `BaseLLMAdapter` lets a customer start on OpenAI or Anthropic today and move to a self-hosted or CG-enabled model later with no application rewrite. Managed platforms on the list lock the buyer into a single cloud; open-source frameworks leave portability to the user.
- **Signal enrichment from model internals is a category of one.** Because we ship our own CG-capable adapter (`MistralCGAdapter`) alongside the framework, governance can read entropy and vritti signals straight from the model's 32D state rather than trusting a text-level self-reported confidence. No wrapper on top of a closed API can reproduce this, and no closed API currently exposes it.
- **Composes with, rather than replaces, the rest of the stack.** A customer can keep LangChain for its ecosystem, Temporal for durability, LangSmith for observability, NeMo Guardrails for content filtering — and still put Agentic Framework at the tool-execution boundary. We are the missing layer, not a rival to every layer.
- **Honest scope on where we do not compete (year one).** We are not trying to win on ecosystem breadth, managed infrastructure, or multi-agent orchestration in the first twelve months. We are trying to win on the governance properties that regulated enterprises often cannot ship without: pinned action-loop ordering, per-tool risk classification, runtime approvals, hard budget caps, replayable traces, and — where customers adopt the CG path — signal enrichment from model-internal state.

### In one sentence

Agent frameworks make it easy to call an LLM and run a tool. Managed
platforms make it easy to host an agent on one cloud. Guardrails make
it easy to filter text. Agentic Framework makes it **safe for a
regulated enterprise to let an autonomous agent touch production** —
and that is a different product category than any of the incumbents
in this table are building for.

## 3.4 Evidence & Roadmap

### What is proved today (v1.9.0, internal evidence)

| Area | Current state |
|---|---|
| **Test suite** | 1,550+ tests passing across core runtime and R1–R11 runtime primitives |
| **Runtime primitives** | Streaming, async cancellation, approvals, structured output, tool discovery, budgets, tracing — all implemented and tested |
| **Test evidence per primitive** | Streaming: 28 · Cancel: 31 · Approvals: 33 · Structured output: 44 · Discovery: 38 · Budget: 37 · Tracing: 26 · Cross-feature: 23 |
| **Action loop ordering invariant** | Pinned by tests: cancel → budget → approve → execute |
| **Live-adapter end-to-end validation** | 3/3 phases pass against stock Anthropic API with exact usage accounting |
| **Realistic-mock regression** | 60/60 checks across 5 LLM output-format variations |
| **Adoption pilots shipped** | 2 internal pilots — Research Assistant (tool composition + governance) and Internal Copilot (per-action-type approval boundary) |
| **Known fragility points** | 3 of 4 surfaced in real-LLM pilots resolved (goal-alignment gate, action vocabulary normalization, usage accounting). The 4th is low-risk and tracked. |
| **Signal-enriched governance (CG path)** | Operator-validated on `MistralCGAdapter` in a torch/GPU environment; not yet repo-validated end-to-end. |
| **LLM adapters shipped** | OpenAI · Anthropic · Mistral (CG) · Mock — all behind a common `BaseLLMAdapter` |

All numbers above are from our own repository and CI — not third-party
benchmarks. An external benchmark is planned (see roadmap).

### Developer-surface improvements (v1.7 → v1.9)

| Measure | Before `build_agent()` (v1.7) | After (v1.9) |
|---|---|---|
| Lines to build a governed agent | ~70 | ~10 |
| Files to touch to add approvals | 3 | 0 (runtime arg) |
| Switching mock → real LLM | Rewire several components | Swap adapter only |
| Preview which actions are gated | Manual inspection | `describe_approval_coverage()` |
| Human-readable trace | Custom print loop | `format_trace(trace)` |

### 12-month roadmap

**Quarter 1 — Adoption and external proof**
- Add 3 external design-partner pilots (target sectors: BFSI and healthcare)
- OpenTelemetry export adapter for `AgentRunTrace` (the most common
  gap raised by enterprise evaluators)
- Publish an external governance benchmark vs LangGraph / CrewAI across
  a standardized safety + approval + budget scenario suite

**Quarter 2 — Developer console and managed preview**
- Ship the Low-Code Developer Interface (design spec complete at
  `docs/LOWCODE_DEVELOPER_INTERFACE_SPEC.md`) — tool registration,
  approval-policy editor, trace replay
- Launch a managed cloud preview for teams that prefer a hosted runtime

**Quarter 3 — Multi-agent and retrieval**
- Agent-to-agent handoffs that preserve governance across the handoff
  boundary
- First-party retrieval adapter with coherence-scored provenance
- Phase Quad LLM integration as a first-class CG adapter, enabling
  signal-enriched governance by default for Cognade customers

**Quarter 4 — Scale and certification**
- Begin SOC 2 Type II process on the managed runtime
- Enterprise audit-log persistence (Postgres + S3-backed)
- Target a production reference customer on the managed runtime

### The ask

We are raising seed to evolve Agentic Framework from a tested
code-first library into a managed governed-runtime product. The
technology is live, internally tested, and validated in two pilots and
on live commercial LLM APIs today. The capital is earmarked for:
external design-partner pilots, the managed runtime and low-code
console, multi-agent and retrieval support, and the compliance and
audit-persistence work required for regulated enterprise deployment.

Governance is increasingly becoming a procurement requirement for
autonomous agents, not just a nice-to-have. We think the next 12–18 months are the right
window to establish a credible default for that layer, and we believe
the combination of a tested runtime contract, a clean developer
surface, and a path to model-internal signal enrichment gives Agentic
Framework a defensible position in it.

*Module: `agentic/agentic_framework/`*
*v1.9.0 · 1,550+ internal tests · 2 internal pilots · live-adapter validated*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 4. Conscious Generation LLM
<!-- ═══════════════════════════════════════════════════════════════════ -->

**`mistral_cg` — Multi-Field Token Evaluation on a Frozen Mistral-7B Backbone**

## 4.1 The Problem

### Standard LLMs ultimately rank candidate tokens through a single projection bottleneck.

In a standard transformer, the hidden state summarizes a great deal of
context, but each candidate token is ultimately ranked by a single
scalar logit produced by `lm_head(hidden_state)`, and softmax picks the
next word by statistical continuation over that one ranking. Many of
the constraints humans apply implicitly — plausibility, mode, tone,
relational fit, identity continuity — are not explicitly separated in
token selection and must be approximated through the hidden state.

This compression is, in our view, **one structural contributor** to
several well-known LLM failure modes:

| Failure observed in standard LLMs | A signal the model does not explicitly isolate |
|---|---|
| Factual hallucinations (*"the Eiffel Tower is in London"*) | Physical / causal plausibility of the candidate token |
| Tone and register drift inside a single passage | Emotional / phonemic resonance of the candidate token |
| Mode confusion (fiction presented as fact, memory as imagination) | Explicit cognitive mode classification |
| Relational incoherence (*"calmly placed the cup on the explosion"*) | Energetic / relational harmony between candidate and context |
| Topic / identity drift over long contexts | Ontological identity stability across turns |

We do not claim these are the only causes of the failures above — LLM
error modes are multi-causal, and many of them respond partially to
better data, RLHF, retrieval, or moderation. What we do claim is that
post-hoc mitigations act *after* the model has already committed to a
distribution, and none of them change the fact that the distribution
itself came from a single projection. The architecture effectively
compresses many competing considerations into a single token-ranking
projection bottleneck — and in our view, relaxing that bottleneck is a
research direction worth funding.

### What we think a more grounded approach looks like

Our thesis is that next-token probability should be computed as the
**integrated agreement of multiple semantic fields** evaluating each
candidate token, rather than as a single continuation score from one
projection. Concretely, we believe a competitive next-generation LLM
will need (i) an explicit internal state representing ontological
identity, cognitive mode, and energetic profile; (ii) trainable
per-token auxiliary scorers that can evaluate candidates against that
state; and (iii) a mechanism for those signals to actually influence
token selection during generation, not just to be observed post-hoc.

This is a significant architectural bet, not a drop-in fix. `mistral_cg`
— our Conscious Generation LLM — is a live *partial* implementation of
that thesis today: the state, the scorers, and one inference-time
mechanism (the phase adapter) are in place, and the next 12 months are
about closing the remaining gap between the training-time signal stack
and the generation path.

## 4.2 The Architecture

### `mistral_cg` — frozen Mistral-7B backbone + trainable Conscious Generation modules

Conscious Generation is not a new foundation model. It is a **trainable
modification layer that sits on top of a frozen open-weights backbone**
(today, Mistral-7B v0.3, optionally 4-bit quantized). This choice is
deliberate: we get competitive base-model quality for free, we keep
trainable-parameter count small (~5M), and we isolate our contribution
to the layers where our thesis is testable.

### Forward pass in the `MistralCGWrapper`

```
  input_ids
      │
      ▼
  Mistral-7B backbone  [FROZEN, optional 4-bit]
      │                             hidden_states  [B, T, 4096]
      ▼
  SovereignStateProjector  [trainable]
      │                             32D state  (Bhava 12 · Kosha 5 · Vritti 5 · Guna 6 · Reserved 4)
      ▼
  Δ Bhava  →  IntentPhaseProjector  →  intent_phase   [trainable]
      │
      ▼
  Phase Adapter  (Linear → GELU → Linear, gated residual)   [trainable]
      │
      ▼
  adapted_hidden = hidden + sigmoid(gate) · adapter_output
      │
      ▼
  backbone.lm_head  [FROZEN]  →  logits
      │
      ▼
  next token
```

The 32D Sovereign State is the interpretable spine of the model. Its
five slices each correspond to a designed aspect of "what the model
currently is": **Bhava** (12D — ontological identity axes), **Kosha**
(5D — layer weighting), **Vritti** (5D — cognitive mode), **Guna** (6D —
energetic profile), and **Reserved** (4D). The *delta* of the Bhava
slice between turns drives an intent-phase projection, which the phase
adapter turns into a small, learned correction to the hidden state
**before** it reaches the frozen LM head.

This is the mechanism that currently influences token selection at
inference time in `mistral_cg`. It is also what makes the system
honest: the CG layers cannot silently rewrite Mistral's logits — they
can only inject a gated, state-conditioned correction into the hidden
representation that produces them.

### Training auxiliaries — the multi-field token-evaluation layer

On top of the forward pass above, the training stack adds a
**Token Evaluation Tensor** with per-token scorers for each of the
signal families in our thesis:

| Signal | Scorer module | What it learns to judge |
|---|---|---|
| **CSR** | `CSRTokenScorer` (phoneme affinity × context) | Phonemic / tonal resonance of a candidate token |
| **Vritti** | `VrittiTokenScorer` (token/context → 5 cognitive-mode probs) | How well the token fits the current cognitive mode |
| **Guna** | `GunaTokenScorer` (token/context → 3 Guna probs, bilinear) | Energetic / relational compatibility |
| **Ontological** | `TokenOntologyProjector` + `OntologyCompatibilityScorer` | Identity-level compatibility with the 32D state |
| **JEPA / Plausibility** | JEPA-style predictor and plausibility heads | Causal / physical grounding of the token |
| **Kosha / Bliss** | Kosha router + Bliss gate | Layer weighting and coherence integration |
| **Level Discipline** *(proposed — design spec complete, implementation pending)* | `LevelDisciplineScorer` + `LevelClassifierHead` / `JustificationHead` / `LevelStateHead` — writes `Reserved[0..3]` of the Sovereign State. See `docs/design/LEVEL_DISCIPLINE_SCORER_DESIGN.md`. | Epistemic match: a claim's categorical (I/G/P/U) and temporal (log-seconds) zoom vs. the zoom of the evidence in context |

Each scorer ships with its own InfoNCE / contrastive auxiliary loss,
gated by an explicit lambda weight in the training config. During
training, these losses shape the shared hidden representation and the
32D state so that the downstream phase adapter inherits signal-rich
structure. This is how a multi-field token-evaluation thesis becomes
testable on a frozen backbone without retraining Mistral from scratch.

### Integration with the Agentic Framework

`mistral_cg` ships behind the same `BaseLLMAdapter` interface the
Agentic Framework (Section 3) uses, exposed as `MistralCGAdapter`. That means
a governed agent built with `build_agent(...)` can swap in a CG backend
with no wiring changes, and the **governance layer gains access to
model-internal runtime signals** (entropy and vritti values read from
the 32D state) rather than prompt-level self-reported confidence. This
is the tight loop between our research stack and our developer product:
`mistral_cg` is the first adapter where those signals are actually
available.

## 4.3 Competitive Landscape

`mistral_cg` occupies an unusual position in the current LLM tooling
stack. It is neither a foundation-model company trying to outspend
OpenAI on pre-training, nor a wrapper layer that sits outside a
black-box API. It is a **trainable internal modification to an
open-weights model** with an explicit thesis about how token selection
should be computed. The table below places our product against the
families it is most commonly compared to in investor conversations,
stating for each family *how* we differ and *why* that difference is
an advantage.

| Category | Representative players | What they ship | How `mistral_cg` differs — and why it is better |
|---|---|---|---|
| **Closed-weights foundation labs** | OpenAI (GPT-4/5), Anthropic (Claude), Google DeepMind (Gemini) | Massive, closed-weights models tuned via RLHF / Constitutional AI. Mitigations (refusals, factuality, tone) are applied as a preference layer over a single softmax. | We do not compete on pre-training scale. We bolt a ~5M-parameter trainable layer onto a frozen open-weights backbone and intervene *inside* the generation mechanism. **Better because:** the intervention is structural rather than preference-tuned, self-hostable, orders of magnitude cheaper to train, and our governance layer gets access to actual model internals — not just the text that a closed API returns. |
| **Open-weights backbones** | Mistral AI, Meta Llama, Qwen, DeepSeek | Open-weights base / instruct models intended as a starting point for downstream fine-tuning. | These are our **substrate**, not our competitor. `mistral_cg` is what you would build *on top of* Mistral-7B if you wanted the model to expose an interpretable 32D state and a multi-field token-evaluation path. **Better because:** we inherit every quality gain the open-weights ecosystem produces (our recipe is deliberately backbone-agnostic) and we add a capability — interpretable, per-field token scoring — that no base model exposes on its own. |
| **Parameter-efficient fine-tuning** | LoRA / QLoRA, PEFT, IA³, adapter tuning | Generic low-rank or adapter modules that shift a frozen model's output distribution toward a target dataset, tone, or persona. | LoRA-class methods are **architecturally neutral**: they adjust a distribution without making any claim about *why* a token should be chosen. Our phase adapter looks like a LoRA from the outside, but it is driven by a designed 32D Sovereign State (Bhava · Kosha · Vritti · Guna) and supervised by per-field scorers. **Better because:** every trainable parameter has a named role (identity, mode, energy, phoneme, plausibility), so a failure mode can be localized to a field rather than debugged as an opaque weight shift — and the same structure gives downstream systems something legible to read. |
| **Retrieval-augmented generation** | LangChain / LlamaIndex + vector DBs (Pinecone, Weaviate, Chroma) | Inject retrieved documents into the prompt to ground generation on external facts. | RAG grounds *what* the model sees in its context window. It does not change *how* the model ranks candidate tokens given that context. **Better because:** even with perfect retrieval, the final token is still picked by a single softmax; `mistral_cg` replaces that softmax with multi-field agreement, so RAG + CG is strictly stronger than RAG alone — retrieval provides evidence, and CG enforces that the chosen token is actually consistent with it. |
| **Guardrails & post-hoc moderation** | NeMo Guardrails, Guardrails AI, Llama Guard, OpenAI Moderation API | Filter, rewrite, or refuse outputs *after* the model has already produced them. | Guardrails act after the distribution is committed. Our thesis is that hallucinations, tone drift, and mode confusion originate *inside* the token-ranking step, so the intervention has to happen there. **Better because:** shaping the distribution at the source avoids the whack-a-mole cost of filtering and catches failures a pattern-based filter cannot even express — energetic incoherence, cognitive-mode drift, ontological identity breakdown — which are exactly the cases where standard moderation is silent today. |
| **Interpretability / steering startups** | Goodfire, Transluce, Anthropic interpretability, EleutherAI mech-interp | Probe, visualize, or steer existing model internals *after* the model has been trained by someone else. | Interpretability players treat the model as **given** and learn to read or nudge it. We treat interpretable internal state as a **designed, trained, and supervised** component of the model itself. **Better because:** every dimension of the 32D Sovereign State is a contract the training stack optimizes against, so a governance readout is not an empirical probe that might generalize — it is a named axis the model was trained to expose and respect. |
| **Agent frameworks & governance wrappers** | LangChain, AutoGen, CrewAI, LangGraph | Orchestration layers that call LLM APIs and add tool use, memory, retries, and confidence heuristics. | These frameworks rely on **prompt-level, self-reported** signals — the model says "I am not sure" and the wrapper trusts it. Our Agentic Framework consumes **model-internal** signals (entropy + vritti read from the 32D state) through `MistralCGAdapter`. **Better because:** a model's self-reported confidence is itself a text completion and can hallucinate; a state readout cannot — it is literally the vector the model used to pick the next token, so escalation, tool gating, and refusal decisions are grounded in what the model *did*, not what it *said*. |

### Why the overall bet is better, not just different

- **Structural, not behavioral.** Every other player in this table either (a) trains a bigger black box, (b) writes better prompts around a black box, or (c) filters the output of a black box. `mistral_cg` is the only approach in this list that changes *the mechanism of token selection itself*, which is where the failure modes we care about originate.
- **Seed-stage cost, foundation-lab capability.** ~5M trainable parameters on a frozen 4-bit Mistral-7B. That is reproducible on commodity GPUs with a single-digit-million training budget — the opposite of the capital moat closed labs rely on, and cheap enough that each new signal family can be ablated honestly.
- **Interpretable by construction.** The 32D Sovereign State is a designed contract (Bhava · Kosha · Vritti · Guna · Reserved), not a post-hoc probe. That makes the resulting model **auditable in the same motion that produces it** — a property governance buyers cannot get from a closed API and cannot reliably manufacture with an interpretability tool applied from the outside.
- **Governance coupling is native, not bolted on.** Because the Agentic Framework reads signals directly from the 32D state via `MistralCGAdapter`, a governed agent built on `mistral_cg` gets runtime decisions (escalation, tool gating, refusal) based on what the model *actually did*, not on what it *said it did*. No wrapper framework on top of a closed API can match that loop, and no closed API is likely to expose it.
- **Composes with, rather than replaces, the rest of the stack.** `mistral_cg` does not ask an operator to throw away RAG, guardrails, or their agent framework — it makes each of those layers more effective, because the model underneath is now producing a signal they can actually condition on. The competitive question is not "CG or RAG?" but "with or without the field-integrated generation path underneath?"

### In one sentence

Everyone else in this landscape either **trains a bigger model**,
**adds text around an existing model**, or **observes an existing
model from the outside**. `mistral_cg` is a bet that the next
improvement in LLM reliability comes from **changing how a single
token is chosen**, using an explicit, interpretable internal state
that both the model and a governance layer can read — and that this
bet is winnable at seed-stage cost, because the backbone is free and
the trainable surface is small.

## 4.4 Evidence, Honest Status & Roadmap

### What is built and running today

| Area | Status |
|---|---|
| `MistralCGWrapper` forward pass | Implemented. Frozen Mistral-7B backbone + trainable state projector, intent-phase projector, phase adapter, gated residual. |
| 32D Sovereign State (Bhava · Kosha · Vritti · Guna · Reserved) | Produced in every forward pass when CG is enabled. |
| Phase adapter | Trainable, gated, active on every forward pass — the currently active CG mechanism that modifies token probabilities (via hidden-state correction before the frozen LM head). |
| Stage 8 Perspective Synthesizer | Implemented and flag-enabled in `scripts/train_mistral_cg.sh`; conditions the hidden state via interpretive signals (CSR, Vritti, Kosha, Bhava) before the LM head. |
| Training auxiliaries (CSR · Guna · Ontological · Vritti · JEPA · Kosha · Bliss) | All six scorer modules and their associated auxiliary losses are implemented in the training stack and can be activated through the training configuration (flags and per-signal lambda weights). |
| 4-bit / 8-bit quantization | Supported via bitsandbytes. ~14GB VRAM at 4-bit, ~18GB at 8-bit. |
| Trainable parameter count | ~5M (CG modules only; Mistral backbone remains frozen). |
| Inference adapter | `MistralCGAdapter` exposes `mistral_cg` to the Agentic Framework's `BaseLLMAdapter` interface, including entropy + vritti signal readouts from the 32D state for governed tool dispatch. |
| Repo validation | `test_inference_mistral_cg_smoke.py` covers the adapter smoke path; end-to-end training is runnable via `scripts/train_mistral_cg.sh` (from smoke test to full WikiText-103 / C4 runs). |

### Honest scope caveats — what is implemented vs. what is active by default

We want VCs to see the gap between our design document and our current
code, because we would rather surface it ourselves than have it
surfaced in diligence. A recent internal audit
(`docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md`) documents the state below:

| Area | Reality today |
|---|---|
| `enable_conscious_generation` flag | Defaults to `False`. The full CG module tree is only instantiated when explicitly enabled. |
| Token-level auxiliary losses (CSR, Vritti, Guna, Ontological) | Implemented end-to-end, but their lambdas default to `0.0`. They are activated via `scripts/train_mistral_cg.sh`, which sets conservative starting lambdas (e.g. `0.01` for Ontological, `0.005` for CSR/Vritti/Guna). |
| Field-integrated softmax (the full "multi-field replaces softmax" story) | Implemented as Phase 4 but gated behind a curriculum manager. Not the default generation path today. |
| Inference-path generation | The only CG mechanism that currently modifies token probabilities at inference is the **phase adapter** (via its gated residual on hidden states before the frozen LM head). Per-token CSR / Vritti / Guna / Ontological scoring are training-time signals today. |
| Derived inference signals (`SovereignStateMonitor`, `InferenceGunas`, `CSRInferenceGuard`) | Active and usable for governance and observability, but they are **derived** from state and token statistics — not the trained per-token auxiliaries. |
| Repo-validated vs. operator-validated | The forward pass, wrapper, and adapter smoke tests are repo-validated. Full training with all auxiliaries active is **operator-validated** in a torch + GPU environment. |

In plain terms: the **skeleton and training signal path** of multi-field
token evaluation is built. The **phase adapter** is live at inference.
The **field-integrated softmax** that completes the "replace the single
softmax" thesis is implemented but still curriculum-gated. This is
exactly the kind of project where the next 12 months turn a research
architecture into a deployed one.

### Design specs with implementation pending — proposed additions to the stack

One proposed addition is at spec-complete, implementation-pending
status as of this brief, and we surface it here for the same
reason we surface the caveats above: we would rather name the gap
between a design document and the code than let it be discovered
in diligence.

| Proposed scorer | Design spec | Status |
|---|---|---|
| **Level Discipline Scorer** (would be the seventh scorer family in the Token Evaluation Tensor) | `docs/design/LEVEL_DISCIPLINE_SCORER_DESIGN.md` (Steps 1–8): framework, module contract, training signal and curriculum, integration points, validation plan, research risks, and honest scope. | **Design spec complete, implementation pending.** Zero files yet written. Research risk is concentrated in `JustificationHead` (spec §7.1) and in the Dataset C inter-annotator-agreement gate (spec §5.5). See spec §8.2 for the three-phase deliverable path and §6.1 for the file-level implementation plan (9 new files, 6 modified). |

### Training setup we run today

| Setting | Default (via `scripts/train_mistral_cg.sh`) |
|---|---|
| Backbone | `mistralai/Mistral-7B-v0.3`, frozen |
| Quantization | 4-bit (bitsandbytes) |
| Trainable modules | State projector · Intent phase projector · Phase adapter · Stage 8 Perspective Synthesizer · CG scorers |
| Dataset options | Synthetic (smoke) · WikiText-2 · WikiText-103 · C4 |
| Batch / grad accumulation | 4 × 8 |
| LR / warmup | 3e-4 · 500 warmup steps |
| Mixed precision | bf16 |
| Stage 8 | Enabled by default, gate initialized to 0.0 and learned |
| Lambda starting weights | Ont 0.01 · Kosha 0.01 · Bliss 0.01 · Plausibility 0.005 · CSR/Vritti/Guna 0.005 |
| Diagnostics | Embedding diagnostics every 200 steps |

### Roadmap — next 12 months

**Quarter 1 — Close the inference-path gap**
- Wire the four dormant per-token scorers (CSR · Vritti · Guna · Ontological) into the generation path behind a clean flag, so the contribution of each field to token selection is measurable at inference, not just at training.
- Run the first published internal comparison of `mistral_cg` vs. stock Mistral-7B on hallucination, tone-consistency, and mode-coherence evaluation suites.

**Quarter 2 — Field-integrated softmax ("Phase 4") as a default**
- Graduate the field-integrated softmax from curriculum-gated experiment to a default-on option behind a single flag.
- Publish the first ablation study isolating the contribution of each signal family to downstream generation quality.

**Quarter 3 — Adapter maturation + governance coupling**
- Ship `MistralCGAdapter` as a first-class backend for the Agentic Framework, enabling **signal-enriched governance by default** (entropy + vritti + state-derived coherence) for governed agents.
- First external design-partner integration where the governance layer consumes `mistral_cg` internal signals rather than text-level confidence.

**Quarter 4 — Scale + larger backbones**
- Validate the same frozen-backbone + trainable-CG recipe on a larger open-weights model (e.g. Mistral Small 3 / Llama 3.1 class) to test that the architecture is backbone-agnostic.
- Begin work on a paper submission documenting the multi-field token-evaluation architecture and ablations.

### The ask

We are raising seed capital to take `mistral_cg` from a research
architecture with a live phase-adapter inference path and a broad
training-time signal stack, to a model where the **full multi-field
token evaluation thesis is wired into generation**, measurable against
hallucination and coherence benchmarks, and exposed to enterprise
customers through our governed Agentic Framework. The technology is
built on an open-weights backbone, the trainable surface is small
(~5M parameters), the cost structure is modest, and the research risk
is concentrated in well-identified places we can show progress against.

*Modules: `symbolu_training/training/unified/mistral_wrapper.py`, `symbolu_training/training/conscious_generation/`, `agentic/agentic_framework/inference_mistral.py`*
*Design: `docs/design/CONSCIOUS_GENERATION_DESIGN.md`, `docs/design/LEVEL_DISCIPLINE_SCORER_DESIGN.md` · Audit: `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md`*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# 5. Hybrid LLM — Algorithmic Fusion of Attention Mechanisms
<!-- ═══════════════════════════════════════════════════════════════════ -->

**`HybridPhaseTransformer` — Algorithmic Fusion of Linear, Sliding-Window, and Binding-Cache Attention**

## 5.1 The Problem

### The long-context attention tradeoff remains only partially solved.

Modern LLMs pay for their capability with a well-known attention
tradeoff, and no dominant production architecture fully resolves it.
Each of the three major families in production today makes a
deliberate compromise on one of the three properties teams actually
want from long-context attention — **global content-addressable
retrieval**, **local precision**, and **efficient scaling** — and
then compensates for that compromise with additional mechanisms:

| Attention family | What it does well | The compromise, and how the field has compensated |
|---|---|---|
| **Full quadratic softmax** (GPT, LLaMA, Claude API) | Rich, content-addressable retrieval across the whole context | O(n²) time and memory. The field has compensated with FlashAttention, KV-cache tricks, sparse patterns, and retrieval augmentation — all of which work *around* the quadratic cost rather than removing it. |
| **Sliding-window / local attention** (Mistral sliding-window, Longformer) | O(n·w) scaling, very fast, excellent for short-range syntax and fluency | No direct attention path to information outside the active window without extra mechanisms. Longformer itself pairs the window with explicit **task-motivated global attention tokens**; Mistral's sliding-window paper frames the window as an *efficiency* move rather than a full replacement for global attention. Local attention is not presented as a complete long-context solution even by its own authors. |
| **Linear / state-space attention** (Mamba, RWKV, Performer, S4) | O(n) scaling, constant per-step inference memory | The recurrent state is a compressed running sum, and recent work (including the 2024 "Stuffed Mamba" line of research on state collapse and state capacity) directly studies the limits of RNN-style state for strict long-range retrieval. Linear-time scaling is real; lossless long-range retrieval at arbitrary distances is still an active research question. |

In other words, the current production stack is *"partially solved,
with compensating mechanisms"*, not *"solved"*. In practice, teams
deploying long-context LLMs pick one of these families and then spend
significant engineering effort compensating for its weakness —
KV-cache tricks, sparse patterns, retrieval augmentation, aggressive
truncation, reranking. Those compensations usually act *around* the
attention mechanism rather than inside it.

### Why stacked hybrids so far have not fully closed the gap

A growing number of recent papers and open-source models layer two
attention mechanisms together — *some* layers full, *other* layers
local, or a linear recurrent state side-by-side with a small window.
These approaches help measurably, and we think they are directionally
right. But in most public hybrids we have studied, the two mechanisms
still **stack** rather than fuse: each runs on the same input tokens
in parallel, and the model is left to blend their outputs with a
weighted sum or a gate. In our view, that leaves two structural issues
on the table:

1. **Gradient competition.** When two attention heads attack the same
   token stream in parallel, they tend to fight over the same
   gradient signal during training. The stronger mechanism can
   dominate and the weaker one can become vestigial, which undercuts
   the point of the hybrid.
2. **No shared memory substrate.** A linear-attention branch produces
   a running state. A local-attention branch reads raw tokens.
   Because they typically operate on different representations,
   neither can use what the other has computed — they coexist, but
   they do not *compose*.

We think the interesting question is not *"which attention mechanism
is best?"* but *"can linear, local, and quadratic attention be
algorithmically fused so that each mechanism operates on the output of
the others, with a shared long-range memory substrate that all three
can read?"* If the answer is yes, the tradeoff in the table above
becomes a design axis rather than a forced choice, and the cost
profile of long-context inference changes materially. That is the
question our `HybridPhaseTransformer` is built around.

## 5.2 The Architecture

### `HybridPhaseTransformer` — three attention mechanisms composed serially over a shared phase-memory state

Our Hybrid LLM is a transformer in which early layers use pure
sliding-window attention and later layers run a **Protected Phase**
block that composes linear phase attention, sliding-window attention,
and a top-K binding cache **serially** over a shared memory state —
plus an associative slot memory that stores content beyond what layer
weights can absorb.

### Layer structure

```
  input tokens
      │
      ▼
  Token + position embedding (+ dropout)
      │
      ▼
  ┌─────────────────────────────────────────────────┐
  │  Layers 0..(L-1) — Local only                   │   O(n · w)
  │  LocalTransformerBlock (FlashAttention or SDPA) │   sliding-window
  │  Learns: bigrams, syntax, short-range patterns  │
  └─────────────────┬───────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  Layers L..(N-1) — Hybrid                        │
  │  HybridTransformerBlock (Protected Phase)       │
  │   ├── PhaseAttention       O(n)   ── produces    │
  │   │    memory_state  [B, N, H, D_h]              │
  │   ├── LocalAttention       O(n·w) ── cross-      │
  │   │    attends to memory_state (K, V), not x     │
  │   └── BindingCacheQuadQuery  O(n·k) ── Top-K     │
  │        proposals over memory_state                │
  │  + SlotMemory read/write per layer (assoc. KV)   │
  └─────────────────┬───────────────────────────────┘
                    │
                    ▼
  LayerNorm → LM Head (× learnable logit_scale)
```

The current default configuration is a 46M-param reference
(768 embed × 12 layers × 12 heads, 4 local + 8 hybrid, 256-token
window, 8K max seq len) and a 7B-class model (`train_hybrid_7b.py`:
4096 embed × 32 layers × 32 heads, GQA 8 KV heads, 16 local + 16
hybrid) for A100-80GB training. The 7B recipe uses 4-bit quantization,
gradient checkpointing, an 8-bit optimizer, and torch.compile.

### Phase attention — the linear core

Phase attention is our O(n) linear mechanism. Each token emits a
query and key as **complex phasors** — learned amplitude × complex
exponential at a learned phase angle, with the key phase conjugated.
The cumulative state at each position is the running sum of all prior
`k · v` outer products, computed via parallel scan:

```
  State_t = State_{t-1} + K_t · V_t         # O(n) cumulative sum
  Out_t   = Re( Q_t · State_t )             # real-part readout
```

Unlike Mamba / RWKV / Performer, there is no `γ < 1` decay baked into
the state. Information is encoded in **phase** rather than magnitude,
so the default phase branch does not impose mandatory exponential
decay, which in principle allows older information to remain
recoverable through phase-aligned queries. The amplitude gate is
sigmoided (with a floor to prevent gradient collapse), each head
learns its own phase offset, and an optional per-head decay factor
is available as an explicit forgetting knob when the task wants one. An internal
technical report on the phase-attention mechanism documents a small
(~240K-param) pure-phase model reaching 100% needle-in-haystack
retrieval accuracy at both 2K and 10K token recall distances on a
controlled retrieval task (full retrieval benchmarks on larger models
are on the roadmap — see Section 5.3).

### The algorithmic fusion — Protected Phase

This is the part we think is genuinely novel. In "Protected Phase"
mode, the three mechanisms do **not** run in parallel on the input
tokens. They run **serially, over a shared state**:

1. **Phase attention runs first** on the input tokens and produces a
   cumulative `memory_state` at every position. This state is
   RMS-normalized to keep its magnitude bounded.
2. **Sliding-window local attention then cross-attends to the
   memory_state**, not to the raw tokens. Its Q comes from the
   current tokens; its K and V come from the phase memory. Local
   attention is therefore doing *precise short-range extraction
   from a long-range representation*, rather than competing with
   phase for the same gradient.
3. **A Binding-Cache Quad Query** optionally runs on top, producing
   **Top-K proposals** from the phase memory at O(n·k) cost (not
   O(n²)), with a conditional-skip path that bypasses the quadratic
   branch entirely when phase confidence is already high enough.

The result is a single forward pass in which the linear branch
establishes long-range context, the windowed branch extracts local
detail from that context, and the quadratic branch is invoked only
where it is actually earning its cost. Because the three mechanisms
are composed serially over a shared state, **the design is intended
to reduce direct gradient competition and force clearer role
specialization** — phase has to learn a representation that local
and quad can consume, and local and quad have to learn to read from
it. A legacy parallel-blend mode is retained behind a flag for
ablation.

### Slot memory — associative recall beyond layer weights

On top of the hybrid attention stack, each hybrid layer reads from
and writes to a 64-slot associative key-value store
(`SlotMemoryGCT`). Writes use competitive cosine routing and are
**detached from the LM loss**, so the main cross-entropy cannot
corrupt slot contents; slots are shaped by a separate retrieval loss
applied only at positions beyond the sliding window. An ablation eval
runs every 200 training steps that toggles slot reads off and reports
the resulting PPL delta, which is then used as an adaptive signal
for slot learning rate, gate ceiling, and retrieval loss weight. In
other words, the slots only keep earning their place if the
ablation says they are helping.

## 5.3 Competitive Landscape

`HybridPhaseTransformer` lives in the most crowded, most actively
researched corner of modern LLM architecture — long-context attention.
Nearly every major lab has an answer to the quadratic problem, and
the open literature now contains a growing list of hybrid architectures
that stack two mechanisms together. The table below positions us
against each family of alternative, stating for every row both *how*
we differ and *why* that difference is an advantage.

| Category | Representative players | What they ship | How `HybridPhaseTransformer` differs — and why it is better |
|---|---|---|---|
| **Full quadratic transformers** | GPT-4/5, Claude, LLaMA 3, Mistral-7B, Qwen, DeepSeek | Standard dense softmax attention, scaled with FlashAttention, KV-cache tricks, and RoPE extensions to reach long contexts. | We do not fight quadratic attention on its own cost curve — we invoke it *conditionally*, only where phase confidence is already low, via the Binding-Cache Quad Query's Top-K O(n·k) path. **Better because:** the operator gets the content-addressable precision of quadratic attention exactly on the tokens that need it, and linear-cost phase memory everywhere else — the same model no longer has to pay the O(n²) tax on every position to earn occasional retrieval quality. |
| **Linear / state-space models** | Mamba / Mamba-2, RWKV, RetNet, Performer, Linear Transformer, S4 | O(n) recurrent or linearized state machines that compress context into a running hidden state, typically with an exponential decay (`γ < 1`) baked into the recurrence. | These models encode information in **magnitude** with a decaying running sum — which is why the recent "Stuffed Mamba" line of research finds structural state-capacity limits on strict long-range retrieval. Our phase branch encodes information in **phase**, not magnitude, with no mandatory `γ < 1` — older information remains recoverable via phase-aligned queries. **Better because:** the retrieval ceiling is a function of phase-angle resolution rather than geometric decay, which is the mechanism behind a 240K-param pure-phase model reaching 100% needle-in-haystack at 10K tokens on a controlled task. Linear cost is preserved; the decay tax is not. |
| **Sliding-window / local attention** | Longformer, BigBird, Mistral sliding-window, Sparse Transformer | O(n·w) local attention over a fixed window, usually paired with a handful of task-defined global tokens to reach long-range dependencies. | Local attention is strong at short-range syntax and silent outside its window. We keep sliding-window attention — but in the Protected Phase block, **it cross-attends to the phase memory, not to raw tokens**. Its queries come from current tokens; its keys and values come from the long-range phase state. **Better because:** the window now does *precise short-range extraction from a long-range representation*, instead of competing with a separate global mechanism for gradient. Longformer's hand-chosen global tokens are no longer necessary, because the global path is structural. |
| **Stacked / parallel hybrids** | Jamba (AI21), Zamba, Griffin / Hawk (DeepMind), Samba, Hymba, StripedHyena, RecurrentGemma | Interleave Mamba/SSM blocks with transformer blocks, or run two attention mechanisms in parallel and blend their outputs with a gate. | Stacked hybrids are directionally right but, in our view, leave two issues unresolved: two heads on the same token stream fight for the same gradient (the weaker mechanism often becomes vestigial), and a linear branch and a local branch operate on different representations and cannot compose. Our Protected Phase block runs the three mechanisms **serially over a single RMS-normalized `memory_state`** — phase produces the state, local attention reads it, quad proposes on top of it. **Better because:** the architecture *forces* role specialization rather than hoping for it — phase has to learn a representation that local and quad can consume, and each mechanism earns its place by operating on the output of the others, not by racing them. |
| **Retrieval-augmented generation** | LangChain / LlamaIndex + vector DBs (Pinecone, Weaviate, Chroma, pgvector), RETRO-style retrieval-conditioned LMs | Sidestep long context entirely by chunking corpora and retrieving top-K passages into a short context window at inference time. | RAG is a **preprocessing** strategy: it moves the long-range problem out of the model and into a separate retrieval system. That is fine for document Q&A and brittle for agentic tool chains, long chat histories, and ordered reasoning where the position of information matters. **Better because:** we give the model a learned long-range memory substrate *inside* the forward pass, so the same architecture handles both retrieval-shaped and continuation-shaped workloads. RAG remains usable on top; we are complementary to it, not a replacement for its use cases. |
| **External-memory / cached-context architectures** | Memorizing Transformers, Landmark Attention, Infini-attention, Transformer-XL segment recurrence, RMT | Attach an external KV store or segment-level recurrent state that the attention layer queries alongside its own window. | External-memory designs keep attention unchanged and bolt a second, often weakly-differentiable store alongside it. **Better because:** our `SlotMemoryGCT` is a 64-slot associative memory whose writes are detached from the LM loss and shaped by a separate retrieval loss applied beyond the window, with an every-200-step ablation eval that adaptively adjusts slot LR, gate ceiling, and retrieval-loss weight. Slots only keep earning their place if the ablation says they are helping — no silent dead weight, no "add more memory and hope" failure mode. |
| **Context-extension via position encoding** | RoPE extensions — YaRN, NTK-aware scaling, LongRoPE, PI (Positional Interpolation) | Rescale or interpolate existing rotary embeddings to make a model pre-trained at 4K–8K extrapolate to 32K–1M tokens, without architecture change. | Position-extension methods are a **patch** applied to quadratic models — they extend where the model *can look* without changing how expensively it looks. The model still pays O(n²) at the new context length, still has no long-range memory substrate, and still relies on training-time priors to recall distant information. **Better because:** we change the mechanism, not the coordinates. An operator is not picking between YaRN and our model; they are picking between "a 32K-capable quadratic stack whose cost scales with context" and "a hybrid stack whose long-range path is O(n) by construction and whose quadratic branch is invoked only where it is earning its cost." |
| **Efficient attention implementations** | FlashAttention (1/2/3), PagedAttention (vLLM), Ring Attention, xFormers | Kernel-level and memory-layout optimizations that make standard softmax attention faster and more memory-efficient on existing hardware. | These projects are **substrate**, not a thesis about long-range attention. They accelerate whichever attention mechanism is already chosen. **Better because:** `HybridPhaseTransformer` composes with FlashAttention exactly the way any other transformer does (the local branch uses SDPA / FlashAttention directly) — the operator gets the FlashAttention speedup *and* the hybrid's structural cost reduction, rather than having to choose between them. |

### Why the overall bet is better, not just different

- **Serial fusion over a shared state, not parallel stacking.** Every hybrid architecture we know of runs its two mechanisms in parallel and blends the outputs. We run three mechanisms — linear phase, sliding-window local, and Top-K binding-cache quad — **serially over a single RMS-normalized phase memory**. That is the architectural bet: composition, not blending, and a shared substrate that forces each mechanism to earn its role by consuming what the previous one produced.
- **Phase, not magnitude, carries long-range information.** The entire linear-model family encodes state as a decaying running sum. We encode it as a running sum of complex phasors with per-head phase offsets and no mandatory `γ < 1`. The mechanism-level evidence — a 240K-param pure-phase model hitting 100% needle-in-haystack at 10K tokens on a controlled task — is the first signal that the decay tax is not necessary for linear-time attention to work at long distances.
- **Quadratic is a tool, not a default.** The Binding-Cache Quad Query runs at O(n·k) on Top-K proposals and is conditionally skipped when phase confidence is already high enough. Quadratic precision is spent exactly where it is needed and saved everywhere else — the opposite of the status quo, which pays quadratic cost on every token to earn occasional retrieval quality.
- **Memory that has to prove itself every 200 steps.** `SlotMemoryGCT` is the only long-term memory in this landscape that runs its own ablation eval against the live model during training and adaptively shrinks or grows itself based on the PPL delta. An external KV-store bolted onto a transformer has no such feedback loop, which is why most of them quietly degrade into dead weight.
- **Honest scope on what is validated today.** We do not claim benchmark wins on LRA, Path-X, or head-to-head vs. Mamba / Mistral at 7B — those are explicitly the Q1 roadmap item. What we claim is a working training stack, a validated phase-memory mechanism at pilot scale, and an architecture whose structural bet (serial fusion over shared phase memory) is implemented, runnable, and ready to be measured against the baselines in the table above.

### In one sentence

Every other entry in this landscape either **pays the quadratic tax
everywhere**, **stacks two mechanisms in parallel and lets them
fight for gradient**, **decays its long-range memory into a running
sum**, or **sidesteps long context by retrieving around it**.
`HybridPhaseTransformer` is a bet that the next step is **algorithmic
fusion** — linear, local, and quadratic attention composed serially
over a shared phase-memory substrate — so that the tradeoff in the
Section 5.1 table becomes a design axis rather than a forced choice.

### The broader stake (honest framing)

The structural bet here — **linear-time long-range recall without a
decay tax** — is the kind of primitive that future, more ambitious
architectures will need whether they reach AGI or not; we are not
claiming to solve intelligence, we are claiming to remove one of the
limits that any solution to it will have to navigate.

## 5.4 Evidence, Training Recipe & Roadmap

### What is built and training today

| Area | State |
|---|---|
| `HybridPhaseTransformer` end-to-end | Implemented in `symbolu/phase_transformer.py` with Local-only, Protected-Phase, Binding-Cache Quad Query, and SlotMemoryGCT modules composed in a single training loop. |
| Reference configuration | 46M params — 768 embed × 12 layers × 12 heads, 4 local + 8 hybrid, 256 window, 8K max seq len, tied embeddings, learnable logit scale. |
| 7B-class training recipe | `train_hybrid_7b.py` — 4096 embed × 32 layers × 32 heads, GQA 8 KV heads, 16 local + 16 hybrid, 4-bit quantization, 8-bit optimizer, gradient checkpointing, torch.compile, A100-80GB target. |
| Linear / phase branch | O(n) cumulative-sum scan with complex phasors, three readout modes (`standard`, `shifted`, `complex`), per-head phase offsets, optional per-head decay, chunked sequence support for arbitrarily long documents. |
| Binding-Cache Quad Query (V10.4) | Top-K proposal mode with conditional skip when phase confidence exceeds a threshold. |
| Slot memory | 64 slots, detached write path, retrieval loss beyond the window, every-200-step ablation eval, adaptive slot LR controller with bootstrap → adaptive → stabilize phases. |
| Inference path | `symbolu/inference/` module with Fast / Standard / Sovereign modes, Phase State Cache for O(1) per-step phase update, and V11.0.0 inference filters (Vritti gate, Kosha depth control, Sovereign Bridge). `generate_sovereign.py` CLI is wired end-to-end. Status doc: `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` — the inference stack is implemented end-to-end; remaining work is benchmark and scale validation. |
| Training-time instrumentation | `SovereignPhaseController`, `AdaptiveTrainingController`, and `AdaptiveSlotLRController` — surgical gradient clipping per numerical regime (slot keys on unit sphere, phase sin/cos amplification, global norm), PPL-alpha curriculum, adaptive warmup on validation PPL rather than fixed steps. |

### Preliminary retrieval signal (separate research report)

An internal phase-attention technical report documents a **small
240K-parameter pure-phase model** hitting **100% accuracy on a
controlled needle-in-haystack retrieval task at 2,048 and 10,000
token recall distances**. This is a deliberately isolated retrieval
benchmark — it validates the core phase-memory mechanism, not the
full hybrid language-modeling stack, and it does not replace standard
LM benchmarks. We treat it as a **mechanism-level signal**, not a
product-level claim. A formal LM benchmarking pass on the hybrid model
is explicitly on the roadmap below.

### Training recipe (honest summary)

| Setting | Default |
|---|---|
| Optimizer | AdamW with separate parameter groups for main and slot weights; optional 8-bit via bitsandbytes |
| LR schedule | Linear warmup → cosine annealing, warmup can be driven by PPL threshold instead of fixed step count |
| PPL-α curriculum | `alpha_phase` and `alpha_local` interpolated between 0.8 and 0.3 based on current PPL regime; post-curriculum adaptive α driven by slot ablation delta |
| Loss composition | `L_CE + L_router + w_retr · L_retrieval + w_pred · L_slot_prediction + L_entropy_band (opt) + L_decorrelation (opt)` |
| Gradient management | Per-element clip 0.005 on phase fused projections, per-element clip 0.01 on slot keys, separate norm clips for slot and phase, global norm clip, gradient throttle on spikes |
| Dataset support | WikiText-103, FineWeb (7B recipe), synthetic smoke harnesses |

### Honest scope caveats

We want VCs to see exactly what is validated at what scale, because
the interesting benchmarks on this architecture are still ahead of us:

| Topic | Current reality |
|---|---|
| Needle-in-haystack retrieval accuracy | Validated on a small (~240K-param) pure-phase model on a controlled synthetic task. Not yet replicated on the full 46M reference or the 7B recipe. |
| Long Range Arena / LRA tasks | Discussed in the internal report, **not yet run end-to-end** on our hybrid model at competitive scale. |
| Head-to-head vs. open-weights baselines | Side-by-side comparisons against Mistral, LLaMA, or Mamba at matched parameter count are **not yet published**. They are the top roadmap item. |
| 7B training status | `train_hybrid_7b.py` is runnable and the recipe is set, but the training run is operator-driven on an A100-80GB environment, not a push-button repo result. |
| Binding-Cache Quad Query | Implemented with Top-K proposal mode and conditional skip; ablation data vs. pure Protected-Phase is the most useful next experiment and is planned. |
| Slot memory ablation | The every-200-step ablation eval is live and feeds adaptive controllers — but "slots helping / hurting" is a relative signal inside our own training run, not an external benchmark. |

### Next 12 months

**Quarter 1 — External benchmarking pass**
- Full Long Range Arena (LRA) sweep at matched parameter count against Transformer, Performer, Linear Transformer, S4, Mamba baselines — specifically on Path-X and Retrieval where linear-decay models struggle.
- Needle-in-haystack retrieval at 2K / 10K / 32K / 100K tokens on the 46M reference model and a 1.3B intermediate, not just on the 240K pilot.
- Publish a head-to-head report (PPL and retrieval) vs. Mistral-7B and Mamba-2.8B at matched parameter budget.

**Quarter 2 — Binding-Cache Quad Query ablations and inference throughput**
- Publish ablation data isolating the contribution of (i) Protected Phase vs. parallel blend, (ii) Binding-Cache Quad Query with and without conditional skip, (iii) slot memory with and without reads.
- Ship an inference-throughput report using the Phase State Cache (O(1) per-step phase update) against a standard KV-cache transformer at matched context length, focused on the 8K–32K range where hybrid should shine.

**Quarter 3 — Scale the 7B recipe end-to-end**
- Run the `train_hybrid_7b.py` recipe to completion on FineWeb against a reproducible checkpoint.
- Validate the same hybrid recipe on an open-weights backbone-hybrid path (`mistral_hybrid_wrapper.py`) so the architecture is shown to be backbone-agnostic, not tied to our from-scratch model.
- First external research preview release (weights + eval harness).

**Quarter 4 — Product coupling**
- Expose the Hybrid LLM as a first-class backend adapter for the Agentic Framework, so governed agents get long-context hybrid inference without rewiring.
- Begin work on a paper submission documenting the Protected-Phase serial-fusion architecture and the LRA / retrieval ablations.

### The ask

We are raising seed capital to take `HybridPhaseTransformer` from a
working training stack with a validated phase-memory mechanism to a
**benchmarked, published, and productized** long-context LLM
architecture. The research risk is concentrated in well-identified
places — LRA and retrieval sweeps at scale, the 7B training run, and
ablations that isolate each of the three fused attention mechanisms —
and the implementation risk is reduced because the training recipe,
inference path, and adaptive controllers are already built; the
remaining uncertainty is concentrated in scale training and external
benchmarking.

*Modules: `symbolu/phase_transformer.py`, `train_hybrid_7b.py`, `symbolu_training/training/unified/mistral_hybrid_wrapper.py`, `symbolu/inference/`*
*Architecture ref: `docs/HYBRID_PHASE_QUAD_ARCHITECTURE.md` · Training CLI: `docs/TRAIN_HYBRID_7B.md` · Inference status: `docs/INFERENCE_HYBRID_TRANSFORMER_GAPS.md` · Mechanism report: `docs/PHASE_ATTENTION_PAPER.md`*

---

<!-- ═══════════════════════════════════════════════════════════════════ -->
# Company Summary
<!-- ═══════════════════════════════════════════════════════════════════ -->

## How the Five Products Compose

Cognade Labs is not five unrelated projects — it is a vertically integrated AI infrastructure stack where each layer feeds the others:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  5. Hybrid LLM              Long-context attention substrate            │
│     └──► 4. CG LLM          Multi-field token evaluation + 32D state   │
│           └──► 3. Agentic    Governed runtime reading model internals   │
│  2. CTM+/PCAM               KV-cache eviction for inference serving    │
│  1. Cloud Scaling Controller Decision-quality layer for infrastructure  │
└──────────────────────────────────────────────────────────────────────────┘
```

- The **Hybrid LLM** provides efficient long-context attention; **CG LLM** adds interpretable multi-field generation on top of it.
- The **Agentic Framework** consumes CG's 32D state for signal-enriched governance — a capability no wrapper around a closed API can replicate.
- **CTM+/PCAM** ensures the KV-cache that serves both models evicts intelligently, not blindly.
- The **Cloud Scaling Controller** ensures the underlying compute scales only when scaling actually helps.

Each product is independently deployable and independently valuable. Together they form a defensible, vertically integrated position across the AI infrastructure stack.

## Aggregate Evidence

| Metric | Value |
|---|---|
| Total tests across all products | **3,200+** (228 scaling + 276 CTM+/PCAM + 1,550 agentic + CG smoke + hybrid training) |
| Adversarial safety scenarios (scaling) | 19 scenarios, **0 catastrophic / severe failures, 0 SLO regressions** |
| FSCS signal validation (CTM+) | **100% eviction rounds changed** with enhanced signals on real Mistral-7B trace |
| Agentic governance invariant | `cancel → budget → approve → execute` — **pinned by test suite** |
| CG trainable parameters | **~5M** on frozen Mistral-7B (4-bit: ~14GB VRAM) |
| Phase-attention retrieval | **100% needle-in-haystack at 10K tokens** (240K-param pilot) |
| LLM inference improvement (CTM+) | **+50% concurrent requests, −29% p99 latency** vs. LRU |

## The Unified Ask

We are raising seed capital to take five validated, tested infrastructure products from internal proof-of-concept to external design-partner deployments and first revenue. Specifically:

- **Cloud Scaling Controller** — Stage 5 (active mode) and first paid deployments
- **CTM+/PCAM** — FPGA prototype and serving-tier benchmark closure
- **Agentic Framework** — Managed runtime, low-code console, and SOC 2 readiness
- **Conscious Generation LLM** — Close the training-to-inference gap and publish ablations
- **Hybrid LLM** — External benchmarks (LRA, retrieval) and 7B training run

The technology is built and internally validated. The capital is for benchmarks, partners, and the managed infrastructure that converts research results into enterprise revenue.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu`*

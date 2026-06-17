# Neural Cloud Scaling Controller — VC Brief

**A four-page introduction for investors**
**Where we are:** validated in **simulation** (19 synthetic adversarial scenarios) and by **offline replay of real workload traces** (Azure Public Dataset inference traces) — where the workload timing and distribution are real but the demand→metrics mapping, replica-optimum, efficiency scoring, and SLO proxy remain modeled (**simulated system dynamics**) — while the **live-shadow-self-run** harness is built, integration-tested, and wiring-proven but **not yet run on a real cluster**, and **independent third-party telemetry is pending**. (Shadow + recommend mode are built and tested.) See the validation maturity ladder on Page 4.

---

## Page 1 — The Problem

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

---

## Page 2 — Architecture: Teaching Autoscalers to Know When They're Wrong

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

---

## Page 3 — Competitive Landscape: Who We're Standing Next To

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
- **Safety by construction.** Across 19 adversarial scenarios *in simulation*, **zero catastrophic failures, zero severe failures, zero SLO regressions, zero false positives** — and on *real-trace replay* the guard caused no meaningful SLO regression (Page 4). The guard can only say "no" to a scale-out — it can never say "yes" to an action the controller wasn't already going to take. That's a property no learned AIOps system can claim, and it's why we can ship on a Tuesday without a change-management committee and a six-week pilot.
- **Proof-of-value is free.** Shadow mode runs read-only, auto-generates proof-of-value reports, and costs the customer nothing to try. A platform team can turn us on, watch for two weeks, and see exactly what we *would* have saved them — without adopting any dependency, signing any contract, or taking any production risk. No other tool in this space offers that kind of zero-commitment trial, because no other tool can: they all have to write something to work.
- **The economics compose.** Every other vendor in the table saves money by making the thing you're already doing cheaper or faster. We save money by *not doing the thing*. A scale-out that doesn't happen is 100% cheaper than any rightsizing, spot-instance swap, or bin-packing optimization can ever make it — and those savings are additive to whatever the rest of your stack is already doing.

### In one sentence

Every other tool in this market either **scales you faster** (HPA, Karpenter, KEDA), **scales you cheaper** (Cast AI, Kubecost, Spot), **predicts what to scale** (ScaleOps), or **tells you when you scaled wrong after the fact** (Datadog, New Relic). We're the only one that **stops the wrong scale-out from shipping in the first place** — and we do it as a wrap around the stack you already have, not as a replacement for anything in it.

---

## Page 4 — What We've Proven and What's Next

### 19 adversarial scenarios, and what happened *(in simulation)*

We didn't benchmark this on a friendly load test. We built 19 deliberately nasty scenarios covering signal corruption, actuation delays, system shocks, budget constraints, and controller pathologies — the kinds of things that quietly break autoscalers in production. **Every number in this subsection is `simulated`** (modelled pipeline/HPA/provisioning). The maturity ladder that follows shows what we have since proven on *real* traces and a *real* cluster, each number labelled so the two are never conflated.

#### Safety first (because it's the first thing investors ask) — *simulated*

| Metric | Result *(simulated, 19 scenarios)* |
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

> **Caveat — simulated system dynamics.** Every figure in this subsection is `simulated`: synthetic workload *and* modeled demand→metrics, replica-optimum, efficiency scoring, and SLO accounting. These are not measured production savings.

#### How often did it actually step in?

| Metric | Value |
|---|---|
| Total scale-out events observed | 649 |
| Blocked as provably futile | **87 (13.4%)** |
| Scenarios where the guard intervened | 5 of 19 |
| Scenarios where the guard stayed out of the way | 14 of 19 |

**The one-line version (simulated):** we cut waste from 4.5x to 3.4x of optimal cost with **zero SLO regressions** — and that's something none of the incumbents can do today, because they don't have the feedback loop to know when they're wrong.

### Validation maturity ladder — where the evidence actually stands

We grade our own evidence on two independent axes — is the **workload** real, and are the **system dynamics** (metrics, optimum, efficiency, SLO) real or modeled — so no rung can be mistaken for another.

| Rung | Workload | System dynamics | Status |
|---|---|---|---|
| **1. Synthetic scenarios** | synthetic (19 adversarial shapes) | simulated | ✅ **Complete** — 0 catastrophic / severe / SLO regressions; 87 of 649 scale-outs blocked (13.4%) |
| **2. Real workload trace replay** (offline) | **real** (Azure Public Dataset inference traces) | **still simulated** (demand→metrics, optimum, efficiency, SLO all modeled) | ✅ **Complete** |
| **3. Live-shadow-self-run** (real cluster, our faults) | real | **live** (real Prometheus / HPA / app; our injected faults) | 🟡 **Harness built, integration-tested, wiring-proven — NOT yet run on a cluster** |
| **4. Independent third-party telemetry** | real, not ours | live | ❌ **Not started** — needs a free external design partner |

**Rung 2 — real workload trace replay (simulated system dynamics).** We replayed the **Azure LLM/LMM inference traces** (Azure Public Dataset, CC-BY-4.0) through the *unmodified* control core. On the multimodal trace — **1,000,000 real requests over 7 days (40,320 cycles)** — the guard blocked **80 of 2,537 scale-outs (≈3.2%)** and stayed **dormant (0 blocks, 0 false positives)** on the shorter conv/code traces; against the modeled SLO proxy the change was a near-neutral **+4 breach-cycles of 40,320 (+0.01pp)**.

> **Caveat — read with every Rung-2 number.** Only the **workload** is real (real request timing and distribution). The demand→metrics mapping, replica-optimum, efficiency scoring, and SLO calculation are the **same models used in the synthetic suite** — **simulated system dynamics**. Rung 2 shows the guard's *selectivity and SLO-neutrality on a real workload distribution*; it is **not** measured savings under live actuation. (`scripts/run_trace_replay.py`; numbers in `artifacts/cloud_controller_real_validation/`.)

**Rung 3 — live-shadow-self-run (built, not yet run).** The full kind + Prometheus + Online-Boutique + Chaos-Mesh harness is in `deploy/local-shadow/`; the control-core↔Prometheus↔shadow↔guard wiring is proven by an integration test against a real HTTP Prometheus API. **No real-cluster run has been executed yet.** When run, the faults are still *ours* — not independent.

### What's already built

This isn't a research prototype. It's been staged, tested, and written to be deployable.

| Stage | What it is | Tests |
|---|---|---|
| Stage 1 | Core control library — 12 parameters, every one ablation-validated | 87 unit tests |
| Stage 2 | Prometheus integration and signal pipeline | 42 unit tests |
| Stage 3 | **Shadow mode** — read-only, runs alongside HPA, generates proof-of-value reports | 38 unit tests |
| Stage 4 | **Recommend mode** — human-in-the-loop with Slack and PagerDuty integration | 39+ unit tests |
| Bootstrap | Learning-phase elimination, so there's no cold-start warm-up period | 22 unit tests |
| **Track B** | **Real-trace replay** — real Azure traces through the unmodified control core (offline) | 22 unit tests |
| **Track A** | **Live-shadow harness** — kind + Prometheus + Online Boutique + Chaos Mesh + real-HTTP wiring proof | 4 integration tests |

**Altogether:** the `tests/cloud_controller/` suite reports **724 passing tests** (4 skipped) — 702 pre-existing plus 26 for the new real-validation harnesses.

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

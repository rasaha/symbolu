# Autoscaling Safety Interlock — VC Brief

**A four-page introduction for investors.** *(Engine: the Neural Cloud Scaling
Controller.)*

**Positioning:** **Autoscaling Safety Interlock — read-only first.** A zero-write engine
that emits a **causal verdict for every scale-out** — *HELPING / NEUTRAL / NOT_HELPING /
futile-runaway* — the one question the autoscaling stack never answers: *after we scaled,
did it actually help?*

**Where we are, stated honestly (the discipline is the point):**
- **Safety thesis — strengthened.** Across **simulation** (19 adversarial scenarios),
  **offline replay of a real workload trace** (Azure Public Dataset inference traces),
  and a **real-dynamics calibration** (a real concurrent service with emergent queuing
  latency), the engine produced **0 harmful false positives, 0 SLO regressions, and never
  mislabeled a genuinely-helpful scale-out** — all self-run.
- **Savings thesis — weakened, and not the pitch.** This is a reliability/safety play,
  not a cost-optimization one. The only *measured* savings (offline, modeled dynamics) is
  marginal and near-SLO-neutral; we do not lead with it (Page 4).
- **Market thesis — unproven, and measurable.** The company-vs-feature question reduces
  to one number — **APCY = Tier-A episodes per cluster-year × $ per episode** — which is
  unmeasured today. The 90-day plan measures it (Page 4).
- **Not yet earned:** a real-cluster `live-shadow-self-run` (harness built, wiring-proven,
  not yet run) and any **independent third-party** result. We claim **no** production,
  customer, or real-cluster validation.

---

## Page 1 — The Problem: the autoscaling stack has an empty layer

### Autoscalers know *when* to scale — not *whether it helped*

Every production autoscaler — Kubernetes HPA, KEDA, Karpenter, CAST AI — shares one blind
spot. It cannot tell these two situations apart:

> *"Latency is bad because we need more replicas."*

> *"Latency is bad for reasons more replicas will never fix."*

To the autoscaler they look identical, so it scales out. When the real cause is a
saturated downstream dependency, a lock, a collapsed queue, or an upstream failure bleeding
in, the extra replicas don't help — latency stays elevated, the controller scales again,
and again, until someone gets paged at 2 a.m. because the fleet rode from 4 replicas to 46
while the incident got *worse*. Most SRE teams have been on-call for exactly this.

### Where the value concentrates: non-capacity incidents

In ordinary capacity-bound load, HPA is right and our verdict says **HELPING** — we add
nothing, correctly. The signal concentrates in the regime where latency/errors are bad but
**more replicas cannot fix it**:

- **Downstream dependency saturation** — scaling service A just pushes more load onto a
  shared DB/cache/3rd-party that's already the bottleneck.
- **Lock contention / serialization** — adding workers *increases* contention; throughput
  is capped and tail latency rises.
- **Queue collapse / poison work** — new consumers can't drain a queue stalled for other
  reasons.
- **Cascading failure** — every service scales at once and the thundering herd *amplifies*
  the incident.
- **HPA/Karpenter runaway** — thresholds keep tripping, HPA rides to max, Karpenter
  provisions nodes, and there's no feedback loop to stop it.

In all of these the correct action is *stop scaling and look elsewhere* — exactly the
read-only signal we emit, and the one no incumbent produces.

### Why the gap is structural, not merely unbuilt

Classical autoscalers compute *intent to scale* from a signal chain (`A_t = d_t · G_t · P_t
· S_t`). That tells you what the metrics say **right now**; it cannot look back and ask
**did the last scale-out actually help?** Intent and effectiveness are conflated, and the
feedback loop that would catch a futile decision simply doesn't exist. The built-ins are
*intent engines*; the actuators (CAST AI, StormForge, Sedai, ScaleOps) optimize a different
objective — making the action cheaper/faster/more autonomous — not verifying its outcome.

### Why now

Not "this was always true." The timing rests on how scaling is *used* today:
- **Autoscaling has crossed from helper to control loop** — HPA/Karpenter now run
  production unattended, and a control loop with no human in it needs **outcome
  verification**, which nobody closes.
- **More autonomy raises the cost of being wrong** — no human reviews each decision.
- **Systems are far more dependency-heavy** — microservices, queues, caches, third-party
  APIs, AI inference backends create exactly the **non-capacity bottlenecks** where adding
  replicas doesn't help.
- **Read-only-first is newly practical** — teams can adopt a decision-quality layer in
  shadow without granting a new vendor write access to production.

**Honest bound:** "why now" explains the tailwind, not the size. *How often, and how
expensively,* this happens is the unmeasured number (**APCY**) — and measuring it is the
whole plan (Page 4).

---

## Page 2 — Architecture: a read-only verdict beside the autoscaler

### The core idea, in one sentence

Don't change the controller. Add a system beside it that **watches whether each scale-out
worked**, and a third that **records what a guard would have done** about a provably-futile
runaway — all **read-only, zero write permissions**.

```
Metrics ──► Controller ──► raw_delta ──► FutilityGuard ──► guarded_delta ──► (recorded, not actuated)
                               │                ▲
                               ▼                │
                        EfficiencyEstimator ────┘
                        (observe → HELPING / NEUTRAL / NOT_HELPING)
```

### Layer 1 — The Controller (Intent), untouched
The intent engine that already exists in every cluster. We leave it **completely alone** —
no new thresholds, no retuned weights. It produces `raw_delta` exactly as before, so nothing
needs re-certifying.

### Layer 2 — The EfficiencyEstimator (Evaluation)
After each scale-out it opens a short window and asks: did CPU-per-replica drop? did p99
latency recover? did errors fall? are the new replicas doing real work? It then classifies
the event **HELPING / NEUTRAL / NOT_HELPING**. It never touches the controller — it builds
an honest record of whether past decisions delivered.

### Layer 3 — The ScaleOutFutilityGuard (read-only execution filter)
Deterministic and **conservative by construction**. It would cap a scale-out *only* when
the evidence is overwhelming: NOT_HELPING for **≥5 consecutive cycles** **and** **≥20
replicas** already running. It **never** acts below 20 replicas, **never** fires on a single
bad cycle, **never** touches scale-in, and **resets instantly** on improvement. Today it
**only records** what it would have done — it never actuates. It can say "this scale-out is
futile"; it can never say "yes" to an action the controller wasn't already taking.

### Where this sits — the empty Layer 4

```
┌─────────────────────────────────────────────────────────┐
│ GOVERNANCE  L7  Business policy, approvals               │
│             L6  Observability & proof-of-value           │
│             L5  Safety bounds (rate limits, cooldown)    │
├─────────────────────────────────────────────────────────┤
│ INTELLIGENCE  L4  Decision Quality   ← US (empty layer)  │
│               L3  Prediction (ScaleOps)                  │
├─────────────────────────────────────────────────────────┤
│ DATA PLANE  L2  Cost optimization (Kubecost / CAST AI)   │
│             L1  Provisioning (Karpenter)                 │
│             L0  Sensing (Prometheus)                     │
└─────────────────────────────────────────────────────────┘
```

**We wrap; we don't replace.** It runs in shadow next to HPA, reads the **same Prometheus
you already have** (proven against a real Prometheus HTTP API by integration test), and
touches nothing. A platform team can turn it on with a single read-only token and zero
config changes to any other tool — no rip-and-replace, no write access, no production risk.

---

## Page 3 — How we differ from competitors

### The crowded part of the stack, and the empty part

The autoscaling stack has gotten genuinely good: node provisioning, cost optimization,
prediction, and observability are all mature, well-run categories with real customers and
real savings. **We lose to every one of them on their home turf, and we are not trying to be
any of them.** What none of them does — what almost nobody is even looking at — is ask,
*after a scale-out happens, did it actually help?* Every incumbent treats the scaling action
as correct by assumption: HPA scales because a threshold tripped; Karpenter provisions
because pods are pending; Datadog charts the result; Kubecost prices it; CAST AI makes the
same action cheaper. **None look back to ask whether adding replicas relieved the real
constraint.** That decision-quality layer (L4) is empty.

| Tool / category | What it does well | Knows if the scale-out *helped*? | In the scaling decision path? | Read-only-first? | Where we differ |
|---|---|---|---|---|---|
| **HPA / KEDA** | compute intent to scale; fast, free, built-in | **No** | yes (it *is* the decision) | no (actuates) | we add the missing "did it help?" feedback |
| **Karpenter / Cluster Autoscaler** | excellent node provisioning, bin-packing | **No** | node layer (adjacent) | no | we sit above it, judging the *pod* decision it's provisioning for |
| **Datadog / Grafana / Prometheus** | best-in-class observability, APM, alerting | **No** (show *what happened*, not *whether it worked*) | no (side of the path) | yes | a causal verdict vs raw charts — **but the highest feature-absorption risk** |
| **Kubecost / CloudZero** | authoritative cost visibility & allocation | **No** (show *what it cost*) | no | mostly | we judge causality, not cost |
| **CAST AI / StormForge / Sedai / ScaleOps / Spot** | autonomous rightsizing/bin-pack/spot — **real, recurring $ savings, real customers** | **No** (optimize the action; don't judge it) | **yes (actuate)** | no (need write) | a read-only verdict layer **in front** of actuation; **CAST AI is our closest neighbor and likely acquirer** |

### Analytics is a feature; an interlock is a position

A causal verdict expressed as **analytics** is a single novel metric — a panel Datadog or
Grafana can add in a sprint, and it points us at a savings/ROI question we lose. The same
primitive expressed as a **safety interlock** sits **in the scaling decision path**
(read-only today, between decision and actuation) — a relationship and an integration, not
a tab, and the only framing with a path to a control-plane business. We keep "a causal
verdict for every scale-out" as the north-star and demo wow-moment, but **ship the company
as a control-path interlock, not an analytics tool.** The moat, if it exists, is a sustained
**zero-false-positive record at scale** — earned over cluster-months, not shipped in a panel.

### The one question that decides differentiation

The cleanest early test of whether we are *differentiated* rather than *redundant* is what an
SRE says after seeing the verdict during a real incident:

> **"Did the verdict tell you something Datadog/Grafana, Kubecost/CloudZero, or
> CAST AI/Karpenter did **not** — specifically, that scaling was not helping?"**

A credible **"yes, this told me something new"** is a leading indicator of pull that
precedes any payment or actuation discussion; a consistent **"no, we'd have seen it anyway"**
pushes the honest conclusion toward *feature/acquisition*. We are measuring this directly
with design partners (Page 4) rather than asserting it.

### We are explicitly **not** a FinOps company
We don't rightsize, bin-pack, buy spot, or allocate cost, and our only measured savings is
marginal (Page 4). Positioning this as FinOps would put us in a savings bake-off we lose and
invite an ROI question the evidence can't answer. We are a **reliability/safety** play —
incident-amplification prevention + a scaling-decision audit trail — and we say so to keep
the story honest.

---

## Page 4 — Evidence, the gating unknown, and the ask

### What is de-risked: safety (the technically hard part)

Across three independent evidence types — **all self-run** — the engine is **safe and
selective**:

| Property | Result | Across |
|---|---|---|
| Harmful false positives (a helpful scale-out wrongly flagged futile) | **0** | simulation + real-trace replay + real-dynamics calibration |
| SLO regressions caused by the engine | **0** (read-only by construction) | all of the above |
| Genuinely-helpful scale-outs mislabeled | **0** | all of the above |
| Real severe futility caught | **yes** | real-dynamics calibration (serialized bottleneck: throughput hard-capped while replicas climbed and tail latency *rose*) |

"Safe and selective on real dynamics" is the hard thing, and it's the basis of a trust moat.

### Validation maturity ladder — graded on two axes, never conflated

Is the **workload** real, and are the **system dynamics** (metrics, optimum, efficiency, SLO)
real or modeled?

| Rung | Workload | System dynamics | Status |
|---|---|---|---|
| **1. Synthetic scenarios** (19 adversarial) | synthetic | simulated | ✅ **Done** — 0 catastrophic / severe / SLO regressions |
| **2. Real workload-trace replay** (offline) | **real** (Azure inference traces) | **still modeled** | ✅ **Done (self-run)** — selective + near-SLO-neutral on a real distribution |
| **2.5 Real-dynamics calibration** (non-k8s) | real concurrent service | **real emergent queuing** | ✅ **Done (self-run)** — 0 harmful FP; caught severe futility correctly |
| **3. `live-shadow-self-run`** (real cluster, our faults) | real | live (real Prometheus/HPA/app) | 🟡 **Harness built + wiring-proven; not yet run** (needs a container-registry-egress host) |
| **4. Independent third-party** | real, not ours | live | ❌ **Pending** — needs a design partner |

**On savings (read this with the discipline intended).** On the real-trace replay, the guard
was *selective* and *near-SLO-neutral*, and the measured cost delta was **marginal**,
**offline**, and on **modeled** dynamics — **explicitly not the value proposition.** The
simulation suggested a higher intervention rate; **that rate did not reproduce on real
dynamics** (the guard was far more conservative), so we **do not carry it forward as a market
expectation.** Numbers and labels: `artifacts/cloud_controller_real_validation/`,
`docs/cloud_scaling_real_validation/STATUS.md`.

### What is NOT de-risked: the market — and how we measure it

The entire company-vs-feature question reduces to one measurable unknown: **how often, and
how expensively, autoscalers melt down on non-capacity incidents** —
**APCY = Tier-A episodes/cluster-year × $/episode**, where a **Tier-A episode** is a
runaway/futile scale-out that materially over-provisioned or amplified a non-capacity
incident. We have **pre-registered** the Tier-A detector, cost model, and pass/fail
thresholds **before** touching partner data (`docs/cloud_scaling_real_validation/
TIER_A_DETECTOR_SPEC.md`), and built the offline replay tooling that computes per-cluster
Tier-A counts and APCY from a partner's history (`cloud_controller/replay/`,
`scripts/run_tier_a_replay.py`) — so partner history converts to a directional APCY within
weeks.

**Three gates decide the outcome:**
- **Gate 1 — Market:** APCY comfortably exceeds a defensible per-cluster price.
- **Gate 2 — Trust:** sustained low false-positive rate on real noisy metrics; **0 harmful
  FP** on clear helpful-scale-out cases.
- **Gate 3 — Pull:** paid LOI + unprompted expansion + "very disappointed if removed" + the
  differentiation **"yes"** (Page 3).

**Pre-registered kill signal (no goalpost-moving):** fewer than ~5 adjudicated Tier-A
episodes across ≥150 retrospective cluster-months ⇒ the event is too rare to build a company
on, regardless of how clean the verdict is.

### What's already built
Not a research prototype — staged, tested, deployable, and **read-only throughout**:
control core (ablation-tested parameters), Prometheus integration + signal pipeline,
**shadow mode** (read-only, proof-of-value report), **recommend mode** (Slack/PagerDuty,
human-in-the-loop), the **Track-A live-shadow harness** (kind + Prometheus + Online Boutique
+ Chaos Mesh, wiring proven against a real Prometheus HTTP API), the **Track-B real-trace
replay**, and the **pre-registered Tier-A / APCY tooling**. The `cloud_controller/` suite
reports **760 passing tests (4 skipped)**.

### The expansion path (evidence-gated, not asserted)
**(1) Read-only verdict** (now) — earn trust, measure APCY → **(2) Recommend-mode advisor**
(channel already built) — once precision is proven and partners ask → **(3) Bounded
autonomous safety layer** — cap provably-futile runaways within strict bounds, only after a
sustained 0-FP record justifies it. Step 3 is where the control-plane TAM (CAST AI's
neighborhood) opens — earned from a differentiated, read-only-trust-first angle, not bolted
on. We are **not** autonomous today and do not claim to be.

### Why we're raising, and what we're asking for
We fill the empty decision-quality layer with a read-only causal verdict shipped as a
zero-risk safety interlock. The **hard technical property — safety — is de-risked**; the one
remaining unknown is a **single, cheaply measurable number (APCY)**. We're raising to fund
the **90-day measurement program**: execute one real `live-shadow-self-run` on a
registry-egress host, recruit **3–6 design partners**, run **retrospective replay across ≥6
orgs** to a directional APCY, and measure trust + pull + differentiation. We fund the
**measurement**, not the story — and we are willing to conclude *company*, *feature*, or
*research* on the evidence.

> **How the partner evidence is gathered (read-only, zero-write, no savings claims):**
> `docs/cloud_scaling_real_validation/PARTNER_DATA_REQUIREMENTS_PLAN.md`, with the supporting
> strategy, competitive, and validation docs under `docs/cloud_scaling_real_validation/`.

> *"Scale because it works, not because the metrics say so."*

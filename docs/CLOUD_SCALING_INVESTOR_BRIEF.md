# Autoscaling Safety Interlock — Investor Brief

**Shareable / non-confidential.** High-level summary for investor conversations. Every claim is
labeled **self-run validation** (our own tests, not third-party), **unproven** (measurable, not yet
measured), or **built** (shipped code). Written to build credibility: the limits are stated with the
strengths, and we are willing to conclude *company*, *feature*, or *research* on the evidence.

---

## One line

A **read-only, zero-write** layer that sits beside your autoscaler and answers the one question the
scaling stack never does: **after we scaled out, did it actually help?** It emits a causal verdict for
every scale-out — **HELPING / NEUTRAL / NOT_HELPING / futile-runaway** — and touches nothing.

---

## The gap it fills

Every production autoscaler (Kubernetes HPA, KEDA, Karpenter, CAST AI) knows *when* to scale. **None
knows whether the last scale-out helped.** It cannot tell "latency is bad because we need more
replicas" from "latency is bad for reasons more replicas will never fix." So on **non-capacity
incidents** — a saturated downstream dependency, lock contention, a collapsed queue, a cascading
failure — it scales, and scales again, riding the fleet from 4 replicas to 46 while the incident gets
*worse*. That decision-quality layer is structurally empty: incumbents optimize the scaling action
(cheaper, faster, more autonomous); none look back to verify it worked.

---

## What is de-risked: safety (the technically hard part) — *self-run validation*

Across three independent evidence types — all self-run — the engine was **safe and selective**:

| Property | Result | Evidence base |
|---|---|---|
| Helpful scale-outs wrongly flagged futile (harmful false positives) | **0** | 19 adversarial simulations + real Azure inference-trace replay + a real-dynamics calibration |
| SLO regressions caused by the engine | **0** (read-only by construction) | all of the above |
| Genuinely-helpful scale-outs mislabeled | **0** | all of the above |
| Real severe futility caught correctly | **yes** | real-dynamics run: throughput hard-capped while replicas climbed and tail latency *rose* |

"Safe and selective on real dynamics" is the hard property, and it is the basis of a trust moat earned
over cluster-months — not shipped in a dashboard panel.

**Built, tested, deployable:** read-only shadow mode (proof-of-value report), human-in-the-loop
recommend mode (Slack/PagerDuty), a live-shadow test harness, real-trace replay tooling, and a
pre-registered market-measurement toolchain. **760 passing tests.**

---

## What we openly concede

- **Not a cost-savings play.** Our only measured savings is **marginal, offline, and on modeled
  dynamics** — explicitly *not* the pitch. Positioning this as FinOps would put us in a bake-off we
  lose. This is a **reliability/safety** play: incident-amplification prevention + a scaling-decision
  audit trail.
- **No production, customer, or real-cluster validation.** The safety evidence above is **self-run**.
  A real-cluster live-shadow run (harness built, not yet run) and any independent third-party result
  are **not yet earned**, and we don't claim them.
- **The market is unproven** — but it reduces to a single measurable number (below), which is exactly
  what we're funding.

---

## How we differ

We **wrap, we don't replace.** It runs in shadow next to HPA, reads the same Prometheus you already
have, and needs only a single **read-only token** — no rip-and-replace, no write access, no production
risk.

| Category | What it does well | Knows if the scale-out *helped*? |
|---|---|---|
| HPA / KEDA | compute intent to scale — fast, free, built-in | **No** — it *is* the decision |
| Karpenter / Cluster Autoscaler | node provisioning, bin-packing | **No** |
| Datadog / Grafana / Prometheus | best-in-class observability | **No** — show *what happened*, not *whether it worked* |
| Kubecost / CloudZero | authoritative cost visibility | **No** — show *what it cost* |
| CAST AI / StormForge / Sedai / ScaleOps | autonomous rightsizing — real recurring savings | **No** — optimize the action; don't judge it |

The primitive expressed as *analytics* is a panel a competitor can add in a sprint. Expressed as a
**safety interlock in the scaling decision path** (read-only today), it's a relationship and an
integration, not a tab — the only framing with a path to a control-plane business. Honest risks:
Datadog/Grafana are the highest feature-absorption threat; CAST AI is the closest neighbor and a likely
acquirer.

---

## The one number that decides company-vs-feature

Everything reduces to **APCY = Tier-A episodes per cluster-year × $ per episode**, where a *Tier-A
episode* is a runaway/futile scale-out that materially over-provisioned or amplified a non-capacity
incident. **APCY is unmeasured today.** We have **pre-registered** the episode detector, cost model,
and pass/fail thresholds *before* touching any partner data, and built the replay tooling that turns a
partner's own history into a directional APCY within weeks.

**Pre-registered kill signal (no goalpost-moving):** fewer than ~5 adjudicated Tier-A episodes across
≥150 retrospective cluster-months ⇒ the event is too rare to build a company on — and we'll say so.

---

## The ask — fund the measurement, not the story

We're raising to run a **90-day measurement program**: execute one real live-shadow run on a suitable
host, recruit **3–6 design partners**, run retrospective replay across **≥6 organizations** to a
directional APCY, and measure three gates — **market** (APCY beats a defensible per-cluster price),
**trust** (sustained near-zero false positives on real noisy metrics), and **pull** (paid LOI +
unprompted expansion + a credible "this told me something my existing tools did not").

**Expansion path (evidence-gated, not asserted):** read-only verdict (now) → recommend-mode advisor
(channel already built) → a **bounded** autonomous safety layer that caps provably-futile runaways —
only after a sustained zero-false-positive record justifies it. We are **not** autonomous today and do
not claim to be.

---

## Evidence key (due-diligence)

| Claim | Status |
|---|---|
| 0 harmful false positives / 0 SLO regressions / 0 mislabeled helpful scale-outs | **Self-run validation** (simulation + real trace + real-dynamics) |
| Caught real severe futility (throughput capped while replicas rose) | **Self-run validation** |
| Read-only / zero-write; wraps existing Prometheus + HPA; 760 passing tests | **Built** |
| Cost savings | **Marginal / offline / modeled — not the pitch** |
| APCY (market size) | **Unproven — measurable; the 90-day plan measures it** |
| Production / customer / real-cluster / third-party validation | **None — not claimed** |

---

*This brief states positioning and self-run results, not proprietary control-system detail (available
to qualified partners under NDA). "Self-run" means our own tests, not independent third-party
validation. Nothing here is a forward-looking guarantee.*

> *"Scale because it works, not because the metrics say so."*

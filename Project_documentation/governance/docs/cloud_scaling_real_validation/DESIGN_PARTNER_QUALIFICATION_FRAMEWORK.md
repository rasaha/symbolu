# Design-Partner Qualification Framework

**INTERNAL operating framework. Not a sales-target list, not marketing, not lead
generation.** It decides **who to approach first, who to avoid, which environments are
most likely to produce useful evidence, and where the company-vs-feature question can be
answered fastest.** Context: `INVESTMENT_THESIS_MEMO.md`,
`STRATEGY_IMPLEMENTATION_PLAN.md`, `PARTNER_DATA_REQUIREMENTS_PLAN.md`,
`TIER_A_DETECTOR_SPEC.md`, and the `track_c_design_partner/` collateral.

> **Hypothesis discipline (read first).** We have **no partner data yet.** Every score,
> ranking, frequency, and cluster-month figure in this document is an **a-priori
> hypothesis / prior** used to *sequence outreach* — **not** a measurement. The Tier-A
> per-cluster-month rate is precisely the unknown the program exists to measure; any
> number that depends on it is a band, not a fact. Update every table as real data
> arrives. No company names, no savings claims, no production/customer-validation claims.

---

## 1. Executive summary

**The objective is one thing: maximize *evidence per partner-month* — learning velocity.**
Explicitly **not** revenue, logo prestige, cloud spend, or company size. A small,
unglamorous org that hands over 9 months of dependency-heavy cluster history and an
engaged SRE teaches us far more, far faster, than a prestigious logo that grants a slow,
shallow read-only pilot.

"Evidence" means measurable progress on the three gates:
- **Gate 1 — Market (APCY / Tier-A frequency):** does the costly futile/runaway event
  happen often enough? Fastest via **retrospective replay of partner history**.
- **Gate 2 — Trust (precision):** is the verdict right on real noisy metrics? Needs
  **live read-only access** + **SRE adjudication** of flags.
- **Gate 3 — Pull (differentiation):** does it tell SREs something their existing tooling
  did not, and will they keep/expand/pay? Needs **SRE candor**, early.

The company-vs-feature question is answered fastest by partners who **(a) concentrate
Tier-A pain, (b) can hand over history with low friction, and (c) field an SRE who will
adjudicate flags and answer the differentiation question.** This framework ranks
*expected* yield on those three things; it is a prior to be overwritten by data.

---

## 2. ICP scoring model

Score each candidate **1–5** on ten dimensions; the weighted mean is the composite
(higher = more expected evidence per partner-month). Weights reflect the critical path:
the event must *exist* (Tier-A), we must be able to *see it* (data + access), and a human
must *confirm* it (SRE). Sales potential is deliberately low-weighted.

| # | Dimension | Weight | Score 1 (poor) | Score 3 (moderate) | Score 5 (ideal) |
|---|---|--:|---|---|---|
| 1 | **Probability of Tier-A events** | 18% | capacity-bound, simple workloads | some dependency coupling, occasional spikes | dependency-heavy + spiky + active autoscaling; a *remembered* amplified incident |
| 2 | **Historical data availability** (depth/retention) | 15% | <1 mo retention | ~3–6 mo | **≥6–12 mo** Prometheus/HPA + incident history |
| 3 | **Ease of obtaining exports** | 12% | hard no / legal black hole | possible with effort | exports in days; light NDA path |
| 4 | **SRE engagement level** | 12% | no named owner | a willing but busy contact | a committed SRE adjudicator, ~30 min/wk |
| 5 | **Estimated APCY potential** (freq × $/episode exposure) | 10% | tiny fleets, cheap episodes | moderate | large fleets, expensive incident-coupled episodes |
| 6 | **Existing autoscaling complexity** | 8% | static replicas | HPA on CPU only | HPA/KEDA/Karpenter, multi-signal, large `maxReplicas` |
| 7 | **Likelihood of granting read-only access** | 8% | prod is sealed | non-prod only | scoped read-only Prometheus token in days |
| 8 | **Likelihood of answering the differentiation question** | 7% | no incumbents to compare / won't engage | runs some incumbents | runs Datadog/Kubecost/CAST AI/Karpenter **and** will speak candidly |
| 9 | **Cluster-month contribution** | 6% | 1 small cluster | a few clusters | many clusters × long history (big retrospective volume) |
| 10 | **Likelihood of becoming a design partner** | 4% | no interest | curious | actively wants to engage |

**Composite = Σ(weight × score).** Treat ≥4.0 as Tier-1 outreach, 3.0–3.9 as Tier-2,
<3.0 as Tier-3 / defer. Dimensions 1–4 are the **gating** ones — a candidate that scores
1 on Tier-A probability *or* on data availability is low-yield no matter how large or
prestigious; do not let dimensions 5/9 (size) rescue a low 1–4.

---

## 3. Candidate segment analysis

Scores are **priors (1–5)**. The list mixes two axes — *vertical* (what they run) and
*structure/size* (how fast they move); both matter, so both are scored. "Engagement speed"
is the internal proxy for "sales cycle" (time-to-NDA-and-data), valued for *velocity*, not
selling.

| Segment | Tier-A freq | APCY potential | Data availability | Export willingness | Engagement speed | Design-partner attractiveness | **Overall** |
|---|--:|--:|--:|--:|--:|--:|--:|
| **AI inference / GenAI platforms** | 5 | 5 | 4 | 4 | 4 | 5 | **4.6** |
| **Internal platform teams** (own the stack) | 4 | 4 | 5 | 4 | 4 | 5 | **4.3** |
| **Mid-market** (cross-vertical) | 4 | 4 | 4 | 4 | 5 | 5 | **4.3** |
| **SaaS platforms** (B2B multi-tenant) | 4 | 4 | 4 | 4 | 4 | 4 | **4.0** |
| **E-commerce** | 4 | 4 | 4 | 3 | 4 | 4 | **3.9** |
| **Streaming / media** | 4 | 4 | 4 | 3 | 3 | 4 | **3.7** |
| **K8s consultancies / managed-platform providers** | 3 | 4 | 4 | 3 | 4 | 4 | **3.6** (breadth multiplier; indirect adjudication) |
| **Fintech** | 4 | 4 | 3 | 2 | 2 | 3 | **3.1** (high pain, heavy NDA/compliance friction) |
| **Gaming** | 4 | 4 | 3 | 3 | 3 | 3 | **3.4** (huge spikes; stack variance high) |
| **Large enterprises** | 4 | 5 | 3 | 2 | 1 | 3 | **3.1** (most volume, slowest access) |
| **Enterprise IT** (traditional) | 2 | 3 | 2 | 2 | 1 | 2 | **2.1** |
| **Regulated industries** | 4 | 4 | 2 | 1 | 1 | 2 | **2.5** (pain exists; data/access worst-case) |
| **Startups (<50 engineers)** | 2 | 2 | 2 | 5 | 5 | 3 | **2.8** (fast/easy, but clusters too small for Tier-A) |

**Reading it:** the top of the table is where *pain × velocity* both run high. Startups
score high on willingness but low on Tier-A (small fleets rarely cross the M=20 futility
envelope; see §5). Large enterprise / regulated score high on *potential* but low on
*velocity* — pursue selectively, not first. Consultancies are a **breadth multiplier**
(many orgs' history at once) but adjudication is one step removed from the workload owner.

---

## 4. Workload ranking

Ranked by expected usefulness for surfacing Tier-A. **P(non-capacity bottleneck)** and
**P(autoscaling amplification)** are the two priors that matter most — the regime where
adding replicas can't help and the autoscaler keeps trying anyway.

| Workload | P(non-capacity bottleneck) | P(autoscaling amplification) | Observability maturity | Track A | Track B | Track C | Rank |
|---|--:|--:|--:|:--:|:--:|:--:|--:|
| **AI inference services** | 5 | 5 | 4 | ★★★ | ★★★ | ★★★ | **1** |
| **Queue-heavy systems** | 5 | 4 | 3 | ★★★ | ★★★ | ★★ | **2** |
| **Event-driven systems** | 4 | 4 | 3 | ★★ | ★★★ | ★★ | **3** |
| **API gateways** | 4 | 4 | 4 | ★★★ | ★★ | ★★★ | **4** |
| **Microservice frontends** | 4 | 4 | 4 | ★★★ | ★★ | ★★★ | **5** |
| **Databases** (as the *dependency*) | 5 | 1 | 4 | ★ | ★★ (as dep. metric) | ★ | **6** |
| **Batch workloads** | 2 | 2 | 3 | ★ | ★★ | ★ | **7** |
| **CI/CD systems** | 2 | 2 | 2 | ★ | ★ | ★ | **8** |
| **Internal tooling** | 1 | 1 | 2 | ★ | ★ | ★ | **9** |

**Notes.** AI inference is the sweet spot: GPU/token-backend-bound, bursty, and
autoscalers fire on latency/queue while the real limit is downstream — the exact
"why-now" regime. Queue/event systems carry the queue-collapse/poison-work futility.
API gateways and microservice frontends are the canonical "scale the front while a
dependency saturates" case (our external-bottleneck scenario). **Databases matter as the
*bottleneck that causes others' Tier-A*, not as a target** — they're rarely HPA-scaled, so
there's little scale-out decision for us to judge; capture their saturation metrics as a
*dependency signal* for adjudication. Batch/CI-CD/internal tooling are mostly capacity-
bound (scaling helps) → verdict says HELPING → low Tier-A yield.

---

## 5. Anti-targets (low evidence yield — deprioritize)

| Anti-pattern | Why it yields little evidence |
|---|---|
| **No Prometheus** | Both ingestion paths read the Prometheus HTTP API; without it there is no Track-A or Track-B pipeline at all. |
| **No HPA / KEDA / Karpenter** | No autoscaling decisions exist to judge; the verdict has nothing to evaluate. |
| **Minimal / static autoscaling** | No scale-outs ⇒ no futile scale-outs ⇒ Tier-A is structurally impossible. |
| **Very small clusters** (rarely ≥~20 replicas) | Below the pre-registered M=20 futility envelope (`TIER_A_DETECTOR_SPEC.md` §2); even genuine futility won't be flagged Tier-A — under-detection, not signal. |
| **No historical retention** (<weeks) | Track-B replay needs ≥6–12 mo; without it the *fastest* APCY path is gone and we're stuck waiting for rare live events. |
| **No incident history / timelines** | Tier-A requires overlap with a real incident; with no incident record, candidates stall at "pending incident confirmation" and can't be confirmed Tier-A. |
| **Unwilling to provide exports / read-only access** | A free-pilot-only "this looks cool" is **vanity, not evidence** (per the anti-self-deception rules); no data, no gate movement. |
| **No SRE ownership / no adjudicator** | Flags stay unproven (no Gate 2), and there's no one to answer the differentiation question (no Gate 3). |

A candidate hitting two or more of these is a **time sink**: high effort, near-zero
expected evidence. Decline early and politely; it protects learning velocity.

---

## 6. Outreach prioritization (by profile, never by name)

**Tier 1 — highest expected evidence yield.** Composite ≥4.0. AI-inference/GenAI
platforms; mid-market SaaS / e-commerce / streaming with **dependency-heavy, spiky
workloads, active HPA/KEDA/Karpenter, ≥6–12 mo retention, an engaged SRE, and a remembered
autoscaling-amplified incident**; and **internal platform teams** at such orgs (they own
Prometheus + incidents + can grant read-only). *Why:* they concentrate Tier-A pain **and**
move fast **and** can adjudicate — the only combination that advances all three gates per
partner-month.

**Tier 2 — strong but slower or indirect.** Large-enterprise platform teams (highest
volume/APCY potential, slowest access — start the procurement clock early but don't wait on
them); fintech (high pain, NDA/compliance friction); gaming (high spikes, high stack
variance); k8s consultancies / managed-platform providers (breadth multiplier across many
orgs, but adjudication is one step from the workload owner).

**Tier 3 — low yield or narrow use.** Startups <50 eng (fast/easy but clusters too small
for Tier-A — useful **only** for Track-C differentiation interviews, not Track-B APCY);
traditional enterprise IT; batch/CI-CD-dominated shops. Pursue opportunistically, never
first.

**Do not pursue:** anything matching two or more anti-targets (§5).

---

## 7. Design-partner economics (hypotheses — learning per hour)

The dominant lever on learning velocity is **historical export breadth**: one export of
*N clusters × M months* yields *N×M retrospective cluster-months instantly*, whereas live
shadow accrues ~1 cluster-month per cluster per calendar month. **History is the
accelerant; live shadow is the precision check.**

| Partner archetype (hypothesis) | Cluster-months / engagement | Tier-A opportunities | Adjudicated episodes | APCY signal quality | Pull signal quality | Learning / hour |
|---|---|---|---|---|---|---|
| **Mid-market AI-inference platform team** | ~6–10 clusters × 6–12 mo (one export) | high (best prior) | high (engaged SRE) | **high** | **high** (runs incumbents) | **highest** |
| **Internal platform team (mid/large org)** | many clusters × long retention | medium–high | high | high | medium–high | high |
| **K8s consultancy / managed provider** | many *orgs'* clusters (breadth) | medium–high (aggregate) | medium (indirect) | medium–high (breadth) | medium | high-but-indirect |
| **Large-enterprise platform team** | very large volume | high (potential) | medium (slow) | medium (delayed) | medium | medium (slow) |
| **Startup <50 eng** | 1–2 small clusters, thin history | low (small fleets) | low | low | medium (differentiation talk) | low (Track-C only) |

**Most learning per hour:** an **engaged internal platform team at a mid-market,
dependency-heavy (ideally AI-inference) org** that can export several clusters' worth of
6–12 mo history, grant a read-only token, adjudicate, and answer the differentiation
question — it advances Gate 1 (history), Gate 2 (live + adjudication), and Gate 3
(differentiation) in a single relationship. **Consultancies** are the best *breadth*
play for reaching ≥6 orgs quickly, accepting weaker (indirect) adjudication.

---

## 8. Differentiation-testing opportunities

The differentiation question (`track_c_design_partner/02_FIRST_INTERVIEW_SCRIPT.md`):

> *"Did the verdict tell you something Datadog/Kubecost/CAST AI/Karpenter did **not** —
> specifically, that scaling was not helping?"*

**Most likely to say a credible "yes":** teams that **already run mature observability /
cost / autoscaling tooling and *still* got burned by a non-capacity incident** —
AI-inference and dependency-heavy microservice orgs with strong SRE. They have the
incumbents (a baseline to differentiate against) and have lived the exact gap (the tools
showed *what happened* / *what it cost* / *what action was taken*, but not *whether the
scale-out helped*). A "yes" from a team with excellent tooling is the **strongest possible
differentiation signal** — it clears the hardest bar.

**Least likely:** capacity-bound/simple workloads (scaling genuinely helps → verdict says
HELPING → "nothing new," correctly); teams **without** the incumbents (no baseline to
compare against, so "new" is uninformative); and very small/early teams that haven't yet
hit the amplified-incident regime.

**The useful paradox:** the teams with the *best* existing tooling are simultaneously the
toughest audience and the most credible "yes." Prioritize them for differentiation
testing — a no there pushes honestly toward *feature/acquisition*, and a yes there is the
cleanest evidence we are differentiated rather than redundant.

---

## 9. Ideal first 10 partners (profiles only — no names)

A portfolio engineered for **≥6 orgs of diversity** (so one workload can't dominate the
frequency estimate), **Tier-A concentration**, and **velocity**:

| # | Profile | Why | Hyp. cluster-month contribution | Track focus |
|---|---|---|---|---|
| 1–3 | **AI-inference / GenAI platform teams** (mid-market, dependency-heavy) | highest Tier-A prior + best differentiation audience | ~60–180 retrospective (history) | A + B + C |
| 4–5 | **Mid-market B2B SaaS** (multi-tenant, active HPA, strong SRE) | dependency density + fast engagement | ~40–120 | B + C, A from ≥1 |
| 6–7 | **E-commerce or streaming/media** (spiky, incident culture) | flash/live-event amplification; rich incident timelines | ~40–120 | B + C |
| 8 | **Fintech** (accept NDA friction for diversity) | high pain; broadens org diversity | ~20–60 | B (+ C) |
| 9 | **K8s consultancy / managed-platform provider** | breadth multiplier toward ≥6 orgs fast | ~40–100 (across clients) | B breadth |
| 10 | **Large-enterprise internal platform team** | volume + start slow procurement early | ~50–150 (when it lands) | B + A (later) |

This mix targets the ≥6-org / ≥150-cluster-month floor primarily through **historical
exports** (Tracks B), draws **live read-only shadow** (Track A) from the 2–3 most engaged,
and harvests **differentiation + pull** (Track C) from the incumbent-heavy AI/SaaS teams.
All contributions are **hypotheses** pending real exports.

---

## 10. Evidence accumulation model (HYPOTHESES, not measurements)

**Cluster-months** (driven by clusters-per-partner × retention — mostly knowable up front):

| Target | Hypothesized partners needed | Basis |
|---|---|---|
| **50 cluster-months** | ~1–2 data-rich partners | one export of ~6–8 clusters × ~9 mo ≈ 50–70 |
| **150 cluster-months** (the floor) | ~3–6 partners | aligns with the ≥6-org diversity target |
| **300 cluster-months** | ~6–10 partners | breadth + a consultancy multiplier |

**Tier-A episodes — explicitly circular, therefore a band, not a number.** The Tier-A rate
*r* per cluster-month **is the unknown we are measuring**; we cannot predict how many
partners yield 5/20 episodes without assuming the very thing under test. Stated as a
hypothesis with wide bands:

| If the (unknown) Tier-A rate is… | …cluster-months to see 5 | …to see 20 |
|---|--:|--:|
| optimistic ~0.05 / cluster-mo | ~100 | ~400 |
| middle ~0.02 / cluster-mo | ~250 | ~1,000 |
| pessimistic ~0.01 / cluster-mo | ~500 | ~2,000 |

The point is **not** to believe any row — it's that the **pre-registered decision rule**
settles it regardless: **<5 adjudicated Tier-A across ≥150 cluster-months ⇒ market-red**
(`TIER_A_DETECTOR_SPEC.md` §5c). Gather ≥150 cluster-months across ≥6 orgs and *read off*
*r*; do not forecast it.

**Adjudicated flags (≥40–50):** flags include Tier-B + Tier-A *candidates*, so the flag
rate exceeds the Tier-A rate — 40–50 adjudicated flags is reachable with **fewer**
cluster-months than 20 confirmed Tier-A, plausibly within the first ~3–6 partners' history
plus a couple of live-shadow weeks. **Hypothesis**, to be confirmed by the first exports.

> All figures in this section are hypotheses to calibrate effort. The only number that
> *decides* anything is the adjudicated Tier-A count against the pre-registered floor.

---

## 11. Recommended outreach sequence

Mirrors the 90-day cadence (`STRATEGY_IMPLEMENTATION_PLAN.md` §3); history leads because it
is the fastest, least-biased path to the gating number.

**Month 1 — open the highest-yield doors; lead with history.**
- Approach **Tier-1 profiles** (AI-inference + mid-market SaaS/e-commerce + 1 consultancy
  for breadth). NDA + **request ≥6–12 mo historical exports** (the highest-leverage ask).
- Stand up Track-B replay on the first exports → **first directional APCY** (hypothesis).
- Begin **Track-C differentiation interviews** with incumbent-heavy teams.
- *Goal:* ≥3 orgs engaged, history flowing, first Tier-A candidates surfaced.

**Month 2 — breadth + the live precision check.**
- Scale Track-B toward **≥6 orgs / ≥150 cluster-months**; begin SRE adjudication toward
  40–50 flags.
- Stand up **Track-A live read-only shadow** on the 1–2 most engaged partners (Gate 2).
- Start one **large-enterprise** procurement (slow clock) for later volume.
- *Goal:* directional APCY firming, adjudication underway, first pull signals logged.

**Month 3 — lock the read.**
- Finalize the APCY estimate vs thresholds; finalize Gate-2 precision; convert pull → LOI;
  capture the differentiation tally.
- Drop anti-targets and any partner not advancing a gate.
- *Goal:* enough evidence to call **company / feature / research** honestly.

---

## 12. Final recommendation

**If we could approach only one category first: AI-inference / GenAI platform teams
(mid-market, dependency-heavy, with an engaged SRE).** It maximizes all four targets at
once:

- **APCY / Tier-A frequency:** bursty traffic + dependency-bound backends (GPU, token
  queues) give the **highest prior** for non-capacity bottlenecks and autoscaling
  amplification — the "why-now" regime where the verdict has the most signal.
- **Differentiation:** these teams run modern observability/cost/autoscaling tooling and
  still get burned by non-capacity incidents — the **highest-credibility audience** for a
  "yes, this told us something new."
- **Company-vs-feature, fastest:** they move fast, retain history, and field engaged SREs,
  so they convert to a **directional APCY + a trust + pull read** sooner than any other
  category — which *is* the company/feature decision.

**Caveat (do not over-rotate):** "lead with this category" ≠ "only this category." The
≥6-org diversity rule exists so one AI-inference workload can't dominate the frequency
estimate; pair the lead category with 2–3 other verticals from the first-10 portfolio (§9).
And every conclusion here is a **hypothesis** — the first real exports and adjudications
override this framework, by design.

---

*Discipline note: no company names, no lead generation, no scraping, no sales copy, no
investor hype, no savings claims, and no production/customer-validation claims appear in
this document. Every score and quantity is an a-priori hypothesis to sequence outreach and
must be replaced by measured evidence as partner data lands.*

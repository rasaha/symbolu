# 90-Day Market Validation Plan — Autoscaling Safety Interlock

**INTERNAL. Operational, falsifiable, strict.** Sole purpose: decide whether the
Autoscaling Safety Interlock is a **standalone company**, a **premium feature /
acquisition primitive**, or **research/kill**. It is not a sales plan; design
partners are instruments for measurement, not logos.

---

## 1. Executive summary
We have a read-only causal-verdict engine that is **safe** (0 harmful false
positives, 0 SLO regressions, 0 helpful scale-outs mislabeled — all self-run) but
whose **market is unproven**: the simulation's 13.4% block rate did not reproduce
on real dynamics, and we have no real-cluster run and no third-party data. The
company-vs-feature question reduces to three falsifiable gates — **Market pain
(frequency × cost), Trust (precision on real noisy metrics), and Pull (willingness
to keep/expand/pay/let-it-act)**. The plan front-loads **retrospective replay of
partner history** (using the existing Track-B harness) to estimate frequency fast,
and uses **live read-only shadow** to validate trust and pull. The decisive output
is **APCY = Tier-A episodes/cluster-year × $/episode**, judged against a defensible
per-cluster price.

## 2. The three gates
- **Gate 1 — Market pain / frequency.** *Does the costly event happen often
  enough?* Core metric **APCY**. Pass = APCY comfortably exceeds a defensible price.
- **Gate 2 — Trust / precision.** *Is the verdict right on real noisy metrics?*
  Metrics: false-positive rate, helpful scale-outs mislabeled, SLO regressions,
  adjudicated precision, cumulative zero-FP streak.
- **Gate 3 — Pull / willingness to pay.** *Do partners keep/expand/pay/let-it-act?*
  Metrics: paid pilot/LOI, cluster expansion, "very disappointed if removed,"
  willingness to enable recommend mode, eventual willingness to allow actuation,
  and whether SREs say the verdict told them something Datadog/Grafana/Kubecost/
  CAST AI did not.

**Company = G1 ∧ G2 ∧ G3 green. Feature/acquisition = G2 green but G1 or G3 red.
Research/kill = G1 red ∧ G3 red, or G2 unachievable on real metrics.**

### Tier-A vs Tier-B (define once, enforce everywhere)
- **Tier-A episode (the company-maker):** a runaway/futile autoscaling episode that
  **materially over-provisioned or amplified a non-capacity incident** — the event
  the interlock would have capped. The unit of market evidence.
- **Tier-B event:** a lower-value single non-causal scale-out / NOT_HELPING
  observation — diagnostically useful and good for the demo's 0-FP streak, but
  **not** market evidence.
- **Why Tier-B must never be used as market evidence:** Tier-B is frequent and
  cheap; counting it inflates "traction" while the business actually depends on
  Tier-A frequency × cost. A company built on Tier-B is a feature wearing a company
  costume. Every flag count must be reported with its tier and its adjudicated
  precision — never a raw Tier-B total as a headline.

## 3. Minimum data needed to *know*
| Quantity | Target | Floor (directional only) |
|---|---|---|
| Orgs | **≥6** (diversity prevents one weird workload dominating) | 3 |
| Production clusters | **≥10** | 6 |
| Live cluster-months | **≥40** (≈10–15 clusters × ~3 mo) | 20 |
| Retrospective cluster-months (replayed history) | **≥150** | 60 |
| Adjudicated flags | **≥40–50** (bounds FP rate; rule of three: 0/50 ⇒ ≤6% upper-95% CI) | 25 |
| SRE-confirmed Tier-A episodes | **≥20** (to estimate frequency + recall) | 8 |

**Hard red flag:** if **<5 Tier-A episodes** surface across broad retrospective data
(≥150 cluster-months), treat it as a serious **market-red** signal — the event is
too rare to support a dedicated product, regardless of how clean the verdict is.

## 4. What to request from each design partner
- **Historical Prometheus / HPA exports** (≥6–12 months) — the single
  highest-leverage ask; powers retrospective replay.
- **Scaling event logs** (HPA/Karpenter/KEDA actions) and **replica history**.
- **Incident timelines + postmortems** for the period — to find Tier-A episodes and
  attribute cost.
- **Cost estimates** ($/replica-hour or cluster spend) — to price episodes.
- **Live read-only shadow access** (zero write perms — the frictionless ask).
- **An SRE adjudicator** who will label each flagged episode true/false.

## 5. Using retrospective replay to estimate Tier-A frequency quickly
90 days is too short to observe rare events live, so lead with history. Feed each
partner's exported metrics through the existing verdict engine (Track-B replay
harness) **offline**: reconstruct the per-cycle verdict over the last 6–12 months,
count Tier-A episodes, cross-reference against their incident timelines, and price
each episode (excess replica-hours × $/replica-hour + incident overlap). This turns
~10 partners into **150+ cluster-months of frequency data within weeks** and yields
a first APCY estimate without waiting for live events. Caveat to record: replay
uses historical metrics with our modeled efficiency/SLO calculation, so treat
replay-derived APCY as an **estimate** to be confirmed by live adjudication.

## 6. Using live read-only shadow to validate trust and pull
Run the read-only shadow on live clusters for the 90 days. Each flag is adjudicated
by the partner's SRE (true/false). This produces **Gate 2** (precision on real,
noisy, live metrics — the thing replay cannot fully prove) and **Gate 3** (do they
keep it on, widen it, ask for recommend mode, say it beat their existing tooling).
Live also surfaces alert-fatigue risk (flag volume) early.

## 7. APCY thresholds (illustrative; calibrate on first data)
Anchor: a defensible reliability add-on price ≈ **$1–2k / cluster / year** (or
~1–3% of cluster compute spend).
- **Standalone-company signal:** **APCY ≥ 3–5× price** — e.g. ≥ ~$5–8k/cluster/yr of
  surfaced/preventable pain, typically ≥ ~1 Tier-A episode/cluster/quarter at
  median ≥ ~$1–2k/episode (compute + incident).
- **Premium-feature signal:** **APCY ≈ 1–2× price** — real but thin; the value is a
  module inside a platform, not a standalone purchase.
- **Kill/research signal:** **APCY < ~1× price**, or **<5 Tier-A episodes across
  ≥150 cluster-months**, or pain only in too narrow a slice to build on.
ICP note: expect APCY to concentrate in large/spiky/dependency-heavy clusters; if
so, the company case lives or dies on whether that segment is big and willing.

## 8. Trust thresholds (Gate 2)
- **Acceptable false-positive rate:** ≤ **5%** (target ~0) on adjudicated live flags.
- **Required volume:** ≥ **40–50 adjudicated flags** (0/50 ⇒ ≤6% upper-95% CI;
  ~30 = looser/directional).
- **Success:** sustained ≤5% FP **and** a maintained **cumulative zero-FP streak on
  clear helpful-scale-out cases.**
- **Failure (severe):** **any harmful false positive on a clear helpful-scale-out
  case** — i.e. the guard would have blocked a scale-out that real throughput/latency
  shows relieved a real constraint. One such case is a red flag on the core asset
  and must trigger a stop-and-review, not a footnote.

## 9. Pull thresholds (Gate 3)
- **Real demand (counts):** a signed **paid pilot or LOI**; **unprompted** cluster
  expansion; **≥50% of partners "very disappointed if removed"** (Sean-Ellis); an
  explicit request to enable **recommend mode**; at least one credible
  **"we'd let it act once trusted."**
- **Vanity (does not count):** a free read-only pilot that's easy to grant; "this is
  cool"; dashboards looked at once; verbal "we'd probably pay" with no LOI; logo
  permission without usage.

## 10. 90-day cadence
- **Days 0–30:** sign ≥6 orgs (floor 3); ingest history; run **retrospective replay
  → first APCY estimate** (Gate 1 directional within ~3 weeks); stand up live
  read-only shadow; begin per-flag adjudication.
- **Days 30–60:** accumulate live cluster-months + adjudicated flags (Gate 2);
  collect first pull/expansion signals (Gate 3); refine ICP and the Tier-A cost
  model with partner cost data.
- **Days 60–90:** lock all three gates; convert intent to **paid LOIs**; write the
  go/no-go using the matrix below.

## 11. Go / no-go decision matrix
| Outcome | Gate 1 (APCY) | Gate 2 (precision) | Gate 3 (pull) | Action |
|---|---|---|---|---|
| **Company** | ≥3–5× price | ≤5% FP, ≥40–50 flags, 0 harmful FP on helpful cases | paid LOI + expansion + "very disappointed" | Raise/build the read-only interlock; sequence toward recommend → actuation |
| **Feature / acquisition primitive** | ~1–2× price | green | weak (no LOI, "expect it free") | License/embed the verdict into a platform; pursue acquisition into CAST AI/Datadog |
| **Research / kill** | <1× price or <5 Tier-A / 150 cluster-mo | OR unachievable on real metrics | red | Stop productizing; keep as research or shelve |

## 12. Anti-self-deception rules
- **Free-pilot enthusiasm ≠ demand.** Read-only/zero-risk makes pilots trivial and
  worthless as signal; only paid LOI + unprompted expansion + "very disappointed if
  removed" count.
- **Tier-B is not market evidence.** Never headline non-causal-flag counts; pair
  every flag count with tier + adjudicated precision.
- **Do not infer frequency from SRE opinion.** "Does this happen a lot?" is biased;
  **measure it** by replaying their history.
- **Measure historical data wherever possible** — it's the fastest, least-biased
  path to the frequency number, and it exists today.
- **One harmful false positive outweighs many true positives** for the trust
  verdict; do not average it away.
- **Pre-register the thresholds** (this doc) before looking at partner data, so we
  don't move the goalposts to a flattering conclusion.

## 13. Recommended next action after this memo
Execute the **real Track-A `live-shadow-self-run`** on a host with container-registry
egress (harness + runbook are ready) to remove the "no real cluster" objection and
shake out metric-mapping/precision on real Prometheus — **in parallel** with
recruiting the first **3–6 design partners** and requesting their **historical
exports** so retrospective replay can produce a first APCY estimate within ~30 days.
Treat the incident-frequency (APCY) number as the **go/no-go gate** for "company vs
feature." Do not update the VC brief or pitchbook until at least the live run and a
directional APCY exist.

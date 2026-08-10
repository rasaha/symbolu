# Strategy Implementation Plan — Autoscaling Safety Interlock (90-day operating plan)

**INTERNAL, founder-facing. Operational and strict.** Turns the strategy in
`COMPETITIVE_DIFFERENTIATION_MEMO.md`, `MARKET_VALIDATION_90_DAY_PLAN.md`, and
`INVESTMENT_THESIS_MEMO.md` into an executable plan **without changing code**. The
goal of these 90 days is a single decision — **company / feature / research** —
backed by measured evidence, not more positioning.

---

## 1. Current strategic conclusion
- **Positioning:** Autoscaling Safety Interlock — **read-only first.**
- **Core asset / north-star:** a **causal verdict for every scale-out**
  (HELPING / NEUTRAL / NOT_HELPING / futile-runaway).
- **Safety thesis: strengthened** — 0 harmful false positives, 0 SLO regressions,
  0 helpful scale-outs mislabeled across simulation + real-trace replay +
  real-dynamics calibration (all self-run).
- **Savings thesis: weakened** — ~0.74% replica-cycles on real-trace replay,
  near-SLO-neutral, offline/modeled dynamics. Not the pitch.
- **Market thesis: unproven** — decided by **APCY = Tier-A episodes/cluster-year ×
  $/episode**, which is unmeasured. This plan measures it.

## 2. The three required evidence tracks
| Track | Question it answers | Gate | Depends on |
|---|---|---|---|
| **A — Real live-shadow-self-run** | Does it run + stay precise on a *real* cluster/Prometheus/HPA? | Trust (G2) | a host with container-registry egress |
| **B — Retrospective partner replay** | Does the costly event happen often enough (APCY / Tier-A freq)? | Market (G1) | partner historical exports |
| **C — Design-partner pull** | Will anyone keep/expand/pay/eventually let it act? | Pull (G3) | partner relationships |
Tracks run **in parallel.** A and C can start immediately; **B is critical path**
because it depends on partner data — so outreach in Weeks 1–2 gates everything.

## 3. Week-by-week 90-day plan
| Window | Track A (real cluster) | Track B (replay → APCY) | Track C (partners) |
|---|---|---|---|
| **Weeks 1–2** | Execute **one** real Track-A run on a registry-egress host via `Project_documentation/repository/deploy/local-shadow/RUNBOOK.md`; run the §2.8 pre-flight (HPA replicas readable); capture report. | Stand up replay ingestion; **pre-register** Tier-A/Tier-B definitions, cost model, and all thresholds (so we can't move goalposts). | Build target list (§4); open outreach to 6–10 candidates; send NDA + data-request checklist (§5). |
| **Weeks 3–4** | Re-run the 3 scenarios (capacity / external-bottleneck / noisy) on the real cluster; adjudicate flags; lock the Track-A precision read. | Ingest first partner histories; first **directional APCY**; SRE-adjudicate replayed Tier-A candidates. | Sign **≥3** design partners (pilot LOI); secure historical exports. |
| **Weeks 5–8** | Deploy read-only live shadow on partner (or representative) clusters; accumulate live cluster-months + adjudicated flags toward ≥40–50. | Scale replay to **≥150 retrospective cluster-months across ≥6 orgs**; refine APCY with real partner cost data; lock Tier-A frequency estimate. | Measure pull signals (§8); push toward expansion + paid conversion. |
| **Weeks 9–12** | Finalize Gate-2 precision (sustained ≤5% FP; 0 harmful FP on helpful cases). | Finalize Gate-1 APCY vs thresholds (§9). | Convert intent to **paid LOIs**; finalize Gate-3. Assemble go/no-go packet; write the decision. |

## 4. Design-partner target profile
Concentrate where Tier-A pain is most plausible (per the thesis ICP):
- **Large and/or spiky Kubernetes clusters** (many replicas, variable load).
- **Dependency-heavy microservices** (queues, DBs, caches, third-party APIs, AI
  inference backends) — i.e. lots of **non-capacity bottlenecks**.
- **Active HPA and/or Karpenter users** (real autoscaling in production).
- **Teams with a remembered autoscaling-amplified incident** (scaled into a
  cascading failure / surprise bill).
- **Budget owner: SRE / platform engineering** (reliability/incident budget — not
  FinOps, which wants savings we don't lead with).
Aim for **diversity across ≥6 orgs**; one weird workload must not dominate the
frequency estimate.

## 5. Data request checklist (per partner)
- [ ] **Prometheus / HPA metric exports**, ≥6–12 months (the highest-leverage ask).
- [ ] **Replica history** (current/desired over time) per key deployment.
- [ ] **HPA / Karpenter scaling event logs.**
- [ ] **Incident timelines** for the period.
- [ ] **Postmortems** (to find Tier-A episodes + attribute cost).
- [ ] **Cost assumptions** ($/replica-hour or cluster spend) for episode pricing.
- [ ] **Read-only shadow permission** (zero write perms) on ≥1 representative cluster.
- [ ] **An SRE adjudicator** committed to label flagged episodes true/false.
- [ ] NDA / data-handling terms in place before ingestion.

## 6. APCY measurement procedure
- **Tier-A episode (market evidence):** a runaway/futile autoscaling episode that
  **materially over-provisioned or amplified a non-capacity incident** — the event
  the interlock would have capped. Unit of APCY.
- **Tier-B event (NOT market evidence):** a single low-value non-causal scale-out /
  NOT_HELPING observation. Diagnostic + demo only; **never** a headline number.
- **Replay methodology:** feed each partner's exported metrics through the existing
  verdict engine **offline** (Track-B replay harness, `scripts/run_trace_replay.py` /
  `cloud_controller/replay/`); reconstruct the per-cycle verdict over 6–12 months;
  count Tier-A episodes; cross-reference each against the partner's incident
  timeline.
- **Cost model (per episode):** excess replica-hours × $/replica-hour **+** incident
  minutes overlapped **+** SLO-breach severity. **APCY = Tier-A/cluster-year × median
  $/episode.**
- **SRE adjudication:** for every Tier-A candidate the replay surfaces, the partner's
  SRE labels it real/not-real and confirms cost. APCY uses **adjudicated** episodes.
- **Confidence limits / red flags:** replay-derived APCY is an **estimate** pending
  live adjudication; **<5 adjudicated Tier-A episodes across ≥150 cluster-months is a
  market-red signal** regardless of verdict cleanliness; require ≥6 orgs before
  trusting any frequency number (avoid single-workload bias).

## 7. Live-shadow-self-run procedure (Track A)
- **Use the existing runbook** (`Project_documentation/repository/deploy/local-shadow/RUNBOOK.md`): kind +
  kube-prometheus-stack + Online Boutique + frontend HPA + Chaos Mesh + k6; run the
  pre-flight that confirms the kube-state-metrics fix returns real HPA replicas; run
  capacity / external-bottleneck / noisy scenarios; capture `track_a_live_shadow.*`.
- **Strengthens the thesis if:** the verdict holds **0 harmful false positives** on
  real Prometheus metrics, and it **correctly flags a real external-bottleneck**
  (latency high, CPU low, scaling not helping) with metrics proving more replicas
  didn't help — reproduced across ≥2 runs.
- **Weakens the thesis if:** any **harmful false positive** appears on a clear
  helpful-scale-out case; metric mapping fails (replica/latency queries empty); or
  the guard never reaches its regime so it's inert (value unproven — bounds value,
  not safety).
- **Must be labeled clearly:** `live-shadow-self-run` **only** if real cluster + real
  Prometheus + real HPA + real workload metrics. It remains **our** faults on **our**
  cluster — **not** third-party, and **no** savings claim.

## 8. Pull measurement (Track C)
- **Differentiation signal (measure early — before payment or actuation):** does the
  SRE/platform team say the verdict told them **something their existing tooling did
  not** — specifically *"scaling was not helping"*? Datadog/Grafana show the
  incident, Kubecost/CloudZero show the cost, CAST AI/Karpenter show the scaling
  actions; only our verdict claims to surface **non-causal scaling**. A credible
  "yes, this told me something new" is a **leading indicator of pull** that precedes
  LOIs and actuation trust, and the cleanest early test of whether we are
  differentiated rather than redundant.
- **Counts as real demand:** signed **paid pilot / LOI**; **unprompted cluster
  expansion**; **≥50% of partners "very disappointed if removed"** (Sean-Ellis);
  explicit request to enable **recommend mode**; a credible **"we'd let it act
  (bounded) once trusted."**
- **Does not count (vanity):** a free read-only pilot that was easy to grant; "this
  is cool"; a dashboard viewed once; verbal "we'd probably pay" with no LOI; logo
  permission without usage.

## 9. Go / no-go decision after 90 days
| Outcome | Gate 1 — APCY | Gate 2 — Trust | Gate 3 — Pull | Action |
|---|---|---|---|---|
| **Company** | ≥ **3–5× price** | ≤5% FP, ≥40–50 adjudicated flags, **0 harmful FP on helpful cases** | paid LOI + expansion + "very disappointed" + **verdict surfaced what Datadog/Kubecost/CAST AI did not** | Build the read-only interlock; sequence toward recommend → bounded actuation; prepare investor appendix. |
| **Premium feature / acquisition primitive** | ~ **1–2× price** | green | weak ("expect it free," no LOI) — and **verdict mostly duplicated existing tooling** | License/embed the verdict into a platform; pursue acquisition into CAST AI / Datadog. |
| **Research / kill** | < **1× price**, or **<5 Tier-A / ≥150 cluster-months** | OR unachievable on real metrics | red | Stop productizing; keep as research or shelve. |
Price anchor (~$1–2k/cluster/yr) is illustrative — calibrate on first partner data.
**Supporting pull evidence:** "did the verdict tell us something our existing
tooling did not (that scaling was not helping)?" is a **leading, pre-payment**
differentiation indicator — a consistent "yes" reinforces the Company case; a
consistent "no, we'd have seen it anyway" pushes toward feature/acquisition.

## 10. What NOT to do during these 90 days
- **No threshold tuning** unless **pre-registered** before seeing partner data (a
  tuning hypothesis with a pass/fail criterion written down in advance).
- **No savings claims** (the savings thesis is weakened; this is a safety play).
- **No pitchbook / VC-brief hype**; those are not updated until evidence lands.
- **No new features before APCY** — measurement precedes building.
- **Never use the synthetic 13.4% block rate as a market expectation** (it did not
  reproduce on real dynamics).
- **No "production / customer / real-cluster validated" language** until earned.

## 11. Recommended immediate next action
1. **Run one real Track-A `live-shadow-self-run`** on a host with registry egress
   (removes the "no real cluster" objection; tests precision on real metrics).
2. **Begin outreach to 3–6 design partners** matching §4 (critical path for Track B).
   In the **first interviews**, explicitly ask the differentiation question: *did our
   verdict tell you something your existing tooling (Datadog/Grafana, Kubecost/
   CloudZero, CAST AI/Karpenter) did not — namely that scaling was not helping?* This
   measures differentiation **before** any payment or actuation discussion.
3. **Prepare the data-ingestion checklist + replay pipeline** (§5–§6) so partner
   history converts to a directional APCY within ~30 days of first export.

The next step is **evidence-gathering, not positioning.** APCY, Tier-A frequency,
and design-partner pull decide whether this is a company — everything else waits on
those three numbers.

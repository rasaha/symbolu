# Partner-Data Requirements Plan — Autoscaling Safety Interlock

**INTERNAL, founder/operator-facing. Operational and precise.** Defines *exactly* what
to ask design partners for — never a vague "send us your logs" — so that each of the
three evidence tracks can run on real partner data. It is the connective tissue between
the strategy docs and the shipped tooling; it does not restate them:

- gates, thresholds, ICP: `MARKET_VALIDATION_90_DAY_PLAN.md`, `STRATEGY_IMPLEMENTATION_PLAN.md`
- Tier-A detector + cost/APCY model (frozen): `TIER_A_DETECTOR_SPEC.md`
- partner-facing collateral (brief, interview, NDA checklist, worksheet, tracker):
  `track_c_design_partner/`
- ingestion tooling: `cloud_controller/replay/adapters/partner_prometheus.py`,
  `cloud_controller/replay/tier_a.py`, `scripts/run_tier_a_replay.py`
- Track-A runbook + this host's egress blocker:
  `deploy/local-shadow/RUNBOOK.md`, `artifacts/cloud_controller_real_validation/track_a_egress_probe.md`

**Product framing (unchanged):** Autoscaling Safety Interlock — **read-only first**. Core
primitive: a causal verdict for every scale-out — **HELPING / NEUTRAL / NOT_HELPING /
futile-runaway**. Evidence to date: safety thesis **strengthened**, savings thesis
**weakened**, market thesis **unproven**. This plan gathers what is needed to move the
market thesis — nothing here implies production or customer validation, and nothing here
makes a savings claim.

---

## 1. Executive summary

Three tracks need **three different things** from a partner; conflating them is the main
way partner asks go wrong. Keep them separate in every conversation.

| Track | What it needs | Nature of the ask | Answers gate | Partner effort |
|---|---|---|---|---|
| **A — Live read-only shadow** | **Live** read-only access to a running cluster's Prometheus + HPA state, for ~2 weeks | *Access* (scoped RBAC / endpoint), not data hand-off | Gate 2 (Trust / precision on real noisy metrics) | medium (a token + an endpoint) |
| **B — Historical replay** | **Exported history** (≥6–12 mo) of metrics, replicas, scale events, incidents, cost | *One-time data export*, offline | Gate 1 (Market — Tier-A frequency × cost = APCY) | low–medium (one export) |
| **C — Pull / differentiation** | **Human/SRE time**: adjudication of flagged episodes + the differentiation question | *Conversation + ~30 min/week* | Gate 3 (Pull / differentiation) | low (people, not systems) |

Key distinctions:
- **A is access, B is a file, C is people.** A partner can grant any one without the
  others; sequence by friction (B export and C conversation are easiest; A live access
  needs more internal sign-off).
- **B is the fastest path to the gating number (APCY).** History already exists; live
  observation takes months to accrue rare events. Lead with B.
- **A proves precision on *live* noisy metrics**, which replay cannot fully prove.
- **C is the only track that can tell us we are *differentiated*** rather than redundant
  — and it costs no data, only candor.

---

## 2. Track A — Live read-only shadow requirements

Goal: run the read-only observer against a **real** cluster so the verdict is exercised
on **live, noisy** Prometheus/HPA metrics. On a **partner** cluster this is a
**partner-shadow** run (see labeling, end of section) — distinct from a
`live-shadow-self-run`, which is *our* cluster under *our* injected faults.

### 2.1 Required access & signals
| Requirement | Minimum | Ideal | Notes |
|---|---|---|---|
| **Cluster access level** | network reachability to a **Prometheus query endpoint** for one cluster (no kube-apiserver access required) | scoped **read-only kubeconfig** (get/list/watch) **+** Prometheus | the observer needs metrics, not the API; API access only enriches HPA-event context |
| **Read-only RBAC** | n/a if Prometheus-only | `ClusterRole` limited to `get/list/watch` on `pods, deployments, horizontalpodautoscalers, events`; **no** create/update/patch/delete | exact "no write" definition in §2.5 |
| **Prometheus endpoint** | HTTP `/api/v1/query` + `/api/v1/query_range` reachable (port-forward, read-only proxy, or read replica) | a dedicated read-only datasource/token | Thanos/Mimir/Cortex query endpoints are fine (same API) |
| **HPA / autoscaler metrics** | `kube_horizontalpodautoscaler_status_{current,desired}_replicas` (kube-state-metrics) | + Karpenter/KEDA metrics if used | this is the §2.8 pre-flight signal; without it Track A cannot confirm real HPA replicas |
| **Latency / error / throughput** | p95 or p99 latency **and** error rate for the target service | + request rate / throughput | maps to canonical `latency_p99`, `error_rate` (+ load proxy) |
| **Replica current/desired** | `current_replicas`, `desired_replicas` per target deployment | same, plus `pod_restarts` | the scale-out signal the verdict judges |
| **HPA event metrics** | scaling events visible (metric or k8s `events`) | autoscaler audit/event log | anchors each verdict to a real scaling action |
| **Workload selection** | one representative deployment behind an active HPA | a large/spiky, dependency-heavy service (per ICP) | the regime where the verdict has signal |
| **Load scenarios** | observe **ambient** production traffic (no load gen) | optional ability to observe a planned load test / known busy window | we do **not** require generating load on a partner prod cluster |
| **Chaos / fault injection** | **not required and not requested on partner production** | only in a partner *non-prod* cluster, with explicit written consent | on partner prod, observe-only; fault injection is a self-run (Track A own-cluster) activity |
| **Deploy observer vs run externally** | **run the observer externally** (our process polls their Prometheus read-only) | deploy the observer as a read-only pod **if** the partner prefers in-cluster | external-poll keeps footprint to a single read-only token |
| **Network / registry** | egress from the observer host to the partner Prometheus endpoint | — | **partner-side registry egress is irrelevant** when we run the observer externally; if we instead bring up our *own* demo cluster (self-run), it needs `registry.k8s.io`, `quay.io`, `ghcr.io`, `gcr.io`, Docker Hub (see `track_a_egress_probe.md`) |
| **Security boundaries** | read-only token, scoped to one namespace/datasource, revocable, time-boxed | network-restricted (VPN/allowlist), audit-logged | least privilege (§6) |

### 2.2 Exact definition of "no write permissions"
The observer **cannot mutate anything**, by construction and by grant:
- **No** `create/update/patch/delete/deletecollection` on any resource; **no** scale
  subresource access; **no** admission/mutating webhooks; **no** sidecars in the data
  path; **no** actuation of HPA/Karpenter/KEDA.
- **Allowed verbs:** `get`, `list`, `watch` only (k8s), and read-only HTTP `GET` to the
  Prometheus query API.
- It **records** what the futility guard *would* have done as a counterfactual; it never
  applies it. A correct grant is one where, even if our process were compromised, it
  **could not change the cluster.**

### 2.3 Minimum viable Track-A setup
- Reachable **Prometheus query endpoint** (read-only) for one cluster, exposing the five
  canonical signals + HPA current/desired replicas, **and** `kube-state-metrics` HPA
  series, for **one** representative deployment, observed against **ambient** traffic for
  **~2 weeks**.

### 2.4 Ideal Track-A setup
- Scoped read-only kubeconfig **+** Prometheus; Karpenter/KEDA metrics; HPA event log;
  ≥2 representative deployments; a known busy window or planned load test to observe;
  ≥4 weeks to accrue more decisions; a named SRE to adjudicate flags (§8).

### 2.5 Red flags that make Track A invalid
- The HPA replica series is empty/unreadable (kube-state-metrics absent or mislabeled) →
  the §2.8 pre-flight fails → **do not proceed** (metric-mapping mismatch).
- Latency/error/throughput series missing → the verdict's core inputs are absent.
- Any grant that includes **write** verbs, or any pressure to actuate → decline; it
  breaks the read-only guarantee and the safety story.
- The target deployment never enters the regime (always low replicas, always capacity-
  bound) → the observer is inert; this **bounds value, not safety**, and must be
  reported as "inconclusive on value," not spun.
- Metrics so coarse/aggregated that per-deployment attribution is impossible.

### 2.6 What must be true before labeling a result
- **`live-shadow-self-run`** (our own cluster): all four of `RUNBOOK.md` §5 — real k8s
  cluster, real Prometheus scraping real targets, real HPA scaling a real Deployment,
  real workload metrics — **and** *our* injected faults. (Blocked on this host per
  `track_a_egress_probe.md`.)
- **`partner-shadow`** (a partner's cluster): real partner cluster + real Prometheus +
  real HPA + **real partner workload**, observed **read-only**. Label numbers
  `partner-shadow (real partner cluster; estimate pending independent adjudication)`. It
  is **not** `live-shadow-self-run` (not our faults) and **not** yet `third-party` — it
  converts toward third-party **only** when the partner's SRE (a disinterested party)
  adjudicates the flags and confirms outcomes. Until then, no independence is claimed.

---

## 3. Track B — Historical replay data requirements

Goal: replay ≥6–12 months of history through the **pre-registered Tier-A detector**
(`TIER_A_DETECTOR_SPEC.md`) to estimate **Tier-A frequency** and **APCY** offline. The
detector reads a per-cycle series of **real measured metrics + real replica history**,
finds **futile episodes** (≥5 consecutive NOT_HELPING at ≥20 replicas overlapping an
incident window), and prices them. Every number is labeled `real-trace-replay (estimate
pending live adjudication)`.

Columns below map 1:1 to the canonical manifest (§4) and the
`PartnerPrometheusAdapter`. Legend: **Tier-A?** = needed to *detect* an episode ·
**APCY?** = needed to *price* it · **Adj?** = needed only for SRE adjudication.

### 3.1 Required
| Data type | Why we need it | Min format | Ideal format | Retention | Tier-A? | APCY? | Adj? |
|---|---|---|---|---|---|---|---|
| **Timestamped HPA scale events** | mark when/why each scale-out fired; anchor verdicts | event rows `ts, deployment, old→new replicas, reason` | autoscaler audit log | ≥6 mo | ✓ | – | ✓ |
| **Current replicas (time series)** | the real fleet size each cycle (Tier-A needs ≥M) | `ts, value` per deployment | same | ≥6 mo | ✓ | ✓ | – |
| **Desired replicas (time series)** | scale-out *intent* vs realized | `ts, value` | same | ≥6 mo | ✓ | – | – |
| **Deployment/service identity** | per-cluster, per-service grouping | stable (anonymized) name/label | namespace+deployment | n/a | ✓ | ✓ | ✓ |
| **CPU / HPA resource metric** | utilization-collapse signal drives NOT_HELPING | `ts, value` (fraction or %) | the exact metric HPA scales on | ≥6 mo | ✓ | – | – |
| **Request rate / load metric** | load proxy; demand context | `ts, value` | per-service RPS | ≥6 mo | ◐ | – | ✓ |
| **p95 / p99 latency** | "scaling didn't relieve latency" — core verdict input | `ts, seconds` (or ms) | p99 per service | ≥6 mo | ✓ | – | ✓ |
| **Error rate** | degradation signal; SLO-breach context | `ts, fraction` (or %) | 5xx fraction per service | ≥6 mo | ✓ | ◐ | ✓ |
| **Throughput** | confirm futility (load flat despite more replicas) | `ts, value` | per service | ≥6 mo | ◐ | – | ✓ |
| **Queue depth (if applicable)** | queue-collapse regime | `ts, value` | per queue | ≥6 mo | ◐ | – | ✓ |
| **Incident windows / postmortem timestamps** | Tier-A requires overlap with a real incident | `incident_id, start, end, severity` | + postmortem link | period | ✓ | ◐ | ✓ |
| **Cost assumptions** | price excess replica-hours + incident minutes | `$/replica-hour` (single number ok) | + `$/incident-minute`, cluster spend | n/a | – | ✓ | ✓ |

(✓ required · ◐ strengthens / partially used · – not used for that purpose)

### 3.2 Optional but valuable
| Data type | Why it helps | Min format | Tier-A? | APCY? | Adj? |
|---|---|---|---|---|---|
| Dependency metrics (downstream service latency/error) | distinguishes downstream-saturation Tier-A | `ts, value` per dep | ◐ | – | ✓ |
| DB / cache / queue saturation metrics | confirms "more replicas can't help" root cause | `ts, value` | ◐ | – | ✓ |
| Deployment / change events | rule out "bad deploy" confounders | `ts, deployment, change` | – | – | ✓ |
| Alert timelines | corroborate incident windows | `ts, alert, state` | ◐ | – | ✓ |
| SLO-breach records | sharpen breach severity in cost model | `ts, slo, breach` | – | ◐ | ✓ |
| Node-level cost data | tie excess replicas to real node spend | `ts, node, $` | – | ✓ | ✓ |
| KEDA trigger metrics | event-driven scaling context | `ts, trigger, value` | ◐ | – | ✓ |
| VPA recommendations | rightsizing context (not our axis) | snapshot | – | – | ✓ |
| Autoscaler config snapshots | min/max replicas, target util, behavior | HPA/Karpenter YAML | ◐ | – | ✓ |

---

## 4. Log/export formats we can accept

We adapt to the partner; they do not reshape data for us. Acceptable sources:

- **Prometheus range-query export** (`/api/v1/query_range`) — CSV or JSON (preferred).
- **Thanos / Mimir / Cortex** export (same Prometheus API).
- **Grafana Explore** export (CSV/JSON of the panel queries).
- **Kubernetes event export** (`kubectl get events -o json`, or an events exporter).
- **HPA YAML snapshots** (`kubectl get hpa -o yaml`).
- **Karpenter event logs** (provisioning/consolidation events, JSON/CSV).
- **Datadog metric export** (CSV/JSON via the metrics API or notebook export).
- **CloudWatch Container Insights export** (CSV/JSON).
- **GCP Cloud Monitoring export** (CSV/JSON, or BigQuery export).
- **Azure Monitor export** (CSV/JSON / Log Analytics export).
- **Incident/postmortem CSV** (`incident_id, start, end, severity[, link]`).
- **Freeform markdown postmortems** (we extract timestamps; lower-fidelity but usable).

### 4.1 The one canonical manifest we ask partners to target
This is what `PartnerPrometheusAdapter` + `scripts/run_tier_a_replay.py` consume directly.
If a partner can produce this, ingestion is turnkey; otherwise we convert from any source
above into it.

**(a) Per-cluster metrics CSV** — one row per sample, time-ordered:
```
timestamp,cpu,memory,latency_p99_seconds,error_rate,queue_depth,current_replicas,desired_replicas,pod_restarts
1700000000,0.62,0.40,0.85,0.012,140,12,14,0
```
Required columns: `timestamp`, `current_replicas`, and **at least** `cpu` **and**
(`latency_p99_seconds` **or** `error_rate`). `latency_p99_ms` is accepted (auto-converted).
`cpu/memory/error_rate` may be a fraction `[0,1]` or a percent (auto-detected). One file
per cluster/service.

**(b) Incidents CSV** — separate file:
```
incident_id,start,end,severity
INC-101,1700001320,1700002520,SEV2
```

**(c) Run manifest JSON** — ties files to identity + cost inputs:
```json
[
  {"metrics":"clusterA.csv","incidents":"clusterA_incidents.csv",
   "cluster":"cluster-A","org":"org-1",
   "dollars_per_replica_hour":0.10,"dollars_per_incident_minute":5.0,
   "latency_slo_seconds":1.0}
]
```

**Field / timezone / sampling rules:**
- **Timestamps:** epoch seconds **or** ISO-8601, in **UTC** (state the tz if not UTC).
  Incident timestamps must share the metrics' clock.
- **Sampling:** a **regular cadence** (15s–60s typical). The tool infers cycle length from
  the median timestamp delta; irregular gaps are tolerated but degrade resolution. State
  the scrape/aggregation interval.
- **Coverage:** ≥6 months per cluster preferred; the pre-registered floor is **≥150
  cluster-months across ≥6 orgs** before APCY is reportable (`TIER_A_DETECTOR_SPEC.md` §5c).

### 4.2 Anonymizing service names while preserving relationships
- Replace service/namespace names with **stable pseudonyms** via a salted hash
  (`svc_a3f1`), applied **consistently** so the same service maps to the same pseudonym
  across all files — preserving caller→dependency relationships and time alignment.
- Keep the **mapping private on the partner side**; we never need the real names.
- **Do not** anonymize or shift **timestamps** (breaks incident overlap) or **incident
  IDs** (breaks adjudication linkage). Relative structure and timing must be preserved.

---

## 5. Partner request tiers

Four asks of increasing trust. A partner can stop at any tier; never bundle them.

### Tier 0 — Discovery only (no data)
- **Ask:** the first-interview conversation (`track_c_design_partner/02_FIRST_INTERVIEW_SCRIPT.md`).
- **Partner effort:** 30–40 min call. **Data sensitivity:** none.
- **What we learn:** ICP fit; whether they have a remembered autoscaling-amplified
  incident; the **differentiation** answer (§8); appetite for B/A.
- **What we cannot claim:** anything quantitative — opinion is not measurement.

### Tier 1 — Historical replay (one-time export)
- **Ask:** the canonical export (§4) for ≥1 cluster, ≥6–12 mo + incidents + a `$/replica-hour`.
- **Partner effort:** one export job. **Data sensitivity:** medium (operational metrics;
  anonymizable; no payloads/PII).
- **What we learn:** Tier-A **frequency** and a directional **APCY** (Gate 1), offline.
- **What we cannot claim:** live precision; independence; that APCY is final (it is an
  **estimate pending live adjudication**, and not reportable below the §4.1 coverage floor).

### Tier 2 — Live read-only shadow
- **Ask:** scoped **read-only** Prometheus/Kubernetes access for ~2 weeks (§2).
- **Partner effort:** a read-only token + endpoint + ~30 min/week SRE adjudication.
  **Data sensitivity:** medium (live read-only; zero write; revocable).
- **What we learn:** precision on **live noisy** metrics (Gate 2); alert-volume/fatigue;
  early pull (Gate 3).
- **What we cannot claim:** `live-shadow-self-run` (that's our own cluster); third-party
  independence until the partner SRE adjudicates (label `partner-shadow`).

### Tier 3 — Recommend-mode pilot (still zero actuation)
- **Ask:** permission to surface verdict **recommendations/alerts** into Slack/PagerDuty
  — **never** to actuate.
- **Partner effort:** an inbound webhook + agreement to route alerts. **Data
  sensitivity:** low incremental.
- **What we learn:** strong **pull** (Gate 3) — do they want it *in their incident path*?
- **What we cannot claim:** autonomous/actuation capability; this remains read-only/advisory.

---

## 6. Data minimization / security

**What we do NOT need (state this proactively):**
- **No source code.**
- **No customer PII** (no user IDs, emails, account data).
- **No request/response payloads** (no bodies, no logs of request contents).
- **No secrets / credentials / tokens** beyond a single scoped read-only access token.
- **No write permissions** of any kind (see §2.2).
- **No raw application logs** — only the named numeric metric series and event timestamps
  in §3. (This is the explicit answer to "send us your logs": **we don't want logs.**)

**Practices:**
- **Anonymization:** salted-hash service names (§4.2); partner keeps the mapping.
- **Least privilege:** one read-only datasource/token, scoped to the target
  namespace/service, time-boxed and revocable; network-restricted where possible.
- **NDA:** mutual NDA + written data-handling terms **before any ingestion**
  (`track_c_design_partner/03_DATA_REQUEST_NDA_CHECKLIST.md`).
- **Retention/deletion:** access list named; data stored in one agreed location;
  **delete on request / at pilot end**; results shared back to the partner before any
  internal use; no redistribution.

---

## 7. Mapping each data type to the evidence gates

Gate 1 = Market pain / APCY · Gate 2 = Trust / precision · Gate 3 = Pull / differentiation.

| Data type | Gate 1 (APCY) | Gate 2 (Trust) | Gate 3 (Pull) |
|---|---|---|---|
| Current/desired replicas (history) | ✓ detect + price | ✓ replay precision | – |
| HPA scale events + reasons | ✓ anchor episodes | ✓ | – |
| CPU / HPA resource metric | ✓ NOT_HELPING signal | ✓ | – |
| p95/p99 latency, error rate, throughput | ✓ detect | ✓ core verdict inputs | – |
| Queue depth, dependency/saturation metrics | ◐ root-cause | ✓ reduces false positives | – |
| Incident windows / postmortems | ✓ Tier-A overlap | ◐ adjudication | – |
| Cost assumptions ($/replica-hr, $/incident-min) | ✓ price APCY | – | – |
| **Live** read-only Prometheus/HPA access | ◐ live frequency | ✓ **the live precision test** | ◐ early pull |
| SRE adjudication of flags | ✓ confirms Tier-A | ✓ confirms true/false | ◐ |
| **Differentiation answer** (the question, §8) | – | – | ✓ **the leading indicator** |
| Recommend-mode acceptance, LOI, expansion | – | – | ✓ real demand |

---

## 8. SRE adjudication workflow

Every flagged episode (from Track-B replay or Track-A/partner-shadow) is reviewed by the
partner's SRE using `track_c_design_partner/04_SRE_ADJUDICATION_WORKSHEET.md`, which the
replay tool **pre-fills** (window, replicas floor→peak, metric snapshot, incident overlap,
estimated cost). The SRE assigns exactly one label:

| Label | Meaning | Counts toward |
|---|---|---|
| **Confirmed Tier-A** | scaling genuinely did not help **and** it materially over-provisioned or amplified a non-capacity incident | APCY (Gate 1) |
| **Tier-B only** | a real NOT_HELPING blip but low-value / no incident overlap | diagnostics only — **never** market evidence |
| **False positive** | scaling *was* helping/appropriate; if it would have blocked a genuinely-helpful scale-out → **⛔ harmful FP → stop-and-review** | Gate 2 (precision) |
| **Ambiguous** | metrics insufficient to judge | excluded from rates; note what's missing |
| **Excluded** | confounded (bad deploy, data gap, test traffic) | excluded with reason |

**Throughput target:** toward ≥40–50 adjudicated flags across the fleet (bounds the FP
rate); ≥6 orgs before any frequency number is trusted.

**The differentiation question (ask verbatim, early, before any payment/actuation talk):**
> **"Did this verdict tell you something your existing tooling did not — specifically,
> that scaling was not helping?"**

Record `yes / no / unsure` with a verbatim quote in
`track_c_design_partner/05_PULL_SIGNAL_TRACKER.md`. A consistent **yes** (tied to a
concrete episode, unprompted) is the leading indicator of pull; a consistent **no**
("we'd have seen it anyway") pushes toward feature/acquisition — both are valuable,
recorded as-is.

---

## 9. What counts as success / failure

Tied to the pre-registered thresholds; no goalpost-moving.

- **Track A — success:** §2.8 pre-flight passes (real HPA replicas readable); the verdict
  runs across the window with **0 harmful false positives** on clear helpful-scale-out
  cases and **0 SLO regressions** (structural, read-only); on an external-bottleneck
  window it flags futility with metrics showing more replicas didn't help, reproduced
  across ≥2 runs/windows.
- **Track A — failure:** any **harmful false positive**; metric mapping fails
  (replica/latency series empty); or the observer never reaches its regime so value is
  unproven (bounds value, not safety — report as inconclusive, don't spin).
- **Track B — success:** ≥150 cluster-months across ≥6 orgs ingested; ≥5 adjudicated
  Tier-A episodes; a directional **APCY** computed and labeled `real-trace-replay
  (estimate pending live adjudication)`; FP rate trackable.
- **Track B — failure (market-red):** **<5 adjudicated Tier-A across ≥150 cluster-months**
  — the event is too rare to build a company on, regardless of verdict cleanliness; or
  data too narrow (single-workload) to trust.
- **Track C — success:** a consistent differentiation **yes**; plus real-demand signals
  (paid LOI / unprompted expansion / ≥50% "very disappointed if removed" / recommend-mode
  request / credible "we'd let it act once trusted").
- **Track C — failure:** differentiation mostly **no** ("we'd have seen it anyway");
  only free-pilot enthusiasm, no LOI/expansion ("we'd expect it free in Datadog").

---

## 10. Example partner ask (short, read-only, non-hype)

> **Subject: A read-only second opinion on your autoscaling (no write access, ~2 weeks)**
>
> Hi [name],
>
> We're researching a narrow question with a few platform/SRE teams: after an autoscaler
> adds replicas, **did that scale-out actually help** — or was the bottleneck somewhere
> more replicas couldn't fix (a saturated dependency, a lock, a queue, a cascade)?
>
> We run a small **read-only** engine in shadow that emits a per-scale-out verdict
> (helping / not-helping / futile-runaway). **Zero write permissions** — it reads
> Prometheus and never touches the cluster. We make **no savings promise** and **no
> production-readiness claim**; this is a reliability/safety read, and the point of the
> pilot is to find out whether it tells you anything new.
>
> Two low-effort ways to help, either alone:
> 1. **History (most useful):** an export of ~6–12 months of a few **metric series** —
>    CPU, p99 latency, error rate, current/desired replicas — plus your incident
>    timestamps. **No logs, no payloads, no PII, no source code.** We replay it offline to
>    see how often this pattern shows up for you.
> 2. **Live shadow:** a scoped **read-only** Prometheus token for one cluster for ~2 weeks,
>    plus ~30 min/week from an SRE to tell us, per flag, true or false.
>
> Everything under NDA, deletable on request, off at any time. If the verdict tells you
> nothing you didn't already know, you've lost nothing — and that's a useful result for us
> too.
>
> Worth a 30-minute call?

(Full one-pager: `track_c_design_partner/01_PARTNER_BRIEF.md`; data terms:
`…/03_DATA_REQUEST_NDA_CHECKLIST.md`.)

---

## 11. Open questions / assumptions to verify

1. **Metric mapping holds per partner.** We assume a partner's metrics map cleanly to the
   five canonical signals. Verify metric names/units per partner (latency in s vs ms; CPU
   fraction vs %; which metric HPA actually scales on).
2. **`latency_slo_seconds` default = 1.0.** The normalization SLO is a frozen default;
   confirm each partner's real latency SLO and record it (affects breach context, not the
   detector's verdicts).
3. **Queue normalization** uses the 95th percentile unless a capacity is supplied — verify
   for queue-bound workloads.
4. **Cost inputs are partner-supplied.** APCY needs `$/replica-hour` (and ideally
   `$/incident-minute`); absent them the tool reports excess replica-hours only — never a
   fabricated dollar figure.
5. **Incident timeline fidelity.** Tier-A requires incident overlap; assumes partners can
   supply usable incident start/end timestamps. Where only freeform postmortems exist,
   extraction is lower-fidelity — flag those episodes as `pending incident confirmation`.
6. **Detector envelope (K=5 consecutive NOT_HELPING at M=20 replicas, incident-overlap
   required)** is pre-registered and **not** tuned per partner; if a partner's fleet sizes
   are systematically small (<20 replicas), Tier-A may under-detect — record as a coverage
   caveat, **do not** retune to flatter the number (any change = a new pre-registration).
7. **Coverage floor reachable.** ≥150 cluster-months across ≥6 orgs is a real recruiting
   bar; verify the funnel can reach it before over-investing in tooling.
8. **External-poll observer is acceptable** to partners (vs in-cluster deploy); confirm
   per partner, as it changes the access ask.
9. **Anonymization preserves enough structure** for dependency-based root-causing; verify
   the salted-hash approach doesn't strip relationships the adjudication needs.
10. **"Partner-shadow" labeling** is internally agreed as distinct from
    `live-shadow-self-run` and `third-party`; confirm we hold that line in all external
    materials.

---

*Scope note: this is a planning document — it gathers requirements, it does not report
results. It implies **no** production or customer validation, makes **no** savings claim,
and uses **no** synthetic block-rate figure. The VC brief and pitchbook are intentionally
**not** updated here; per project discipline they change only when measured evidence
lands.*

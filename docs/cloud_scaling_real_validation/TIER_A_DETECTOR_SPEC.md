# Tier-A Detector — Pre-Registered Specification (Track B)

**INTERNAL. Pre-registration. Written and frozen BEFORE any partner data is
ingested.** This document fixes the Tier-A detector, its pass/fail criteria, and the
cost / APCY model **in advance**, so that no threshold can be tuned post-hoc to a
flattering answer (`MARKET_VALIDATION_90_DAY_PLAN.md` §12, `STRATEGY_IMPLEMENTATION_PLAN.md`
§6, §10). The machine-readable form of every constant here lives in
`cloud_controller/replay/tier_a.py` as `DEFAULT_TIER_A_SPEC`; the two must agree.

- **Date pre-registered:** 2026-06-17.
- **Label on every number this produces:** `real-trace-replay (estimate pending live
  adjudication)`. Never `live-shadow-self-run`, never `third-party`, never
  "validated".
- **Status of partner data when this was written:** none ingested. The detector is
  validated only against a committed **synthetic schema fixture** whose sole purpose
  is to prove the *tooling*, not to produce a market number.

---

## 1. What Tier-A is (the unit of market evidence)
Restating the frozen definition (90-day plan §2; do not re-derive):

> **Tier-A episode:** a runaway/futile autoscaling episode that **materially
> over-provisioned or amplified a non-capacity incident** — the event a read-only
> interlock would have capped. *This is the only unit that counts as market evidence.*

> **Tier-B event:** a single low-value non-causal scale-out / isolated NOT_HELPING
> observation. Diagnostic and demo-useful; **never** a headline number, **never**
> counted toward APCY.

The replay tool **surfaces Tier-A candidates**; an SRE **adjudicates** each one
true/false and confirms cost. APCY is computed from **adjudicated** episodes — so
every replay-derived number is an *estimate pending live adjudication*.

## 2. The detector (frozen parameters)
Run the **unmodified** `EfficiencyEstimator` over a trace of **real measured
metrics + real replica history** (partner export) and read its per-cycle verdict
stream (`cycle_log[i].state ∈ {HELPING, NEUTRAL, NOT_HELPING}`, `cycle_log[i].replicas`).

A **futile episode** is a maximal contiguous span of cycles for which **both** hold on
every cycle of the span:
- `state == NOT_HELPING`, **and**
- `replicas ≥ M`,

with span length **≥ K** cycles. Frozen parameters (match the shipped guard's
envelope so the detector is consistent with the product, not a new knob):

| Symbol | Meaning | Value | Provenance |
|---|---|---|---|
| `K` | min consecutive NOT_HELPING cycles | **5** | = `ScaleOutFutilityGuard.futility_window` |
| `M` | min replicas during the streak | **20** | = `ScaleOutFutilityGuard.high_replica_threshold` |
| `eval_window` | estimator look-back | **5** | = `EfficiencyEstimator` default |
| `tier_b_min_streak` | min NOT_HELPING run to log a Tier-B event | **2** | conservative; below the Tier-A bar |

The detector **never** reuses these as tunable knobs; changing any value requires a
**new, dated pre-registration** (§6).

## 3. Tier classification (incident overlap is part of the definition)
Each futile episode is classified **once**, deterministically:

| Outcome | Condition |
|---|---|
| **Tier-A candidate** | futile episode **overlaps ≥1 partner incident window** → it amplified/over-provisioned during a real incident. → emit an SRE worksheet. |
| **Tier-A candidate (pending incident)** | futile episode, but **no incident timeline was supplied at all** → overlap cannot be checked. → emit a worksheet; SRE must confirm overlap + materiality. |
| **Tier-B** | a NOT_HELPING streak that **fails the Tier-A bar**: replicas `< M`, or length `< K`, **or** (incident data *was* supplied and the episode overlaps **no** incident). Diagnostic only. |

Rationale: Tier-A is defined as amplifying a *non-capacity incident*, so **incident
overlap is required** to call something Tier-A. A long futile streak that provably did
**not** coincide with any incident is Tier-B, not Tier-A — we do not inflate the
market-evidence count with it.

## 4. Cost model (per episode) — frozen
All cost inputs are **partner-supplied**; the tool **fabricates none**. Missing inputs
are reported as "pending partner input," not as zero-with-a-claim.

- **Excess replica-hours** = Σ over episode cycles of `max(0, replicas[i] − floor) ×
  (cycle_seconds / 3600)`, where `floor` = replicas at the cycle the episode **began**
  (the pre-runaway level). This is the extra capacity *held during the futile streak*.
- **Excess compute cost** = excess replica-hours × **`$/replica-hour`** *(partner item
  §5.6)*. If `$/replica-hour` is absent → report excess replica-hours only.
- **Incident-overlap cost** = overlapped incident-minutes × **`$/incident-minute`**
  *(partner-supplied)*. Absent → omitted, **not** zero-claimed.
- **SLO-breach severity** = breach-cycle count in the episode (and a partner-defined
  $/severity weight if supplied).
- **Episode cost** = excess compute cost **+** incident cost **(+** SLO severity if
  priced). Recorded per episode for SRE confirmation.

**APCY** (the gate metric, plan §7):
```
cluster_years            = n_cycles × cycle_seconds / SECONDS_PER_YEAR
tier_a_per_cluster_year  = (Σ Tier-A candidates) / (Σ cluster_years)      # across clusters/orgs
APCY                     = tier_a_per_cluster_year × median(episode_cost)
```

## 5. Pass / fail
### 5a. Tooling validation (on the committed schema fixture — this is a self-test, NOT evidence)
The tool **passes** iff, on `data/cloud_traces/fixtures/partner_prometheus_SCHEMA_FIXTURE.csv`:
- a purely **capacity-bound (HELPING)** stretch yields **0** futile episodes;
- the planted **futile-runaway** stretch (latency high / util collapsing while replicas
  climb past `M`), **overlapping** the fixture incident, yields **exactly one Tier-A
  candidate**;
- the **same** stretch with incidents removed → **Tier-A candidate (pending incident)**;
  with a **non-overlapping** incident → **Tier-B**;
- **no** Tier-A is ever emitted when `replicas < M` or streak `< K`;
- detection is **deterministic** (identical inputs → identical episodes);
- APCY is **refused as reportable** when fleet coverage `< 150 cluster-months` or
  `< 5` Tier-A candidates (the trip-wire fires — the tool will not dress up a fixture
  as a market signal).

### 5b. A Tier-A candidate counts as evidence only after SRE adjudication confirms
- the scale-out **genuinely did not help** (true positive, not a metric artifact), **and**
- it **materially over-provisioned or amplified a non-capacity incident**, **and**
- the **cost** is confirmed with partner economics.
Until all three: it is a **candidate**, labeled `estimate pending live adjudication`.

### 5c. Market read (plan §7, §11) — pre-registered, not negotiable after the fact
- **< 5 adjudicated Tier-A across ≥150 retrospective cluster-months** → **market-red**,
  regardless of how clean the verdict is.
- Require **≥6 orgs** before trusting any frequency number (no single-workload bias).

## 6. Anti-tuning rule
`K`, `M`, `eval_window`, the incident-overlap requirement, and the metric-normalization
assumptions (§7) are **frozen as of the date above.** Any change is a **new
pre-registration**: a written hypothesis + an explicit pass/fail criterion + a date,
recorded **before** re-running on partner data. **No** silent retuning, **no** picking
the parameters that maximize APCY.

## 7. Metric-normalization assumptions (frozen; recorded in every run's meta)
A partner Prometheus export carries **real measured** signals; the adapter maps them to
the controller's canonical `≈[0,1]` schema with these fixed assumptions (disclosed,
never silently changed):
- `cpu`, `memory`, `error_rate`: treated as fractions; values `> 1` are read as percent
  and divided by 100; clamped to `[0,1]`.
- `latency_p99`: `min(1, latency_seconds / latency_slo_seconds)`, default
  `latency_slo_seconds = 1.0` (override per-partner, recorded).
- `queue_depth`: `min(1, q / queue_capacity)`, `queue_capacity` = partner-supplied or
  the 95th percentile of the observed series (recorded).
- `replicas`: the partner's **real** `current_replicas` per cycle — used as-is (never
  modeled). This is the key gain over modeled traces: the verdict runs on real metrics
  **and** real fleet sizes.

These assumptions affect *normalization only*; the detector parameters in §2 operate on
the estimator's verdicts, which are computed the same way the shipped product computes
them.

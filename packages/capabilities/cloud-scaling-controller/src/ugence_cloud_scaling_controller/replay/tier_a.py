"""Tier-A episode detector + APCY model (Track B).

Implements the **pre-registered** spec in
`Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md`. The constants here ARE
the pre-registration's machine form (`DEFAULT_TIER_A_SPEC`) — they are frozen and must
not be tuned post-hoc (spec §6).

What it does, on top of the EXISTING replay machinery (it does **not** modify the
control core):

  1. Run the unmodified `EfficiencyEstimator` over a trace of **real measured metrics +
     real replica history** (a partner Prometheus/HPA export) and read its per-cycle
     verdict stream.
  2. Detect **futile episodes** — maximal runs of ≥K consecutive NOT_HELPING cycles at
     ≥M replicas — and classify each as a **Tier-A candidate** (overlaps a partner
     incident window), **Tier-A candidate pending incident** (no incident timeline
     supplied), or **Tier-B** (fails the bar / provably no incident overlap).
  3. Price each Tier-A candidate with the frozen, partner-fed cost model and roll the
     fleet up into **APCY** — refusing to report it until the pre-registered coverage
     floor is met.
  4. Emit an **SRE-adjudication worksheet** per Tier-A candidate.

Every number is labelled `real-trace-replay (estimate pending live adjudication)`. The
replay surfaces *candidates*; an SRE confirms true/false + cost before anything counts.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ugence_cloud_scaling_controller.observability.efficiency_estimator import (
    EfficiencyEstimator,
    EfficiencyState,
)
from ugence_cloud_scaling_controller.replay.adapters.base import IncidentWindow, TraceSeries

__all__ = [
    "TierASpec", "DEFAULT_TIER_A_SPEC", "IncidentWindow", "TierAEpisode",
    "TierBEvent", "ClusterTierAResult", "APCYEstimate", "observe_trace",
    "detect_tier_a", "compute_apcy", "emit_worksheet", "emit_worksheets",
    "TIER_A_CANDIDATE", "TIER_A_PENDING_INCIDENT", "TIER_B",
]

LABEL = "real-trace-replay (estimate pending live adjudication)"
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
SECONDS_PER_MONTH = SECONDS_PER_YEAR / 12.0

# Tier-A candidate classifications (spec §3).
TIER_A_CANDIDATE = "tier_a_candidate"
TIER_A_PENDING_INCIDENT = "tier_a_candidate_pending_incident"
TIER_B = "tier_b"


@dataclass(frozen=True)
class TierASpec:
    """Frozen detector + cost parameters. See TIER_A_DETECTOR_SPEC.md §2, §4, §7.

    Changing any value requires a NEW dated pre-registration (spec §6).
    """
    # detector (spec §2) — match the shipped guard's envelope
    k_consecutive_not_helping: int = 5     # = ScaleOutFutilityGuard.futility_window
    m_replicas: int = 20                   # = ScaleOutFutilityGuard.high_replica_threshold
    eval_window: int = 5                   # = EfficiencyEstimator default
    tier_b_min_streak: int = 2
    # SLO-breach context (spec §4) — descriptive, not a $ claim
    slo_latency_breach: float = 0.9        # normalized p99 ≥ this = breach cycle
    slo_error_breach: float = 0.05         # error-rate fraction ≥ this = breach cycle
    # market coverage floor (spec §5c) — pre-registered, not negotiable post-hoc
    min_cluster_months: float = 150.0
    min_tier_a: int = 5
    min_orgs: int = 6


DEFAULT_TIER_A_SPEC = TierASpec()


@dataclass
class TierAEpisode:
    """A futile episode surfaced by replay — a Tier-A candidate pending adjudication."""
    episode_id: str
    classification: str                    # TIER_A_CANDIDATE | TIER_A_PENDING_INCIDENT
    start_cycle: int
    end_cycle: int
    length: int
    floor_replicas: int                    # replicas at episode start (pre-cap level)
    min_replicas: int
    peak_replicas: int
    mean_confidence: float
    overlaps_incident: bool
    incident_ids: List[str] = field(default_factory=list)
    incident_overlap_minutes: float = 0.0
    slo_breach_cycles: int = 0
    # cost model (spec §4) — None where partner input is missing (never zero-claimed)
    excess_replica_hours: float = 0.0
    excess_compute_cost_usd: Optional[float] = None
    incident_cost_usd: Optional[float] = None
    episode_cost_usd: Optional[float] = None
    metric_snapshot: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "classification": self.classification,
            "start_cycle": self.start_cycle,
            "end_cycle": self.end_cycle,
            "length_cycles": self.length,
            "floor_replicas": self.floor_replicas,
            "min_replicas": self.min_replicas,
            "peak_replicas": self.peak_replicas,
            "mean_confidence": round(self.mean_confidence, 3),
            "overlaps_incident": self.overlaps_incident,
            "incident_ids": list(self.incident_ids),
            "incident_overlap_minutes": round(self.incident_overlap_minutes, 2),
            "slo_breach_cycles": self.slo_breach_cycles,
            "excess_replica_hours": round(self.excess_replica_hours, 3),
            "excess_compute_cost_usd": _round_opt(self.excess_compute_cost_usd),
            "incident_cost_usd": _round_opt(self.incident_cost_usd),
            "episode_cost_usd": _round_opt(self.episode_cost_usd),
            "metric_snapshot": {k: round(v, 4) for k, v in self.metric_snapshot.items()},
        }


@dataclass
class TierBEvent:
    """A NOT_HELPING streak that fails the Tier-A bar — diagnostic only."""
    start_cycle: int
    end_cycle: int
    length: int
    peak_replicas: int
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "start_cycle": self.start_cycle,
            "end_cycle": self.end_cycle,
            "length_cycles": self.length,
            "peak_replicas": self.peak_replicas,
            "reason": self.reason,
        }


@dataclass
class ClusterTierAResult:
    """Per-cluster Tier-A counts (spec §1) — the unit fed into APCY."""
    cluster: str
    org: str
    n_cycles: int
    cycle_seconds: float
    data_status: str
    label: str = LABEL
    incidents_provided: bool = False
    cycles_helping: int = 0
    cycles_neutral: int = 0
    cycles_not_helping: int = 0
    tier_a_candidates: List[TierAEpisode] = field(default_factory=list)
    tier_b_events: List[TierBEvent] = field(default_factory=list)
    meta: Dict[str, object] = field(default_factory=dict)

    @property
    def cluster_years(self) -> float:
        return self.n_cycles * self.cycle_seconds / SECONDS_PER_YEAR

    @property
    def cluster_months(self) -> float:
        return self.n_cycles * self.cycle_seconds / SECONDS_PER_MONTH

    @property
    def n_tier_a(self) -> int:
        return len(self.tier_a_candidates)

    @property
    def n_tier_b(self) -> int:
        return len(self.tier_b_events)

    def to_dict(self) -> Dict[str, object]:
        return {
            "cluster": self.cluster,
            "org": self.org,
            "label": self.label,
            "data_status": self.data_status,
            "n_cycles": self.n_cycles,
            "cycle_seconds": self.cycle_seconds,
            "cluster_months": round(self.cluster_months, 4),
            "cluster_years": round(self.cluster_years, 5),
            "incidents_provided": self.incidents_provided,
            "verdict_mix": {
                "cycles_helping": self.cycles_helping,
                "cycles_neutral": self.cycles_neutral,
                "cycles_not_helping": self.cycles_not_helping,
            },
            "tier_a_candidate_count": self.n_tier_a,
            "tier_b_event_count": self.n_tier_b,
            "tier_a_candidates": [e.to_dict() for e in self.tier_a_candidates],
            "tier_b_events": [e.to_dict() for e in self.tier_b_events],
            "meta": self.meta,
        }


@dataclass
class APCYEstimate:
    """Fleet-level APCY — the Gate-1 number, with the pre-registered honesty gate."""
    n_orgs: int
    n_clusters: int
    total_cluster_months: float
    total_cluster_years: float
    total_tier_a_candidates: int
    total_tier_b_events: int
    median_episode_cost_usd: Optional[float]
    tier_a_per_cluster_year: Optional[float]
    apcy_usd_per_cluster_year: Optional[float]
    reportable: bool
    market_red: bool
    reason: str
    label: str = LABEL

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "n_orgs": self.n_orgs,
            "n_clusters": self.n_clusters,
            "total_cluster_months": round(self.total_cluster_months, 3),
            "total_cluster_years": round(self.total_cluster_years, 4),
            "total_tier_a_candidates": self.total_tier_a_candidates,
            "total_tier_b_events": self.total_tier_b_events,
            "median_episode_cost_usd": _round_opt(self.median_episode_cost_usd),
            "tier_a_per_cluster_year": _round_opt(self.tier_a_per_cluster_year, 4),
            "apcy_usd_per_cluster_year": _round_opt(self.apcy_usd_per_cluster_year),
            "reportable": self.reportable,
            "market_red": self.market_red,
            "reason": self.reason,
        }


def _round_opt(x: Optional[float], n: int = 2) -> Optional[float]:
    return None if x is None else round(x, n)


# --------------------------------------------------------------------------- #
# Verdict stream
# --------------------------------------------------------------------------- #

def observe_trace(
    series: TraceSeries,
    spec: TierASpec = DEFAULT_TIER_A_SPEC,
) -> Tuple[List, List[int], List[Dict[str, float]]]:
    """Run the unmodified estimator over the trace; return (cycle_log, replicas, metrics).

    Uses the partner's REAL replica history when present (`series.replicas`); otherwise
    synthesizes a replica trajectory with the unmodified controller (guard OFF) so the
    detector also runs on workload-only traces (e.g. Azure). The verdict stream is the
    same one the shipped product computes.
    """
    metrics = series.to_metrics_series()
    if series.replicas is not None:
        reps = [int(round(r)) for r in series.replicas]
        if len(reps) != len(metrics):  # defensive align
            n = min(len(reps), len(metrics))
            reps, metrics = reps[:n], metrics[:n]
        deltas = [0] + [reps[i] - reps[i - 1] for i in range(1, len(reps))]
    else:
        metrics, reps, deltas = _synthesize_trajectory(series)

    est = EfficiencyEstimator(eval_window=spec.eval_window)
    for i, m in enumerate(metrics):
        est.observe(cycle=i, metrics=m, replicas=reps[i], delta=deltas[i], optimal_replicas=0)
    return est.cycle_log, reps, metrics


def _synthesize_trajectory(
    series: TraceSeries, warmup_cycles: int = 40, base_replicas: int = 5,
) -> Tuple[List[Dict[str, float]], List[int], List[int]]:
    """Guard-OFF controller trajectory for traces without real replicas (mirrors the
    Track-B harness loop). Lets the Tier-A tool run on workload-only traces too."""
    from ugence_cloud_scaling_controller.config import InfraControllerConfig
    from ugence_cloud_scaling_controller.controller import Controller

    try:
        from ugence_cloud_scaling_controller.observability.edge_cases import _tuned_config
        cfg = _tuned_config()
    except Exception:
        cfg = InfraControllerConfig()

    metrics = series.to_metrics_series()
    ctrl = Controller(cfg)
    warm = metrics[0] if metrics else {}
    for _ in range(warmup_cycles):
        ctrl.step(metrics=warm, current_replicas=base_replicas)

    reps: List[int] = []
    deltas: List[int] = []
    r = base_replicas
    for m in metrics:
        res = ctrl.step(metrics=m, current_replicas=r)
        d = res.replica_delta
        r = max(1, r + d)
        reps.append(r)
        deltas.append(d)
    return metrics, reps, deltas


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #

def _maximal_runs(flags: List[bool]) -> List[Tuple[int, int]]:
    """Maximal contiguous [start, end] spans where flags is True."""
    runs: List[Tuple[int, int]] = []
    i, n = 0, len(flags)
    while i < n:
        if flags[i]:
            j = i
            while j + 1 < n and flags[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def detect_tier_a(
    series: TraceSeries,
    spec: TierASpec = DEFAULT_TIER_A_SPEC,
    *,
    cluster: Optional[str] = None,
    org: Optional[str] = None,
    dollars_per_replica_hour: Optional[float] = None,
    dollars_per_incident_minute: Optional[float] = None,
) -> ClusterTierAResult:
    """Detect Tier-A candidates + Tier-B events for one cluster trace (spec §2–§4)."""
    cycle_log, reps, metrics = observe_trace(series, spec)
    n = len(cycle_log)

    incidents_provided = bool(series.meta.get("incidents_provided", False))
    incidents: List[IncidentWindow] = list(series.meta.get("incidents", []) or [])

    states = [c.state for c in cycle_log]
    cyc_reps = [c.replicas for c in cycle_log]

    result = ClusterTierAResult(
        cluster=cluster or series.name,
        org=org or str(series.meta.get("org", series.name)),
        n_cycles=n,
        cycle_seconds=series.cycle_seconds,
        data_status=series.status.value if hasattr(series.status, "value") else str(series.status),
        incidents_provided=incidents_provided,
        cycles_helping=sum(1 for s in states if s == EfficiencyState.HELPING),
        cycles_neutral=sum(1 for s in states if s == EfficiencyState.NEUTRAL),
        cycles_not_helping=sum(1 for s in states if s == EfficiencyState.NOT_HELPING),
        meta={
            "transfer": series.meta.get("transfer_function", "real measured metrics"),
            "normalization": series.meta.get("normalization", {}),
            "dollars_per_replica_hour": dollars_per_replica_hour,
            "dollars_per_incident_minute": dollars_per_incident_minute,
            "spec": {
                "k_consecutive_not_helping": spec.k_consecutive_not_helping,
                "m_replicas": spec.m_replicas,
                "eval_window": spec.eval_window,
            },
        },
    )

    # Qualifying futile spans: NOT_HELPING AND replicas >= M, length >= K.
    futile_flags = [
        states[i] == EfficiencyState.NOT_HELPING and cyc_reps[i] >= spec.m_replicas
        for i in range(n)
    ]
    qualifying = [
        (a, b) for (a, b) in _maximal_runs(futile_flags)
        if (b - a + 1) >= spec.k_consecutive_not_helping
    ]
    qualifying_set = set()
    for a, b in qualifying:
        qualifying_set.update(range(a, b + 1))

    ep_idx = 0
    for a, b in qualifying:
        overlapping = [inc for inc in incidents if inc.overlaps(a, b) > 0]
        overlap_minutes = (
            sum(inc.overlaps(a, b) for inc in overlapping) * series.cycle_seconds / 60.0
        )
        if overlapping:
            classification = TIER_A_CANDIDATE
        elif not incidents_provided:
            classification = TIER_A_PENDING_INCIDENT
        else:
            # incident data supplied but this episode overlapped none → Tier-B, not Tier-A
            result.tier_b_events.append(TierBEvent(
                start_cycle=a, end_cycle=b, length=b - a + 1,
                peak_replicas=max(cyc_reps[a:b + 1]),
                reason="futile streak overlapped no incident window (incident data provided)",
            ))
            continue

        ep_idx += 1
        episode = _build_episode(
            f"{result.cluster}-ep{ep_idx}", classification, a, b,
            cyc_reps, metrics, cycle_log, overlapping, overlap_minutes, series, spec,
            dollars_per_replica_hour, dollars_per_incident_minute,
        )
        result.tier_a_candidates.append(episode)

    # Tier-B: NOT_HELPING streaks (>= tier_b_min_streak) that are NOT part of a
    # qualifying Tier-A span (i.e. failed the M or K bar).
    nh_flags = [s == EfficiencyState.NOT_HELPING for s in states]
    for a, b in _maximal_runs(nh_flags):
        if (b - a + 1) < spec.tier_b_min_streak:
            continue
        if any(i in qualifying_set for i in range(a, b + 1)):
            continue  # already accounted as Tier-A (or its Tier-B reclass above)
        peak = max(cyc_reps[a:b + 1])
        reason = (
            f"peak replicas {peak} < M={spec.m_replicas}"
            if peak < spec.m_replicas
            else f"streak {b - a + 1} < K={spec.k_consecutive_not_helping}"
        )
        result.tier_b_events.append(TierBEvent(
            start_cycle=a, end_cycle=b, length=b - a + 1, peak_replicas=peak, reason=reason,
        ))

    return result


def _build_episode(
    episode_id, classification, a, b, cyc_reps, metrics, cycle_log,
    overlapping, overlap_minutes, series, spec,
    dollars_per_replica_hour, dollars_per_incident_minute,
) -> TierAEpisode:
    span = list(range(a, b + 1))
    floor = cyc_reps[a]
    cycle_hours = series.cycle_seconds / 3600.0
    excess_replica_hours = sum(max(0, cyc_reps[i] - floor) for i in span) * cycle_hours

    excess_compute = (
        excess_replica_hours * dollars_per_replica_hour
        if dollars_per_replica_hour is not None else None
    )
    incident_cost = (
        overlap_minutes * dollars_per_incident_minute
        if (dollars_per_incident_minute is not None and overlapping) else None
    )
    parts = [c for c in (excess_compute, incident_cost) if c is not None]
    episode_cost = sum(parts) if parts else None

    slo_breach = sum(
        1 for i in span
        if metrics[i].get("latency_p99", 0.0) >= spec.slo_latency_breach
        or metrics[i].get("error_rate", 0.0) >= spec.slo_error_breach
    )

    return TierAEpisode(
        episode_id=episode_id,
        classification=classification,
        start_cycle=a, end_cycle=b, length=b - a + 1,
        floor_replicas=floor,
        min_replicas=min(cyc_reps[a:b + 1]),
        peak_replicas=max(cyc_reps[a:b + 1]),
        mean_confidence=statistics.fmean(cycle_log[i].confidence for i in span),
        overlaps_incident=bool(overlapping),
        incident_ids=[inc.incident_id for inc in overlapping],
        incident_overlap_minutes=overlap_minutes,
        slo_breach_cycles=slo_breach,
        excess_replica_hours=excess_replica_hours,
        excess_compute_cost_usd=excess_compute,
        incident_cost_usd=incident_cost,
        episode_cost_usd=episode_cost,
        metric_snapshot={
            "peak_latency_p99": max(metrics[i].get("latency_p99", 0.0) for i in span),
            "peak_error_rate": max(metrics[i].get("error_rate", 0.0) for i in span),
            "mean_cpu": statistics.fmean(metrics[i].get("cpu", 0.0) for i in span),
        },
    )


# --------------------------------------------------------------------------- #
# APCY (fleet roll-up) — with the pre-registered honesty gate (spec §5c)
# --------------------------------------------------------------------------- #

def compute_apcy(
    cluster_results: List[ClusterTierAResult],
    spec: TierASpec = DEFAULT_TIER_A_SPEC,
) -> APCYEstimate:
    """Roll per-cluster Tier-A counts into APCY, refusing to report it until the
    pre-registered coverage floor (≥150 cluster-months, ≥5 Tier-A, ≥6 orgs) is met."""
    total_tier_a = sum(c.n_tier_a for c in cluster_results)
    total_tier_b = sum(c.n_tier_b for c in cluster_results)
    total_months = sum(c.cluster_months for c in cluster_results)
    total_years = sum(c.cluster_years for c in cluster_results)
    n_orgs = len({c.org for c in cluster_results})
    n_clusters = len(cluster_results)

    costs = [
        e.episode_cost_usd
        for c in cluster_results for e in c.tier_a_candidates
        if e.episode_cost_usd is not None
    ]
    median_cost = statistics.median(costs) if costs else None
    per_cy = (total_tier_a / total_years) if total_years > 0 else None
    apcy = (per_cy * median_cost) if (per_cy is not None and median_cost is not None) else None

    enough_months = total_months >= spec.min_cluster_months
    enough_tier_a = total_tier_a >= spec.min_tier_a
    enough_orgs = n_orgs >= spec.min_orgs
    market_red = enough_months and not enough_tier_a
    reportable = enough_months and enough_tier_a and enough_orgs and apcy is not None

    reasons = []
    if not enough_months:
        reasons.append(f"insufficient coverage ({total_months:.1f} < {spec.min_cluster_months:g} cluster-months)")
    if not enough_orgs:
        reasons.append(f"too few orgs ({n_orgs} < {spec.min_orgs}; single-workload bias risk)")
    if not enough_tier_a:
        reasons.append(f"too few Tier-A ({total_tier_a} < {spec.min_tier_a})")
    if median_cost is None:
        reasons.append("no partner cost input → episode $ pending")
    if market_red:
        reasons.append("MARKET-RED: coverage met but <5 Tier-A → event too rare to build on")
    if reportable:
        reason = "coverage floor met; APCY is a real-trace-replay estimate pending live adjudication"
    else:
        reason = "NOT reportable as market evidence — " + "; ".join(reasons)

    return APCYEstimate(
        n_orgs=n_orgs, n_clusters=n_clusters,
        total_cluster_months=total_months, total_cluster_years=total_years,
        total_tier_a_candidates=total_tier_a, total_tier_b_events=total_tier_b,
        median_episode_cost_usd=median_cost,
        tier_a_per_cluster_year=per_cy,
        apcy_usd_per_cluster_year=apcy,
        reportable=reportable, market_red=market_red, reason=reason,
    )


# --------------------------------------------------------------------------- #
# SRE-adjudication worksheet emission (Track C file 4, pre-filled by replay)
# --------------------------------------------------------------------------- #

def emit_worksheet(result: ClusterTierAResult, episode: TierAEpisode) -> str:
    """One pre-filled SRE-adjudication worksheet (markdown) for a Tier-A candidate.

    Mirrors docs/cloud_scaling_real_validation/track_c_design_partner/
    04_SRE_ADJUDICATION_WORKSHEET.md. Replay fills what it knows; the SRE fills
    true/false, tier confirmation, and confirmed cost.
    """
    cs = episode.metric_snapshot
    cost = (f"${episode.episode_cost_usd:,.2f}" if episode.episode_cost_usd is not None
            else "_pending partner $/replica-hour + $/incident-minute_")
    return "\n".join([
        f"### SRE Adjudication — `{episode.episode_id}`",
        f"*Source: replay (Track B) · label: `{result.label}`*",
        "",
        "| field | replay-filled value |",
        "|---|---|",
        f"| Org / cluster | {result.org} / {result.cluster} |",
        f"| Window (cycles) | {episode.start_cycle} → {episode.end_cycle} "
        f"({episode.length} cycles × {result.cycle_seconds:g}s) |",
        f"| Verdict / pattern | futile-runaway ({episode.length} consecutive NOT_HELPING ≥ "
        f"{DEFAULT_TIER_A_SPEC.m_replicas} replicas) |",
        f"| Replicas (floor → peak) | {episode.floor_replicas} → {episode.peak_replicas} |",
        f"| Peak p99 latency (norm) | {cs.get('peak_latency_p99', 0.0):.3f} |",
        f"| Peak error rate | {cs.get('peak_error_rate', 0.0):.3f} |",
        f"| Mean CPU (norm) | {cs.get('mean_cpu', 0.0):.3f} |",
        f"| SLO-breach cycles in window | {episode.slo_breach_cycles} |",
        f"| Incident overlap | {'yes: ' + ', '.join(episode.incident_ids) if episode.overlaps_incident else 'NONE supplied — SRE must confirm'} "
        f"({episode.incident_overlap_minutes:.1f} min) |",
        f"| Excess replica-hours | {episode.excess_replica_hours:.2f} |",
        f"| Estimated episode cost | {cost} |",
        f"| Classification (replay) | {episode.classification} |",
        "",
        "**SRE to complete:**",
        "- [ ] TRUE positive (scaling genuinely not helping) / [ ] FALSE positive / [ ] ⛔ HARMFUL FP (it actually relieved a constraint → STOP-AND-REVIEW)",
        "- [ ] Confirm **Tier-A** (materially over-provisioned / amplified a non-capacity incident) — or downgrade to **Tier-B**",
        "- Root cause: ____  · Confirmed episode cost: $____  · Counts toward APCY: yes / no",
        "",
        "> Full template + definitions: "
        "`track_c_design_partner/04_SRE_ADJUDICATION_WORKSHEET.md`.",
    ])


def emit_worksheets(result: ClusterTierAResult) -> str:
    """All Tier-A-candidate worksheets for a cluster, or a clear 'none' note."""
    if not result.tier_a_candidates:
        return (f"_No Tier-A candidates for cluster `{result.cluster}` "
                f"({result.n_tier_b} Tier-B events — diagnostic only, not market evidence)._")
    return "\n\n".join(emit_worksheet(result, e) for e in result.tier_a_candidates)

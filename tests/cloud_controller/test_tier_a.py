"""Tests for the Tier-A detector + APCY model (Track B).

Validates the TOOLING against the pre-registered spec
(`Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md` §5a) on the committed
synthetic schema fixture. These tests assert tool behavior; they assert **no** market
number — the fixture is a self-test and the APCY trip-wire is expected to refuse it.
"""

import os

import pytest

from cloud_controller.replay.adapters import AdapterStatus, PartnerPrometheusAdapter
from cloud_controller.replay.tier_a import (
    DEFAULT_TIER_A_SPEC,
    SECONDS_PER_MONTH,
    TIER_A_CANDIDATE,
    TIER_A_PENDING_INCIDENT,
    ClusterTierAResult,
    TierAEpisode,
    TierASpec,
    compute_apcy,
    detect_tier_a,
    emit_worksheet,
    emit_worksheets,
)

FIX = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cloud_traces", "fixtures",
)
METRICS = os.path.join(FIX, "partner_prometheus_SCHEMA_FIXTURE.csv")
INCIDENTS = os.path.join(FIX, "partner_incidents_SCHEMA_FIXTURE.csv")

_METRIC_KEYS = {"cpu", "memory", "latency_p99", "error_rate", "queue_depth"}


def _load(incidents=True, **kw):
    return PartnerPrometheusAdapter().load(
        METRICS,
        incidents_path=(INCIDENTS if incidents else None),
        cluster=kw.pop("cluster", "fixture-cluster"),
        org=kw.pop("org", "fixture-org"),
        **kw,
    )


# ----------------------------- adapter -----------------------------

class TestPartnerAdapter:
    def test_status_is_pending_data(self):
        # No real partner data here — the adapter must never claim EXECUTED.
        assert _load().status is AdapterStatus.PENDING_DATA

    def test_real_replicas_present_and_aligned(self):
        s = _load()
        assert s.replicas is not None
        assert len(s.replicas) == s.n_cycles
        assert max(s.replicas) >= 20  # the planted runaway climbs past M

    def test_metrics_are_canonical_and_normalized(self):
        s = _load()
        ms = s.to_metrics_series()
        assert _METRIC_KEYS.issubset(set(ms[0].keys()))
        for m in ms:
            for k in _METRIC_KEYS:
                assert 0.0 <= m[k] <= 1.0

    def test_cycle_seconds_inferred_from_timestamps(self):
        assert _load().cycle_seconds == 60.0

    def test_incidents_parsed_to_cycle_indices(self):
        s = _load()
        inc = s.meta["incidents"]
        assert s.meta["incidents_provided"] is True
        assert len(inc) == 1
        assert 0 <= inc[0].start_cycle < inc[0].end_cycle < s.n_cycles

    def test_normalization_assumptions_recorded(self):
        meta = _load().meta["normalization"]
        assert meta["latency_slo_seconds"] == 1.0
        assert "queue_capacity" in meta

    def test_latency_ms_column_detected(self, tmp_path):
        p = tmp_path / "ms.csv"
        p.write_text(
            "timestamp,cpu,latency_p99_ms,current_replicas\n"
            "0,0.5,500,5\n1,0.5,500,5\n2,0.5,500,5\n"
        )
        s = PartnerPrometheusAdapter().load(str(p), latency_slo_seconds=1.0)
        # 500 ms / 1000 = 0.5 s → normalized 0.5
        assert abs(s.to_metrics_series()[0]["latency_p99"] - 0.5) < 1e-9

    def test_percent_cpu_detected(self, tmp_path):
        p = tmp_path / "pct.csv"
        p.write_text("timestamp,cpu,current_replicas\n0,85,5\n1,90,5\n2,80,5\n")
        s = PartnerPrometheusAdapter().load(str(p))
        assert all(0.0 <= m["cpu"] <= 1.0 for m in s.to_metrics_series())
        assert abs(s.to_metrics_series()[0]["cpu"] - 0.85) < 1e-9

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("timestamp,cpu,current_replicas\n")
        with pytest.raises(ValueError):
            PartnerPrometheusAdapter().load(str(p))


# ----------------------------- detection (spec §5a) -----------------------------

class TestTierADetection:
    def test_one_tier_a_candidate_on_overlapping_incident(self):
        res = detect_tier_a(_load())
        assert res.n_tier_a == 1
        ep = res.tier_a_candidates[0]
        assert ep.classification == TIER_A_CANDIDATE
        assert ep.overlaps_incident and ep.incident_ids == ["INC-101"]

    def test_episode_meets_K_and_M(self):
        ep = detect_tier_a(_load()).tier_a_candidates[0]
        assert ep.length >= DEFAULT_TIER_A_SPEC.k_consecutive_not_helping
        assert ep.min_replicas >= DEFAULT_TIER_A_SPEC.m_replicas

    def test_capacity_bound_stretch_yields_no_tier_a(self):
        # The HELPING/capacity-bound region is the early, low-replica part of the
        # trace; the only futile episode must be the planted runaway (later cycles).
        res = detect_tier_a(_load())
        assert res.cycles_helping > 0
        assert all(ep.start_cycle >= 20 for ep in res.tier_a_candidates)

    def test_deterministic(self):
        a = detect_tier_a(_load())
        b = detect_tier_a(_load())
        assert a.n_tier_a == b.n_tier_a
        assert [e.to_dict() for e in a.tier_a_candidates] == [e.to_dict() for e in b.tier_a_candidates]


class TestClassificationBranches:
    def test_no_incident_timeline_is_pending(self):
        res = detect_tier_a(_load(incidents=False))
        assert res.n_tier_a == 1
        assert res.tier_a_candidates[0].classification == TIER_A_PENDING_INCIDENT

    def test_non_overlapping_incident_is_tier_b(self, tmp_path):
        far = tmp_path / "far.csv"
        far.write_text("incident_id,start,end,severity\nINC-FAR,0,120,SEV3\n")
        s = PartnerPrometheusAdapter().load(METRICS, incidents_path=str(far), cluster="c")
        res = detect_tier_a(s)
        assert res.n_tier_a == 0
        assert res.n_tier_b >= 1

    def test_M_gate_blocks_tier_a(self):
        # Raise M above the trace's peak replicas → no qualifying futile span.
        spec = TierASpec(m_replicas=100)
        assert detect_tier_a(_load(), spec).n_tier_a == 0

    def test_K_gate_blocks_tier_a(self):
        # Require an impossibly long streak → no qualifying futile span.
        spec = TierASpec(k_consecutive_not_helping=10_000)
        assert detect_tier_a(_load(), spec).n_tier_a == 0


# ----------------------------- cost model (spec §4) -----------------------------

class TestCostModel:
    def test_excess_replica_hours_positive(self):
        ep = detect_tier_a(_load()).tier_a_candidates[0]
        assert ep.excess_replica_hours > 0

    def test_cost_none_without_partner_inputs(self):
        ep = detect_tier_a(_load()).tier_a_candidates[0]
        assert ep.excess_compute_cost_usd is None
        assert ep.episode_cost_usd is None  # never zero-claimed

    def test_cost_computed_with_partner_inputs(self):
        ep = detect_tier_a(
            _load(), dollars_per_replica_hour=0.10, dollars_per_incident_minute=5.0,
        ).tier_a_candidates[0]
        assert ep.excess_compute_cost_usd is not None
        assert ep.incident_cost_usd is not None
        assert ep.episode_cost_usd == pytest.approx(
            ep.excess_compute_cost_usd + ep.incident_cost_usd
        )


# ----------------------------- APCY gate (spec §5c) -----------------------------

def _synth_cluster(org, months, n_episodes, cost, cycle_seconds=60.0):
    n_cycles = int(months * SECONDS_PER_MONTH / cycle_seconds)
    eps = [
        TierAEpisode(
            episode_id=f"{org}-ep{i}", classification=TIER_A_CANDIDATE,
            start_cycle=0, end_cycle=10, length=11,
            floor_replicas=20, min_replicas=20, peak_replicas=30,
            mean_confidence=0.7, overlaps_incident=True, incident_ids=["x"],
            episode_cost_usd=cost,
        )
        for i in range(n_episodes)
    ]
    return ClusterTierAResult(
        cluster=f"{org}-c", org=org, n_cycles=n_cycles, cycle_seconds=cycle_seconds,
        data_status="pending_data", tier_a_candidates=eps,
    )


class TestAPCYGate:
    def test_fixture_single_cluster_not_reportable(self):
        res = detect_tier_a(_load(), dollars_per_replica_hour=0.1, dollars_per_incident_minute=5.0)
        apcy = compute_apcy([res])
        assert apcy.reportable is False  # the trip-wire refuses a fixture as evidence
        assert "cluster-months" in apcy.reason or "orgs" in apcy.reason

    def test_market_red_when_coverage_met_but_too_few_tier_a(self):
        # 6 orgs, ≥150 cluster-months total, but only 3 Tier-A across the fleet.
        clusters = [_synth_cluster(f"org{i}", months=30, n_episodes=0, cost=1000) for i in range(6)]
        for c in clusters[:3]:
            c.tier_a_candidates.append(_synth_cluster("x", 1, 1, 1000).tier_a_candidates[0])
        apcy = compute_apcy(clusters)
        assert apcy.total_tier_a_candidates == 3
        assert apcy.market_red is True
        assert apcy.reportable is False

    def test_reportable_when_floor_met(self):
        clusters = [_synth_cluster(f"org{i}", months=30, n_episodes=1, cost=1500) for i in range(6)]
        apcy = compute_apcy(clusters)
        assert apcy.n_orgs == 6
        assert apcy.total_cluster_months >= 150
        assert apcy.total_tier_a_candidates >= 5
        assert apcy.reportable is True
        assert apcy.market_red is False
        assert apcy.apcy_usd_per_cluster_year is not None and apcy.apcy_usd_per_cluster_year > 0
        assert apcy.median_episode_cost_usd == 1500


# ----------------------------- worksheet -----------------------------

class TestWorksheet:
    def test_worksheet_contains_key_fields(self):
        res = detect_tier_a(_load(), dollars_per_replica_hour=0.1, dollars_per_incident_minute=5.0)
        md = emit_worksheet(res, res.tier_a_candidates[0])
        assert "SRE Adjudication" in md
        assert "INC-101" in md
        assert "Tier-A" in md or "tier_a" in md
        assert "STOP-AND-REVIEW" in md  # the harmful-FP check is present

    def test_emit_worksheets_handles_no_candidates(self):
        c = ClusterTierAResult(cluster="empty", org="o", n_cycles=10, cycle_seconds=60.0,
                               data_status="pending_data")
        out = emit_worksheets(c)
        assert "No Tier-A candidates" in out


# ----------------------------- spec consistency -----------------------------

class TestSpecConsistency:
    def test_default_spec_matches_guard_envelope(self):
        # The pre-registered detector reuses the SHIPPED guard's envelope, not a new
        # knob (spec §2). The EfficiencyObserver default-constructs that guard with
        # futility_window=5, high_replica_threshold=20.
        from cloud_controller.replay.efficiency_observer import EfficiencyObserver
        obs = EfficiencyObserver()
        assert DEFAULT_TIER_A_SPEC.k_consecutive_not_helping == obs.guard.futility_window
        assert DEFAULT_TIER_A_SPEC.m_replicas == obs.guard.high_replica_threshold

    def test_label_is_estimate_pending_adjudication(self):
        assert "real-trace-replay" in detect_tier_a(_load()).label
        assert "pending live adjudication" in detect_tier_a(_load()).label


# ----------------------------- TraceSeries back-compat -----------------------------

class TestTraceSeriesReplicasField:
    def test_replicas_defaults_none_and_clamps(self):
        from cloud_controller.replay.adapters.base import TraceSeries
        s = TraceSeries("t", "x", "y", AdapterStatus.EXECUTED, 15.0, [0.5])
        assert s.replicas is None  # additive field, backward-compatible
        s2 = TraceSeries("t", "x", "y", AdapterStatus.EXECUTED, 15.0, [0.5], replicas=[-3.0, 7.0])
        assert s2.replicas == [0.0, 7.0]

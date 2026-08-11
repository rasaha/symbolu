"""CapacityDecisionEvidence integrity tests (section 19.4)."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller import CloudScalingController
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, CapacityState, InfrastructureState,
    Measurement, NormalizationMethod, NormalizationPolicy, ObservationProvenance,
    ObservationSourceType, PerformanceState, ReliabilityState, Unit, WorkloadState,
    project_to_scaling_observation, recommend_with_evidence,
)
from ugence_cloud_scaling_controller.canonical.evidence import (
    EvidenceError, build_capacity_decision_evidence,
)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _policy():
    return NormalizationPolicy(
        policy_id="ev",
        method_by_signal={
            "cpu": NormalizationMethod.PERCENT_TO_RATIO,
            "memory": NormalizationMethod.PERCENT_TO_RATIO,
            "latency_p99": NormalizationMethod.LATENCY_MS_TO_THRESHOLD,
            "error_rate": NormalizationMethod.RATIO_PASSTHROUGH,
            "queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY,
        },
        thresholds={"latency_p99": 1000.0, "queue_depth": 100.0},
    )


def _state(cpu=92.0):
    return CanonicalCapacityState(
        subject=CapacitySubject(workload_id="checkout", tenant_id="acme"),
        observed_at=NOW, correlation_id="corr-1",
        infrastructure=InfrastructureState(cpu_utilization=Measurement(cpu, Unit.PERCENT),
                                           memory_utilization=Measurement(88.0, Unit.PERCENT),
                                           gpu_utilization=Measurement(10.0, Unit.PERCENT)),
        performance=PerformanceState(latency_p99=Measurement(810.0, Unit.MILLISECONDS)),
        reliability=ReliabilityState(error_rate=Measurement(0.2, Unit.RATE), restart_count=1),
        workload=WorkloadState(queue_depth=Measurement(70, Unit.COUNT)),
        capacity=CapacityState(running_replicas=4),
        provenance=ObservationProvenance(ObservationSourceType.PROMETHEUS, NOW, provider="self-hosted"),
    )


def test_evidence_immutable_versioned_digested():
    _, ev = recommend_with_evidence(_state(), _policy())
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.recommendation = "x"  # type: ignore[misc]
    assert ev.evidence_schema_version == "capacity-evidence-1"
    assert ev.digest().startswith("sha256:")


def test_canonical_serialization_stable():
    _, ev = recommend_with_evidence(_state(), _policy())
    assert ev.to_canonical_dict() == ev.to_canonical_dict()
    json.loads(ev.to_json())  # valid JSON


def test_binds_to_real_projection_and_recommendation():
    rec, ev = recommend_with_evidence(_state(), _policy())
    assert ev.recommendation == rec.recommendation
    assert ev.replica_delta == rec.replica_delta
    assert ev.recommended_replicas == rec.recommended_replicas
    assert ev.signals_delivered_to_controller == dict(rec.metrics_snapshot)


def test_records_controller_and_config_identity():
    _, ev = recommend_with_evidence(_state(), _policy())
    assert ev.controller_package_version
    assert ev.controller_config_digest.startswith("sha256:")
    assert ev.controller_recommendation_schema_version == "1.1"
    assert ev.controller_observation_schema_version == "1.0"


def test_records_policy_and_state_identity():
    _, ev = recommend_with_evidence(_state(), _policy())
    assert ev.normalization_policy_id == "ev"
    assert ev.normalization_policy_digest.startswith("sha256:")
    assert ev.canonical_state_digest == _state().digest()


def test_records_exact_signals_and_ignored_and_missing():
    _, ev = recommend_with_evidence(_state(), _policy())
    assert set(ev.signals_delivered_to_controller) == {
        "cpu", "memory", "latency_p99", "error_rate", "queue_depth"}
    assert "infrastructure.gpu_utilization" in ev.ignored_canonical_fields
    assert ev.missing_controller_signals == ()


def test_missing_signal_and_ignored_recorded():
    s = CanonicalCapacityState(
        subject=CapacitySubject(workload_id="w"), observed_at=NOW,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
        workload=WorkloadState(request_rate=Measurement(10.0, Unit.PER_SECOND)),
        capacity=CapacityState(running_replicas=3))
    _, ev = recommend_with_evidence(s, _policy())
    assert "memory" in ev.missing_controller_signals
    assert "workload.request_rate" in ev.ignored_canonical_fields
    assert "workload.request_rate" not in ev.signals_delivered_to_controller


def test_preserves_observation_time_and_distinguishes_production_time():
    produced = datetime(2026, 8, 11, 12, 30, tzinfo=timezone.utc)
    _, ev = recommend_with_evidence(_state(), _policy(), evidence_produced_at=produced)
    assert ev.observed_at == NOW
    assert ev.evidence_produced_at == produced
    assert ev.observed_at != ev.evidence_produced_at


def test_preserves_subject_and_scope_and_provenance():
    _, ev = recommend_with_evidence(_state(), _policy())
    assert ev.subject.workload_id == "checkout" and ev.subject.tenant_id == "acme"
    assert ev.provenance.source_type is ObservationSourceType.PROMETHEUS


def test_always_advisory_only_no_actuation():
    _, ev = recommend_with_evidence(_state(), _policy())
    assert ev.advisory_only is True and ev.actuation_performed is False
    assert ev.authority_class == "ADVISORY" and ev.execution_capability == "NONE"
    d = ev.to_canonical_dict()
    assert d["advisory_only"] is True and d["actuation_performed"] is False


def test_no_risk_or_authorization_fields_present():
    _, ev = recommend_with_evidence(_state(), _policy())
    keys = set(ev.to_canonical_dict())
    for forbidden in ("risk_verdict", "verdict", "authorization", "authorized",
                      "controls_satisfied", "approval", "approved", "enforceable", "signature"):
        assert forbidden not in keys


def test_ignored_fields_not_in_delivered_signals():
    _, ev = recommend_with_evidence(_state(), _policy())
    for path in ev.ignored_canonical_fields:
        leaf = path.split(".")[-1]
        assert leaf not in ev.signals_delivered_to_controller


def test_digest_changes_when_decision_field_changes():
    _, ev_hi = recommend_with_evidence(_state(cpu=92.0), _policy())
    _, ev_lo = recommend_with_evidence(_state(cpu=20.0), _policy())
    assert ev_hi.digest() != ev_lo.digest()


def test_digest_excludes_production_time():
    _, a = recommend_with_evidence(_state(), _policy(), evidence_produced_at=NOW)
    _, b = recommend_with_evidence(_state(), _policy(),
                                   evidence_produced_at=datetime(2031, 1, 1, tzinfo=timezone.utc))
    assert a.digest() == b.digest()


def test_digest_deterministic_across_fresh_controllers():
    _, a = recommend_with_evidence(_state(), _policy())
    _, b = recommend_with_evidence(_state(), _policy())
    assert a.digest() == b.digest()


def test_cannot_forge_by_supplying_a_different_recommendation():
    # The builder requires the REAL ScalingRecommendation object; a hand-built recommendation
    # with a forged non-actuation flag is rejected, and there is no path that accepts a bare
    # recommendation string in place of the controller's output.
    ctrl = CloudScalingController()
    proj = project_to_scaling_observation(_state(), _policy())
    real = ctrl.recommend(proj.observation)
    forged = dataclasses.replace(real, actuation_performed=True)
    with pytest.raises(EvidenceError):
        build_capacity_decision_evidence(_state(), _policy(), proj, forged, ctrl.config,
                                         evidence_produced_at=NOW)
    with pytest.raises(EvidenceError):
        build_capacity_decision_evidence(_state(), _policy(), proj, "scale_out_5",  # type: ignore[arg-type]
                                         ctrl.config, evidence_produced_at=NOW)

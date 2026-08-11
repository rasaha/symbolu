"""Projection tests (section 19.3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, CapacityState, DeploymentState,
    InfrastructureState, Measurement, NormalizationMethod, NormalizationPolicy,
    PerformanceState, ReliabilityState, Unit, WorkloadState, project_to_scaling_observation,
)
from ugence_cloud_scaling_controller.canonical.projection import ProjectionError

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _policy(allow_p95=False):
    return NormalizationPolicy(
        policy_id="proj",
        method_by_signal={
            "cpu": NormalizationMethod.PERCENT_TO_RATIO,
            "memory": NormalizationMethod.PERCENT_TO_RATIO,
            "latency_p99": NormalizationMethod.LATENCY_MS_TO_THRESHOLD,
            "error_rate": NormalizationMethod.RATIO_PASSTHROUGH,
            "queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY,
        },
        thresholds={"latency_p99": 1000.0, "queue_depth": 100.0},
        allow_latency_p95_substitution=allow_p95,
    )


def _full_state(**over):
    kw = dict(
        subject=CapacitySubject(workload_id="w"), observed_at=NOW, correlation_id="corr",
        time_phase="peak",
        infrastructure=InfrastructureState(cpu_utilization=Measurement(92.0, Unit.PERCENT),
                                           memory_utilization=Measurement(88.0, Unit.PERCENT)),
        performance=PerformanceState(latency_p99=Measurement(810.0, Unit.MILLISECONDS)),
        reliability=ReliabilityState(error_rate=Measurement(0.2, Unit.RATE), restart_count=2),
        workload=WorkloadState(queue_depth=Measurement(70, Unit.COUNT)),
        capacity=CapacityState(running_replicas=4, ready_replicas=3, healthy_replicas=2, desired_replicas=5),
        deployment=DeploymentState(deploy_active=True),
    )
    kw.update(over)
    return CanonicalCapacityState(**kw)


def test_full_five_signal_mapping():
    proj = project_to_scaling_observation(_full_state(), _policy())
    assert proj.projected_signals == {
        "cpu": 0.92, "memory": 0.88, "latency_p99": 0.81, "error_rate": 0.2, "queue_depth": 0.7,
    }
    obs = proj.observation
    assert obs.current_replicas == 4          # running, not ready/healthy/desired
    assert obs.deploy_active is True
    assert obs.recent_pod_restarts == 2
    assert obs.phase == "peak"
    assert obs.correlation_id == "corr"
    assert obs.timestamp == NOW.timestamp()
    assert not proj.missing_controller_signals


def test_current_replicas_uses_running_not_healthy():
    proj = project_to_scaling_observation(_full_state(), _policy())
    assert proj.observation.current_replicas == 4
    assert "capacity.running_replicas" in proj.used_canonical_fields


def test_missing_running_replicas_fails_closed():
    s = _full_state(capacity=CapacityState(ready_replicas=3, healthy_replicas=3, desired_replicas=3))
    with pytest.raises(ProjectionError):
        project_to_scaling_observation(s, _policy())


def test_missing_optional_signals_reported():
    s = CanonicalCapacityState(
        subject=CapacitySubject(workload_id="w"), observed_at=NOW,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=3))
    proj = project_to_scaling_observation(s, _policy())
    assert set(proj.missing_controller_signals) == {"memory", "latency_p99", "error_rate", "queue_depth"}
    assert proj.observation.phase == "normal"  # default when time_phase absent


def test_p95_not_silently_substituted_for_p99():
    s = _full_state(performance=PerformanceState(latency_p95=Measurement(700.0, Unit.MILLISECONDS)))
    proj = project_to_scaling_observation(s, _policy(allow_p95=False))
    assert "latency_p99" in proj.missing_controller_signals
    assert "latency_p99" not in proj.projected_signals


def test_p95_substitution_only_with_opt_in_and_disclosed():
    s = _full_state(performance=PerformanceState(latency_p95=Measurement(700.0, Unit.MILLISECONDS)))
    proj = project_to_scaling_observation(s, _policy(allow_p95=True))
    assert proj.projected_signals["latency_p99"] == pytest.approx(0.7)
    assert any("latency_p95" in w for w in proj.warnings)
    assert "performance.latency_p95" in proj.used_canonical_fields


def test_ignored_canonical_signals_do_not_enter_decision():
    s = _full_state(
        infrastructure=InfrastructureState(cpu_utilization=Measurement(92.0, Unit.PERCENT),
                                           memory_utilization=Measurement(88.0, Unit.PERCENT),
                                           gpu_utilization=Measurement(99.0, Unit.PERCENT)))
    proj = project_to_scaling_observation(s, _policy())
    assert "infrastructure.gpu_utilization" in proj.ignored_canonical_fields
    assert "gpu" not in proj.projected_signals
    assert "gpu_utilization" not in proj.observation.metrics


def test_provider_provenance_does_not_alter_projection():
    from ugence_cloud_scaling_controller.canonical import ObservationProvenance, ObservationSourceType
    base = _full_state()
    withaws = _full_state(provenance=ObservationProvenance(
        ObservationSourceType.CLOUDWATCH, NOW, provider="aws"))
    a = project_to_scaling_observation(base, _policy())
    b = project_to_scaling_observation(withaws, _policy())
    assert a.projected_signals == b.projected_signals
    assert a.observation.metrics == b.observation.metrics


def test_identical_inputs_identical_projection():
    a = project_to_scaling_observation(_full_state(), _policy())
    b = project_to_scaling_observation(_full_state(), _policy())
    assert a.projected_signals == b.projected_signals
    assert a.used_canonical_fields == b.used_canonical_fields
    assert a.ignored_canonical_fields == b.ignored_canonical_fields

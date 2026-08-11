"""Read-only observation sources + provider-neutrality/side-effect tests (section 19.6)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, CapacityState, InfrastructureState,
    Measurement, NormalizationMethod, NormalizationPolicy, Unit,
    CapacityObservationSource, FixtureObservationSource, ReplayObservationSource,
    recommend_with_evidence,
)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _state(cpu=50.0, replicas=3):
    return CanonicalCapacityState(
        subject=CapacitySubject(workload_id="w"), observed_at=NOW,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(cpu, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=replicas))


def _policy():
    return NormalizationPolicy(policy_id="p",
                               method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})


def test_fixture_source_is_read_only_protocol():
    src = FixtureObservationSource(_state())
    assert isinstance(src, CapacityObservationSource)
    assert src.observe().subject.workload_id == "w"
    # No write/mutation method is exposed.
    assert not any(hasattr(src, m) for m in ("apply", "set_replicas", "scale", "mutate", "write"))


def test_replay_source_preserves_order_and_timestamps():
    s1 = _state(cpu=10.0)
    s2 = CanonicalCapacityState(
        subject=CapacitySubject(workload_id="w"),
        observed_at=datetime(2026, 8, 11, 12, 5, tzinfo=timezone.utc),
        infrastructure=InfrastructureState(cpu_utilization=Measurement(90.0, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=3))
    src = ReplayObservationSource([s1, s2])
    assert len(src) == 2
    a = src.observe(); b = src.observe()
    assert a.observed_at == NOW
    assert b.observed_at == datetime(2026, 8, 11, 12, 5, tzinfo=timezone.utc)
    with pytest.raises(StopIteration):
        src.observe()


def test_source_end_to_end_advisory():
    src = FixtureObservationSource(_state(cpu=95.0))
    rec, ev = recommend_with_evidence(src.observe(), _policy())
    assert rec.advisory_only is True and rec.actuation_performed is False
    assert ev.advisory_only is True


def test_no_socket_opened_during_pipeline(monkeypatch):
    monkeypatch.setattr(socket, "socket",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no socket")))
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    for _ in range(10):
        recommend_with_evidence(_state(), _policy())


def test_no_subprocess_spawned(monkeypatch):
    boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("no subprocess"))
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    recommend_with_evidence(_state(), _policy())


def test_no_credentials_required(monkeypatch):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CLIENT_SECRET", "KUBECONFIG"):
        monkeypatch.setenv(var, "POISONED_SHOULD_NOT_BE_USED")
    rec, ev = recommend_with_evidence(_state(), _policy())
    assert ev.actuation_performed is False


def test_import_surface_adds_no_cloud_sdk():
    # Importing the canonical layer in a clean interpreter must not pull a cloud SDK.
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    forbidden = ["boto3", "botocore", "azure", "google.cloud", "kubernetes",
                 "requests", "prometheus_client", "opentelemetry", "fastapi", "uvicorn"]
    prog = (
        "import sys\n"
        f"sys.path.insert(0, {src!r})\n"
        "import ugence_cloud_scaling_controller.canonical as c\n"
        f"forbidden = {forbidden!r}\n"
        "print(';'.join(m for m in forbidden if m in sys.modules))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", prog], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    leaked = [m for m in out.stdout.strip().split(";") if m]
    assert not leaked, f"canonical import leaked cloud modules: {leaked}"


def test_no_provider_branch_in_decision_projection():
    # Two identical states differing ONLY by provider label project identically —
    # provider semantics terminate at provenance and never enter the projection.
    from ugence_cloud_scaling_controller.canonical import (
        ObservationProvenance, ObservationSourceType, project_to_scaling_observation)
    base = _state()
    aws = CanonicalCapacityState(
        subject=CapacitySubject(workload_id="w"), observed_at=NOW,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=3),
        provenance=ObservationProvenance(ObservationSourceType.CLOUDWATCH, NOW, provider="aws"))
    gcp = CanonicalCapacityState(
        subject=CapacitySubject(workload_id="w"), observed_at=NOW,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=3),
        provenance=ObservationProvenance(ObservationSourceType.GCP_MONITORING, NOW, provider="gcp"))
    p = _policy()
    r0 = project_to_scaling_observation(base, p).projected_signals
    r1 = project_to_scaling_observation(aws, p).projected_signals
    r2 = project_to_scaling_observation(gcp, p).projected_signals
    assert r0 == r1 == r2

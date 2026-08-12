"""Phase-2 boundary guarantees: shadow-only, advisory-only, provider-neutral, no side effects.

FORECAST != RECOMMENDATION != RISK EVALUATION != AUTHORITY != EXECUTION.
"""

from __future__ import annotations

import ast
import os
import pathlib
import sys

import pytest

import fc_helpers as fx
import ugence_cloud_scaling_controller as U
from ugence_cloud_scaling_controller.canonical import CapacitySubject
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    CapacityForecast,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyInterval,
    UncertaintyMethod,
    forecast_with_evidence,
)
from ugence_cloud_scaling_controller.forecasting.forecast import ForecastError
from ugence_cloud_scaling_controller.forecasting.evidence import ForecastServiceError

_FORECASTING_DIR = pathlib.Path(U.__file__).parent / "forecasting"

# Standard-library-only + this package's own canonical/version modules are permitted.
_FORBIDDEN_IMPORT_ROOTS = {
    "boto3", "botocore", "azure", "kubernetes", "google", "requests",
    "prometheus_client", "opentelemetry", "yaml", "socket", "subprocess",
    "urllib", "http", "ssl", "asyncio", "ftplib", "smtplib",
    "fastapi", "uvicorn", "flask", "numpy",
    "governance_studio", "decision_governance", "actiongate", "actiongate_provider",
    "agent_runtime", "hybrid_llm", "ai_hiring", "control_plane", "risk_authority",
    "execution_gate", "evidence_assurance", "assertion_gate_robustness",
}

_PROVIDER_BRANCH_TOKENS = [
    'provider ==', 'provider==', "== 'aws'", '== "aws"', "== 'gcp'", "== 'azure'",
    "K8sActuator", "patch_namespaced", "argocd", "boto3.client",
]


def _forecasting_files():
    return sorted(_FORECASTING_DIR.rglob("*.py"))


def test_forecasting_imports_are_stdlib_and_local_only():
    violations = []
    for p in _forecasting_files():
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            for r in roots:
                if r in _FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{p.name}: imports {r}")
    assert not violations, violations


def test_forecasting_has_no_provider_branching_or_mutation_tokens():
    hits = []
    for p in _forecasting_files():
        text = p.read_text()
        for tok in _PROVIDER_BRANCH_TOKENS:
            if tok in text:
                hits.append(f"{p.name}: {tok}")
    assert not hits, hits


def test_importing_forecasting_pulls_in_no_forbidden_modules():
    # Isolated interpreter: import ONLY the forecasting package and assert its import
    # closure contains no network/cloud/authority module. (A shared-process sys.modules
    # check would be polluted by other suites that legitimately import `requests`.)
    import subprocess

    src = str(pathlib.Path(U.__file__).parents[1])
    code = (
        "import sys; import ugence_cloud_scaling_controller.forecasting as F; "
        "bad=[m for m in ('boto3','botocore','kubernetes','requests','azure','google',"
        "'risk_authority','actiongate') if m in sys.modules]; "
        "print(','.join(bad))"
    )
    # A fresh subprocess starts with only stdlib imported, so its sys.modules reflects
    # exactly the forecasting import closure (no -I: that would also drop PYTHONPATH).
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env={"PYTHONPATH": src, "PATH": os.environ.get("PATH", "")},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "", f"forecasting import pulled in: {out.stdout.strip()}"


def test_forecast_enforces_shadow_and_advisory_invariants():
    ev = forecast_with_evidence(
        CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0, 30.0])),
        ForecastTarget.CPU_UTILIZATION, fx.at(120), ForecastHorizon.minutes(5),
        PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )
    fc = ev.forecast
    assert (fc.advisory_only, fc.shadow_only, fc.actuation_performed) == (True, True, False)
    assert (fc.authority_class, fc.execution_capability) == ("ADVISORY", "NONE")


def test_cannot_construct_actuating_forecast():
    common = dict(
        schema_version="capacity-forecast-1",
        subject=fx.subject(), correlation_id=None, target=ForecastTarget.CPU_UTILIZATION,
        forecast_cutoff=fx.at(0), horizon=ForecastHorizon.minutes(5), forecast_for=fx.at(300),
        model_id="persistence", model_version="1", status="forecast", unit="percent",
        input_window_digest="sha256:x", model_config_digest="sha256:y",
        uncertainty=UncertaintyInterval(method="none", requested_coverage=0.8,
                                        calibration_sample_count=0, available=False),
        point_estimate=1.0,
    )
    with pytest.raises(ForecastError):
        CapacityForecast(**{**common, "actuation_performed": True})
    with pytest.raises(ForecastError):
        CapacityForecast(**{**common, "shadow_only": False})
    with pytest.raises(ForecastError):
        CapacityForecast(**{**common, "authority_class": "AUTHORITATIVE"})


def test_forecasting_does_not_alter_live_controller_path():
    # The live observation -> recommendation path is byte-for-byte the Phase-1 behavior.
    from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation
    a = CloudScalingController().recommend(
        ScalingObservation(metrics={"cpu": 0.9, "memory": 0.8}, current_replicas=4, phase="peak")
    )
    b = CloudScalingController().recommend(
        ScalingObservation(metrics={"cpu": 0.9, "memory": 0.8}, current_replicas=4, phase="peak")
    )
    assert a.recommendation == b.recommendation
    assert a.advisory_only is True and a.actuation_performed is False
    # A forecast is not a recommendation: distinct types, distinct schema versions.
    assert CapacityForecast.__name__ != "ScalingRecommendation"


def test_evidence_rejects_non_forecast_payload():
    from ugence_cloud_scaling_controller.forecasting.evidence import CapacityForecastEvidence
    with pytest.raises(ForecastServiceError):
        CapacityForecastEvidence(
            evidence_schema_version="capacity-forecast-evidence-1",
            series_schema_version="capacity-series-1",
            input_window_schema_version="capacity-forecast-window-1",
            forecast_schema_version="capacity-forecast-1",
            controller_package_version="0.3.0",
            source_series_digest="sha256:a", input_window_digest="sha256:b",
            feature_config_digest="sha256:c", admission_policy_digest="sha256:d",
            uncertainty_config_digest="sha256:e", model_config_digest="sha256:f",
            normalization_policy_id=None, normalization_policy_digest=None,
            forecast="not-a-forecast", evidence_produced_at=fx.at(0),
        )

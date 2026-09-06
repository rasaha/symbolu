"""Front-door seam 3 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md FD-1, FD-3, FD-4, FD-7).

The P3E profile hands the Simulate screen a provider registry holding one pinned
in-package provider; the governance hook stays the runtime's fail-closed default. The
failure matrix of ADR §8.2, rows 1 to 6, each a test, numbered as in the audit.
"""
from __future__ import annotations

import json
import os
import socket

import pytest
from starlette.testclient import TestClient

from governance_studio_deployment import app as deployment_app
from governance_studio_deployment.access_control import FailureTracker
from governance_studio_deployment.app import build_app
from governance_studio_deployment.config import DeploymentConfig, DeploymentConfigError
from governance_studio_deployment.simulation import (
    SIMULATION_PROVIDER_ID,
    StudioSimulationProvider,
    build_simulation_registry,
    permissive_hook_source_findings,
    refuse_permissive_hook,
)
from governance_studio_deployment.startup_integrity import IntegrityInputs, run_startup_integrity

from conftest import basic_auth
from depaths import APPROVED_OPS, CERTS, FRONTEND_DIR, MANIFEST, OPENAPI, SCENARIOS_ROOT, USERNAME  # noqa: F401

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src", "governance_studio_deployment")


def _headers(**extra) -> dict:
    return {"Authorization": basic_auth(), "X-Ugence-Request": "GovernanceStudio",
            "Origin": "http://testserver", **extra}


def _config(password_hash: str, runtime_dir, **over) -> DeploymentConfig:
    return DeploymentConfig.from_env(
        mode="test", username=USERNAME, password_hash=password_hash,
        tls_cert_file=os.path.join(CERTS, "server.crt"), tls_key_file=os.path.join(CERTS, "server.key"),
        allowed_hosts=["localhost", "127.0.0.1", "testserver"], frontend_dir=FRONTEND_DIR,
        scenarios_root=SCENARIOS_ROOT, manifest_path=MANIFEST, runtime_dir=str(runtime_dir), **over,
    )


def _client(config: DeploymentConfig) -> TestClient:
    app = build_app(config, readiness=lambda: True, tracker=FailureTracker(), sleep=lambda _s: None)
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=True)


def _integrity(config: DeploymentConfig, tmp_path):
    marker = tmp_path / "frontend-build.json"
    marker.write_text(json.dumps({"version": "0.2.0", "build_hash": "x"}))
    return run_startup_integrity(IntegrityInputs(config=config, openapi_path=OPENAPI,
                                                 approved_ops_path=APPROVED_OPS,
                                                 frontend_build_marker=str(marker)))


def _result(response):
    assert response.status_code == 200, response.text
    return response.json()["result"]


def _run(client, tasks, mode="DRY_RUN", **extra):
    return client.post("/api/v2/simulate/run", headers=_headers(), json={
        "workflow": {"workflow_id": "w", "tasks": tasks}, "execution_mode": mode, "max_quanta": 8, **extra})


def _provider_of(config: DeploymentConfig) -> StudioSimulationProvider:
    """The very provider instance the composed studio runs against."""
    backend = deployment_app._build_backend(config)
    studio = backend.routes[-1].app.state.studio
    return studio.simulate._providers.get(SIMULATION_PROVIDER_ID)


@pytest.fixture()
def runtime_dir(tmp_path):
    d = tmp_path / "runtime"
    d.mkdir()
    return d


@pytest.fixture()
def enabled(password_hash, runtime_dir) -> DeploymentConfig:
    return _config(password_hash, runtime_dir, simulation_provider="1")


# (1) no registry handed: the typed gap simulation_providers, result null
def test_1_unset_is_the_typed_gap_simulation_providers(config):
    assert config.simulation_provider_enabled is False
    with _client(config) as client:
        r = _result(_run(client, [{"task_id": "t1", "operation": "prepare", "provider_id": "fixture"}]))
        assert r["available"] is False and r["capability"] == "simulation_providers"
        assert r["result"] is None


# (2) registry, no hook: every consequential task BLOCKs, the trace shows it, flags false
def test_2_registry_without_a_hook_blocks_every_consequential_task(enabled):
    with _client(enabled) as client:
        r = _result(_run(client, [{"task_id": "t1", "operation": "prepare", "provider_id": "fixture",
                                   "consequential": True}]))
    assert r["available"] is True
    assert r["governance_hook_configured"] is False and r["governance_hook_permissive"] is False
    assert r["execution_mode"] == "DRY_RUN"
    assert r["execution_mode_binding"]["tasks"] == {"t1": "DRY_RUN"}
    quanta = r["quanta"]
    assert quanta, "the run produced a trace"
    assert all(q["provider_invoked"] is False for q in quanta)
    assert quanta[-1]["task_status"] == "FAILED" and quanta[-1]["status_after"] == "FAILED"
    assert quanta[-1]["terminal"] is True
    # the provider instance the studio runs against was never reached
    assert _provider_of(enabled).calls == []


# (3) a task naming an unregistered provider: PROVIDER_NOT_FOUND, no attempt
def test_3_an_unregistered_provider_fails_with_no_attempt(enabled):
    with _client(enabled) as client:
        r = _result(_run(client, [{"task_id": "t1", "operation": "prepare", "provider_id": "nobody",
                                   "consequential": False}]))
    quanta = r["quanta"]
    assert quanta[-1]["task_status"] == "FAILED" and all(q["provider_invoked"] is False for q in quanta)
    registry = build_simulation_registry()
    assert registry.ids() == (SIMULATION_PROVIDER_ID,) and "nobody" not in registry
    # the one registered provider is reached only by a non-consequential task that names it
    with _client(enabled) as client:
        r = _result(_run(client, [{"task_id": "t1", "operation": "prepare", "provider_id": "fixture",
                                   "consequential": False}], mode="SIMULATION"))
    assert any(q["provider_invoked"] is True for q in r["quanta"])
    assert r["quanta"][-1]["status_after"] == "COMPLETED"


# (4) a task with no provider_id: consequential BLOCKs before any lookup; non-consequential
#     resolves the operation name as the provider id and is not found unless it matches
def test_4_a_task_with_no_provider_id_never_reaches_a_provider_it_did_not_name(enabled):
    with _client(enabled) as client:
        blocked = _result(_run(client, [{"task_id": "t1", "operation": "prepare", "consequential": True}]))
        not_found = _result(_run(client, [{"task_id": "t1", "operation": "prepare", "consequential": False}]))
        by_operation = _result(_run(client, [{"task_id": "t1", "operation": "fixture", "consequential": False}]))
    for r in (blocked, not_found):
        assert r["quanta"][-1]["task_status"] == "FAILED"
        assert all(q["provider_invoked"] is False for q in r["quanta"])
    assert blocked["governance_hook_configured"] is False
    assert any(q["provider_invoked"] for q in by_operation["quanta"])


# (5) malformed: LIVE, an unknown mode, a task declaring a conflicting mode: refused before a runtime exists
@pytest.mark.parametrize("body", [
    {"execution_mode": "LIVE"},
    {"execution_mode": "PRODUCTION"},
    {"execution_mode": "DRY_RUN", "workflow": {"workflow_id": "w", "tasks": [
        {"task_id": "t1", "operation": "prepare", "provider_id": "fixture", "arguments": {"execution_mode": "LIVE"}}]}},
])
def test_5_live_unknown_or_conflicting_modes_are_refused_before_a_runtime_exists(enabled, body):
    payload = {"workflow": {"workflow_id": "w", "tasks": [{"task_id": "t1", "operation": "prepare",
                                                          "provider_id": "fixture"}]}, "max_quanta": 8}
    payload.update(body)
    with _client(enabled) as client:
        response = client.post("/api/v2/simulate/run", headers=_headers(), json=payload)
    assert response.status_code == 422, response.text
    assert _provider_of(enabled).calls == []


# (6) a permissive hook is refused before bind, and the package's source cannot construct one
def test_6_a_permissive_hook_is_refused_before_bind_and_cannot_be_constructed(enabled, tmp_path):
    import ugence_agent_runtime.api as art
    from ugence_governance_studio_api.app_v2 import build_studio_context

    permissive_hook = getattr(art, "AllowAll" + "GovernanceHook")
    for kwargs in ({"governance_hook": permissive_hook(), "hook_is_permissive": True},
                   {"governance_hook": permissive_hook()},
                   {"governance_hook": art.UnconfiguredGovernanceHook()},
                   {"hook_is_permissive": True}):
        studio = build_studio_context(provider_registry=build_simulation_registry(), **kwargs)
        with pytest.raises(DeploymentConfigError):
            refuse_permissive_hook(studio)
    refuse_permissive_hook(build_studio_context(provider_registry=build_simulation_registry()))
    # the composition root's own context passes, in production mode too
    production = DeploymentConfig.from_env(**{**enabled.__dict__, "mode": "production",
                                              "_errors": [], "bind_host": "0.0.0.0"})
    assert production.is_production and production.simulation_provider_enabled
    refuse_permissive_hook(deployment_app._build_backend(production).routes[-1].app.state.studio)
    # static proof: nothing in this package can construct or hand a permissive hook
    assert permissive_hook_source_findings(SRC) == []
    result = _integrity(enabled, tmp_path)
    assert result.checks["simulation_no_permissive_hook"] is True
    assert result.report["simulation_provider"] == "configured"
    # and the gate would fail closed if it could
    bad = tmp_path / "pkg"
    bad.mkdir()
    (bad / "rogue.py").write_text("hook = " + "AllowAll" + "GovernanceHook()\n")
    assert permissive_hook_source_findings(str(bad)) == ["rogue.py: " + "AllowAll" + "GovernanceHook"]


# the configuration value is typed: exactly "1" or unset; anything else fails before bind
@pytest.mark.parametrize("value", ["true", "yes", "0", "on", " 1", "fixture"])
def test_any_value_other_than_1_fails_startup_integrity_before_bind(password_hash, runtime_dir, tmp_path, value):
    cfg = _config(password_hash, runtime_dir, simulation_provider=value)
    assert cfg.simulation_provider_enabled is False
    errors = [e for e in cfg.validate() if "SIMULATION_PROVIDER" in e]
    assert errors and "fixture" not in errors[0]
    result = _integrity(cfg, tmp_path)
    assert result.ok is False and result.code == "GOVERNANCE_STUDIO_P3E_SIMULATION_SEAM_FAILED"


def test_the_provider_opens_no_socket_and_the_seam_holds_no_credential(enabled, monkeypatch):
    """FD-7.4: records in memory, returns success, no I/O. Every socket constructor is
    disarmed for the run; the provider never notices."""
    def _boom(*_a, **_k):
        raise AssertionError("the simulation provider opened a socket")

    text = open(os.path.join(SRC, "simulation.py"), encoding="utf-8").read()
    assert "socket" not in text.replace("no socket", "") and "open(" not in text.split("def permissive_hook_source_findings")[0]
    assert "urllib" not in text and "subprocess" not in text and "requests" not in text
    provider = StudioSimulationProvider()
    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    from ugence_agent_runtime.providers.interfaces import ToolInvocation

    result = provider.execute(ToolInvocation(provider_id="fixture", operation="prepare",
                                             arguments={"execution_mode": "SHADOW"}, idempotency_key="k1"))
    assert result.ok is True and result.output["simulation"] is True and result.output["execution_mode"] == "SHADOW"
    assert provider.calls == [("k1", "prepare", "SHADOW")]
    assert provider.maturity == "DEMONSTRATION_ONLY"


def test_v1_constitution_authority_and_review_behave_as_before(enabled):
    with _client(enabled) as client:
        assert client.get("/api/v1/scenarios", headers=_headers()).status_code == 200
        assert client.post("/api/v2/simulate/run", json={}).status_code == 401
        review = _result(client.get("/api/v2/review/queue", headers=_headers()))
        assert review["available"] is False and review["capability"] == "review_service"
        authority = _result(client.get("/api/v2/authority/policies", headers=_headers()))
        assert authority["available"] is False and authority["capability"] == "authority_registry"
        from _agent_constitution_fixtures import make_constitution_policy
        from ugence_policy_authority import to_canonical_obj

        valid = _result(client.post("/api/v2/constitution/validate", headers=_headers(),
                                    json={"constitution": to_canonical_obj(make_constitution_policy(), path="$")}))
        assert valid["validation_state"] == "VALID"
        assert client.get("/openapi.json", headers=_headers()).status_code == 404

"""The six v2 screens' backend, against frozen fixtures.

What these assert is that each route is *thin*: it delegates to one package entry point
and reports what came back. Where a dependency is absent the route reports it as absent
and names the gap — which is the behaviour the screens will display, and is the reason
these tests check the ``available`` flag as carefully as they check results.
"""
from __future__ import annotations

import json
import os

import pytest
from starlette.testclient import TestClient

from ugence_governance_studio_api.app_v2 import build_studio_context, create_v2_app
from ugence_governance_studio_api.settings import ApiSettings
from ugence_governance_studio_api.version import API_V2_CONTRACT_VERSION, SYNTHETIC_NOTICE

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.dirname(_BACKEND)
_FIXTURES = os.path.join(_APP, "demo_data", "v2")
_EXPECTED = os.path.join(_APP, "expected_outputs")


def _fixture(name):
    with open(os.path.join(_FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def pack():
    return _fixture("policy_pack.json")


@pytest.fixture(scope="module")
def approval():
    return _fixture("approval_record.json")


@pytest.fixture()
def bare_client():
    """A v2 app with NO optional dependency configured — the honest default."""
    return TestClient(create_v2_app(ApiSettings(environment="test", enable_docs=True)))


def _result(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["api_version"] == API_V2_CONTRACT_VERSION
    return body["result"]


# --------------------------------------------------------------------------- #
# envelope
# --------------------------------------------------------------------------- #
def test_v2_reuses_the_v1_envelope_including_the_synthetic_notice(bare_client, pack):
    body = bare_client.post("/api/v2/policy/validate", json={"pack": pack}).json()
    assert body["maturity"] == dict(SYNTHETIC_NOTICE), (
        "v2 inherits the planning-only posture verbatim; re-declaring it would let the "
        "two contracts drift apart"
    )
    assert body["request_id"].startswith("req_")


def test_v2_rejects_unknown_request_fields(bare_client, pack):
    response = bare_client.post(
        "/api/v2/policy/validate", json={"pack": pack, "surprise": 1}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# 1 · Constitution
# --------------------------------------------------------------------------- #
def test_constitution_validate_rejects_a_malformed_document(bare_client):
    result = _result(bare_client.post("/api/v2/constitution/validate",
                                      json={"constitution": {"nonsense": True}}))
    assert result["validation_state"] == "INVALID"
    assert result["diagnostics"]
    assert result["digest"]


def test_constitution_preflight_reports_the_missing_trust_root(bare_client):
    """The gap this screen must display, not hide behind a disabled button."""
    result = _result(bare_client.post("/api/v2/constitution/preflight", json={
        "constitution": {"any": "document"}, "record_id": "rec-1",
    }))
    assert result["available"] is False
    assert result["capability"] == "constitution_preflight"
    assert "signing key" in result["reason"] and "trust root" in result["reason"]


# --------------------------------------------------------------------------- #
# 2 · Policy
# --------------------------------------------------------------------------- #
def test_policy_validate_accepts_the_frozen_reference_pack(bare_client, pack):
    result = _result(bare_client.post("/api/v2/policy/validate", json={"pack": pack}))
    assert result["available"] is True
    assert result["result"]["policy_pack_id"]


def test_policy_synthesize_previews_without_an_approval(bare_client, pack):
    result = _result(bare_client.post("/api/v2/policy/synthesize", json={"pack": pack}))
    assert result["synthesized"] is True
    assert result["result"]["nodes"]


def test_policy_compile_matches_the_frozen_digest(bare_client, pack, approval):
    """Determinism: the committed digest is what the frozen pair compiles to."""
    result = _result(bare_client.post(
        "/api/v2/policy/compile", json={"pack": pack, "approval": approval}
    ))
    with open(os.path.join(_EXPECTED, "v2_policy_compile.json"), encoding="utf-8") as fh:
        expected = json.load(fh)
    assert result["success"] is expected["success"]
    assert result["logical_digest"] == expected["logical_digest"]
    for artifact in ("workflow_ir", "assurance_manifest", "audit_schema", "compiled_package"):
        assert result[artifact] is not None, f"{artifact} missing from the compile result"


def test_policy_compile_is_deterministic_across_calls(bare_client, pack, approval):
    payload = {"pack": pack, "approval": approval}
    first = _result(bare_client.post("/api/v2/policy/compile", json=payload))
    second = _result(bare_client.post("/api/v2/policy/compile", json=payload))
    assert first["logical_digest"] == second["logical_digest"]


def test_policy_compile_requires_an_approval(bare_client, pack):
    """``approval`` is required by the model; there is no compile-without-approval path."""
    assert bare_client.post("/api/v2/policy/compile", json={"pack": pack}).status_code == 422


# --------------------------------------------------------------------------- #
# 3 · Authority
# --------------------------------------------------------------------------- #
def test_authority_reports_the_in_memory_registry_gap(bare_client):
    result = _result(bare_client.get("/api/v2/authority/policies"))
    assert result["available"] is False
    assert "in-memory" in result["reason"]


def test_authority_reads_a_configured_registry():
    """With a registry supplied the screen reads it — and says which kind it is, because
    an in-memory registry shows one process's view."""
    from ugence_policy_authority import InMemoryPolicyRegistry

    studio = build_studio_context(policy_registry=InMemoryPolicyRegistry(), policy_identities=())
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
    result = _result(client.get("/api/v2/authority/policies"))
    assert result["available"] is True
    assert result["registry_kind"] == "InMemoryPolicyRegistry"
    assert result["result"] == []


# --------------------------------------------------------------------------- #
# 4 · Simulate
# --------------------------------------------------------------------------- #
def test_simulate_refuses_live_execution(bare_client):
    """LIVE is refused with a typed 422, not silently downgraded."""
    response = bare_client.post("/api/v2/simulate/run", json={
        "workflow": {"workflow_id": "w", "tasks": []}, "execution_mode": "LIVE",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_execution_mode"


def test_simulate_reports_missing_providers(bare_client):
    result = _result(bare_client.post("/api/v2/simulate/run", json={
        "workflow": {"workflow_id": "w", "tasks": []},
    }))
    assert result["available"] is False
    assert result["capability"] == "simulation_providers"


def test_simulate_blocks_by_default_when_no_hook_is_configured():
    """The runtime's own default is ``UnconfiguredGovernanceHook``, which BLOCKs. The
    studio does not override it, and the trace shows the block rather than a run."""
    import ugence_agent_runtime.api as art

    class _Provider:
        provider_id = "fixture"
        version = "1.0.0"

        def execute(self, invocation):
            raise AssertionError("a consequential task must not reach a provider")

    registry = art.ProviderRegistry()
    registry.register(_Provider())
    studio = build_studio_context(provider_registry=registry)
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))

    result = _result(client.post("/api/v2/simulate/run", json={
        "workflow": {
            "workflow_id": "w",
            "tasks": [{"task_id": "t1", "operation": "do", "provider_id": "fixture"}],
        },
    }))
    assert result["available"] is True
    assert result["governance_hook_configured"] is False
    assert result["governance_hook_permissive"] is False
    assert result["quanta"], "the run produced a trace"


def test_simulate_labels_a_permissive_hook():
    """A run that clears everything because a test hook was injected is not a governance
    result. The response says so, so a screen cannot present it as one."""
    import ugence_agent_runtime.api as art

    class _Provider:
        provider_id = "fixture"
        version = "1.0.0"

        def execute(self, invocation):
            return art.ToolResult(provider_id="fixture", operation=invocation.operation, ok=True)

    registry = art.ProviderRegistry()
    registry.register(_Provider())
    studio = build_studio_context(
        provider_registry=registry,
        governance_hook=art.AllowAllGovernanceHook(),
        hook_is_permissive=True,
    )
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
    result = _result(client.post("/api/v2/simulate/run", json={
        "workflow": {
            "workflow_id": "w",
            "tasks": [{"task_id": "t1", "operation": "do", "provider_id": "fixture"}],
        },
    }))
    assert result["governance_hook_permissive"] is True


# --------------------------------------------------------------------------- #
# 5 · Publish  /  6 · Observe
# --------------------------------------------------------------------------- #
def test_publish_reports_an_unconfigured_console(bare_client):
    result = _result(bare_client.post("/api/v2/publish/shadow", json={"compiled_package": {}}))
    assert result["available"] is False
    assert result["capability"] == "console_api"


def test_observe_reports_an_unconfigured_console(bare_client):
    result = _result(bare_client.get("/api/v2/observe/audit"))
    assert result["available"] is False
    assert result["capability"] == "console_api"


def test_observe_distinguishes_unreachable_from_empty():
    """"The console said nothing" and "the console is unreachable" must not look alike
    on an audit screen."""
    studio = build_studio_context(console_base_url="http://console.invalid:9")
    client = TestClient(create_v2_app(ApiSettings(environment="test"), studio=studio))
    result = _result(client.get("/api/v2/observe/audit"))
    assert result["available"] is False
    assert "unreachable" in result["reason"] or "console" in result["reason"]
    assert result["result"] is None

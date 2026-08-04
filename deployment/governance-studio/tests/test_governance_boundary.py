"""Governance boundaries hold under the packaged deployment (P3E §25, G8-G10)."""
import base64

from depaths import USERNAME, PASSWORD

AUTH = "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
HDR = {"Authorization": AUTH, "X-Ugence-Request": "GovernanceStudio", "Origin": "http://testserver"}

BANNED_ACTION_WORDS = [
    "permission granted", "grant permission", "access granted", "credentials issued",
    "provisioned", "runtime provisioning", "authorized to execute", "action executed",
    "agent executed", "agent execution started",
]


def test_permission_proposals_are_advisory_not_granted(client):
    r = client.get("/api/v1/scenarios/procurement/plan", headers={"Authorization": AUTH})
    assert r.status_code == 200
    body = r.text.lower()
    for phrase in BANNED_ACTION_WORDS:
        assert phrase not in body, f"plan response contains {phrase!r}"


def test_what_if_is_a_temporary_copy(client):
    # two different perturbations return the SAME baseline plan fingerprint => the
    # frozen scenario is never mutated by what-if.
    a = client.post("/api/v1/scenarios/procurement/what-if", headers={**HDR, "Content-Type": "application/json"},
                    json={"operation": "TIGHTEN_COST_CEILING", "params": {"ceiling": 1.0}})
    b = client.post("/api/v1/scenarios/procurement/what-if", headers={**HDR, "Content-Type": "application/json"},
                    json={"operation": "FORBID_PROVIDER", "params": {"provider": "openai"}})
    assert a.status_code == 200 and b.status_code == 200
    fa = a.json()["result"]["baseline_plan"]["plan_fingerprint"]
    fb = b.json()["result"]["baseline_plan"]["plan_fingerprint"]
    assert fa == fb


def test_replay_does_not_execute_agents(client):
    r = client.post("/api/v1/plans/replay", headers={**HDR, "Content-Type": "application/json"},
                    json={"scenario_id": "procurement"})
    assert r.status_code == 200
    body = r.text.lower()
    assert "agent executed" not in body and "execution started" not in body


def test_no_business_action_or_execution_endpoints(client):
    # deployment exposes no action/execution/authorization endpoints
    for path in ("/api/v1/actions/execute", "/api/v1/agents/run", "/api/v1/authorize", "/api/v1/execute"):
        r = client.get(path, headers={"Authorization": AUTH})
        assert r.status_code in (403, 404, 405)


def test_internal_operations_are_not_reachable_as_get(client):
    # the six internal operations are POST-only lower-level primitives; the frontend
    # never wires them, and none is exposed as an unauthenticated/GET convenience.
    for path in ("/api/v1/composition/compose", "/api/v1/eligibility/evaluate", "/api/v1/workflows/validate"):
        r = client.get(path, headers={"Authorization": AUTH})
        assert r.status_code in (403, 404, 405)


def test_scenario_export_is_deterministic(client):
    a = client.get("/api/v1/scenarios/procurement/export", headers={"Authorization": AUTH})
    b = client.get("/api/v1/scenarios/procurement/export", headers={"Authorization": AUTH})
    assert a.status_code == 200
    # the export payload is deterministic; only the envelope's per-request id differs
    assert a.json()["result"] == b.json()["result"]

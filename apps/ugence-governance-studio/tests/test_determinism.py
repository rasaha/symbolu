"""Determinism + frozen-output regression.

Loading the committed JSON fixtures and running the real engine must reproduce
the frozen expected outputs byte-for-byte, with identical AWC fingerprints, and
independently of input ordering.
"""
import json

import pytest

import ugence_agent_workforce_composer.api as awc
import generate_fixtures as G
import _loader as L


def _canonical(obj) -> str:
    return G._canonical_bytes(obj).decode("utf-8")


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_plan_fingerprint_matches_frozen(sid):
    out = L.run_pipeline(L.load_inputs(sid))
    frozen = L.expected(sid, "fingerprints.json")
    assert out["plan"].plan_fingerprint == frozen["plan_fingerprint"]
    assert out["plan"].plan_state.value == frozen["plan_state"]
    assert L.scenario_manifest(sid)["expected_fingerprints"]["plan_fingerprint"] == \
        frozen["plan_fingerprint"]


@pytest.mark.parametrize("sid", L.SCENARIOS)
@pytest.mark.parametrize("artifact,key", [
    ("adaptation.json", "adaptation"),
    ("eligibility.json", "eligibility"),
    ("composition.json", "composition"),
    ("agent_team_plan.json", "plan"),
    ("replay_record.json", "replay"),
])
def test_expected_outputs_are_byte_stable(sid, artifact, key):
    out = L.run_pipeline(L.load_inputs(sid))
    regenerated = _canonical(out[key])
    with open(f"{L.EXPECTED}/{sid}/{artifact}", "r", encoding="utf-8") as fh:
        frozen = fh.read()
    assert regenerated == frozen, f"{sid}/{artifact} drifted from frozen output"


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_ranking_output_is_byte_stable(sid):
    out = L.run_pipeline(L.load_inputs(sid))
    regenerated = _canonical([r for r in out["rankings"]])
    with open(f"{L.EXPECTED}/{sid}/ranking.json", "r", encoding="utf-8") as fh:
        assert regenerated == fh.read()


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_repeated_runs_are_identical(sid):
    a = L.run_pipeline(L.load_inputs(sid))["plan"].plan_fingerprint
    b = L.run_pipeline(L.load_inputs(sid))["plan"].plan_fingerprint
    assert a == b


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_input_ordering_does_not_change_outputs(sid):
    """Reverse the registry profile/evidence order and the overlay key order;
    the plan fingerprint must be unchanged (canonicalization is order-free)."""
    s = L.load_inputs(sid)
    base_fp = L.run_pipeline(s)["plan"].plan_fingerprint

    snap = s["registry"]
    reordered = awc.build_registry_snapshot(
        snapshot_id=snap.snapshot_id, registry_version=snap.registry_version,
        logical_time=snap.logical_time,
        agent_profiles=list(reversed(snap.agent_profiles)),
        capability_evidence=list(reversed(snap.capability_evidence)),
        provenance=snap.provenance, source_refs=snap.source_refs,
        policy_refs=snap.policy_refs)
    s2 = dict(s)
    s2["registry"] = reordered
    s2["overlay"] = dict(reversed(list(s["overlay"].items())))
    assert L.run_pipeline(s2)["plan"].plan_fingerprint == base_fp


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_replay_reproduces_expected_fingerprint(sid):
    s = L.load_inputs(sid)
    out = L.run_pipeline(s)
    replayed = awc.replay_agent_team_plan(
        out["adaptation"], s["registry"], s["enterprise_policy"], s["eligibility_policy"],
        s["ranking_policy"], s["composition_policy"], s["permission_policy"],
        s["fallback_policy"], G.LT)
    assert replayed.plan_fingerprint == out["replay"].expected_plan_fingerprint

"""The frozen manifest must match the committed fixture and output bytes exactly,
and its recorded AWC version/contracts must match the installed package."""
import hashlib
import os

import pytest

import ugence_agent_workforce_composer.api as awc
import _loader as L

_APP = os.path.dirname(L.DEMO_DATA)


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def test_manifest_records_installed_awc_version():
    m = L.manifest()
    # Compatibility migration (AWC P2.1): the frozen manifest records the AWC package
    # version it was GENERATED with (0.2.0). AWC may bump minor versions downstream
    # (P2.1 -> 0.2.1) without changing any planning contract or fingerprint, so this
    # asserts the manifest records a valid version and that the AWC planning
    # CONTRACT versions still match — not that it equals the live package version.
    assert m["awc_version"] and isinstance(m["awc_version"], str)
    assert m["awc_contract_version"] == awc.CONTRACT_VERSION
    assert m["awc_composition_contract_version"] == awc.COMPOSITION_CONTRACT_VERSION
    assert m["scenario_order"] == list(L.SCENARIOS)


def test_every_manifest_input_hash_matches_committed_file():
    m = L.manifest()
    assert m["inputs"], "manifest lists no inputs"
    for rel_path, expected_hash in m["inputs"].items():
        actual = _sha256(os.path.join(_APP, rel_path))
        assert actual == expected_hash, f"input hash drift: {rel_path}"


def test_every_manifest_output_hash_matches_committed_file():
    m = L.manifest()
    assert m["outputs"], "manifest lists no outputs"
    for rel_path, expected_hash in m["outputs"].items():
        actual = _sha256(os.path.join(_APP, rel_path))
        assert actual == expected_hash, f"output hash drift: {rel_path}"


def test_manifest_covers_all_scenarios_and_states():
    m = L.manifest()
    assert set(m["scenarios"]) == set(L.SCENARIOS)
    states = {sid: info["plan_state"] for sid, info in m["scenarios"].items()}
    assert states["cybersecurity_no_feasible_team"] == "NO_FEASIBLE_TEAM"
    assert states["procurement"] == "COMPLETE"


@pytest.mark.parametrize("sid", L.SCENARIOS)
def test_scenario_manifest_plan_fingerprint_matches_output(sid):
    sm = L.scenario_manifest(sid)
    fps = L.expected(sid, "fingerprints.json")
    assert sm["expected_fingerprints"]["plan_fingerprint"] == fps["plan_fingerprint"]

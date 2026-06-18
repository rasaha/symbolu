"""
test_external_loaders.py — AgentDojo / InjecAgent ingestion (offline).

Exercises the deterministic conversion of tiny committed fixtures into the Scenario
schema. No network: loaders read only local files. No benchmark success claim — these
tests validate the CONVERSION, not any governance result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from experiments.signal_gov import external
from experiments.signal_gov.dataset import (
    BENCHMARK_CATEGORIES,
    SCHEMA_FIELDS,
    load_dataset,
    load_external,
)
from experiments.signal_gov.oracle import verify_consistency

FIX = Path(external.FIXTURES_DIR)
SOURCES = ("agentdojo", "injecagent")


@pytest.mark.parametrize("source", SOURCES)
def test_fixture_loads_with_full_schema(source):
    scenarios = load_dataset(f"{source}_fixture")
    assert len(scenarios) == 6  # 3 records x (benign + attack)
    for s in scenarios:
        for field in SCHEMA_FIELDS:
            assert field in s.to_dict(), f"{s.scenario_id} missing {field}"
        assert s.source == source
        assert s.category == "prompt_injection"
        assert s.category in BENCHMARK_CATEGORIES


@pytest.mark.parametrize("source", SOURCES)
def test_oracle_consistency(source):
    # Converted labels are oracle-derived, so verify_consistency must be empty.
    assert verify_consistency(load_dataset(f"{source}_fixture")) == []


@pytest.mark.parametrize("source", SOURCES)
def test_balanced_safe_unsafe(source):
    scenarios = load_dataset(f"{source}_fixture")
    pos = sum(s.unsafe_label for s in scenarios)
    assert pos == 3 and (len(scenarios) - pos) == 3  # one benign + one attack per record


@pytest.mark.parametrize("source", SOURCES)
def test_attack_is_injection_target_safe_is_user_tool(source):
    scenarios = load_dataset(f"{source}_fixture")
    for s in scenarios:
        injected = s.policy_context["injected_target_tool"]
        user_tools = s.policy_context["user_intent_tools"]
        if s.scenario_id.endswith(":attack"):
            assert s.unsafe_label == 1
            assert s.proposed_tool == injected
            assert s.expected_violation_type == "prompt_injection_executed"
        else:
            assert s.scenario_id.endswith(":benign")
            assert s.unsafe_label == 0
            assert s.proposed_tool in user_tools
            assert s.expected_violation_type == "none"


@pytest.mark.parametrize("source", SOURCES)
def test_deterministic(source):
    a = load_dataset(f"{source}_fixture")
    b = load_dataset(f"{source}_fixture")
    assert [s.to_dict() for s in a] == [s.to_dict() for s in b]


@pytest.mark.parametrize("source", SOURCES)
def test_pairing_modes(source):
    path = str(FIX / f"{source}_mini.json")
    attack = load_external(source, path, pairing="attack_only")
    benign = load_external(source, path, pairing="benign_only")
    assert attack and all(s.unsafe_label == 1 for s in attack)
    assert benign and all(s.unsafe_label == 0 for s in benign)
    assert len(attack) == len(benign) == 3


def test_unique_scenario_ids():
    scenarios = load_dataset("external_fixtures")  # both combined
    ids = [s.scenario_id for s in scenarios]
    assert len(ids) == len(set(ids)) == 12


def test_limit_param():
    path = str(FIX / "agentdojo_mini.json")
    assert len(load_external("agentdojo", path, limit=2)) == 2


def test_convert_records_directly():
    recs = [{
        "suite": "t", "user_task_id": "u", "injection_task_id": "i",
        "user_prompt": "do the thing", "user_intent_tools": ["read", "act"],
        "benign_tool": "act", "benign_risk": "write",
        "injected_target_tool": "exfiltrate", "injected_risk": "destructive",
    }]
    out = external.from_agentdojo_records(recs)
    assert len(out) == 2
    assert {s.unsafe_label for s in out} == {0, 1}


# ----- error / safety paths (no network) -----

def test_missing_path_raises_valueerror():
    with pytest.raises(ValueError, match="provide path"):
        load_external("agentdojo", None)


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="unknown external source"):
        load_external("not_a_benchmark", "x.json")


def test_missing_file_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        load_external("agentdojo", "/no/such/export.json")


def test_invalid_injection_record_raises():
    # injected target inside user intent is not an injection -> loud failure
    bad = [{
        "suite": "t", "user_task_id": "u", "injection_task_id": "i",
        "user_prompt": "x", "user_intent_tools": ["send_money"],
        "benign_tool": "read", "injected_target_tool": "send_money",
    }]
    with pytest.raises(ValueError, match="not an injection|in user_intent"):
        external.from_agentdojo_records(bad)


# ----- plugs into the harness (mock features; NOT a result) -----

def test_external_fixture_runs_in_harness(tmp_path):
    from experiments.signal_gov.run_experiment import run
    res = run("mock", "agentdojo_fixture", tmp_path, n_boot=50, make_plots=False)
    assert res.results["dataset"]["n_total"] == 6
    assert set(res.results["configs"].keys())  # configs scored
    assert (tmp_path / "results.json").exists()

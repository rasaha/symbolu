"""Offline simulation: fixture labels, expectation coverage, determinism."""

from __future__ import annotations

import json
import os

from ugence_llm_steering_controller.simulation import FIXTURE_LABELS, run_scenario, run_suite

_FIX = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fixtures"))


def _load_suite():
    with open(os.path.join(_FIX, "suite.json"), encoding="utf-8") as fh:
        return json.load(fh)["scenarios"]


def test_fixture_labels_are_mandatory_and_correct():
    assert FIXTURE_LABELS == {
        "evidence_class": "FAKE_LOCAL_FIXTURE",
        "provider_status": "NO_PROVIDER_CALLED",
        "execution_status": "NO_MODEL_EXECUTED",
    }


def test_all_fixture_expectations_met():
    report = run_suite(_load_suite())
    assert report["total"] == report["checked"]
    assert report["expectations_met"] == report["checked"]
    # Every scenario carries the fixture labels.
    for s in report["scenarios"]:
        assert s["labels"] == FIXTURE_LABELS


def test_simulation_is_deterministic():
    scenarios = _load_suite()
    a = run_suite(scenarios)
    b = run_suite(scenarios)
    assert a == b


def test_single_scenario_record_shape():
    scenarios = _load_suite()
    rec = run_scenario(scenarios[0])
    assert rec["labels"] == FIXTURE_LABELS
    assert rec["result"]["recommendation_only"] is True
    assert rec["result"]["execution_status"] == "NOT_EXECUTED"


def test_all_scenario_files_present_and_loadable():
    files = [f for f in os.listdir(_FIX) if f.startswith("scenario_") and f.endswith(".json")]
    assert len(files) >= 18
    for f in files:
        with open(os.path.join(_FIX, f), encoding="utf-8") as fh:
            json.load(fh)  # must be valid JSON

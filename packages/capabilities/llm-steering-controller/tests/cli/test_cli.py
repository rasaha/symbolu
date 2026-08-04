"""CLI: subcommands, advisory banner, deterministic output, error handling."""

from __future__ import annotations

import json
import os
import subprocess
import sys

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
_FIX = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fixtures"))


def _run(args, stdin=None):
    env = {"PYTHONPATH": _SRC, "PATH": os.environ.get("PATH", "")}
    return subprocess.run([sys.executable, "-m", "ugence_llm_steering_controller.cli", *args],
                          input=stdin, capture_output=True, text=True, env=env)


def test_version():
    r = _run(["version"])
    assert r.returncode == 0
    assert json.loads(r.stdout)["version"] == "0.1.0"


def test_inspect_reports_advisory_and_banner():
    r = _run(["inspect"])
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["authority_class"] == "ADVISORY"
    assert payload["execution_capability"] == "NONE"
    assert "ROUTING RECOMMENDATION ONLY" in r.stderr
    assert "NO PROVIDER REQUEST WAS EXECUTED" in r.stderr


def test_validate_registry_ok():
    reg = json.dumps({"providers": [{"provider_id": "p"}],
                      "models": [{"model_id": "m", "provider_id": "p", "context_limit": 8000}]})
    r = _run(["validate-registry", "--input", "-"], stdin=reg)
    assert r.returncode == 0
    assert json.loads(r.stdout)["valid"] is True


def test_validate_registry_rejects_secret():
    reg = json.dumps({"providers": [{"provider_id": "p", "api_key": "x"}], "models": []})
    r = _run(["validate-registry", "--input", "-"], stdin=reg)
    assert r.returncode == 1
    assert json.loads(r.stdout)["valid"] is False


def test_recommend_fixture():
    path = os.path.join(_FIX, "scenario_multiple_eligible_models_quality_first.json")
    r = _run(["recommend", "--fixture", path])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["status"] == "RECOMMENDED"
    assert out["recommendation"]["execution_status"] == "NOT_EXECUTED"
    assert "NO PROVIDER REQUEST WAS EXECUTED" in r.stderr


def test_explain_fixture():
    path = os.path.join(_FIX, "scenario_multiple_eligible_models_quality_first.json")
    r = _run(["explain", "--fixture", path])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["explanation"]["summary"]
    assert out["recommendation_only"] is True


def test_simulate_suite():
    path = os.path.join(_FIX, "suite.json")
    r = _run(["simulate", "--fixture", path])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["labels"]["evidence_class"] == "FAKE_LOCAL_FIXTURE"
    assert out["expectations_met"] == out["checked"]


def test_verify_package_self_check():
    r = _run(["verify-package"])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["verified"] is True


def test_invalid_json_exits_nonzero():
    r = _run(["recommend", "--fixture", "-"], stdin="{not json")
    assert r.returncode != 0


def test_missing_fixture_exits_nonzero():
    r = _run(["recommend", "--fixture", "/nonexistent/thing.json"])
    assert r.returncode == 2


def test_no_live_invocation_subcommand():
    r = _run(["--help"])
    # The subcommand list must not offer a live-invocation / execution command.
    subcommands = {"inspect", "validate-registry", "recommend", "explain", "simulate",
                   "verify-package", "version"}
    for banned in ("invoke", "call-provider", "run-model", "dispatch"):
        assert banned not in r.stdout.lower()
    for expected in subcommands:
        assert expected in r.stdout

"""CLI tests for ``ugence-cloud-scaling`` (evaluate / demo / version)."""

from __future__ import annotations

import json

import pytest

from ugence_cloud_scaling_controller import cli
from ugence_cloud_scaling_controller.version import __version__


def test_version_command(capsys):
    rc = cli.main(["version"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["version"] == __version__
    assert out["name"] == "ugence-cloud-scaling-controller"


def test_demo_command_emits_json(capsys):
    rc = cli.main(["demo"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["advisory_only"] is True
    assert out["actuation_performed"] is False
    assert out["schema_version"] == "1.0"


def test_demo_is_deterministic_in_decision_fields(capsys):
    cli.main(["demo"])
    a = json.loads(capsys.readouterr().out)
    cli.main(["demo"])
    b = json.loads(capsys.readouterr().out)
    for f in ("recommendation", "replica_delta", "action_score", "pressure"):
        assert a[f] == b[f]


def test_evaluate_from_stdin(capsys, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(
        json.dumps({"metrics": {"cpu": 0.9, "memory": 0.85}, "current_replicas": 4,
                    "correlation_id": "cli-1"})))
    rc = cli.main(["evaluate", "--input", "-"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["correlation_id"] == "cli-1"
    assert out["advisory_only"] is True


def test_evaluate_from_file_and_output(tmp_path, capsys):
    obs = tmp_path / "obs.json"
    obs.write_text(json.dumps({"metrics": {"cpu": 0.5}, "current_replicas": 3}))
    out = tmp_path / "rec.json"
    rc = cli.main(["evaluate", "--input", str(obs), "--output", str(out)])
    assert rc == 0
    written = json.loads(out.read_text())
    assert written["schema_version"] == "1.0"


def test_evaluate_sequence_array(tmp_path, capsys):
    obs = tmp_path / "seq.json"
    obs.write_text(json.dumps([
        {"metrics": {"cpu": 0.4}, "current_replicas": 4},
        {"metrics": {"cpu": 0.95}, "current_replicas": 4, "phase": "peak"},
    ]))
    rc = cli.main(["evaluate", "--input", str(obs)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and len(out) == 2


def test_invalid_json_returns_nonzero(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    rc = cli.main(["evaluate", "--input", str(bad)])
    assert rc != 0
    assert "invalid JSON" in capsys.readouterr().err


def test_invalid_observation_returns_nonzero(tmp_path, capsys):
    bad = tmp_path / "obs.json"
    bad.write_text(json.dumps({"metrics": {"cpu": "high"}, "current_replicas": 3}))
    rc = cli.main(["evaluate", "--input", str(bad)])
    assert rc != 0
    assert "invalid observation" in capsys.readouterr().err


def test_missing_file_returns_nonzero(capsys):
    rc = cli.main(["evaluate", "--input", "/no/such/file.json"])
    assert rc != 0
    assert "not found" in capsys.readouterr().err

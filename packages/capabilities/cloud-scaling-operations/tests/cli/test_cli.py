"""CLI tests — default is non-mutating; live requires explicit flags and fails closed."""

from __future__ import annotations

import json

from ugence_cloud_scaling_operations import cli
from ugence_cloud_scaling_operations.version import __version__


def test_version(capsys):
    assert cli.main(["version"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["version"] == __version__


def test_inspect_capabilities_is_honest(capsys):
    assert cli.main(["inspect-capabilities"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["execution_capability"] == "INFRASTRUCTURE_MUTATION"
    assert out["advisory_only"] is False
    assert out["live_execution_enabled_by_default"] is False
    assert out["default_mode"] == "dry_run"


def test_verify_install(capsys):
    assert cli.main(["verify-install"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["import"] == "ok" and out["default_mode"] == "dry_run"


def test_dry_run_is_non_mutating(tmp_path, capsys):
    req = tmp_path / "req.json"
    req.write_text(json.dumps({"target_cluster": "c", "target_namespace": "n",
                               "target_resource": "r", "current_replicas": 3,
                               "target_replicas": 5}))
    assert cli.main(["dry-run", "--input", str(req)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["outcome"] == "proposed" and out["applied"] is False


def test_execute_without_live_flag_refuses(capsys):
    rc = cli.main(["execute", "--input", "-"])
    assert rc != 0
    assert "requires --mode live" in capsys.readouterr().err


def test_execute_live_without_authorization_refuses(capsys):
    rc = cli.main(["execute", "--mode", "live"])
    assert rc != 0
    assert "authorization" in capsys.readouterr().err


def test_execute_live_with_flags_still_fails_closed(tmp_path, capsys):
    authz = tmp_path / "a.json"
    authz.write_text("{}")
    rc = cli.main(["execute", "--mode", "live", "--authorization", str(authz), "--confirm"])
    assert rc != 0  # no operator backend/creds -> fails closed, never mutates
    assert "backend" in capsys.readouterr().err

"""Adapter behavior (mocked, sandboxed) and the file-backed CLI flow."""

from __future__ import annotations

import json
import tempfile

import pytest

from action_gateway import ToolRequest
from action_gateway.adapters import FilesystemTool, default_adapters
from action_gateway.broker import MockCredentialBroker
from action_gateway.cli import main
from action_gateway.errors import AdapterError


def _cred(broker, perm):
    tok = {"payload": {"credential_scope": {"permissions": [perm]},
                       "expiration": "2999-01-01T00:00:00.000Z"}, "token_hash": "h"}
    return broker.issue(token=tok, requested_permissions=[perm], principal="agent://x",
                        now="2026-07-12T14:00:00.000Z")


def test_filesystem_adapter_sandbox_escape_blocked():
    tool = FilesystemTool(tempfile.mkdtemp())
    broker = MockCredentialBroker()
    req = ToolRequest(tool="filesystem", verb="write", target=["file://../escape.txt"],
                      args={"content": "x"})
    with pytest.raises(AdapterError):
        tool.execute(req, _cred(broker, "fs:write"), broker=broker,
                     now="2026-07-12T14:00:00.000Z")


def test_network_and_cluster_adapters_are_mocked():
    adapters = default_adapters(tempfile.mkdtemp())
    broker = MockCredentialBroker()
    for name, verb, perm in [("http", "request", "http:request"),
                             ("kubernetes", "delete", "k8s:delete"),
                             ("terraform", "apply", "tf:apply"),
                             ("shell", "run", "shell:run")]:
        req = ToolRequest(tool=name, verb=verb, target=["res://x"], args={})
        res = adapters[name].execute(req, _cred(broker, perm), broker=broker,
                                     now="2026-07-12T14:00:00.000Z")
        assert res["mocked"] == "true"


def _run(argv, capsys):
    code = main(argv)
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out


def test_cli_full_session(capsys, tmp_path):
    sess = str(tmp_path / "s.json")
    sandbox = str(tmp_path / "sb")
    _run(["--session", sess, "start", "--sandbox-root", sandbox], capsys)
    # denied delete: submit -> evaluate -> execute blocked
    _, sub = _run(["--session", sess, "submit", "--tool", "filesystem", "--verb",
                   "delete", "--target", "file://x.txt", "--args",
                   '{"last_replica": false}'], capsys)
    rid = sub["request_id"]
    _, dec = _run(["--session", sess, "evaluate", rid], capsys)
    assert dec["outcome"] == "DENY"
    code, ex = _run(["--session", sess, "execute", rid], capsys)
    assert code != 0 and ex["error_code"] == "E_NO_EXECUTION_TOKEN"
    # audit + verify
    _, aud = _run(["--session", sess, "audit"], capsys)
    assert aud["intact"] and aud["length"] >= 1
    code, ver = _run(["--session", sess, "verify"], capsys)
    assert code == 0 and ver["intact"]


def test_cli_never_emits_signature_material(capsys, tmp_path):
    sess = str(tmp_path / "s.json")
    _run(["--session", sess, "start"], capsys)
    _, sub = _run(["--session", sess, "submit", "--tool", "terraform", "--verb",
                   "apply", "--target", "svc://x", "--args", "{}"], capsys)
    _, dec = _run(["--session", sess, "evaluate", sub["request_id"]], capsys)
    # decision output carries hashes only, never a raw signature field
    assert "signature" not in dec and "sig" not in dec

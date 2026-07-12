"""Audit integrity + redaction, metrics, persistence/restart, concurrency, demos."""

from __future__ import annotations

import threading

from action_gateway_mcp import McpGateway
from action_gateway_mcp.audit import redact
from tests.helpers import approved_terraform, load_scenarios, make


def test_both_audit_chains_intact_after_flow():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    mcp.execute(cs.context(), p["request_id"])
    v = mcp.verify_audit()
    assert v["intact"] and v["protocol"]["intact"] and v["enforcement"]["intact"]


def test_protocol_audit_covers_lifecycle():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    mcp.execute(cs.context(), p["request_id"])
    events = {r["event"] for r in mcp.audit.dump()}
    for e in ("MCP:request_received", "MCP:envelope_constructed", "MCP:decision",
              "MCP:simulation_produced", "MCP:execution_attempted", "MCP:execution_completed"):
        assert e in events, e


def test_sensitive_arguments_redacted():
    r = redact({"path": "x", "content": "s3cr3t", "password": "p", "safe": "ok"})
    assert r["content"] == "[REDACTED]" and r["password"] == "[REDACTED]"
    assert r["path"] == "x" and r["safe"] == "ok"


def test_metrics_track_outcomes_and_bypass():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    mcp.execute(cs.context(), p["request_id"])
    mcp.execute(cs.context(), p["request_id"])  # replay
    m = mcp.metrics_snapshot()
    assert m["executed_actions"] == 1
    assert m["token_replays"] == 1
    assert m["rejected_bypass_attempts"] >= 1
    assert m["by_outcome"].get("ALLOW", 0) >= 1


def test_metrics_do_not_affect_authorization():
    mcp, cs = make()
    # inflate a counter; a denied action stays denied regardless
    mcp.metrics.inc("executed_actions", 1000)
    p = mcp.prepare(cs.context(), "iam.grant",
                    {"role": "arn:role/x", "grantee": "agent://sre/1"})
    assert mcp.evaluate(cs.context(), p["request_id"])["outcome"] == "DENY"


def test_persistence_restart_then_replay_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    mcp.execute(cs.context(), p["request_id"])
    restored = McpGateway.restore(mcp.snapshot(), clock=mcp.clock)
    assert restored.verify_audit()["intact"]
    # spent nonce + protocol dedup survive restart
    r = restored.execute(cs.context(), p["request_id"])
    assert r["reason_codes"] == ["E_NONCE_REPLAY"]


def test_parallel_duplicate_execution_at_most_one_commit():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    results = []

    def worker(ctx):
        results.append(mcp.execute(ctx, p["request_id"]))

    ctxs = [cs.context() for _ in range(4)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in ctxs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    commits = [r for r in results if r.get("state") == "COMPLETED"]
    assert len(commits) == 1
    assert mcp.verify_audit()["intact"]


def test_all_demo_scenarios_pass():
    scenarios = load_scenarios()
    results = scenarios.run_all()
    failed = [r["scenario"] for r in results if not r["passed"]]
    assert not failed, failed
    assert len(results) == 15

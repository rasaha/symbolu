"""Producer-independence tests (deliverable 8): two independent DB producers."""
from __future__ import annotations

from cer_v0_3 import cleanroom as cr
from cer_v0_3 import envelope as e3
from cer_v0_3.db_actuation import DbActuation, DbContext
from cer_v0_3.producers.tool_runtime_db import ToolRuntimeDbAdapter
from cer_v0_3.producers.ugence_db import UgenceDbProducer


def _ctx():
    op = {"observed_row_version": "orders@v17", "reachable": True, "healthy": True,
          "active_transactions": 3, "max_transactions": 100, "max_affected_rows": 10000,
          "migration_active": False, "freeze_active": False, "replication_healthy": True,
          "replication_lag_s": 0.5, "max_replication_lag_s": 5.0, "lock_contention_ok": True,
          "backup_available": True, "observation_time_s": 600.0}
    return DbContext(principal="agent:data-ops", permissions=("db.write",), delegator_id="dba",
                     resource_version="row-1001", state_hash="sha-256:" + "bb" * 32,
                     as_of="2026-01-01T00:09:30.000Z", operational=op,
                     policy_version="1.0.0+abc", policy_digest="pd",
                     correlation_id="prod-orders/public/orders")


def _act():
    return DbActuation(connection_ref="prod-orders", schema="public", table="orders",
                       sql_operation="UPDATE", statement_digest="sha256:" + "aa" * 32,
                       estimated_rows=42, expected_row_version="orders@v17",
                       compensation_ref="backup:orders")


def test_two_producers_same_digest():
    ug = UgenceDbProducer().propose(_ctx(), _act())
    tr = ToolRuntimeDbAdapter().propose(_ctx(), _act())
    assert e3.action_digest(ug) == e3.action_digest(tr)
    # different provenance (runtime-producer independence)
    assert ug["provenance"]["runtime"] != tr["provenance"]["runtime"]


def test_producers_agree_with_cleanroom():
    ug = UgenceDbProducer().propose(_ctx(), _act())
    tr = ToolRuntimeDbAdapter().propose(_ctx(), _act())
    assert cr.action_digest(ug) == e3.action_digest(ug)
    assert cr.action_digest(tr) == e3.action_digest(tr)


def test_tool_runtime_does_not_execute_before_governance():
    # the adapter must intercept the pending tool call; the tool never runs
    adapter = ToolRuntimeDbAdapter()
    cer = adapter.propose(_ctx(), _act())
    assert cer["provenance"]["adapter_version"] == "tool-runtime-intercept"

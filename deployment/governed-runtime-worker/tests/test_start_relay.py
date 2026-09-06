"""Front-door seam 6 (ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md §11, rulings FD-10.1 to
FD-10.3) at the worker's edge, without PostgreSQL: the starter over an adapter double,
and the sixth route over the composed service shape.

Rows of the §11.3 failure matrix proven here: 3 (nothing a caller sends can name a
definition, provider, mode or digest; a foreign digest is the adapter's refusal),
4 (idempotent on the instance id; a conflicting duplicate refused), 8 (LIVE is not a
mode the route has), 9 (no credential crosses on the start). The end-to-end rows run
over the real adapter in ``test_end_to_end.py``.
"""

from __future__ import annotations

import pytest

from governed_runtime_worker import ShadowRunStarter, ShadowWorkload, instance_id_for
from ugence_durable_execution.errors import DefinitionVersionMismatch, InstanceIdentityError
from ugence_governed_review_service import (
    ROUTES,
    StartResult,
    build_app,
    start_view,
)

from conftest import DIGEST

WF = ShadowWorkload.WORKFLOW_ID


class _Outcome:
    def __init__(self, awaiting: bool = True, reason: str = "ESCALATE") -> None:
        self.awaiting_external = awaiting
        self.stop_reason = reason


class _AdapterDouble:
    """The three calls the starter makes, with the adapter's own refusal rules."""

    def __init__(self, bound_digest: str = DIGEST) -> None:
        self.bound = bound_digest
        self.rows: dict = {}
        self.starts: list = []
        self.advances: list = []

    def status(self, *, instance_id: str):
        row = self.rows.get(instance_id)
        return {"known": row is not None, **(row or {})}

    def start(self, *, workflow_id, definition_digest, instance_id, correlation_id, inputs):
        self.starts.append((workflow_id, definition_digest, instance_id, correlation_id, dict(inputs)))
        row = self.rows.get(instance_id)
        if row is not None:
            if row["workflow_id"] != workflow_id or row["definition_digest"] != definition_digest:
                raise InstanceIdentityError(f"instance {instance_id!r} already exists differently")
            return instance_id
        if definition_digest != self.bound:
            raise DefinitionVersionMismatch(instance_id, definition_digest, self.bound)
        if workflow_id != WF:
            raise KeyError(f"the shadow workload defines only {WF!r}")
        self.rows[instance_id] = {"workflow_id": workflow_id, "definition_digest": definition_digest}
        return instance_id

    def advance(self, *, instance_id: str, attempt_token: str):
        self.advances.append((instance_id, attempt_token))
        return _Outcome()

    # the review service's own contract check
    def signal(self, *, instance_id, signal_name, payload):  # pragma: no cover - never called here
        raise AssertionError("the start relay never signals")

    def resume(self, *, instance_id):  # pragma: no cover - never called here
        raise AssertionError("the start relay never resumes")


def _starter(adapter=None, digest: str = DIGEST) -> ShadowRunStarter:
    return ShadowRunStarter(adapter=adapter or _AdapterDouble(), workflow_id=WF,
                            definition_digest=digest, workload_maturity="FIXTURE_ONLY")


# --------------------------------------------------------------------------- #
# the starter
# --------------------------------------------------------------------------- #
def test_a_start_passes_the_deployments_own_digest_mints_the_instance_and_runs_one_quantum():
    adapter = _AdapterDouble()
    out = _starter(adapter).start(correlation_id="c-1")
    assert out.result is StartResult.STARTED and out.started and out.advanced
    assert out.instance_id == instance_id_for(WF, "c-1") and out.instance_id.startswith("shadow-")
    assert out.workflow_id == WF and out.definition_digest == DIGEST and out.correlation_id == "c-1"
    assert out.awaiting_external is True and out.stop_reason == "ESCALATE"
    assert out.workload_maturity == "FIXTURE_ONLY"
    (start,) = adapter.starts
    assert start == (WF, DIGEST, out.instance_id, "c-1", {})
    assert adapter.advances == [(out.instance_id, f"{out.instance_id}:start")]


def test_row_4_the_same_correlation_id_replays_and_runs_nothing_more():
    adapter = _AdapterDouble()
    first = _starter(adapter).start(correlation_id="c-1")
    again = _starter(adapter).start(correlation_id="c-1")
    assert again.result is StartResult.REPLAYED and again.started and not again.advanced
    assert again.instance_id == first.instance_id
    assert len(adapter.advances) == 1, "a replay never advances"
    assert "nothing was re-run" in again.reason


def test_without_a_correlation_id_the_worker_mints_a_fresh_instance_each_time():
    adapter = _AdapterDouble()
    a = _starter(adapter).start(correlation_id=None)
    b = _starter(adapter).start(correlation_id=None)
    assert a.result is b.result is StartResult.STARTED
    assert a.instance_id != b.instance_id and a.correlation_id != b.correlation_id
    assert a.correlation_id.startswith("shadow-") and a.instance_id == instance_id_for(WF, a.correlation_id)


def test_row_3_a_foreign_digest_is_the_adapters_refusal_mapped_to_a_typed_outcome():
    adapter = _AdapterDouble(bound_digest="shadow-v2")
    out = _starter(adapter, digest="shadow-v1").start(correlation_id="c-1")
    assert out.result is StartResult.REFUSED_DEFINITION and not out.started
    assert "shadow-v2" in out.reason and "refusing" in out.reason
    assert adapter.advances == [] and adapter.rows == {}


def test_row_4_a_conflicting_duplicate_is_refused_not_overwritten():
    adapter = _AdapterDouble()
    first = _starter(adapter).start(correlation_id="c-1")
    # the deployment is redeployed under a new definition; the old correlation id returns
    adapter.bound = "shadow-v2"
    out = _starter(adapter, digest="shadow-v2").start(correlation_id="c-1")
    assert out.result is StartResult.REFUSED_CONFLICT and not out.started
    assert out.instance_id == first.instance_id
    assert adapter.rows[first.instance_id]["definition_digest"] == DIGEST, "the first stands"
    assert len(adapter.advances) == 1


def test_a_workload_without_the_shadow_workflow_is_a_definition_refusal():
    class _NoSuch(_AdapterDouble):
        def start(self, **kw):
            raise KeyError("the workload defines only 'wf-other'")

    out = _starter(_NoSuch()).start(correlation_id="c")
    assert out.result is StartResult.REFUSED_DEFINITION and "defines no" in out.reason


def test_the_starter_requires_the_deployments_digest_and_takes_no_definition():
    with pytest.raises(ValueError, match="definition_digest is required"):
        ShadowRunStarter(adapter=_AdapterDouble(), workflow_id=WF, definition_digest="",
                         workload_maturity="FIXTURE_ONLY")
    import inspect

    params = inspect.signature(ShadowRunStarter.start).parameters
    assert set(params) == {"self", "correlation_id"}, "nothing else can be supplied (FD-10.3)"


# --------------------------------------------------------------------------- #
# the sixth route over the service shape the worker composes
# --------------------------------------------------------------------------- #
@pytest.fixture()
def route_client(tmp_path):
    from fastapi.testclient import TestClient
    from ugence_approval_workflow import StaticApproverEligibility
    from ugence_governed_review import build_review_ledger
    from ugence_authority_directory import SqliteAuthorityDirectory
    from ugence_governed_review_service import ReviewService, StaticRunReader, TenantMode

    from conftest import ROLE, TENANT, Clock

    adapter = _AdapterDouble()
    directory = SqliteAuthorityDirectory(str(tmp_path / "dir.sqlite3"), production_mode=False)
    ledger = build_review_ledger(str(tmp_path / "approvals.sqlite3"), directory, production_mode=False)
    service = ReviewService(
        ledger=ledger, adapter=adapter, reader=StaticRunReader(), tenant_id=TENANT,
        clock=Clock().datetime, eligibility=StaticApproverEligibility(()),
        tenant_mode=TenantMode.SINGLE_TENANT, production=False, starter=_starter(adapter),
    )
    del ROLE
    with TestClient(build_app(service)) as client:
        yield client, adapter
    ledger.close()
    directory.close()


def test_the_sixth_route_is_in_the_table_and_names_no_prohibited_verb():
    assert ROUTES[5] == ("POST", "/review/runs", "review_start_shadow_run")
    for verb in ("issue", "activate", "revoke", "grant", "authorize", "clear", "execute",
                 "resume", "release", "continue", "signal", "retry"):
        assert verb not in ROUTES[5][1] and verb not in ROUTES[5][2]


def test_row_8_and_9_the_route_starts_shadow_only_and_carries_no_credential(route_client):
    client, adapter = route_client
    started = client.post("/review/runs", json={"correlation_id": "c-http"})
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["result"] == "STARTED" and body["mode"] == "shadow"
    assert body["maturity"] == "REFERENCE_GRADE_SHADOW_ONLY" and body["workload_maturity"] == "FIXTURE_ONLY"
    assert body["definition_digest"] == DIGEST
    for mode in ("live", "LIVE", "dry_run"):
        r = client.post("/review/runs", json={"correlation_id": "c-http", "mode": mode})
        assert r.status_code == 409 and r.json()["result"] == "REFUSED_MODE", mode
    assert len(adapter.starts) == 1, "a refused mode never reached the adapter"
    for key in ("workflow", "tasks", "provider_id", "definition_digest", "execution_mode",
                "instance_id", "authorization", "token", "proof"):
        r = client.post("/review/runs", json={"correlation_id": "c-http", key: "x"})
        assert r.status_code == 422, key
    assert len(adapter.starts) == 1
    replay = client.post("/review/runs", json={"correlation_id": "c-http"})
    assert replay.status_code == 200 and replay.json()["result"] == "REPLAYED"
    assert replay.json()["instance_id"] == body["instance_id"]
    assert len(adapter.advances) == 1
    view_keys = set(start_view(_starter(adapter).start(correlation_id="c-view")))
    assert view_keys == set(body), "the wire view is the typed outcome and nothing else"
    for secret in ("postgresql", "password", "token"):
        assert secret not in started.text.lower()

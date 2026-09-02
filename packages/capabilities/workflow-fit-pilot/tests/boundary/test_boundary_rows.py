"""§8 rows A12–A18, A13a, A16a, A16b: the separate-process capture boundary."""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import datetime, timezone

import pytest

import pilot_fixtures as pf
from ugence_reasoning_method_governance.api import CountBasis, UsageAvailabilityToken
from ugence_workflow_fit_pilot._canon import digest_of
from ugence_workflow_fit_pilot.api import (
    BoundaryProcess,
    CaptureAttemptStatus,
    PilotError,
    PilotErrorCode as E,
    envelope_id_for,
    issue_attestation,
    record_canonical_payload,
    recompute_telemetry,
    render,
    run_pilot,
)
from ugence_workflow_fit_pilot.boundary.frames import capture_from_json, method_to_json


def refuses(code, fn):
    with pytest.raises(PilotError) as ei:
        fn()
    assert ei.value.code is code, f"expected {code.value}, got {ei.value.code.value}: {ei.value.detail}"


def _run(mode="ok", executor=None, calls=None):
    m = pf.manifest()
    adv = pf.advisory(m.plan.task_class)
    return m, run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=executor or pf.FakeExecutor(calls or pf.DEFAULT_CALLS), scorer=pf.KeywordScorer(),
                        identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env(mode))


def test_a12_boundary_count_populates_telemetry_and_workflow_count_is_diagnostic():
    m, res = _run(executor=pf.FakeExecutor(pf.DEFAULT_CALLS, report_offset=1))
    run = next(r for r in res.runs if r.method.method_id == "linear_chain")
    assert run.record.telemetry.llm_calls == 2 and run.record.telemetry.llm_calls_basis is CountBasis.INJECTED_COUNTER
    assert run.record.telemetry.capture_refs[0] == m.manifest_digest and len(run.record.telemetry.capture_refs) == 3
    assert run.diagnostics.total_llm_calls_reported == 4 and run.diagnostics.harness_observed_calls == 2 and run.diagnostics.label == "RUNTIME_REPORTED_DIAGNOSTIC"
    assert run.attestation.record_digest == run.record.record_digest
    view = next(v for v in res.result.evidence_status if v.record_digest == run.record.record_digest)
    assert view.attestation_status.value == "ATTESTED" and set(view.attested_fields) == set(run.attestation.attested_fields)
    assert run.record.telemetry.token_count_basis is CountBasis.PROVIDER_REPORTED
    assert "RUNTIME_REPORTED_DIAGNOSTIC: total_llm_calls_reported=4" in render(res)


def test_a13_issue_attestation_recomputes_and_refuses():
    m, res = _run()
    run = next(r for r in res.runs if r.method.method_id == "linear_chain")
    decl = m.capture_boundary
    payload_ok = record_canonical_payload(run.record)
    eid = envelope_id_for(run.record.record_digest, decl.boundary_identity)
    env = issue_attestation(payload_ok, run.capture_records, declaration=decl, record_issuer_identity="adapter:pilot-runner", requester_identity="requester:pilot", envelope_id=eid)
    assert env.record_digest == run.record.record_digest and env.attester_identity == decl.boundary_identity
    tampered = json.loads(json.dumps(payload_ok)); tampered["telemetry"]["llm_calls"] = "99"
    refuses(E.TELEMETRY_NOT_RECOMPUTED, lambda: issue_attestation(tampered, run.capture_records, declaration=decl, record_issuer_identity="a", requester_identity="r", envelope_id=eid))
    wrong_digest = dict(payload_ok); wrong_digest["record_digest"] = "0" * 64
    refuses(E.TELEMETRY_NOT_RECOMPUTED, lambda: issue_attestation(wrong_digest, run.capture_records, declaration=decl, record_issuer_identity="a", requester_identity="r", envelope_id=envelope_id_for("0" * 64, decl.boundary_identity)))
    refuses(E.TELEMETRY_NOT_RECOMPUTED, lambda: issue_attestation(payload_ok, run.capture_records[:-1], declaration=decl, record_issuer_identity="a", requester_identity="r", envelope_id=eid))
    refuses(E.SELF_ATTESTATION, lambda: issue_attestation(payload_ok, run.capture_records, declaration=decl, record_issuer_identity=decl.boundary_identity, requester_identity="r", envelope_id=eid))
    refuses(E.SELF_ATTESTATION, lambda: issue_attestation(payload_ok, run.capture_records, declaration=decl, record_issuer_identity="a", requester_identity=decl.boundary_identity, envelope_id=eid))
    refuses(E.ATTESTATION_MISMATCH, lambda: issue_attestation(payload_ok, run.capture_records, declaration=decl, record_issuer_identity="a", requester_identity="r", envelope_id="att:other"))


def test_a13a_attested_at_is_boundary_generated():
    import inspect

    assert "attested_at" not in inspect.signature(issue_attestation).parameters
    m, res = _run()
    for run in res.runs:
        assert run.attestation.attested_at.tzinfo is not None
        assert all(run.attestation.attested_at >= c.captured_at for c in run.capture_records)


def test_a14_incomplete_capture_yields_no_record_and_inconclusive_state():
    class Skipper(pf.FakeExecutor):
        """Makes one call outside the stub for debate: the harness count exceeds the capture."""

        def execute(self, method, query, context, client):
            if method.method_id == "debate":
                client._inner.calls += 1  # bypasses the boundary: harness-observed > captured
                # (the counting wrapper is the harness count; bump it too)
                client.calls += 1
            return super().execute(method, query, context, client)

    m, res = _run(executor=Skipper(pf.DEFAULT_CALLS))
    run = next(r for r in res.runs if r.method.method_id == "debate")
    assert not run.complete and run.record is None and run.attestation is None
    st = [s for s in res.states if s.method.method_id == "debate"][-1]
    assert st.state.value == "INCONCLUSIVE" and st.refusal_codes == ("CAPTURE_INCOMPLETE",)
    assert res.coverage.methods_without_record == (run.method,) and not res.coverage.summary_permitted
    # a case never run: gap detected at RUN_END
    class CaseSkipper(pf.FakeExecutor):
        def execute(self, method, query, context, client):
            if method.method_id == "map_reduce" and "refund" in query:
                return pf.ExecutionOutcome("ANSWER: skipped", 0)
            return super().execute(method, query, context, client)

    m2, res2 = _run(executor=CaseSkipper(pf.DEFAULT_CALLS))
    mr = next(r for r in res2.runs if r.method.method_id == "map_reduce")
    assert mr.complete  # every case had CASE_BEGIN/END; zero calls in one case is captured == observed (0)
    # duplicate case begin is detected by the server directly
    bp = BoundaryProcess(m, "stub_provider:make_provider", env=pf.boundary_env())
    try:
        conn = bp.connect()
        method = m.methods[0].method
        conn.send({"kind": "RUN_BEGIN", "manifest_digest": m.manifest_digest, "run_id": "r1", "method": method_to_json(method)})
        c = m.benchmark.case_digests[0]
        conn.send({"kind": "CASE_BEGIN", "run_id": "r1", "case_digest": c}); conn.send({"kind": "CASE_END", "run_id": "r1", "case_digest": c, "harness_observed_calls": 0})
        conn.send({"kind": "CASE_BEGIN", "run_id": "r1", "case_digest": c}); conn.send({"kind": "CASE_END", "run_id": "r1", "case_digest": c, "harness_observed_calls": 0})
        end = conn.send({"kind": "RUN_END", "run_id": "r1", "case_digests": list(m.benchmark.case_digests), "harness_observed_calls": 0})
        assert not end["complete"] and any("twice" in r for r in end["reasons"])
        refuses(E.CAPTURE_INCOMPLETE, lambda: conn.send({"kind": "ATTEST", "run_id": "r1", "record_payload": {}, "record_issuer_identity": "a", "requester_identity": "r", "envelope_id": "x"}))
        refuses(E.MANIFEST_MISMATCH, lambda: conn.send({"kind": "RUN_BEGIN", "manifest_digest": "0" * 64, "run_id": "r2", "method": method_to_json(method)}))
        conn.close()
    finally:
        bp.stop()


def test_a15_token_availability_per_field():
    m, res = _run(mode="no_usage_second")
    lc = next(r for r in res.runs if r.method.method_id == "linear_chain")  # two calls: second has no usage
    assert lc.record.telemetry.token_usage is None and lc.record.telemetry.token_usage_availability is UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED
    assert lc.attestation.attested_fields == ("telemetry.llm_calls",)
    m2, res2 = _run(mode="partial_usage_second")
    lc2 = next(r for r in res2.runs if r.method.method_id == "linear_chain")
    tu = lc2.record.telemetry.token_usage
    assert tu.total_tokens is not None and tu.input_tokens is None
    assert lc2.attestation.attested_fields == ("telemetry.llm_calls", "telemetry.token_usage.total_tokens")
    m3, res3 = _run(mode="ok")
    lc3 = next(r for r in res3.runs if r.method.method_id == "linear_chain")
    assert set(lc3.attestation.attested_fields) == {"telemetry.llm_calls", "telemetry.token_usage.input_tokens", "telemetry.token_usage.output_tokens", "telemetry.token_usage.total_tokens"}


def test_a16a_gateway_round_trip_failure_and_invalid_factory():
    m, res = _run(mode="raise")  # every run's second provider call raises; the stub workflow propagates it
    lc = next(r for r in res.runs if r.method.method_id == "linear_chain")
    assert not lc.complete and any(r.startswith("WORKFLOW_FAILED") for r in lc.reasons) and lc.record is None
    statuses = [c.status for c in lc.capture_records]
    assert CaptureAttemptStatus.EXCEPTION in statuses and CaptureAttemptStatus.SUCCEEDED in statuses
    failed = next(c for c in lc.capture_records if c.status is CaptureAttemptStatus.EXCEPTION)
    assert failed.usage is None and failed.provider_invoked
    for c in lc.capture_records:
        assert "ANSWER" not in json.dumps(dataclasses.asdict(c), default=str) and "Compare vendor" not in json.dumps(dataclasses.asdict(c), default=str)
    st = [s for s in res.states if s.method.method_id == "linear_chain"][-1]
    assert st.state.value == "INCONCLUSIVE" and st.refusal_codes == ("WORKFLOW_FAILED",)
    refuses(E.PROVIDER_FACTORY_INVALID, lambda: BoundaryProcess(m, "stub_provider:not_a_provider", env=pf.boundary_env()))
    refuses(E.PROVIDER_FACTORY_INVALID, lambda: BoundaryProcess(m, "no_such_module:make", env=pf.boundary_env()))


def test_a16b_canonical_capture_order_is_deterministic():
    m, res = _run()
    lc = next(r for r in res.runs if r.method.method_id == "linear_chain")
    shuffled = tuple(reversed(lc.capture_records))
    a = recompute_telemetry(m.manifest_digest, lc.capture_records)
    b = recompute_telemetry(m.manifest_digest, shuffled)
    assert a == b == lc.record.telemetry
    rt = tuple(capture_from_json(json.loads(json.dumps(__import__("ugence_workflow_fit_pilot.boundary.frames", fromlist=["capture_to_json"]).capture_to_json(c)))) for c in lc.capture_records)
    assert rt == lc.capture_records


def test_a17_a18_slice_1_self_attestation_and_unresolved_attester(monkeypatch):
    from ugence_readiness_comparison import compare
    from ugence_reasoning_method_governance.api import ReadinessComparisonRequest

    m, res = _run()
    req = res.request
    # A18: attester not resolved -> ignored, UNATTESTED
    unresolved = dataclasses.replace(req, resolved_authorities=())
    r2 = compare(unresolved, produced_at=pf.NOW)
    assert all(v.attestation_status.value == "UNATTESTED" for v in r2.evidence_status) and len(r2.ignored_envelopes) == len(req.attestation_envelopes)
    # A17: the boundary identity equal to the record issuer is refused by issue_attestation before Slice 1 would;
    # Slice 1's own SELF_ATTESTATION still holds when a requester names itself as attester.
    self_req = dataclasses.replace(req, requester_identity=m.capture_boundary.boundary_identity)
    r3 = compare(self_req, produced_at=pf.NOW)
    assert any(x.code.value == "SELF_ATTESTATION" for x in r3.refusals)

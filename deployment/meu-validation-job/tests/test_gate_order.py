"""The order of refusal, proven gate by gate.

The owner's correction of 2026-09-13: a live run must be refused by the earliest
outstanding governance gate, and nothing may be composed until every gate before
``LIVE_TRANSPORT`` has passed. Leading with the missing transport is wrong twice over —
it is not the first thing outstanding, and it invites "authorize it and it will run".

Each test below walks one gate forward and asserts the refusal moves with it, never
jumping to the transport, and that nothing was constructed on the way.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from meu_validation_job import GATES, GATES_BEFORE_COMPOSITION, evaluate_gates, load_config, run
from meu_validation_job.gates import (
    CONFIGURATION, EXECUTION_POSTURE, LIVE_AUTHORIZATION, LIVE_EGRESS, LIVE_TRANSPORT,
    STEP8_DESIGNATIONS, STEP8_INDEPENDENT_VERIFICATION)
from meu_validation_job.job import ci_marker_variables, load_records
from meu_validation_job.report import NOTHING_COMPOSED
from meu_validation_job.version import EXIT_OK, EXIT_REFUSED
from ugence_model_egress_unit import LIVE_VENDOR_EGRESS

from _fixtures import (NOW, RECORDS, authorization_record, complete_designation,
                       pinned_validation_record, write_config)

NO_CI = {"HOME": "/home/ugence"}


def test_the_declared_order_is_the_owners_order():
    assert GATES == (CONFIGURATION, EXECUTION_POSTURE, STEP8_DESIGNATIONS,
                     STEP8_INDEPENDENT_VERIFICATION, LIVE_AUTHORIZATION, LIVE_EGRESS,
                     LIVE_TRANSPORT)
    assert LIVE_TRANSPORT not in GATES_BEFORE_COMPOSITION
    assert GATES_BEFORE_COMPOSITION == GATES[:-1]
    assert GATES.index(LIVE_TRANSPORT) == len(GATES) - 1, "the transport is last, always"


def _live(tmp_path, **over):
    over.setdefault("mode", "live")
    return run(load_config(write_config(tmp_path, **over)), now=NOW, environ=NO_CI)


def _authorized(tmp_path, **over):
    """Everything an owner can supply, supplied: designations, verification, authorization."""

    authorization = authorization_record()
    (tmp_path / "auth.json").write_text(json.dumps(authorization), encoding="utf-8")
    return _live(tmp_path, designation=complete_designation(),
                 validation=pinned_validation_record(authorization),
                 authorization_record_path=str(tmp_path / "auth.json"), **over)


# --- each earlier gate is reported before the transport ---------------------------------

@pytest.mark.parametrize("marker", ["CI", "GITHUB_ACTIONS"])
def test_a_prohibited_posture_is_reported_before_the_missing_transport(marker, tmp_path):
    result = run(load_config(write_config(tmp_path, mode="live", designation=complete_designation())),
                 now=NOW, environ={marker: "true"})
    assert result.exit_code == EXIT_REFUSED
    assert result.report["gates"][GATES.index(EXECUTION_POSTURE)]["status"] == "BLOCKED"
    assert result.messages[0].startswith(f"live mode refused at {EXECUTION_POSTURE}")
    assert "CI runner" in result.messages[0]


def test_missing_designations_are_reported_before_the_missing_transport(tmp_path):
    result = _live(tmp_path)
    assert result.messages[0].startswith(f"live mode refused at {STEP8_DESIGNATIONS}")
    assert "17 of 17 designation obligations are not supplied" in result.messages[0]
    blocked = result.report["blocked_gates"]
    assert blocked.index(STEP8_DESIGNATIONS) < blocked.index(LIVE_TRANSPORT)


def test_missing_independent_verification_is_reported_before_the_missing_transport(tmp_path):
    designation = complete_designation()
    designation["step8_required_values"]["attestation"]["independently_checked_by"] = None
    result = _live(tmp_path, designation=designation)
    assert result.messages[0].startswith(f"live mode refused at {STEP8_INDEPENDENT_VERIFICATION}")
    assert "no independent verification" in result.messages[0]
    blocked = result.report["blocked_gates"]
    assert blocked.index(STEP8_INDEPENDENT_VERIFICATION) < blocked.index(LIVE_TRANSPORT)
    assert STEP8_DESIGNATIONS not in blocked, "the values are supplied; only the check is missing"


def test_missing_live_authorization_is_reported_before_the_missing_transport(tmp_path):
    result = _live(tmp_path, designation=complete_designation())
    assert result.messages[0].startswith(f"live mode refused at {LIVE_AUTHORIZATION}")
    assert "NOT_GIVEN" in result.messages[0]
    blocked = result.report["blocked_gates"]
    assert blocked.index(LIVE_AUTHORIZATION) < blocked.index(LIVE_TRANSPORT)


def test_disabled_live_egress_is_reported_before_the_missing_transport(tmp_path):
    """With the designations accepted, verified and authorized, the egress flag is what
    remains before the transport — and it is still false."""

    assert LIVE_VENDOR_EGRESS is False
    result = _authorized(tmp_path)
    assert result.messages[0].startswith(f"live mode refused at {LIVE_EGRESS}")
    assert "LIVE_VENDOR_EGRESS is False" in result.messages[0]
    assert result.report["blocked_gates"] == [LIVE_EGRESS, LIVE_TRANSPORT]


def test_the_refusal_walks_forward_one_gate_at_a_time_and_never_starts_at_the_transport(tmp_path):
    """The whole sequence in one place: each state's first blocked gate, in order."""

    designation = complete_designation()
    unverified = complete_designation()
    unverified["step8_required_values"]["attestation"]["independently_checked_by"] = None
    walked = [
        _live(tmp_path).report["gates"],
        _live(tmp_path, designation=unverified).report["gates"],
        _live(tmp_path, designation=designation).report["gates"],
        _authorized(tmp_path).report["gates"],
    ]
    firsts = [next(g["gate"] for g in gates if g["status"] == "BLOCKED") for gates in walked]
    assert firsts == [STEP8_DESIGNATIONS, STEP8_INDEPENDENT_VERIFICATION, LIVE_AUTHORIZATION, LIVE_EGRESS]
    assert LIVE_TRANSPORT not in firsts, "the transport is never the first thing outstanding"
    assert [GATES.index(gate) for gate in firsts] == sorted(GATES.index(gate) for gate in firsts)


# --- and nothing is constructed on the way ------------------------------------------------

def _boom(*args, **kwargs):
    raise AssertionError("a refused run constructed a component it must never touch")


def _arm_the_credential_path(monkeypatch):
    """Arm every path that reaches Google, custody or a real credential.

    These are the components the owner enumerated: the Google client, the custody
    adapter and any Secret Manager materialization. Nothing in this repository may
    build one outside an authorized live dispatch — not on a refusal, not offline.
    """

    import ugence_model_egress_custody_gcp as custody
    import ugence_model_egress_custody_gcp.client as client_module
    import meu_validation_job.composition as composition

    monkeypatch.setattr(client_module, "build_google_secret_manager_client", _boom)
    monkeypatch.setattr(composition, "build_google_secret_manager_client", _boom)
    monkeypatch.setattr(composition, "build_custody_adapter", _boom)
    monkeypatch.setattr(custody.ProductionFormSecretManagerCustodyAdapter, "__init__", _boom)
    monkeypatch.setattr(custody.ProductionFormSecretManagerCustodyAdapter, "materialize", _boom)


@pytest.fixture
def nothing_may_be_constructed(monkeypatch):
    """Arm every construction path to raise. A refusal that touched one would fail here.

    A *refused live* run composes nothing whatsoever, so the provider and the transport
    are armed here alongside the credential path.
    """

    import ugence_model_egress_provider_openai as adapter

    _arm_the_credential_path(monkeypatch)
    monkeypatch.setattr(adapter.OpenAIResponsesProvider, "__init__", _boom)
    monkeypatch.setattr(adapter.FakeTransport, "send", _boom)
    yield


@pytest.fixture
def no_credential_path_may_be_constructed(monkeypatch):
    """The offline half of the same guarantee.

    Offline mode is *supposed* to build the harness's injected fake provider and fake
    transport — that is the whole approved offline path, and arming those would assert
    the opposite of what the design requires. What it must never build is the credential
    path: a Google client, a custody adapter, a real transport, a socket, or a
    materialized credential. Sockets are refused suite-wide by ``conftest``; the real
    transport has no implementation in this distribution at all.
    """

    _arm_the_credential_path(monkeypatch)
    yield


@pytest.mark.parametrize("state", ["undesignated", "unverified", "unauthorized", "authorized"])
def test_no_client_adapter_transport_socket_or_materialization_on_any_earlier_refusal(
        state, tmp_path, nothing_may_be_constructed):
    """Sockets are already refused for the whole suite by ``conftest``; everything else is
    armed by the fixture above. Every refusal state must come back clean."""

    designation = complete_designation()
    if state == "unverified":
        designation["step8_required_values"]["attestation"]["independently_checked_by"] = None
    if state == "authorized":
        result = _authorized(tmp_path)
    elif state == "undesignated":
        result = _live(tmp_path)
    else:
        result = _live(tmp_path, designation=designation)
    assert result.exit_code == EXIT_REFUSED
    assert result.report["credential_materialized"] is False
    assert result.report["secret_version_accessed"] is None
    assert result.report["network_opened"] is False
    assert result.report["components_composed"] == NOTHING_COMPOSED
    assert result.report["components_composed"]["transport"] == "none", \
        "a refused run composes no transport at all, not even a fake one"


def test_offline_constructs_none_of_them_and_leaves_the_canonical_records_byte_identical(
        tmp_path, no_credential_path_may_be_constructed):
    before = {name: hashlib.sha256((RECORDS / name).read_bytes()).hexdigest()
              for name in ("MEU_LIVE_PROVIDER_DESIGNATION.json", "MEU_LIVE_VALIDATION.json")}
    config = load_config(write_config(tmp_path, mode="offline"))
    result = run(config, now=NOW, environ=NO_CI)
    assert result.exit_code == EXIT_OK and result.outcome == "OFFLINE_CONFORMANT"
    assert result.report["credential_materialized"] is False
    assert result.report["secret_version_accessed"] is None
    assert result.report["network_opened"] is False
    assert result.report["components_composed"] == {
        "google_secret_manager_client": False, "custody_adapter": False, "transport": "fake"
    }, "offline builds the harness's injected fake and nothing on the credential path"
    after = {name: hashlib.sha256((RECORDS / name).read_bytes()).hexdigest() for name in before}
    assert after == before, "the offline run mutated a canonical record"
    # and the records the run itself read are untouched too
    for path in (config.designation_record_path, config.validation_record_path):
        assert pathlib.Path(path).is_file()


def test_the_composition_guard_and_the_gate_order_cannot_drift_apart():
    """``may_compose_components`` is exactly "every gate before the transport"."""

    from meu_validation_job.gates import GateOutcome, GateReport
    for index, gate in enumerate(GATES_BEFORE_COMPOSITION):
        report = GateReport(tuple(
            GateOutcome(g, "BLOCKED" if g == gate else "PASSED", "x") for g in GATES))
        assert report.may_compose_components is False, f"{gate} must block composition"
        assert report.first_blocked == gate
    all_but_transport = GateReport(tuple(
        GateOutcome(g, "BLOCKED" if g == LIVE_TRANSPORT else "PASSED", "x") for g in GATES))
    assert all_but_transport.may_compose_components is True
    assert all_but_transport.may_dispatch_a_genuine_call is False

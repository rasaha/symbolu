"""The composition root: no credential path is built while a gate is outstanding, and the
real Google client is reached only when nothing is injected."""

from __future__ import annotations

import json

import pytest

from meu_validation_job import GATES, GateOutcome, GateReport, evaluate_gates, load_config
from meu_validation_job.gates import LIVE_TRANSPORT
from meu_validation_job.composition import CompositionRefused, build_custody_adapter
from meu_validation_job.job import ci_marker_variables, load_records
from ugence_model_egress_custody_gcp import (
    GoogleClientUnavailable, ProductionFormSecretManagerCustodyAdapter)
from ugence_model_egress_unit import CredentialRequest, materialize_with_audit

from _fixtures import (NOW, RESOURCE, SA, FakeClient, authorization_record, complete_designation,
                       pinned_validation_record, write_config)

NO_CI = {"HOME": "/home/ugence"}
FAKE_PAYLOAD = "MARKER-FAKE-JOB-PAYLOAD-NOT-A-KEY"


def _gates_with(config, designation, validation, authorization=None):
    return evaluate_gates(config, designation_record=designation, validation_record=validation,
                          authorization_record=authorization,
                          variables=ci_marker_variables(NO_CI), now=NOW)


def all_composition_gates_passed() -> GateReport:
    """A report with every gate before LIVE_TRANSPORT passed.

    Built rather than reached, because `LIVE_VENDOR_EGRESS` is False in every installed
    distribution and no configuration can make it true. The composition root's contract
    is "compose only when gates 1 to 6 have passed", and this is how a test states those
    gates without pretending the repository is in a state it is not in. The test below
    proves the real state refuses.
    """

    return GateReport(tuple(
        GateOutcome(gate, "PASSED" if gate != LIVE_TRANSPORT else "BLOCKED",
                    "asserted by this fixture" if gate != LIVE_TRANSPORT else "no transport exists")
        for gate in GATES))


def _designated(tmp_path):
    """A configuration and designation that pass every gate this repository can pass."""

    authorization = authorization_record()
    path = write_config(tmp_path, designation=complete_designation(),
                        validation=pinned_validation_record(authorization),
                        authorization_record_path=str(tmp_path / "auth.json"))
    (tmp_path / "auth.json").write_text(json.dumps(authorization), encoding="utf-8")
    config = load_config(path)
    designation, validation, authorization_doc = load_records(config)
    return config, designation, _gates_with(config, designation, validation, authorization_doc)


def test_nothing_is_composed_while_any_earlier_gate_is_outstanding(tmp_path):
    config = load_config(write_config(tmp_path))
    designation, validation, _ = load_records(config)
    gates = _gates_with(config, designation, validation)
    client = FakeClient()
    with pytest.raises(CompositionRefused) as info:
        build_custody_adapter(config, designation_record=designation, gates=gates, client=client)
    assert "nothing is composed while STEP8_DESIGNATIONS is outstanding" in str(info.value)
    assert client.calls == [], "a refused composition still reached Secret Manager"


def test_a_designated_run_without_the_canonical_authorization_composes_nothing(tmp_path):
    config = load_config(write_config(tmp_path, designation=complete_designation()))
    designation, validation, _ = load_records(config)
    gates = _gates_with(config, designation, validation)
    with pytest.raises(CompositionRefused, match="LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION is outstanding"):
        build_custody_adapter(config, designation_record=designation, gates=gates, client=FakeClient())


def test_an_authorized_run_still_composes_nothing_while_live_egress_is_disabled(tmp_path):
    """The real repository state: everything an owner can supply is supplied, and the
    egress flag alone still refuses composition."""

    config, designation, gates = _designated(tmp_path)
    assert gates.first_blocked == "LIVE_VENDOR_EGRESS"
    client = FakeClient()
    with pytest.raises(CompositionRefused, match="LIVE_VENDOR_EGRESS is outstanding"):
        build_custody_adapter(config, designation_record=designation, gates=gates, client=client)
    assert client.calls == []


def test_with_every_composition_gate_passed_an_injected_client_composes_the_adapter(tmp_path):
    config, designation, _ = _designated(tmp_path)
    gates = all_composition_gates_passed()
    assert gates.may_compose_components is True
    assert gates.may_dispatch_a_genuine_call is False, "the transport gate cannot pass in this slice"
    client = FakeClient()
    adapter = build_custody_adapter(config, designation_record=designation, gates=gates, client=client)
    assert isinstance(adapter, ProductionFormSecretManagerCustodyAdapter)
    assert adapter.is_production_authoritative is True
    lease = adapter.materialize(
        CredentialRequest(request_id=__import__("uuid").uuid4(), tenant_id=__import__("uuid").uuid4(),
                          vendor="openai", credential_profile="openai-validation", requested_at=NOW),
        now=NOW)
    assert client.calls == [RESOURCE]
    assert lease.use(lambda s: s, now=NOW) == FAKE_PAYLOAD
    assert FAKE_PAYLOAD not in repr(lease) and FAKE_PAYLOAD not in json.dumps(lease.as_record())


def test_the_real_google_client_is_only_reached_when_nothing_is_injected(tmp_path):
    """With no client the composition root calls the builder. Here the SDK is absent, so
    it raises the typed unavailability rather than reaching a network."""

    config, designation, _ = _designated(tmp_path)
    gates = all_composition_gates_passed()
    with pytest.raises(GoogleClientUnavailable, match="not installed"):
        build_custody_adapter(config, designation_record=designation, gates=gates)


def test_a_composed_adapter_audits_with_identifiers_only(tmp_path):
    config, designation, _ = _designated(tmp_path)
    adapter = build_custody_adapter(config, designation_record=designation,
                                    gates=all_composition_gates_passed(), client=FakeClient())
    import uuid
    _, event = materialize_with_audit(
        adapter, CredentialRequest(request_id=uuid.uuid4(), tenant_id=uuid.uuid4(), vendor="openai",
                                   credential_profile="openai-validation", requested_at=NOW), now=NOW)
    record = json.dumps(event.as_record())
    assert FAKE_PAYLOAD not in record and event.secret_version_ref == RESOURCE

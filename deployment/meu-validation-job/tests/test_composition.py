"""The composition root: no credential path is built while a gate is outstanding, and the
real Google client is reached only when nothing is injected."""

from __future__ import annotations

import json

import pytest

from meu_validation_job import evaluate_gates, load_config
from meu_validation_job.composition import CompositionRefused, build_custody_adapter
from meu_validation_job.job import ci_marker_variables, load_records
from ugence_model_egress_custody_gcp import (
    GoogleClientUnavailable, ProductionFormSecretManagerCustodyAdapter)
from ugence_model_egress_unit import CredentialRequest, materialize_with_audit

from _fixtures import (NOW, RESOURCE, SA, FakeClient, authorization_record, complete_designation,
                       pinned_validation_record, write_config)

NO_CI = {"HOME": "/home/ugence"}
FAKE_PAYLOAD = "MARKER-FAKE-JOB-PAYLOAD-NOT-A-KEY"


def _fully_gated(tmp_path):
    """A run with every gate passed except the transport, which cannot pass in this slice."""

    authorization = authorization_record()
    path = write_config(tmp_path, designation=complete_designation(),
                        validation=pinned_validation_record(authorization),
                        authorization_record_path=str(tmp_path / "auth.json"))
    (tmp_path / "auth.json").write_text(json.dumps(authorization), encoding="utf-8")
    config = load_config(path)
    designation, validation, authorization_doc = load_records(config)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           authorization_record=authorization_doc,
                           variables=ci_marker_variables(NO_CI), now=NOW)
    return config, designation, gates


def test_no_credential_path_is_composed_while_any_credential_gate_is_outstanding(tmp_path):
    config = load_config(write_config(tmp_path))
    designation, validation, _ = load_records(config)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           variables=ci_marker_variables(NO_CI), now=NOW)
    client = FakeClient()
    with pytest.raises(CompositionRefused, match="STEP8_DESIGNATION"):
        build_custody_adapter(config, designation_record=designation, gates=gates, client=client)
    assert client.calls == [], "a refused composition still reached Secret Manager"


def test_a_designated_run_without_the_canonical_authorization_composes_nothing(tmp_path):
    config = load_config(write_config(tmp_path, designation=complete_designation()))
    designation, validation, _ = load_records(config)
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           variables=ci_marker_variables(NO_CI), now=NOW)
    with pytest.raises(CompositionRefused, match="LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION"):
        build_custody_adapter(config, designation_record=designation, gates=gates, client=FakeClient())


def test_with_every_credential_gate_passed_an_injected_client_composes_the_adapter(tmp_path):
    config, designation, gates = _fully_gated(tmp_path)
    assert gates.may_materialize_a_credential is True
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

    config, designation, gates = _fully_gated(tmp_path)
    with pytest.raises(GoogleClientUnavailable, match="not installed"):
        build_custody_adapter(config, designation_record=designation, gates=gates)


def test_a_composed_adapter_audits_with_identifiers_only(tmp_path):
    config, designation, gates = _fully_gated(tmp_path)
    adapter = build_custody_adapter(config, designation_record=designation, gates=gates,
                                    client=FakeClient())
    import uuid
    _, event = materialize_with_audit(
        adapter, CredentialRequest(request_id=uuid.uuid4(), tenant_id=uuid.uuid4(), vendor="openai",
                                   credential_profile="openai-validation", requested_at=NOW), now=NOW)
    record = json.dumps(event.as_record())
    assert FAKE_PAYLOAD not in record and event.secret_version_ref == RESOURCE

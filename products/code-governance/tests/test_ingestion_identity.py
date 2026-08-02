"""Acceptance tests 1-6: ingestion and exact change identity."""
from __future__ import annotations

import pytest

from cg_helpers import T0, make_payload, revision_of
from ugence_code_governance import (
    CodeGovernanceService,
    GovernedChangeIdentity,
    MalformedEventError,
    MergeMethod,
    SignatureVerificationError,
    TenantMismatchError,
    UnsupportedEventError,
)
from ugence_code_governance.github import compute_signature, normalize_pull_request_event
import json


def _identity(**kw) -> GovernedChangeIdentity:
    return normalize_pull_request_event(
        make_payload(**kw), tenant_id="acme", captured_at=T0, delivery_id="d")


# 1. valid PR event creates exact change identity
def test_valid_pr_event_creates_identity():
    change = _identity()
    assert change.repository == "acme/widgets"
    assert change.pull_request_number == 42
    assert change.base_sha == "base-sha-1"
    assert change.head_sha == "head-sha-1"
    assert change.target_branch == "main"
    assert change.fingerprint  # deterministic, non-empty


def test_same_normalized_identity_same_fingerprint():
    assert _identity().fingerprint == _identity().fingerprint


# 2. duplicate delivery is idempotent
def test_duplicate_delivery_is_idempotent(service: CodeGovernanceService):
    p = make_payload()
    c1 = service.ingest_change_event(p, tenant_id="acme", captured_at=T0, delivery_id="dup")
    c2 = service.ingest_change_event(p, tenant_id="acme", captured_at=T0, delivery_id="dup")
    assert c1.fingerprint == c2.fingerprint
    assert revision_of(c1) == revision_of(c2)
    # only one run exists for the revision
    assert len(service._runs) == 1


# 3. changed head SHA creates a new revision
def test_changed_head_creates_new_revision(service: CodeGovernanceService):
    c1 = service.ingest_change_event(make_payload(head_sha="h1"), tenant_id="acme",
                                     captured_at=T0, delivery_id="d1")
    c2 = service.ingest_change_event(make_payload(head_sha="h2"), tenant_id="acme",
                                     captured_at=T0, delivery_id="d2")
    assert c1.fingerprint != c2.fingerprint
    assert revision_of(c1) != revision_of(c2)
    assert len(service._runs) == 2


def test_fingerprint_changes_with_governed_fields():
    base = _identity()
    assert _identity(head_sha="other").fingerprint != base.fingerprint
    assert _identity(base_sha="other").fingerprint != base.fingerprint
    assert _identity(name="other").fingerprint != base.fingerprint
    # merge method
    m1 = normalize_pull_request_event(make_payload(), tenant_id="acme", captured_at=T0,
                                      delivery_id="d", merge_method=MergeMethod.MERGE)
    m2 = normalize_pull_request_event(make_payload(), tenant_id="acme", captured_at=T0,
                                      delivery_id="d", merge_method=MergeMethod.SQUASH)
    assert m1.fingerprint != m2.fingerprint


def test_fingerprint_changes_with_tenant():
    a = normalize_pull_request_event(make_payload(), tenant_id="acme", captured_at=T0, delivery_id="d")
    b = normalize_pull_request_event(make_payload(), tenant_id="globex", captured_at=T0, delivery_id="d")
    assert a.fingerprint != b.fingerprint


def test_delivery_id_and_capture_time_do_not_change_fingerprint():
    from datetime import datetime, timezone
    a = normalize_pull_request_event(make_payload(), tenant_id="acme", captured_at=T0, delivery_id="d1")
    b = normalize_pull_request_event(
        make_payload(), tenant_id="acme",
        captured_at=datetime(2027, 5, 5, tzinfo=timezone.utc), delivery_id="d2")
    assert a.fingerprint == b.fingerprint


# 4. malformed event fails closed
def test_malformed_event_fails_closed():
    with pytest.raises(MalformedEventError):
        normalize_pull_request_event({"action": "opened"}, tenant_id="acme",
                                     captured_at=T0, delivery_id="d")


def test_unsupported_action_is_deterministic():
    with pytest.raises(UnsupportedEventError):
        normalize_pull_request_event(make_payload(action="assigned"), tenant_id="acme",
                                     captured_at=T0, delivery_id="d")


# 5. tenant mismatch fails
def test_tenant_mismatch_fails():
    with pytest.raises(TenantMismatchError):
        normalize_pull_request_event(
            make_payload(installation="install-9"), tenant_id="acme",
            captured_at=T0, delivery_id="d",
            installation_tenant_map={"install-9": "globex"})


# 6. signature mismatch fails when signature verification is enabled
def test_signature_mismatch_fails():
    body = json.dumps(make_payload()).encode()
    with pytest.raises(SignatureVerificationError):
        normalize_pull_request_event(
            make_payload(), tenant_id="acme", captured_at=T0, delivery_id="d",
            secret="s3cr3t", signature_header="sha256=deadbeef", raw_body=body)


def test_signature_match_passes():
    body = json.dumps(make_payload()).encode()
    sig = compute_signature("s3cr3t", body)
    change = normalize_pull_request_event(
        make_payload(), tenant_id="acme", captured_at=T0, delivery_id="d",
        secret="s3cr3t", signature_header=sig, raw_body=body)
    assert change.repository == "acme/widgets"

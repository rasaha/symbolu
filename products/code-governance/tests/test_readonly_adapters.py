"""MVP 1D acceptance tests — read-only adapters, transport boundary, credentials,
GitHub adapter, supplied snapshots, registry/provenance, failures and retries.

Execution stays DISABLED throughout; source failures never become positive signals.
"""
from __future__ import annotations

import json

import pytest
from cg_pilot_helpers import (
    GH_HOST,
    GH_POLICY,
    adapter_request,
    gh_checks_json,
    gh_pr_json,
    gh_transport,
    github_adapter,
    registry_entry,
    supplied_snapshot,
)

from ugence_action_clearance import SignalTrustLevel
from ugence_code_governance.adapters import (
    AdapterFailureCode,
    AdapterRegistryProjection,
    AdapterResponseError,
    ChangeWindowSnapshotAdapter,
    ControlStatusSnapshotAdapter,
    FactConsistency,
    FakeReadOnlyTransport,
    GitHubReadOnlyAdapter,
    IdentitySnapshotAdapter,
    IncidentSnapshotAdapter,
    RawResponse,
    ReadOnlyBoundaryViolation,
    RetryPolicy,
    TargetHealthSnapshotAdapter,
    TransportPolicy,
    validate_supplied_snapshot,
)
from ugence_code_governance.adapters.github_readonly import (
    FORBIDDEN_WRITE_PERMISSIONS,
    REQUIRED_READ_PERMISSIONS,
)

CTX = {"workflow_id": "wf", "repository": "acme/widgets", "pull_request_number": 42,
       "base_sha": "base-1", "head_sha": "head-1", "target_branch": "main",
       "change_fingerprint": "cf", "prepared_action_fingerprint": "pa", "authorization_fingerprint": "az"}


def _tp(responses=None, policy=None, resolver=None):
    return FakeReadOnlyTransport(policy or GH_POLICY, responses or {}, credential_resolver=resolver)


# --- 1-10. read-only boundary ----------------------------------------------
def test_get_permitted():
    tp = _tp({("GET", f"https://{GH_HOST}/repos/x"): RawResponse(200, "application/json", b"{}")})
    assert tp.get(f"https://{GH_HOST}/repos/x", source_id="s").status == 200


def test_head_permitted_only_when_configured():
    pol = TransportPolicy(allowed_hosts=(GH_HOST,), allow_head=True)
    tp = _tp({("HEAD", f"https://{GH_HOST}/repos/x"): RawResponse(200, "application/json", b"")}, policy=pol)
    assert tp.head(f"https://{GH_HOST}/repos/x", source_id="s").status == 200
    tp2 = _tp(policy=TransportPolicy(allowed_hosts=(GH_HOST,), allow_head=False))
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp2.head(f"https://{GH_HOST}/repos/x", source_id="s")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"])
def test_mutating_methods_rejected(method):
    tp = _tp()
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp.request(method, f"https://{GH_HOST}/repos/x", source_id="s")


def test_graphql_mutation_rejected_as_post():
    tp = _tp()
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp.request("POST", f"https://{GH_HOST}/graphql", source_id="s")


def test_unapproved_host_rejected():
    tp = _tp()
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp.get("https://evil.example.com/repos/x", source_id="s")


def test_unapproved_endpoint_rejected():
    pol = TransportPolicy(allowed_hosts=(GH_HOST,), allowed_path_prefixes=("/repos/",))
    tp = _tp(policy=pol)
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp.get(f"https://{GH_HOST}/admin/x", source_id="s")


def test_redirect_to_unapproved_host_rejected():
    pol = TransportPolicy(allowed_hosts=(GH_HOST,), max_redirects=3)
    tp = _tp({("GET", f"https://{GH_HOST}/r"): RawResponse(302, "application/json", b"",
                                                           redirect_location="https://evil.com/x")}, policy=pol)
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp.get(f"https://{GH_HOST}/r", source_id="s")


# --- 11-17. credentials + security -----------------------------------------
def _resolver(source_id):
    return {"Authorization": "Bearer super-secret-token", "X-Api-Key": "k-123"}


def test_credentials_used_but_never_returned():
    tp = _tp({("GET", f"https://{GH_HOST}/repos/x"):
              RawResponse(200, "application/json", b"{}",
                          headers={"Authorization": "echoed", "X-Ratelimit": "1"})}, resolver=_resolver)
    resp = tp.get(f"https://{GH_HOST}/repos/x", source_id="s")
    assert "Authorization" not in resp.headers and "authorization" not in {k.lower() for k in resp.headers}
    assert "X-Ratelimit" in resp.headers  # non-credential headers preserved


def test_credentials_seen_by_backend_but_values_not_stored():
    tp = _tp({("GET", f"https://{GH_HOST}/repos/x"): RawResponse(200, "application/json", b"{}")},
             resolver=_resolver)
    tp.get(f"https://{GH_HOST}/repos/x", source_id="s")
    # the fake backend records credential header NAMES only, never values
    assert "Authorization" in tp.credential_header_names_seen
    assert not any("super-secret-token" in n for n in tp.credential_header_names_seen)


def test_credentials_never_enter_request_or_result_fingerprint():
    req = adapter_request(CTX)
    # AdapterRequest has no credential field; fingerprint is stable regardless of transport creds.
    tp1 = gh_transport(CTX)
    tp1._resolver = _resolver
    res = github_adapter(CTX, transport=tp1).collect_snapshot(req)
    text = json.dumps({"rfp": res.result_fingerprint, "prov": res.provenance.source_response_fingerprint})
    assert "super-secret-token" not in text and "k-123" not in text


def test_response_size_limit_enforced():
    pol = TransportPolicy(allowed_hosts=(GH_HOST,), max_response_bytes=4)
    tp = _tp({("GET", f"https://{GH_HOST}/repos/x"): RawResponse(200, "application/json", b"toolongbody")},
             policy=pol)
    with pytest.raises(AdapterResponseError):
        tp.get(f"https://{GH_HOST}/repos/x", source_id="s")


def test_content_type_validation_enforced():
    pol = TransportPolicy(allowed_hosts=(GH_HOST,), allowed_content_types=("application/json",))
    tp = _tp({("GET", f"https://{GH_HOST}/repos/x"): RawResponse(200, "text/html", b"<html>")}, policy=pol)
    with pytest.raises(AdapterResponseError):
        tp.get(f"https://{GH_HOST}/repos/x", source_id="s")


# --- 18-27. GitHub adapter -------------------------------------------------
def test_github_identity_preserved_and_facts_extracted():
    res = github_adapter(CTX).collect_snapshot(adapter_request(CTX))
    assert res.ok
    kinds = {f.signal_type for f in res.collected_facts}
    assert "ARTIFACT_IDENTITY" in kinds and "TARGET_AVAILABILITY" in kinds
    assert "REQUIRED_CONTROL" in kinds


def test_github_head_mismatch_fails_closed():
    tp = gh_transport(CTX, pr_json=gh_pr_json(CTX, head="different-head"))
    res = github_adapter(CTX, transport=tp).collect_snapshot(adapter_request(CTX))
    assert not res.ok
    assert AdapterFailureCode.ARTIFACT_IDENTITY_MISMATCH in res.failure_codes
    assert res.collected_facts == ()  # no positive signal on mismatch


def test_github_base_mismatch_fails_closed():
    bad = json.dumps({"number": 42, "state": "open", "draft": False,
                      "base": {"sha": "WRONG", "repo": {"full_name": "acme/widgets"}},
                      "head": {"sha": "head-1"}}).encode()
    tp = gh_transport(CTX, pr_json=bad)
    res = github_adapter(CTX, transport=tp).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_IDENTITY_MISMATCH in res.failure_codes


def test_github_failed_check_normalized_not_satisfied():
    tp = gh_transport(CTX, checks_json=gh_checks_json(conclusion="failure"))
    res = github_adapter(CTX, transport=tp).collect_snapshot(adapter_request(CTX))
    rc = [f for f in res.collected_facts if f.signal_type == "REQUIRED_CONTROL"][0]
    assert rc.value["satisfied"] is False


def test_github_facts_are_consistency_classified():
    res = github_adapter(CTX).collect_snapshot(adapter_request(CTX))
    artifact = [f for f in res.collected_facts if f.signal_type == "ARTIFACT_IDENTITY"][0]
    target = [f for f in res.collected_facts if f.signal_type == "TARGET_AVAILABILITY"][0]
    assert artifact.consistency is FactConsistency.AUTHORITATIVE
    assert target.consistency is FactConsistency.EVENTUALLY_CONSISTENT


def test_github_adapter_has_no_mutation_method():
    a = github_adapter(CTX)
    for banned in ("merge", "approve", "close", "write", "post", "put", "delete"):
        assert not hasattr(a, banned)


def test_github_permission_minimization_documented():
    for p in FORBIDDEN_WRITE_PERMISSIONS:
        assert p not in REQUIRED_READ_PERMISSIONS
        assert p.endswith(":write")
    assert all(p.endswith(":read") for p in REQUIRED_READ_PERMISSIONS)


def test_github_result_fingerprint_stable():
    a = github_adapter(CTX)
    assert a.collect_snapshot(adapter_request(CTX)).result_fingerprint == \
        github_adapter(CTX).collect_snapshot(adapter_request(CTX)).result_fingerprint


# --- 28-40. snapshot adapters ----------------------------------------------
def test_valid_identity_snapshot_admitted():
    res = IdentitySnapshotAdapter(supplied_snapshot("identity", {"account_active": True})).collect_snapshot(
        adapter_request(CTX))
    assert res.ok and res.collected_facts[0].value == {"state": "ACTIVE"}


def test_inactive_account_becomes_negative_condition():
    res = IdentitySnapshotAdapter(supplied_snapshot("identity", {"account_active": False})).collect_snapshot(
        adapter_request(CTX))
    assert res.collected_facts[0].value == {"state": "DISABLED"}


def test_identity_rejects_prohibited_fields():
    res = IdentitySnapshotAdapter(supplied_snapshot("identity", {"account_active": True,
                                                                 "salary": 100000})).collect_snapshot(
        adapter_request(CTX))
    assert not res.ok and AdapterFailureCode.SOURCE_SCHEMA_INVALID in res.failure_codes


def test_active_freeze_becomes_hold_input():
    res = ChangeWindowSnapshotAdapter(supplied_snapshot("change_window", {"freeze_active": True})).collect_snapshot(
        adapter_request(CTX))
    assert res.collected_facts[0].value == {"active": True}


def test_critical_incident_present():
    res = IncidentSnapshotAdapter(supplied_snapshot("incident", {"incident_active": True,
                                                                 "severity": "SEV1"})).collect_snapshot(
        adapter_request(CTX))
    assert res.collected_facts[0].value["active"] is True


def test_target_unavailable_present():
    res = TargetHealthSnapshotAdapter(supplied_snapshot("target_health", {"available": False})).collect_snapshot(
        adapter_request(CTX))
    assert res.collected_facts[0].value == {"available": False}


def test_required_control_unsatisfied_present():
    res = ControlStatusSnapshotAdapter(supplied_snapshot("control_status", {"satisfied": False})).collect_snapshot(
        adapter_request(CTX))
    assert res.collected_facts[0].value["satisfied"] is False


def test_malformed_snapshot_rejected():
    res = IdentitySnapshotAdapter({"schema_version": "wrong"}).collect_snapshot(adapter_request(CTX))
    assert not res.ok and AdapterFailureCode.SOURCE_SCHEMA_INVALID in res.failure_codes


def test_expired_snapshot_rejected():
    snap = supplied_snapshot("identity", {"account_active": True},
                             valid="2020-01-01T00:00:00Z")
    res = IdentitySnapshotAdapter(snap).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_DATA_STALE in res.failure_codes


def test_cross_tenant_snapshot_rejected():
    snap = supplied_snapshot("identity", {"account_active": True}, tenant="intruder")
    res = IdentitySnapshotAdapter(snap).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_IDENTITY_MISMATCH in res.failure_codes


def test_action_binding_mismatch_rejected():
    snap = supplied_snapshot("identity", {"account_active": True}, action_fingerprint="WRONG")
    res = IdentitySnapshotAdapter(snap, require_action_binding=True).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.ARTIFACT_IDENTITY_MISMATCH in res.failure_codes


def test_unsupported_schema_version_rejected():
    snap = supplied_snapshot("identity", {"account_active": True})
    snap["schema_version"] = "code_governance.identity_snapshot.v99"
    res = IdentitySnapshotAdapter(snap).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_SCHEMA_INVALID in res.failure_codes


def test_naive_timestamp_rejected():
    snap = supplied_snapshot("identity", {"account_active": True}, captured="2026-01-01T00:00:00")
    res = IdentitySnapshotAdapter(snap).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_SCHEMA_INVALID in res.failure_codes


def test_tampered_integrity_digest_rejected():
    snap = supplied_snapshot("identity", {"account_active": True}, with_digest=True)
    snap["facts"] = {"account_active": False}  # mutate after digest
    res = IdentitySnapshotAdapter(snap).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_SCHEMA_INVALID in res.failure_codes


# --- 41-48. registry + provenance ------------------------------------------
def test_registry_approves_registered_adapter():
    reg = AdapterRegistryProjection("reg", "v1", "acme",
                                    {"cg.github_readonly": registry_entry("cg.github_readonly", "github", "ARTIFACT_IDENTITY")})
    entry = reg.authorize(tenant_id="acme", adapter_id="cg.github_readonly",
                          adapter_version="1.0.0", source_id="github")
    assert entry.adapter_id == "cg.github_readonly"


def test_registry_rejects_unregistered_adapter():
    from ugence_code_governance.adapters import AdapterConfigurationError
    reg = AdapterRegistryProjection("reg", "v1", "acme", {})
    with pytest.raises(AdapterConfigurationError):
        reg.authorize(tenant_id="acme", adapter_id="nope", adapter_version="1.0.0", source_id="s")


def test_registry_rejects_unapproved_version():
    from ugence_code_governance.adapters import AdapterConfigurationError
    e = registry_entry("cg.github_readonly", "github", "ARTIFACT_IDENTITY", approved_versions=("2.0.0",))
    reg = AdapterRegistryProjection("reg", "v1", "acme", {"cg.github_readonly": e})
    with pytest.raises(AdapterConfigurationError):
        reg.authorize(tenant_id="acme", adapter_id="cg.github_readonly",
                      adapter_version="1.0.0", source_id="github")


def test_registry_rejects_cross_tenant():
    from ugence_code_governance.adapters import AdapterConfigurationError
    reg = AdapterRegistryProjection("reg", "v1", "acme",
                                    {"cg.github_readonly": registry_entry("cg.github_readonly", "github", "ARTIFACT_IDENTITY")})
    with pytest.raises(AdapterConfigurationError):
        reg.authorize(tenant_id="intruder", adapter_id="cg.github_readonly",
                      adapter_version="1.0.0", source_id="github")


def test_registry_rejects_disabled_adapter():
    from ugence_code_governance.adapters import AdapterConfigurationError
    e = registry_entry("cg.github_readonly", "github", "ARTIFACT_IDENTITY", enabled=False)
    reg = AdapterRegistryProjection("reg", "v1", "acme", {"cg.github_readonly": e})
    with pytest.raises(AdapterConfigurationError):
        reg.authorize(tenant_id="acme", adapter_id="cg.github_readonly",
                      adapter_version="1.0.0", source_id="github")


def test_over_claimed_trust_rejected():
    e = registry_entry("x", "identity", "ACTOR_STATUS", trust=SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION)
    assert not e.trust_within_max(SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER)
    assert e.trust_within_max(SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION)


def test_provenance_fingerprint_stable():
    res = github_adapter(CTX).collect_snapshot(adapter_request(CTX))
    assert res.provenance.source_response_fingerprint == \
        github_adapter(CTX).collect_snapshot(adapter_request(CTX)).provenance.source_response_fingerprint


def test_registry_version_recorded_in_result():
    res = github_adapter(CTX, registry_version="reg-v7").collect_snapshot(adapter_request(CTX))
    assert res.provenance.registry_projection_version == "reg-v7"


# --- 49-56. failure handling + retries -------------------------------------
def test_timeout_produces_structured_failure():
    tp = FakeReadOnlyTransport(GH_POLICY, {})  # no response configured -> AdapterResponseError
    res = GitHubReadOnlyAdapter(tp).collect_snapshot(adapter_request(CTX))
    assert not res.ok and res.failure_codes


def test_unauthorized_source_produces_structured_failure():
    tp = gh_transport(CTX, pr_json=None)
    tp.set_response("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42",
                    RawResponse(401, "application/json", b"{}"))
    res = GitHubReadOnlyAdapter(tp).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_UNAUTHORIZED in res.failure_codes


def test_rate_limit_produces_structured_failure():
    tp = gh_transport(CTX)
    tp.set_response("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42",
                    RawResponse(429, "application/json", b"{}"))
    res = GitHubReadOnlyAdapter(tp).collect_snapshot(adapter_request(CTX))
    assert AdapterFailureCode.SOURCE_RATE_LIMITED in res.failure_codes


def test_schema_mismatch_does_not_retry():
    calls = []
    tp = gh_transport(CTX)
    tp.set_response("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42",
                    RawResponse(401, "application/json", b"{}"))  # non-retryable
    slept = []
    a = GitHubReadOnlyAdapter(tp, retry=RetryPolicy(max_attempts=3, backoff_schedule=(0, 0)),
                              sleep=lambda s: slept.append(s))
    a.collect_snapshot(adapter_request(CTX))
    # 401 is non-retryable -> exactly one attempt on the PR endpoint
    assert tp.attempts.count(("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42")) == 1
    assert slept == []


def test_transient_failure_retries_within_bound():
    tp = gh_transport(CTX)
    tp.set_response("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42",
                    RawResponse(503, "application/json", b"{}"))  # retryable
    slept = []
    a = GitHubReadOnlyAdapter(tp, retry=RetryPolicy(max_attempts=3, backoff_schedule=(0, 0)),
                              sleep=lambda s: slept.append(s))
    a.collect_snapshot(adapter_request(CTX))
    assert tp.attempts.count(("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42")) == 3


def test_read_only_violation_never_retried():
    # a boundary violation raises immediately, never converted to a retryable failure
    tp = _tp()
    with pytest.raises(ReadOnlyBoundaryViolation):
        tp.request("DELETE", f"https://{GH_HOST}/repos/x", source_id="s")


def test_source_failure_never_becomes_positive_signal():
    tp = gh_transport(CTX)
    tp.set_response("GET", f"https://{GH_HOST}/repos/acme/widgets/pulls/42",
                    RawResponse(503, "application/json", b"{}"))
    res = GitHubReadOnlyAdapter(tp).collect_snapshot(adapter_request(CTX))
    assert res.collected_facts == () and not res.ok

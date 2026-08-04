"""Security: secret redaction, no token leakage, bounded retries, URL allowlists."""

from __future__ import annotations

from ugence_cloud_scaling_operations import (
    OperationsConfig, TargetPolicy, ExecutionMode, GateExecutor, InMemoryAuditSink,
)
from ugence_cloud_scaling_operations.audit import redact, AuditEvent
import ops_support as support


def test_redact_scrubs_secret_keys_and_bearer():
    payload = {"authorization": "Bearer abc.def.ghi", "token": "s3cr3t",
               "nested": {"api_key": "k", "safe": "value"},
               "note": "call with Bearer zzz.yyy please"}
    r = redact(payload)
    assert r["authorization"] == "<redacted>"
    assert r["token"] == "<redacted>"
    assert r["nested"]["api_key"] == "<redacted>"
    assert r["nested"]["safe"] == "value"
    assert "zzz.yyy" not in r["note"] and "<redacted>" in r["note"]


def test_audit_event_extra_is_redacted():
    ev = AuditEvent(
        event_id="e1", timestamp=1.0, tenant_id="t", actor_id="a", authorization_id="x",
        decision_id="d", recommendation_id="r", target="c/n/res", requested_action="scale",
        authorized_bounds=None, execution_mode="live", pre_state=1, post_state=2,
        result="applied", denial_reason=None, retry_count=0, rollback_reference=None,
        package_version="0.1.0", source_revision=None,
        extra={"argocd_token": "SECRET", "ok": 1})
    d = ev.to_dict()
    assert d["extra"]["argocd_token"] == "<redacted>" and d["extra"]["ok"] == 1


def test_gate_never_leaks_token_in_outcome():
    def http(method, url, headers, timeout):
        # token would be in headers; must never surface in outcome/detail
        return (500, "server error")
    cfg = OperationsConfig(mode=ExecutionMode.LIVE, target_policy=TargetPolicy(
        allowed_clusters=("prod-a",), allowed_namespaces=("web",),
        allowed_resources=("frontend",)), argocd_allowed_base_urls=("https://argo",),
        max_retries=1)
    g = GateExecutor(cfg, http=http, verifier=support.verifier())
    out = g.sync(support.make_request(action="argocd_sync"),
                 support.make_authorization(permitted_action="argocd_sync"),
                 base_url="https://argo", token="super-secret-token", tenant_id="tenant-1")
    assert "super-secret-token" not in out.detail
    assert out.retry_count <= cfg.max_retries


def test_malformed_url_rejected():
    def http(*a): return (200, "ok")
    cfg = OperationsConfig(mode=ExecutionMode.LIVE, target_policy=TargetPolicy(
        allowed_clusters=("prod-a",), allowed_namespaces=("web",),
        allowed_resources=("frontend",)), argocd_allowed_base_urls=("https://argo",))
    g = GateExecutor(cfg, http=http, verifier=support.verifier())
    out = g.sync(support.make_request(action="argocd_sync"),
                 support.make_authorization(permitted_action="argocd_sync"),
                 base_url="not-a-url", tenant_id="tenant-1")
    assert out.applied is False

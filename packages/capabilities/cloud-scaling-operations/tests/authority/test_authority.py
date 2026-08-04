"""Authority tests: fail-closed denials + the one accepted path (LIVE mode)."""

from __future__ import annotations

import pytest

from ugence_cloud_scaling_operations import (
    ControlledScalingExecutor, OperationsConfig, TargetPolicy, ExecutionMode,
    FakeScalingBackend, ExecutionIntegrityError,
)
import ops_support as support


def _live_executor(**over):
    tp = TargetPolicy(allowed_clusters=("prod-a",), allowed_namespaces=("web",),
                      allowed_resources=("frontend",), max_replica_delta=5,
                      min_replicas=1, max_replicas=10)
    cfg = OperationsConfig(mode=ExecutionMode.LIVE, target_policy=tp)
    return ControlledScalingExecutor(
        cfg, backend=FakeScalingBackend({"prod-a/web/frontend": 3}),
        verifier=support.verifier(), clock=lambda: 1500.0, **over)


def _run(authz, req=None, tenant="tenant-1"):
    ex = _live_executor()
    return ex.execute(req or support.make_request(), authz, tenant_id=tenant)


def test_missing_authorization_denied():
    r = _run(None)
    assert r.outcome == "denied" and r.applied is False


def test_expired_authorization_denied():
    r = _run(support.make_authorization(expires_at=1400.0))
    assert r.outcome == "denied" and "expired" in (r.detail + (r.denial_reason or ""))


def test_not_yet_valid_denied():
    r = _run(support.make_authorization(issued_at=1600.0, expires_at=1700.0))
    assert r.outcome == "denied"


def test_mismatched_tenant_denied():
    r = _run(support.make_authorization(), tenant="tenant-OTHER")
    assert r.outcome == "denied"


def test_mismatched_target_denied():
    r = _run(support.make_authorization(target_resource="frontend"),
             req=support.make_request(target_resource="frontend"))  # matches
    assert r.outcome == "applied"
    r2 = _run(support.make_authorization(),
              req=support.make_request(target_resource="backend"))
    assert r2.outcome == "denied"


def test_mismatched_action_denied():
    r = _run(support.make_authorization(permitted_action="rollback"))
    assert r.outcome == "denied"


def test_bounds_violation_denied():
    r = _run(support.make_authorization(maximum_replicas=4),
             req=support.make_request(target_replicas=8, current_replicas=3))
    assert r.outcome == "denied"


def test_delta_violation_denied():
    r = _run(support.make_authorization(maximum_delta=1),
             req=support.make_request(target_replicas=9, current_replicas=3))
    assert r.outcome == "denied"


def test_untrusted_issuer_denied():
    r = _run(support.make_authorization(issuer="rogue", sign=False))
    assert r.outcome == "denied"


def test_bad_signature_denied():
    authz = support.make_authorization(sign=False)  # no signature
    r = _run(authz)
    assert r.outcome == "denied"


def test_recommendation_mismatch_denied():
    r = _run(support.make_authorization(recommendation_id="rec-OTHER"))
    assert r.outcome == "denied"


def test_valid_authorization_accepted():
    r = _run(support.make_authorization())
    assert r.outcome == "applied" and r.applied is True and r.post_state == 5


def test_reused_authorization_with_changed_request_denied():
    ex = _live_executor()
    authz = support.make_authorization()
    r1 = ex.execute(support.make_request(), authz, tenant_id="tenant-1")
    assert r1.outcome == "applied"
    # Same idempotency key, different target_replicas -> integrity error.
    with pytest.raises(ExecutionIntegrityError):
        ex.execute(support.make_request(target_replicas=4), authz, tenant_id="tenant-1")


def test_stale_observation_denied():
    r = _run(support.make_authorization(),
             req=support.make_request(observed_at=100.0))  # far older than window
    assert r.outcome == "denied"

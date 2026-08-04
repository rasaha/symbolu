"""Shared test helpers: build signed authorizations and requests."""
from __future__ import annotations

from ugence_cloud_scaling_operations import (
    ExecutionAuthorization, ExecutionRequest, ReferenceAuthorityVerifier,
)

ISSUER = "gov"
SECRET = "test-secret"


def verifier(require_signature=True):
    return ReferenceAuthorityVerifier({ISSUER: SECRET}, require_signature=require_signature)


def make_request(**over):
    d = dict(action="scale", target_cluster="prod-a", target_namespace="web",
             target_resource="frontend", current_replicas=3, target_replicas=5,
             recommendation_id="rec-1", idempotency_key="idem-1", correlation_id="corr-1")
    d.update(over)
    return ExecutionRequest(**d)


def make_authorization(*, sign=True, **over):
    d = dict(authorization_id="auth-1", decision_id="dec-1", recommendation_id="rec-1",
             tenant_id="tenant-1", actor_id="ops", authority_source="gov",
             issued_at=0.0, expires_at=4102444800.0, permitted_action="scale",
             target_cluster="prod-a", target_namespace="web", target_resource="frontend",
             current_replicas=3, minimum_replicas=1, maximum_replicas=10, maximum_delta=5,
             reason="load", policy_version="p1", idempotency_key="idem-1", nonce="nonce-1",
             issuer="gov")
    d.update(over)
    authz = ExecutionAuthorization(**d)
    if sign:
        sig = ReferenceAuthorityVerifier({ISSUER: SECRET}).sign(authz, ISSUER)
        authz = ExecutionAuthorization(**{**d, "signature": sig})
    return authz

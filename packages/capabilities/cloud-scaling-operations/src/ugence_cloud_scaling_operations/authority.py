"""Authority verification — fail-closed checks that an ExecutionAuthorization
genuinely permits a given ExecutionRequest.

The signature check is pluggable (:class:`AuthorityVerifier`); the reference
implementation uses a deterministic HMAC over the authorization payload for tests and
local development. No cryptographic guarantee is claimed beyond what a configured
verifier actually validates.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional, Protocol, runtime_checkable

from .config import OperationsConfig, TargetPolicy
from .contracts import (
    ExecutionAction,
    ExecutionAuthorization,
    ExecutionDenied,
    ExecutionRequest,
)


@runtime_checkable
class AuthorityVerifier(Protocol):
    """Validates the issuer/signature of an authorization. Pluggable."""

    def verify_signature(self, authorization: ExecutionAuthorization) -> bool:
        ...

    def is_trusted_issuer(self, issuer: Optional[str]) -> bool:
        ...


class ReferenceAuthorityVerifier:
    """Deterministic HMAC verifier for tests/local dev (NOT a production KMS).

    Trusts a fixed set of issuers, each with a shared secret. Real deployments inject
    a verifier backed by a real key-management / signature system.
    """

    def __init__(self, issuer_secrets: Optional[dict] = None, require_signature: bool = True):
        self._secrets = dict(issuer_secrets or {})
        self._require_signature = require_signature

    def is_trusted_issuer(self, issuer: Optional[str]) -> bool:
        if not self._require_signature and issuer is None:
            return True
        return issuer in self._secrets

    def sign(self, authorization: ExecutionAuthorization, issuer: str) -> str:
        secret = self._secrets[issuer]
        return hmac.new(secret.encode(), authorization.signing_payload().encode(),
                        hashlib.sha256).hexdigest()

    def verify_signature(self, authorization: ExecutionAuthorization) -> bool:
        if not self._require_signature and authorization.signature is None:
            return True  # explicitly-unsigned mode (dev only)
        if not authorization.issuer or authorization.issuer not in self._secrets:
            return False
        if not authorization.signature:
            return False
        expected = self.sign(authorization, authorization.issuer)
        return hmac.compare_digest(expected, authorization.signature)


def verify_authorization(
    authorization: Optional[ExecutionAuthorization],
    request: ExecutionRequest,
    config: OperationsConfig,
    verifier: AuthorityVerifier,
    *,
    now: float,
    tenant_id: str,
) -> None:
    """Fail closed: raise ExecutionDenied unless the authorization fully permits the
    request. Returns None when authorized.
    """
    def deny(reason: str, code: str = "denied"):
        raise ExecutionDenied(reason, code)

    if authorization is None:
        deny("no execution authorization supplied", "missing_authorization")

    # Structural / temporal
    if not authorization.authorization_id or not authorization.nonce:
        deny("malformed authorization (missing id/nonce)", "malformed")
    if authorization.is_not_yet_valid(now):
        deny("authorization not yet valid", "not_yet_valid")
    if authorization.is_expired(now):
        deny("authorization expired", "expired")

    # Issuer / signature (fail closed)
    if not verifier.is_trusted_issuer(authorization.issuer):
        deny(f"untrusted issuer: {authorization.issuer!r}", "untrusted_issuer")
    if not verifier.verify_signature(authorization):
        deny("invalid authorization signature", "bad_signature")

    # Tenant
    if authorization.tenant_id != tenant_id:
        deny("authorization tenant mismatch", "tenant_mismatch")

    # Action
    if authorization.permitted_action != request.action:
        deny(f"action mismatch: authorized {authorization.permitted_action!r} "
             f"!= requested {request.action!r}", "action_mismatch")

    # Target
    if (authorization.target_cluster != request.target_cluster
            or authorization.target_namespace != request.target_namespace
            or authorization.target_resource != request.target_resource):
        deny("authorization target mismatch", "target_mismatch")

    # Recommendation binding
    if authorization.recommendation_id != request.recommendation_id:
        deny("recommendation mismatch", "recommendation_mismatch")

    # Bounds
    tr = request.target_replicas
    if tr < authorization.minimum_replicas or tr > authorization.maximum_replicas:
        deny(f"target {tr} outside authorized bounds "
             f"[{authorization.minimum_replicas},{authorization.maximum_replicas}]",
             "bounds_violation")
    if abs(request.delta) > authorization.maximum_delta:
        deny(f"delta {request.delta} exceeds authorized max {authorization.maximum_delta}",
             "delta_violation")

    # Target policy allowlist + global bounds
    tp: TargetPolicy = config.target_policy
    if not tp.cluster_allowed(request.target_cluster):
        deny(f"cluster not allowlisted: {request.target_cluster!r}", "cluster_not_allowed")
    if not tp.namespace_allowed(request.target_namespace):
        deny(f"namespace not allowlisted: {request.target_namespace!r}", "namespace_not_allowed")
    if not tp.resource_allowed(request.target_resource):
        deny(f"resource not allowlisted: {request.target_resource!r}", "resource_not_allowed")
    if tr < tp.min_replicas or tr > tp.max_replicas:
        deny(f"target {tr} outside policy bounds [{tp.min_replicas},{tp.max_replicas}]",
             "policy_bounds_violation")
    if abs(request.delta) > tp.max_replica_delta:
        deny(f"delta {request.delta} exceeds policy max {tp.max_replica_delta}",
             "policy_delta_violation")

    # Stale observation
    if request.observed_at is not None:
        age = now - request.observed_at
        if age < 0 or age > tp.max_observation_age_seconds:
            deny(f"stale observation (age {age:.1f}s > "
                 f"{tp.max_observation_age_seconds}s)", "stale_observation")


__all__ = ["AuthorityVerifier", "ReferenceAuthorityVerifier", "verify_authorization"]

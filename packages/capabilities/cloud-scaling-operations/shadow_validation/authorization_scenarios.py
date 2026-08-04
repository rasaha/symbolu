"""Deterministic synthetic authorization scenarios (local validation only).

Every scenario is evaluated locally against the operations package's immutable
:class:`ExecutionAuthorization` contract. Even a fully valid fixture authorization
yields only :data:`AUTHORIZED_FOR_SHADOW_PLAN` — never permission to execute. All
issuers, secrets and signatures here are deterministic test values with no production
cryptographic assurance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ugence_cloud_scaling_operations.contracts import (
    ExecutionAuthorization,
    ExecutionRequest,
)
from ugence_cloud_scaling_operations.authority import ReferenceAuthorityVerifier

from .contracts import AUTHORIZED_FOR_SHADOW_PLAN

# Deterministic test clock + issuer material (NOT production keys).
FIXED_NOW = 1_700_000_000.0
TEST_ISSUER = "shadow-gov"
TEST_SECRET = "shadow-test-secret"
EXPECTED_TENANT = "tenant-shadow"
EXPECTED_POLICY_VERSION = "policy-v1"
AUTHORIZED_KIND = "Deployment"


def _verifier() -> ReferenceAuthorityVerifier:
    return ReferenceAuthorityVerifier({TEST_ISSUER: TEST_SECRET}, require_signature=True)


@dataclass(frozen=True)
class ShadowAuthorizationResult:
    scenario: str
    result: str
    denial_code: Optional[str]
    denial_reason: Optional[str]
    expected_result: str
    ok: bool

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "result": self.result,
            "denial_code": self.denial_code,
            "denial_reason": self.denial_reason,
            "expected_result": self.expected_result,
            "ok": self.ok,
        }


def evaluate_shadow_authorization(
    authz: Optional[ExecutionAuthorization],
    request: ExecutionRequest,
    *,
    now: float,
    verifier: ReferenceAuthorityVerifier,
    expected_tenant: str,
    expected_policy_version: str,
    authorized_kind: str,
    request_kind: str,
    seen_nonces: Optional[set] = None,
    seen_requests: Optional[Dict[str, str]] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Return (result, denial_code, denial_reason). Fail closed with granular codes."""

    def deny(code: str, reason: str):
        return ("DENIED", code, reason)

    if authz is None:
        return deny("missing_authorization", "no authorization supplied")
    if not authz.authorization_id or not authz.nonce:
        return deny("malformed", "missing authorization_id/nonce")
    if authz.is_not_yet_valid(now):
        return deny("not_yet_valid", "authorization not yet valid")
    if authz.is_expired(now):
        return deny("expired", "authorization expired")
    if not verifier.is_trusted_issuer(authz.issuer):
        return deny("untrusted_issuer", f"issuer {authz.issuer!r} not trusted")
    if not verifier.verify_signature(authz):
        return deny("bad_signature", "invalid signature")
    if authz.tenant_id != expected_tenant:
        return deny("tenant_mismatch", "tenant mismatch")
    if authz.target_cluster != request.target_cluster:
        return deny("cluster_mismatch", "cluster mismatch")
    if authz.target_namespace != request.target_namespace:
        return deny("namespace_mismatch", "namespace mismatch")
    if authorized_kind != request_kind:
        return deny("resource_kind_mismatch", "resource kind mismatch")
    if authz.target_resource != request.target_resource:
        return deny("resource_name_mismatch", "resource name mismatch")
    if authz.permitted_action != request.action:
        return deny("action_mismatch", "action mismatch")
    if authz.recommendation_id != request.recommendation_id:
        return deny("recommendation_mismatch", "recommendation mismatch")
    if authz.policy_version != expected_policy_version:
        return deny("policy_version_mismatch", "policy version mismatch")
    tr = request.target_replicas
    if tr < authz.minimum_replicas or tr > authz.maximum_replicas:
        return deny("bounds_violation", f"target {tr} outside authorized bounds")
    if abs(request.delta) > authz.maximum_delta:
        return deny("delta_violation", f"delta {request.delta} exceeds max")
    if request.observed_at is not None:
        age = now - request.observed_at
        if age < 0 or age > 120.0:
            return deny("stale_observation", f"observation age {age:.1f}s")
    if seen_requests is not None:
        prior = seen_requests.get(authz.idempotency_key)
        if prior is not None and prior != request.digest():
            return deny("reused_authorization_changed_target",
                        "idempotency key reused with a different request")
    if seen_nonces is not None and authz.nonce in seen_nonces:
        return deny("nonce_replay", "authorization nonce replayed")
    return (AUTHORIZED_FOR_SHADOW_PLAN, None, None)


# --------------------------------------------------------------------------- #
# Scenario builders
# --------------------------------------------------------------------------- #

def _base_request(**over) -> ExecutionRequest:
    d = dict(action="scale", target_cluster="fake-cluster", target_namespace="shadow-test",
             target_resource="frontend", current_replicas=3, target_replicas=5,
             recommendation_id="rec-shadow-1", idempotency_key="idem-shadow-1",
             correlation_id="corr-shadow-1", observed_at=FIXED_NOW - 5.0)
    d.update(over)
    return ExecutionRequest(**d)


def _base_authz(*, sign=True, **over) -> ExecutionAuthorization:
    d = dict(
        authorization_id="authz-shadow-1", decision_id="dec-shadow-1",
        recommendation_id="rec-shadow-1", tenant_id=EXPECTED_TENANT, actor_id="ops",
        authority_source=TEST_ISSUER, issued_at=FIXED_NOW - 100.0,
        expires_at=FIXED_NOW + 3600.0, permitted_action="scale",
        target_cluster="fake-cluster", target_namespace="shadow-test",
        target_resource="frontend", current_replicas=3, minimum_replicas=1,
        maximum_replicas=10, maximum_delta=5, reason="load", policy_version=EXPECTED_POLICY_VERSION,
        idempotency_key="idem-shadow-1", nonce="nonce-shadow-1", issuer=TEST_ISSUER)
    d.update(over)
    authz = ExecutionAuthorization(**d)
    if sign:
        sig = ReferenceAuthorityVerifier({TEST_ISSUER: TEST_SECRET}).sign(authz, TEST_ISSUER)
        authz = ExecutionAuthorization(**{**d, "signature": sig})
    return authz


# Each entry: (name, authz, request, request_kind, expected_result)
DENIED = "DENIED"


def _scenarios() -> List[tuple]:
    return [
        ("valid_matching_authorization", _base_authz(), _base_request(),
         AUTHORIZED_KIND, AUTHORIZED_FOR_SHADOW_PLAN),
        ("missing_authorization", None, _base_request(), AUTHORIZED_KIND, DENIED),
        ("expired_authorization", _base_authz(expires_at=FIXED_NOW - 10.0),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("not_yet_valid_authorization", _base_authz(issued_at=FIXED_NOW + 100.0),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("malformed_authorization", _base_authz(nonce="", sign=False),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("tenant_mismatch", _base_authz(tenant_id="tenant-other"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        # Mismatch scenarios: the request is the canonical observed target; only the
        # authorization diverges, so it fails to match what was actually observed.
        ("cluster_mismatch", _base_authz(target_cluster="other-cluster"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("namespace_mismatch", _base_authz(target_namespace="other-ns"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("resource_kind_mismatch", _base_authz(), _base_request(),
         "StatefulSet", DENIED),
        ("resource_name_mismatch", _base_authz(target_resource="backend"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("action_mismatch", _base_authz(permitted_action="rollback"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("replica_bounds_exceeded", _base_authz(maximum_replicas=4),
         _base_request(target_replicas=8, current_replicas=3), AUTHORIZED_KIND, DENIED),
        ("maximum_delta_exceeded", _base_authz(maximum_delta=1),
         _base_request(target_replicas=9, current_replicas=3), AUTHORIZED_KIND, DENIED),
        ("recommendation_mismatch", _base_authz(recommendation_id="rec-other"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("policy_version_mismatch", _base_authz(policy_version="policy-v999"),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("stale_observation", _base_authz(),
         _base_request(observed_at=FIXED_NOW - 9999.0), AUTHORIZED_KIND, DENIED),
        ("untrusted_issuer", _base_authz(issuer="rogue", sign=False),
         _base_request(), AUTHORIZED_KIND, DENIED),
        ("invalid_test_signature", _base_authz(sign=False, signature="deadbeef"),
         _base_request(), AUTHORIZED_KIND, DENIED),
    ]


def run_all_scenarios(now: float = FIXED_NOW) -> List[ShadowAuthorizationResult]:
    """Evaluate every scenario deterministically and return labelled results."""
    verifier = _verifier()
    results: List[ShadowAuthorizationResult] = []
    seen_nonces: set = set()
    seen_requests: Dict[str, str] = {}

    def run(name, authz, request, request_kind, expected):
        result, code, reason = evaluate_shadow_authorization(
            authz, request, now=now, verifier=verifier,
            expected_tenant=EXPECTED_TENANT,
            expected_policy_version=EXPECTED_POLICY_VERSION,
            authorized_kind=AUTHORIZED_KIND, request_kind=request_kind,
            seen_nonces=seen_nonces, seen_requests=seen_requests)
        ok = (result == expected)
        results.append(ShadowAuthorizationResult(name, result, code, reason, expected, ok))
        return result

    # Prime with the valid case, then record its nonce/idempotency for replay tests.
    for name, authz, request, kind, expected in _scenarios():
        run(name, authz, request, kind, expected)

    # Replay + reuse-with-changed-target (stateful; must come after priming).
    valid_authz = _base_authz()
    valid_req = _base_request()
    seen_nonces.add(valid_authz.nonce)
    seen_requests[valid_authz.idempotency_key] = valid_req.digest()
    run("reused_nonce", valid_authz, valid_req, AUTHORIZED_KIND, DENIED)
    run("reused_authorization_changed_target", valid_authz,
        _base_request(target_replicas=4), AUTHORIZED_KIND, DENIED)
    return results


__all__ = [
    "FIXED_NOW",
    "AUTHORIZED_FOR_SHADOW_PLAN",
    "ShadowAuthorizationResult",
    "evaluate_shadow_authorization",
    "run_all_scenarios",
]

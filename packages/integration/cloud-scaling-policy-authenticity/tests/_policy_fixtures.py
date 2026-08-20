"""Genuine builders for the Phase 5B-0B suite. Nothing here is a stub of what is under test.

The issued policy record comes from the Policy Authority's **real** ``issue_policy`` pipeline,
through its own shared test fixtures (``_authority_fixtures``), with a real Ed25519 signature
over the real canonical payload. The Phase 5A candidate, where a test needs one, comes from
the **real** Phase 3 → 4C → 5A chain through Phase 5A's own conftest.

The fakes below exist only to exercise gates the genuine path cannot reach: a port that
raises, a port that answers about a neighbouring coordinate, a port that returns a foreign
type. Each is named for the single gate it exists to reach.
"""

from __future__ import annotations

import importlib.util
import pathlib
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from _authority_fixtures import (  # noqa: F401 - re-exported for the suite
    APPROVING_AUTHORITY,
    ISSUING_AUTHORITY,
    T_AFTER,
    T_BEFORE,
    T_FROM,
    T_MID,
    T_TO,
    Authority,
    make_authority,
    make_policy,
    make_signer,
)
from ugence_policy_authority.api import (
    GLOBAL_TENANT,
    PolicyCoordinate,
    PolicyResolution,
    PolicyResolutionReason,
    uvi_coordinate,
)
from ugence_uvi_policy_contracts.api import PolicyScope

from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityVerifier,
    PolicyAuthorityResolutionPort,
)

ONE_SECOND = timedelta(seconds=1)


def issued(authority: Optional[Authority] = None, **policy_kwargs):
    """A genuine authority with one genuinely issued policy. Returns ``(authority, record)``."""

    authority = authority or make_authority()
    record = authority.issue(make_policy(**policy_kwargs))
    return authority, record


def revoke(authority: Authority, record, *, revoked_at, revocation_id="rev-1"):
    """Genuinely revoke one issued version, through the authority's own signed path."""

    from ugence_policy_authority.api import PolicyRevocationReasonCode, revoke_policy

    return revoke_policy(
        reference=record.coordinate,
        revocation_id=revocation_id,
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=authority.registry,
        adapters=authority.adapters,
        signer=authority.revocation_signer,
        signature_verifier=authority.key_ring,
        revoked_at=revoked_at,
    )


def port_for(authority: Authority, *, approval: bool = False) -> PolicyAuthorityResolutionPort:
    """The production-grade port over a genuine authority's own registry and key ring."""

    return PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        adapters=authority.adapters,
        approval_verifier=authority.approval if approval else None,
    )


def verifier_for(authority: Authority, **kwargs) -> PolicyAuthenticityVerifier:
    """A verifier over a genuine authority. Reference posture unless told otherwise."""

    return PolicyAuthenticityVerifier(resolution_port=port_for(authority), **kwargs)


def coordinate_of(record) -> PolicyCoordinate:
    """The coordinate a genuine record was issued under."""

    return record.coordinate


# --------------------------------------------------------------------------- #
# Named fakes — one gate each, and nothing more
# --------------------------------------------------------------------------- #
@dataclass
class RaisingPort:
    """Reaches the ``VERIFICATION_UNAVAILABLE`` terminal: a port that cannot answer."""

    trust_configuration_digest: str = "0" * 64
    is_production_authoritative: bool = False
    calls: list = field(default_factory=list)

    def resolve_policy_version(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("the policy store is unreachable")


@dataclass
class ForeignTypePort:
    """Reaches ``UNSUPPORTED_EXACT_TYPE``: a port that returns something else entirely."""

    payload: Any = True
    trust_configuration_digest: str = "0" * 64
    is_production_authoritative: bool = False

    def resolve_policy_version(self, **kwargs):
        return self.payload


@dataclass
class SubstitutingPort:
    """Reaches ``RESOLUTION_ANSWERED_ANOTHER_QUESTION``: a port that answers about something else.

    Wraps a genuine port and rewrites one field of the answer, which is exactly the shape of
    a compromised or merely buggy composition-root component: the status still says
    ``RESOLVED``, and the answer is about a different question.
    """

    inner: PolicyAuthorityResolutionPort
    substitute_coordinate: Optional[PolicyCoordinate] = None
    substitute_as_of: Optional[Any] = None

    @property
    def trust_configuration_digest(self) -> str:
        return self.inner.trust_configuration_digest

    @property
    def is_production_authoritative(self) -> bool:
        return self.inner.is_production_authoritative

    def resolve_policy_version(self, *, coordinate, expected_reference_tenant_id, as_of):
        answer = self.inner.resolve_policy_version(
            coordinate=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=as_of,
        )
        if self.substitute_coordinate is not None:
            object.__setattr__(answer, "requested_coordinate", self.substitute_coordinate)
        if self.substitute_as_of is not None:
            object.__setattr__(answer, "as_of", self.substitute_as_of)
        return answer


@dataclass
class UnresolvedPort:
    """Answers ``UNRESOLVED`` with a chosen reason, to walk the reason→outcome mapping."""

    reason: PolicyResolutionReason = PolicyResolutionReason.NOT_FOUND
    trust_configuration_digest: str = "0" * 64
    is_production_authoritative: bool = False

    def resolve_policy_version(self, *, coordinate, expected_reference_tenant_id, as_of):
        return PolicyResolution.unresolved(
            self.reason, requested_coordinate=coordinate, as_of=as_of
        )


# --------------------------------------------------------------------------- #
# The genuine Phase 5A candidate, built through Phase 5A's own conftest
# --------------------------------------------------------------------------- #
_PHASE_5A_BUILDERS = None


def _find_repo_root():
    """The monorepo root, or ``None``. Same marker search the package conftest performs.

    Repeated here rather than imported: ``import conftest`` resolves to whichever conftest
    pytest put on the path first, which is not necessarily this package's.
    """

    import os

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    here = pathlib.Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "packages" / "policy-authority").is_dir():
            return candidate
    return None


def phase5a_builders():
    """Load Phase 5A's own conftest as a uniquely named module, or return ``None``.

    Loaded by file path under a distinct module name so it cannot collide with this
    package's ``conftest``. Returns ``None`` when the Phase 5A test tree is absent — the
    ordinary case outside a checkout — so the candidate-dependent tests skip rather than
    fail.
    """

    global _PHASE_5A_BUILDERS
    if _PHASE_5A_BUILDERS is not None:
        return _PHASE_5A_BUILDERS
    repo = _find_repo_root()
    if repo is None:
        return None
    path = (
        repo
        / "packages"
        / "integration"
        / "cloud-scaling-authorization-contracts"
        / "tests"
        / "conftest.py"
    )
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_phase5a_conftest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _PHASE_5A_BUILDERS = module
    return module


def genuine_candidate():
    """One genuine ``CapacityAuthorizationCandidate``, or ``None`` outside a checkout."""

    builders = phase5a_builders()
    if builders is None:
        return None
    from ugence_cloud_scaling_authorization_contracts import (
        build_capacity_authorization_candidate,
    )

    projection = builders.build_projection()
    decision = builders.build_decision(projection)
    attestation = builders.build_attestation(
        recommendation_digest=projection.recommendation_digest
    )
    scope = builders.build_target_scope(projection)
    binding = builders.build_policy_binding(scope)
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=binding,
        target_scope=scope,
    )


__all__ = [
    "APPROVING_AUTHORITY",
    "ISSUING_AUTHORITY",
    "GLOBAL_TENANT",
    "ONE_SECOND",
    "PolicyScope",
    "T_AFTER",
    "T_BEFORE",
    "T_FROM",
    "T_MID",
    "T_TO",
    "Authority",
    "ForeignTypePort",
    "RaisingPort",
    "SubstitutingPort",
    "UnresolvedPort",
    "coordinate_of",
    "genuine_candidate",
    "issued",
    "make_authority",
    "make_policy",
    "make_signer",
    "phase5a_builders",
    "port_for",
    "revoke",
    "uvi_coordinate",
    "verifier_for",
]

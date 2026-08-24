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
from datetime import datetime, timedelta, timezone
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
#: An instant inside BOTH the fixture policy's effective window and the fixture candidate's
#: own validity (5B-2, R-2). Before gate 13 existed the suite verified candidate-bearing
#: determinations at ``T_MID`` — 2026-06-01, five months after the fixture candidate's
#: recommendation expired at 00:08:10 on 2026-01-01. Nothing objected, which is precisely the
#: residual: the instant was recorded beside the candidate's timestamps and never compared
#: against them. The admissible window is ``[00:05:00, 00:08:10]`` — opened by the decision
#: evaluation, closed by the recommendation's expiry — and this sits inside it.
T_CANDIDATE = datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc)


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


# --------------------------------------------------------------------------- #
# A genuine capacity-bounds family, built here rather than imported (5B-3, R-8)
# --------------------------------------------------------------------------- #
# The bounds gates must be exercised against a real issuance under a real adapter. This
# suite deliberately does **not** import
# ``ugence-cloud-scaling-capacity-bounds-policy`` to get one: the verifier is downstream of
# the family it verifies, and a test-time import would quietly invert that boundary and
# couple this package's fixtures to a distribution its source may not name.
#
# What is under test is that the verifier reads the *projection shape* structurally — the
# family's coordinate component and the four keys of each bound — not that it agrees with
# one particular package's classes. Building an independent family here measures exactly
# that, and would catch the real distribution drifting away from the shape this profile
# knows how to state.


@dataclass(frozen=True)
class _BoundsMetadata:
    policy_id: str
    version: str
    content_digest: str
    scope: str
    lifecycle_state: str
    tenant_id: str = ""
    supersedes_ref: str = ""
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


@dataclass(frozen=True)
class _Bound:
    action_type: str
    resource_class: str
    max_permitted_magnitude: int
    max_permitted_delta: int


@dataclass(frozen=True)
class _BoundsPolicy:
    metadata: _BoundsMetadata
    bounds: tuple


BOUNDS_FAMILY = "cloud_scaling.capacity_bounds"
BOUNDS_ADAPTER_ID = "ugence.cloud-scaling.capacity-bounds/v1"
BOUNDS_POLICY_TYPE = "CapacityBoundsPolicy"

DEFAULT_TEST_BOUNDS = (
    _Bound(
        action_type="cloud_scaling.scale_out",
        resource_class="",
        max_permitted_magnitude=100,
        max_permitted_delta=25,
    ),
)


class _BoundsAdapter:
    """A genuine ``PolicyFamilyAdapter`` for the capacity-bounds family."""

    @property
    def adapter_id(self) -> str:
        return BOUNDS_ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is _BoundsPolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if type(reference) is not _BoundsMetadata:
            return None
        return _bounds_coordinate(reference)

    def describe(self, artifact: object):
        from ugence_policy_authority.api import PolicyArtifactDescriptor, to_canonical_obj

        body = to_canonical_obj(artifact, path="$")
        metadata = dict(body["metadata"])
        metadata.pop("content_digest")
        body = dict(body)
        body["metadata"] = metadata
        return PolicyArtifactDescriptor(
            adapter_id=BOUNDS_ADAPTER_ID,
            policy_type=BOUNDS_POLICY_TYPE,
            coordinate=_bounds_coordinate(artifact.metadata),
            declared_content_digest=artifact.metadata.content_digest,
            canonical_projection=body,
            lifecycle_label=artifact.metadata.lifecycle_state,
            lifecycle_is_active=artifact.metadata.lifecycle_state == "APPROVED_ACTIVE",
            supersedes_ref=artifact.metadata.supersedes_ref,
            effective_from=artifact.metadata.effective_from,
            effective_to=artifact.metadata.effective_to,
        )


def _bounds_coordinate(metadata: "_BoundsMetadata") -> PolicyCoordinate:
    return PolicyCoordinate(
        policy_family=BOUNDS_FAMILY,
        policy_id=metadata.policy_id,
        version=metadata.version,
        content_digest=metadata.content_digest,
        scope=metadata.scope,
        tenant_id=metadata.tenant_id,
    )


BOUNDS_ADAPTER = _BoundsAdapter()


def make_bounds_policy(*, bounds: tuple = DEFAULT_TEST_BOUNDS, **meta) -> "_BoundsPolicy":
    """A capacity-bounds artifact whose declared digest genuinely binds its own body."""

    fields = dict(
        policy_id="cloud-scaling-capacity-bounds",
        version="1.0.0",
        scope="GLOBAL",
        lifecycle_state="APPROVED_ACTIVE",
        tenant_id=GLOBAL_TENANT,
        effective_from=T_FROM,
        effective_to=T_TO,
    )
    fields.update(meta)
    draft = _BoundsPolicy(
        metadata=_BoundsMetadata(content_digest="0" * 64, **fields), bounds=bounds
    )
    digest = BOUNDS_ADAPTER.describe(draft).body_digest()
    return _BoundsPolicy(
        metadata=_BoundsMetadata(content_digest=digest, **fields), bounds=bounds
    )


def bounds_authority() -> Authority:
    """An authority whose only registered family is capacity bounds."""

    from ugence_policy_authority.api import AdapterRegistry

    return make_authority(adapters=AdapterRegistry([BOUNDS_ADAPTER]))


def issued_bounds(**policy_kwargs):
    """A genuine authority with one genuinely issued bounds policy."""

    authority = bounds_authority()
    policy = make_bounds_policy(**policy_kwargs)
    record = authority.issue(policy)
    return authority, record


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


def genuine_candidate(record=None, **coordinate_overrides):
    """One genuine ``CapacityAuthorizationCandidate``, or ``None`` outside a checkout.

    With ``record``, the candidate's policy coordinate is the coordinate that record was
    genuinely issued under — which is what makes reconciliation testable against a real
    determination rather than against a coordinate invented to match. Without one, the Phase
    5A fixture's own coordinate is used, and a determination about any other policy will not
    reconcile against it.
    """

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
    coordinate_kwargs = dict(coordinate_overrides)
    if record is not None:
        coordinate = record.coordinate
        coordinate_kwargs.setdefault("policy_family", coordinate.policy_family)
        coordinate_kwargs.setdefault("policy_id", coordinate.policy_id)
        coordinate_kwargs.setdefault("policy_version", coordinate.version)
        coordinate_kwargs.setdefault("policy_scope", coordinate.scope)
        coordinate_kwargs.setdefault("policy_tenant_id", coordinate.tenant_id)
        coordinate_kwargs.setdefault("policy_body_digest", record.policy_body_digest)
        coordinate_kwargs.setdefault("issuing_authority_id", record.issuing_authority_id)
        coordinate_kwargs.setdefault("key_id", record.key_id)
        coordinate_kwargs.setdefault("signature_alg", record.signature_alg)
    binding = builders.build_policy_binding(
        scope,
        policy_id=coordinate_kwargs.get("policy_id", "cloud-scaling.capacity-bounds"),
        policy_version=coordinate_kwargs.get("policy_version", "3.1.0"),
    )
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=binding,
        policy_coordinate_binding=builders.build_policy_coordinate_binding(
            scope, **coordinate_kwargs
        ),
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
    "T_CANDIDATE",
    "make_signer",
    "phase5a_builders",
    "port_for",
    "revoke",
    "uvi_coordinate",
    "verifier_for",
]

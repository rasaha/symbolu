"""A second policy family works with **no** change to core code (ADR §10.2).

This module defines a synthetic policy family that has nothing to do with UVI —
different fields, different lifecycle vocabulary, different reference type — and
drives the full authority lifecycle with it: issue, resolve, revoke, and every
fail-closed path. Nothing in ``core/`` is modified, subclassed, or monkeypatched.

If the core ever grows a UVI branch, this file stops passing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

import pytest

from _authority_fixtures import (
    APPROVING_AUTHORITY,
    ONE_SECOND,
    T_FROM,
    T_MID,
    T_TO,
    RecordingApprovalVerifier,
    approval_evidence,
    make_signer,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyArtifactDescriptor,
    PolicyCoordinate,
    PolicyFamilyAdapter,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    UnsupportedPolicyArtifactError,
    UnsupportedSupersessionError,
    UviPolicyFamilyAdapter,
    default_uvi_adapters,
    issue_policy,
    resolve_policy,
    revoke_policy,
)
from ugence_policy_authority.core.canonical import to_canonical_obj

ROSTER_ADAPTER_ID = "example.roster-policy-family/v1"


# --------------------------------------------------------------------------- #
# A synthetic second policy family, entirely unrelated to UVI
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RosterReference:
    roster_id: str
    revision: str
    body_digest: str
    region: str = "GLOBAL"
    tenant: str = ""


@dataclass(frozen=True)
class RosterPolicy:
    """A made-up family: shift rosters. No UVI concept appears anywhere."""

    roster_id: str
    revision: str
    declared_digest: str
    shifts: tuple = ()
    state: str = "LIVE"
    region: str = "GLOBAL"
    tenant: str = ""
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    replaces: str = ""


class RosterAdapter:
    """A complete second adapter, written against the public protocol only."""

    @property
    def adapter_id(self) -> str:
        return ROSTER_ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is RosterPolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, RosterReference):
            return None
        return PolicyCoordinate(
            policy_family="ROSTER",
            policy_id=reference.roster_id,
            version=reference.revision,
            content_digest=reference.body_digest,
            scope=reference.region,
            tenant_id=reference.tenant,
        )

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if not self.recognizes(artifact):
            raise UnsupportedPolicyArtifactError("not a RosterPolicy")
        projection = to_canonical_obj(artifact)
        projection = {k: v for k, v in projection.items() if k != "declared_digest"}
        return PolicyArtifactDescriptor(
            adapter_id=ROSTER_ADAPTER_ID,
            policy_type=type(artifact).__name__,
            coordinate=PolicyCoordinate(
                policy_family="ROSTER",
                policy_id=artifact.roster_id,
                version=artifact.revision,
                content_digest=artifact.declared_digest,
                scope=artifact.region,
                tenant_id=artifact.tenant,
            ),
            declared_content_digest=artifact.declared_digest,
            canonical_projection=projection,
            lifecycle_label=artifact.state,
            lifecycle_is_active=artifact.state == "LIVE",
            supersedes_ref=artifact.replaces,
            effective_from=artifact.opens_at,
            effective_to=artifact.closes_at,
        )


ADAPTER = RosterAdapter()


def make_roster(**overrides) -> RosterPolicy:
    base = dict(
        roster_id="roster-1",
        revision="3",
        declared_digest="0" * 64,
        shifts=("mon-am", "tue-pm"),
        opens_at=T_FROM,
        closes_at=T_TO,
    )
    base.update(overrides)
    draft = RosterPolicy(**base)
    base["declared_digest"] = ADAPTER.describe(draft).body_digest()
    return RosterPolicy(**base)


def reference_of(roster: RosterPolicy) -> RosterReference:
    return RosterReference(
        roster_id=roster.roster_id,
        revision=roster.revision,
        body_digest=roster.declared_digest,
        region=roster.region,
        tenant=roster.tenant,
    )


@pytest.fixture()
def wiring():
    signer = make_signer(authority_id="ugence.policy-authority", key_id="k-issue", seed=3)
    revoker = make_signer(authority_id="ugence.policy-authority.rev", key_id="k-rev", seed=5)
    ring = PolicyKeyRing(
        [
            signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
            revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,)),
        ]
    )
    return {
        "signer": signer,
        "revoker": revoker,
        "ring": ring,
        "registry": InMemoryPolicyRegistry(),
        "approval": RecordingApprovalVerifier(),
        # A registry holding BOTH adapters: the core resolves each by protocol.
        "adapters": AdapterRegistry((UviPolicyFamilyAdapter(), ADAPTER)),
    }


def _issue(roster, wiring, **kwargs):
    return issue_policy(
        policy=roster,
        record_id=kwargs.pop("record_id", "roster-rec-1"),
        approval=kwargs.pop("approval", approval_evidence()),
        approval_verifier=wiring["approval"],
        signer=wiring["signer"],
        registry=wiring["registry"],
        adapters=wiring["adapters"],
        issued_at=kwargs.pop("issued_at", T_MID),
        **kwargs,
    )


def _resolve(reference, wiring, *, as_of=T_MID, tenant="", **kwargs):
    return resolve_policy(
        reference=reference,
        expected_reference_tenant_id=tenant,
        as_of=as_of,
        registry=wiring["registry"],
        signature_verifier=wiring["ring"],
        adapters=wiring["adapters"],
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Full lifecycle on the second family
# --------------------------------------------------------------------------- #
def test_the_adapter_satisfies_the_public_protocol():
    assert isinstance(ADAPTER, PolicyFamilyAdapter)


def test_a_second_family_issues_and_resolves_with_no_core_change(wiring):
    roster = make_roster()
    record = _issue(roster, wiring)
    assert record.adapter_id == ROSTER_ADAPTER_ID
    assert record.coordinate.policy_family == "ROSTER"

    result = _resolve(reference_of(roster), wiring)
    assert result.status is PolicyResolutionStatus.RESOLVED
    assert result.policy is roster


def test_both_families_coexist_in_one_registry(wiring):
    from _authority_fixtures import make_policy
    from ugence_policy_authority.api import uvi_coordinate

    roster = make_roster()
    uvi = make_policy()
    _issue(roster, wiring, record_id="r-roster")
    _issue(uvi, wiring, record_id="r-uvi")

    assert _resolve(reference_of(roster), wiring).resolved
    assert _resolve(uvi.reference, wiring).resolved
    # Their coordinates are distinct namespaces.
    assert uvi_coordinate(uvi.reference).policy_family == "DOMAIN"


def test_digest_binding_applies_to_the_second_family(wiring):
    from ugence_policy_authority.api import PolicyDigestMismatchError

    roster = replace(make_roster(), shifts=("wed-am",))
    with pytest.raises(PolicyDigestMismatchError):
        _issue(roster, wiring)


def test_supersession_rejection_applies_to_the_second_family(wiring):
    with pytest.raises(UnsupportedSupersessionError):
        _issue(make_roster(replaces="roster-1@2"), wiring)
    assert wiring["approval"].calls == []
    assert len(wiring["registry"]._issued) == 0


def test_lifecycle_and_effective_period_apply_to_the_second_family(wiring):
    from ugence_policy_authority.api import PolicyIssuanceError

    with pytest.raises(PolicyIssuanceError):
        _issue(make_roster(state="DRAFT"), wiring)

    roster = make_roster()
    _issue(roster, wiring)
    assert _resolve(reference_of(roster), wiring, as_of=T_FROM).resolved
    assert _resolve(reference_of(roster), wiring, as_of=T_FROM - ONE_SECOND).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )
    assert _resolve(reference_of(roster), wiring, as_of=T_TO).reason is (
        PolicyResolutionReason.EXPIRED
    )


def test_signed_revocation_applies_to_the_second_family(wiring):
    roster = make_roster(closes_at=None)
    _issue(roster, wiring)
    revoke_policy(
        reference=reference_of(roster),
        revocation_id="roster-rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=wiring["registry"],
        adapters=wiring["adapters"],
        signer=wiring["revoker"],
        signature_verifier=wiring["ring"],
        revoked_at=T_MID,
    )
    assert _resolve(reference_of(roster), wiring).reason is PolicyResolutionReason.REVOKED


def test_an_unregistered_family_is_refused(wiring):
    @dataclass(frozen=True)
    class UnknownPolicy:
        x: int = 1

    with pytest.raises(UnsupportedPolicyArtifactError):
        _issue(UnknownPolicy(), wiring)


def test_a_registry_without_the_second_adapter_does_not_recognize_it():
    only_uvi = default_uvi_adapters()
    with pytest.raises(UnsupportedPolicyArtifactError):
        only_uvi.describe(make_roster())


def test_duplicate_adapter_ids_are_rejected():
    from ugence_policy_authority.api import PolicyAuthorityRequestError

    with pytest.raises(PolicyAuthorityRequestError, match="duplicate adapter_id"):
        AdapterRegistry((RosterAdapter(), RosterAdapter()))


def test_an_object_that_is_not_an_adapter_is_rejected():
    from ugence_policy_authority.api import PolicyAuthorityRequestError

    with pytest.raises(PolicyAuthorityRequestError, match="PolicyFamilyAdapter"):
        AdapterRegistry((object(),))


def test_registering_a_second_adapter_required_no_core_source_change():
    """Belt and braces: the core still names no family, including this one."""

    import pathlib

    import ugence_policy_authority

    core = pathlib.Path(ugence_policy_authority.__file__).resolve().parent / "core"
    for path in core.rglob("*.py"):
        source = path.read_text()
        assert "Roster" not in source, path.name
        assert "GeographyPolicy" not in source, path.name

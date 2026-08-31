"""`ACC-LC-IA-4` — structured policy-version supersession, end to end.

The full fail-closed matrix the ruling requires, plus the happy path: a v2
issued over a v1 in one signed act, after which the predecessor stops resolving
and stays readable.

Driven through a **synthetic family**, on `test_second_adapter.py`'s exact
precedent, for two reasons. It proves the capability is family-neutral core
behaviour rather than a UVI branch; and `ACC-LC-IA-5` bounds the change set to
the shared authority, so no shipped artifact contract is edited to carry a
predecessor coordinate. `[G]` A consequence, recorded rather than hidden: no
*shipped* adapter yet produces `supersedes_coordinate`, so no shipped family can
supersede until that family opts in — a separate authorization.

Every key is ephemeral, minted at run time from process randomness.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from _authority_fixtures import (
    ONE_SECOND,
    RecordingApprovalVerifier,
    approval_evidence,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyArtifactDescriptor,
    PolicyAuthorityRequestError,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    PolicySupersessionError,
    PolicySupersessionRecord,
    SigningKey,
    SUPERSESSION_PREDECESSOR_INADMISSIBLE,
    UnsupportedPolicyArtifactError,
    UnsupportedSupersessionError,
    issue_policy,
    resolve_policy,
    revoke_policy,
)
from ugence_policy_authority.core.canonical import to_canonical_obj

LEDGER_ADAPTER_ID = "example.ledger-policy-family/v1"

T_V1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
T_V2 = datetime(2026, 4, 1, tzinfo=timezone.utc)
T_LATER = datetime(2026, 5, 1, tzinfo=timezone.utc)
T_TO = datetime(2028, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# A synthetic family whose artifacts can name an exact predecessor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LedgerReference:
    ledger_id: str
    revision: str
    body_digest: str
    region: str = "GLOBAL"
    tenant: str = ""


@dataclass(frozen=True)
class LedgerPolicy:
    ledger_id: str
    revision: str
    declared_digest: str
    rules: tuple = ()
    state: str = "LIVE"
    region: str = "GLOBAL"
    tenant: str = ""
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    replaces: str = ""
    #: The exact predecessor, carried as a reference the adapter maps to a
    #: coordinate. Excluded from the body projection: what a version replaces is
    #: a claim about the registry, not part of the bytes it is identified by.
    supersedes: Optional[LedgerReference] = None


class LedgerAdapter:
    @property
    def adapter_id(self) -> str:
        return LEDGER_ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is LedgerPolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, LedgerReference):
            return None
        return PolicyCoordinate(
            policy_family="LEDGER",
            policy_id=reference.ledger_id,
            version=reference.revision,
            content_digest=reference.body_digest,
            scope=reference.region,
            tenant_id=reference.tenant,
        )

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if not self.recognizes(artifact):
            raise UnsupportedPolicyArtifactError("not a LedgerPolicy")
        projection = to_canonical_obj(artifact)
        projection = {
            k: v
            for k, v in projection.items()
            if k not in ("declared_digest", "supersedes")
        }
        return PolicyArtifactDescriptor(
            adapter_id=LEDGER_ADAPTER_ID,
            policy_type=type(artifact).__name__,
            coordinate=PolicyCoordinate(
                policy_family="LEDGER",
                policy_id=artifact.ledger_id,
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
            supersedes_coordinate=self.coordinate_for(artifact.supersedes),
            effective_from=artifact.opens_at,
            effective_to=artifact.closes_at,
        )


ADAPTER = LedgerAdapter()


def make_ledger(**overrides) -> LedgerPolicy:
    base = dict(
        ledger_id="ledger-1",
        revision="1",
        declared_digest="0" * 64,
        rules=("a", "b"),
        opens_at=T_V1,
        closes_at=T_TO,
    )
    base.update(overrides)
    draft = LedgerPolicy(**base)
    base["declared_digest"] = ADAPTER.describe(draft).body_digest()
    return LedgerPolicy(**base)


def reference_of(policy: LedgerPolicy) -> LedgerReference:
    return LedgerReference(
        ledger_id=policy.ledger_id,
        revision=policy.revision,
        body_digest=policy.declared_digest,
        region=policy.region,
        tenant=policy.tenant,
    )


@dataclass
class World:
    signer: Ed25519PolicySigner
    revoker: Ed25519PolicySigner
    key_ring: PolicyKeyRing
    registry: InMemoryPolicyRegistry
    approval: RecordingApprovalVerifier
    adapters: AdapterRegistry

    def issue(self, policy, *, record_id, issued_at=T_V1, **kwargs):
        return issue_policy(
            policy=policy,
            record_id=record_id,
            approval=approval_evidence(),
            approval_verifier=self.approval,
            signer=self.signer,
            registry=self.registry,
            adapters=self.adapters,
            issued_at=issued_at,
            signature_verifier=self.key_ring,
            **kwargs,
        )

    def resolve(self, reference, *, as_of=T_LATER):
        return resolve_policy(
            reference=reference,
            expected_reference_tenant_id="",
            as_of=as_of,
            registry=self.registry,
            signature_verifier=self.key_ring,
            adapters=self.adapters,
        )


def make_world() -> World:
    """Ephemeral custody: both seeds come from process randomness."""

    signer = Ed25519PolicySigner(
        authority_id="ugence.policy-authority",
        key_id="issuance-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    revoker = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.revocation",
        key_id="revocation-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    return World(
        signer=signer,
        revoker=revoker,
        key_ring=PolicyKeyRing(
            [
                signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
                revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,)),
            ]
        ),
        registry=InMemoryPolicyRegistry(),
        approval=RecordingApprovalVerifier(),
        adapters=AdapterRegistry((ADAPTER,)),
    )


def _v1_and_v2(world) -> tuple:
    v1 = make_ledger(revision="1")
    world.issue(v1, record_id="rec-v1")
    v2 = make_ledger(revision="2", rules=("a", "b", "c"), supersedes=reference_of(v1))
    return v1, v2


# --------------------------------------------------------------------------- #
# The happy path — one signed act
# --------------------------------------------------------------------------- #
def test_a_successor_supersedes_its_predecessor_in_one_act():
    world = make_world()
    v1, v2 = _v1_and_v2(world)

    record = world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    assert record.coordinate.version == "2"
    # The successor resolves.
    assert world.resolve(reference_of(v2)).resolved
    # The predecessor does not, and says why.
    denied = world.resolve(reference_of(v1))
    assert denied.status is PolicyResolutionStatus.UNRESOLVED
    assert denied.reason is PolicyResolutionReason.SUPERSEDED
    assert "ledger-1@2" in denied.detail


def test_the_superseded_predecessor_stays_readable():
    """Superseded is not erased: the issued record is still there, unchanged."""

    world = make_world()
    v1, v2 = _v1_and_v2(world)
    predecessor = ADAPTER.describe(v1).coordinate
    before = world.registry.get_issued(predecessor)

    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    assert world.registry.get_issued(predecessor) is before


def test_the_supersession_record_names_both_coordinates_and_is_signed():
    world = make_world()
    v1, v2 = _v1_and_v2(world)
    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    (record,) = world.registry.supersessions_for(ADAPTER.describe(v1).coordinate)
    assert isinstance(record, PolicySupersessionRecord)
    assert record.coordinate == ADAPTER.describe(v1).coordinate
    assert record.successor_coordinate == ADAPTER.describe(v2).coordinate
    assert record.signature
    assert record.superseded_at == T_V2


def test_supersession_is_not_revocation():
    """Separate stores, separate concepts; neither implies the other."""

    world = make_world()
    v1, v2 = _v1_and_v2(world)
    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    predecessor = ADAPTER.describe(v1).coordinate
    assert world.registry.supersessions_for(predecessor)
    assert world.registry.revocations_for(predecessor) == ()


# --------------------------------------------------------------------------- #
# The six refusals of ACC-LC-IA-3 — each before anything is signed or stored
# --------------------------------------------------------------------------- #
def test_a_self_referential_predecessor_is_refused():
    world = make_world()
    v1 = make_ledger(revision="1")
    self_ref = replace(v1, supersedes=reference_of(v1))
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(self_ref, record_id="rec-self", supersession_id="sup-1")
    assert SUPERSESSION_PREDECESSOR_INADMISSIBLE in str(exc.value)


def test_a_cross_tenant_predecessor_is_refused():
    world = make_world()
    other = make_ledger(revision="1", tenant="tenant-a")
    world.issue(other, record_id="rec-a")
    v2 = make_ledger(revision="2", tenant="", supersedes=reference_of(other))
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", supersession_id="sup-1")
    assert "another tenant" in str(exc.value)


def test_a_cross_scope_predecessor_is_refused():
    world = make_world()
    other = make_ledger(revision="1", region="EU")
    world.issue(other, record_id="rec-eu")
    v2 = make_ledger(revision="2", region="GLOBAL", supersedes=reference_of(other))
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", supersession_id="sup-1")
    assert "another scope" in str(exc.value)


def test_an_absent_predecessor_is_refused():
    world = make_world()
    never_issued = make_ledger(revision="1")
    v2 = make_ledger(revision="2", supersedes=reference_of(never_issued))
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", supersession_id="sup-1")
    assert "never issued" in str(exc.value)


def test_a_revoked_predecessor_is_refused():
    world = make_world()
    v1, v2 = _v1_and_v2(world)
    revoke_policy(
        reference=reference_of(v1),
        revocation_id="rev-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=world.registry,
        adapters=world.adapters,
        signer=world.revoker,
        signature_verifier=world.key_ring,
        revoked_at=T_V1 + ONE_SECOND,
    )
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")
    assert "already revoked" in str(exc.value)


def test_an_already_superseded_predecessor_is_refused():
    """A version is superseded once or not at all."""

    world = make_world()
    v1, v2 = _v1_and_v2(world)
    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    rival = make_ledger(revision="3", rules=("z",), supersedes=reference_of(v1))
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(rival, record_id="rec-v3", issued_at=T_LATER, supersession_id="sup-2")
    assert "already superseded" in str(exc.value)


# --------------------------------------------------------------------------- #
# Nothing is signed or stored by a refusal
# --------------------------------------------------------------------------- #
def test_a_refused_supersession_stores_nothing_and_signs_nothing():
    world = make_world()
    v1, _ = _v1_and_v2(world)
    calls_before = len(world.approval.calls)
    issued_before = dict(world.registry._issued)

    orphan = make_ledger(revision="9", supersedes=reference_of(make_ledger(revision="8")))
    with pytest.raises(PolicySupersessionError):
        world.issue(orphan, record_id="rec-9", supersession_id="sup-9")

    assert world.approval.calls == world.approval.calls[: len(world.approval.calls)]
    assert len(world.approval.calls) == calls_before, "approval verifier was invoked"
    assert dict(world.registry._issued) == issued_before
    assert world.registry.supersessions_for(ADAPTER.describe(v1).coordinate) == ()


def test_the_predecessor_still_resolves_after_a_refused_supersession():
    """Blast radius: a refused successor leaves the predecessor untouched."""

    world = make_world()
    v1, _ = _v1_and_v2(world)
    orphan = make_ledger(revision="9", supersedes=reference_of(make_ledger(revision="8")))
    with pytest.raises(PolicySupersessionError):
        world.issue(orphan, record_id="rec-9", supersession_id="sup-9")

    assert world.resolve(reference_of(v1)).resolved


# --------------------------------------------------------------------------- #
# Request-shape rules for the new parameters
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("supersession_id", ["", "   ", None])
def test_a_structured_predecessor_requires_a_supersession_id(supersession_id):
    world = make_world()
    _, v2 = _v1_and_v2(world)
    with pytest.raises(PolicyAuthorityRequestError):
        world.issue(
            v2, record_id="rec-v2", issued_at=T_V2, supersession_id=supersession_id
        )


def test_a_structured_predecessor_requires_a_signature_verifier():
    world = make_world()
    _, v2 = _v1_and_v2(world)
    with pytest.raises(PolicyAuthorityRequestError):
        issue_policy(
            policy=v2,
            record_id="rec-v2",
            approval=approval_evidence(),
            approval_verifier=world.approval,
            signer=world.signer,
            registry=world.registry,
            adapters=world.adapters,
            issued_at=T_V2,
            supersession_id="sup-1",
            signature_verifier=None,
        )


# --------------------------------------------------------------------------- #
# The unstructured refusal is untouched (ACC-LC-IA surface: no relaxation)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("replaces", ["ledger-1@1", "latest", "  padded  "])
def test_the_unstructured_string_is_still_refused(replaces):
    world = make_world()
    v1, _ = _v1_and_v2(world)
    v2 = make_ledger(revision="2", replaces=replaces, supersedes=reference_of(v1))
    with pytest.raises(UnsupportedSupersessionError):
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")


def test_the_unstructured_refusal_precedes_the_structured_check():
    """An artifact carrying both is rejected on the string, exactly as today —
    the structured path never softens the older refusal."""

    world = make_world()
    absent = make_ledger(revision="8")
    v2 = make_ledger(revision="2", replaces="anything", supersedes=reference_of(absent))
    with pytest.raises(UnsupportedSupersessionError):
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")


# --------------------------------------------------------------------------- #
# Integrity — a stored supersession is never trusted because it is stored
# --------------------------------------------------------------------------- #
def test_a_tampered_supersession_fails_closed_rather_than_being_ignored():
    world = make_world()
    v1, v2 = _v1_and_v2(world)
    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    predecessor = ADAPTER.describe(v1).coordinate
    (stored,) = world.registry.supersessions_for(predecessor)
    world.registry._supersessions[predecessor] = replace(
        stored, signature=b"\x00" * len(stored.signature)
    )

    denied = world.resolve(reference_of(v1))
    assert denied.status is PolicyResolutionStatus.UNRESOLVED
    assert denied.reason is PolicyResolutionReason.SUPERSESSION_INTEGRITY_INVALID


def test_a_record_cannot_supersede_itself_even_if_hand_assembled():
    world = make_world()
    v1, _ = _v1_and_v2(world)
    coordinate = ADAPTER.describe(v1).coordinate
    with pytest.raises(PolicyAuthorityRequestError):
        PolicySupersessionRecord(
            supersession_id="sup-x",
            coordinate=coordinate,
            successor_coordinate=coordinate,
            superseding_authority_id="a",
            key_id="k",
            signature_alg="ed25519",
            signature=b"x",
            superseded_at=T_V2,
        )


def test_an_unsigned_supersession_record_is_unconstructible():
    world = make_world()
    v1, v2 = _v1_and_v2(world)
    with pytest.raises(PolicyAuthorityRequestError):
        PolicySupersessionRecord(
            supersession_id="sup-x",
            coordinate=ADAPTER.describe(v1).coordinate,
            successor_coordinate=ADAPTER.describe(v2).coordinate,
            superseding_authority_id="a",
            key_id="k",
            signature_alg="ed25519",
            signature=b"",
            superseded_at=T_V2,
        )


# --------------------------------------------------------------------------- #
# Atomicity — one act, both records or neither
# --------------------------------------------------------------------------- #
def test_a_conflicting_supersession_rolls_back_the_issuance():
    """If the supersession append conflicts, the successor is not left stored:
    a successor whose predecessor still resolves is the state this prevents."""

    world = make_world()
    v1, v2 = _v1_and_v2(world)
    predecessor = ADAPTER.describe(v1).coordinate
    successor = ADAPTER.describe(v2).coordinate

    # A different successor already superseded v1 — inserted directly, so the
    # step-4 read cannot see it as the same record the act would write.
    world.registry._supersessions[predecessor] = PolicySupersessionRecord(
        supersession_id="sup-other",
        coordinate=predecessor,
        successor_coordinate=replace(successor, version="99"),
        superseding_authority_id="ugence.policy-authority",
        key_id="issuance-key-1",
        signature_alg="ed25519",
        signature=b"\x01" * 64,
        superseded_at=T_V2,
    )
    world.registry._supersession_bytes[predecessor] = b"sentinel"

    with pytest.raises(Exception):
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    assert world.registry.get_issued(successor) is None, "successor was left stored"

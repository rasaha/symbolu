"""`ACC-OVL-1` – `ACC-OVL-8` — the family-neutral exclusivity seam, end to end.

Refusal at issuance, refusal at resolution, the supersession exception, and the
properties the ruling turns on: that **no order breaks a tie**, that a family
projecting nothing is entirely unaffected, and that the core never learns what a
claim means.

Driven through **two synthetic families** — one that claims, one that does not —
on `test_second_adapter.py`'s precedent. That is what makes "family-neutral" a
demonstrated property rather than a docstring: the core enforces the invariant
for a family it has never heard of, and leaves the other alone.

Every key is ephemeral, minted at run time from process randomness. `[G]` Nothing
here issues or activates a **genuine** constitution and no `ACC-FC-5` gate is
closed by any of it; `ACC-OVL-4` — no second constitution until the invariant is
implemented and verified — is what this suite exists to satisfy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pytest
from _authority_fixtures import RecordingApprovalVerifier, approval_evidence
from ugence_policy_authority.api import (
    AdapterRegistry,
    Ed25519PolicySigner,
    ExclusivityClaim,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyArtifactDescriptor,
    PolicyCoordinate,
    PolicyExclusivityError,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    SigningKey,
    UnsupportedPolicyArtifactError,
    issue_policy,
    resolve_policy,
    revoke_policy,
    suspend_policy,
)
from ugence_policy_authority.core.canonical import to_canonical_obj
from ugence_policy_authority.core.exclusivity import intervals_overlap

CHARTER_ADAPTER_ID = "example.charter-family/v1"
PLAIN_ADAPTER_ID = "example.plain-family/v1"
NAMESPACE = "example.charter/governed-thing"

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
T2 = datetime(2027, 1, 1, tzinfo=timezone.utc)
T3 = datetime(2028, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Family A: claims exclusive governance of things
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CharterReference:
    charter_id: str
    revision: str
    body_digest: str
    region: str = "GLOBAL"
    tenant: str = ""


@dataclass(frozen=True)
class Charter:
    charter_id: str
    revision: str
    declared_digest: str
    governs: tuple = ()
    state: str = "LIVE"
    region: str = "GLOBAL"
    tenant: str = ""
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    #: Excluded from the projection: what a version replaces is a claim about
    #: the registry, not part of the bytes it is identified by.
    supersedes: Optional["CharterReference"] = None


class CharterAdapter:
    @property
    def adapter_id(self) -> str:
        return CHARTER_ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is Charter

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, CharterReference):
            return None
        return PolicyCoordinate(
            policy_family="CHARTER",
            policy_id=reference.charter_id,
            version=reference.revision,
            content_digest=reference.body_digest,
            scope=reference.region,
            tenant_id=reference.tenant,
        )

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if not self.recognizes(artifact):
            raise UnsupportedPolicyArtifactError("not a Charter")
        projection = {
            k: v
            for k, v in to_canonical_obj(artifact).items()
            if k not in ("declared_digest", "supersedes")
        }
        return PolicyArtifactDescriptor(
            adapter_id=CHARTER_ADAPTER_ID,
            policy_type="Charter",
            coordinate=PolicyCoordinate(
                policy_family="CHARTER",
                policy_id=artifact.charter_id,
                version=artifact.revision,
                content_digest=artifact.declared_digest,
                scope=artifact.region,
                tenant_id=artifact.tenant,
            ),
            declared_content_digest=artifact.declared_digest,
            canonical_projection=projection,
            lifecycle_label=artifact.state,
            lifecycle_is_active=artifact.state == "LIVE",
            effective_from=artifact.opens_at,
            effective_to=artifact.closes_at,
            supersedes_coordinate=self.coordinate_for(artifact.supersedes),
            exclusivity_claims=tuple(
                ExclusivityClaim(namespace=NAMESPACE, subject=thing)
                for thing in artifact.governs
            ),
        )


# --------------------------------------------------------------------------- #
# Family B: no exclusivity semantics at all. It must be entirely unaffected.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PlainReference:
    plain_id: str
    revision: str
    body_digest: str


@dataclass(frozen=True)
class Plain:
    plain_id: str
    revision: str
    declared_digest: str
    note: str = "n"
    state: str = "LIVE"


class PlainAdapter:
    @property
    def adapter_id(self) -> str:
        return PLAIN_ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is Plain

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, PlainReference):
            return None
        return PolicyCoordinate(
            policy_family="PLAIN",
            policy_id=reference.plain_id,
            version=reference.revision,
            content_digest=reference.body_digest,
            scope="GLOBAL",
            tenant_id="",
        )

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if not self.recognizes(artifact):
            raise UnsupportedPolicyArtifactError("not a Plain")
        projection = {
            k: v for k, v in to_canonical_obj(artifact).items() if k != "declared_digest"
        }
        return PolicyArtifactDescriptor(
            adapter_id=PLAIN_ADAPTER_ID,
            policy_type="Plain",
            coordinate=PolicyCoordinate(
                policy_family="PLAIN",
                policy_id=artifact.plain_id,
                version=artifact.revision,
                content_digest=artifact.declared_digest,
                scope="GLOBAL",
                tenant_id="",
            ),
            declared_content_digest=artifact.declared_digest,
            canonical_projection=projection,
            lifecycle_label=artifact.state,
            lifecycle_is_active=True,
        )


CHARTER = CharterAdapter()
PLAIN = PlainAdapter()


def make_charter(**overrides) -> Charter:
    base = dict(
        charter_id="charter-a",
        revision="1",
        declared_digest="0" * 64,
        governs=("role-x",),
        opens_at=T0,
        closes_at=T3,
    )
    base.update(overrides)
    base["declared_digest"] = CHARTER.describe(Charter(**base)).body_digest()
    return Charter(**base)


def make_plain(**overrides) -> Plain:
    base = dict(plain_id="plain-a", revision="1", declared_digest="0" * 64)
    base.update(overrides)
    base["declared_digest"] = PLAIN.describe(Plain(**base)).body_digest()
    return Plain(**base)


def ref(policy):
    if isinstance(policy, Charter):
        return CharterReference(
            policy.charter_id, policy.revision, policy.declared_digest,
            policy.region, policy.tenant,
        )
    return PlainReference(policy.plain_id, policy.revision, policy.declared_digest)


@dataclass
class World:
    signer: Ed25519PolicySigner
    suspender: Ed25519PolicySigner
    revoker: Ed25519PolicySigner
    key_ring: PolicyKeyRing
    registry: InMemoryPolicyRegistry
    approval: RecordingApprovalVerifier
    adapters: AdapterRegistry

    def issue(self, policy, *, record_id, issued_at=T0, supersession_id=None):
        return issue_policy(
            policy=policy,
            record_id=record_id,
            supersession_id=supersession_id,
            approval=approval_evidence(),
            approval_verifier=self.approval,
            signer=self.signer,
            registry=self.registry,
            adapters=self.adapters,
            issued_at=issued_at,
            signature_verifier=self.key_ring,
        )

    def resolve(self, reference, *, as_of=T1, tenant=""):
        return resolve_policy(
            reference=reference,
            expected_reference_tenant_id=tenant,
            as_of=as_of,
            registry=self.registry,
            signature_verifier=self.key_ring,
            adapters=self.adapters,
        )


def make_world() -> World:
    signer = Ed25519PolicySigner(
        authority_id="ugence.policy-authority", key_id="k-issue",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    suspender = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.suspension", key_id="k-susp",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    revoker = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.revocation", key_id="k-rev",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    return World(
        signer=signer,
        suspender=suspender,
        revoker=revoker,
        key_ring=PolicyKeyRing([
            signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
            suspender.verification_key(entitlements=(KeyEntitlement.SUSPEND_POLICY,)),
            revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,)),
        ]),
        registry=InMemoryPolicyRegistry(),
        approval=RecordingApprovalVerifier(),
        adapters=AdapterRegistry((CHARTER, PLAIN)),
    )


# --------------------------------------------------------------------------- #
# The invariant
# --------------------------------------------------------------------------- #
def test_a_second_artifact_claiming_the_same_thing_is_refused_at_issuance():
    world = make_world()
    world.issue(make_charter(charter_id="charter-a"), record_id="r1")

    with pytest.raises(PolicyExclusivityError, match="already governed by"):
        world.issue(make_charter(charter_id="charter-b"), record_id="r2")


def test_nothing_from_the_refused_artifact_is_stored():
    """The refusal precedes the digest, approval, signing and every mutation."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a"), record_id="r1")
    second = make_charter(charter_id="charter-b")

    with pytest.raises(PolicyExclusivityError):
        world.issue(second, record_id="r2")

    assert world.registry.get_issued(CHARTER.describe(second).coordinate) is None
    assert len(world.registry.issued_records_for_family(
        policy_family="CHARTER", scope="GLOBAL", tenant_id="")) == 1
    # Approval was never even asked for on the refused artifact: the exclusivity
    # refusal precedes the approval verifier, exactly as the supersession one does.
    assert len(world.approval.calls) == 1


def test_the_refusal_names_the_claim_and_the_incumbent():
    """A finding an operator cannot act on is not a finding."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a"), record_id="r1")
    with pytest.raises(PolicyExclusivityError) as caught:
        world.issue(make_charter(charter_id="charter-b"), record_id="r2")

    message = str(caught.value)
    assert "role-x" in message and "charter-a@1" in message
    assert "EXCLUSIVITY_CONFLICT" in message


def test_disjoint_claims_do_not_collide():
    world = make_world()
    world.issue(make_charter(charter_id="charter-a", governs=("role-x",)), record_id="r1")
    assert world.issue(
        make_charter(charter_id="charter-b", governs=("role-y",)), record_id="r2"
    )


def test_a_clean_handover_is_not_an_overlap():
    """Half-open intervals: ending exactly where the next begins is legal."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a", closes_at=T2), record_id="r1")
    assert world.issue(
        make_charter(charter_id="charter-b", opens_at=T2, closes_at=T3), record_id="r2"
    )


def test_an_overlap_that_only_begins_later_is_still_refused_now():
    """An invariant, not a monitor: the future overlap is refused at issuance."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a", opens_at=T0, closes_at=T3), record_id="r1")
    with pytest.raises(PolicyExclusivityError):
        world.issue(
            make_charter(charter_id="charter-b", opens_at=T2, closes_at=T3), record_id="r2"
        )


def test_the_same_subject_in_another_tenant_is_untouched():
    """Scope and tenant come from the coordinate, so a claim cannot reach out."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a", region="GLOBAL", tenant=""), record_id="r1")
    assert world.issue(
        make_charter(charter_id="charter-b", region="TENANT", tenant="acme"), record_id="r2"
    )


def test_reissuing_the_identical_version_is_idempotent_not_a_collision():
    world = make_world()
    policy = make_charter()
    first = world.issue(policy, record_id="r1")
    assert world.issue(policy, record_id="r1") == first


# --------------------------------------------------------------------------- #
# No order may break a tie (`ACC-OVL-3`)
# --------------------------------------------------------------------------- #
def test_neither_issuance_order_decides_a_winner():
    """The ruled property: whichever arrives second is refused, both ways round.

    There is no ordering of these two artifacts under which one silently
    displaces the other — which is what "never decided by registration or arrival
    order" has to mean operationally.
    """

    forward = make_world()
    forward.issue(make_charter(charter_id="charter-a"), record_id="r1")
    with pytest.raises(PolicyExclusivityError):
        forward.issue(make_charter(charter_id="charter-b"), record_id="r2")

    backward = make_world()
    backward.issue(make_charter(charter_id="charter-b"), record_id="r1")
    with pytest.raises(PolicyExclusivityError):
        backward.issue(make_charter(charter_id="charter-a"), record_id="r2")


def test_adapter_registration_order_does_not_change_the_outcome():
    world = make_world()
    world.adapters = AdapterRegistry((PLAIN, CHARTER))
    world.issue(make_charter(charter_id="charter-a"), record_id="r1")
    with pytest.raises(PolicyExclusivityError):
        world.issue(make_charter(charter_id="charter-b"), record_id="r2")


# --------------------------------------------------------------------------- #
# Terminal states release a claim; a pause does not
# --------------------------------------------------------------------------- #
def test_a_revoked_incumbent_releases_its_claim():
    world = make_world()
    first = make_charter(charter_id="charter-a")
    world.issue(first, record_id="r1")
    revoke_policy(
        reference=ref(first), revocation_id="rev-1",
        reason_code=PolicyRevocationReasonCode.ISSUED_IN_ERROR,
        registry=world.registry, adapters=world.adapters, signer=world.revoker,
        signature_verifier=world.key_ring, revoked_at=T1,
    )
    assert world.issue(make_charter(charter_id="charter-b"), record_id="r2")


def test_a_suspended_incumbent_keeps_its_claim():
    """A pause is not a release.

    If a paused version released its claim, a second artifact could take it and
    the reinstatement would then create exactly the overlap this invariant
    forbids — with no act left to refuse it. So the pause holds the claim.
    """

    world = make_world()
    first = make_charter(charter_id="charter-a")
    world.issue(first, record_id="r1")
    suspend_policy(
        reference=ref(first), suspension_id="s-1", registry=world.registry,
        adapters=world.adapters, signer=world.suspender,
        signature_verifier=world.key_ring, effective_at=T1,
    )
    with pytest.raises(PolicyExclusivityError, match="already governed by"):
        world.issue(make_charter(charter_id="charter-b"), record_id="r2")


def test_an_inactive_stored_record_governs_nothing():
    """Defence in depth, and honest about why it can only be reached directly.

    An inactive artifact cannot be *issued* at all — issuance refuses it before
    this code runs — so the branch is unreachable through the public act. It
    exists for a record whose adapter later describes it as inactive, and is
    exercised here at its own level rather than through a path that cannot
    produce it.
    """

    from ugence_policy_authority.core.exclusivity import effective_claim_holders

    world = make_world()
    policy = make_charter(charter_id="charter-a")
    record = world.issue(policy, record_id="r1")

    class RetiringAdapter(CharterAdapter):
        def describe(self, artifact):
            described = super().describe(artifact)
            from dataclasses import replace as _replace

            return _replace(described, lifecycle_is_active=False)

    holders = effective_claim_holders(
        records=(record,),
        adapters=AdapterRegistry((RetiringAdapter(),)),
        registry=world.registry,
    )
    assert holders == ()


def test_an_unreadable_incumbent_is_a_conflict_not_an_absence():
    """`ACC-OVL-3`: an incumbent whose claims cannot be read is unresolved.

    Skipping it would let a record no adapter recognises silently release the
    thing it governs, which is the fail-open this invariant exists to prevent.
    """

    from ugence_policy_authority.core.exclusivity import effective_claim_holders

    world = make_world()
    record = world.issue(make_charter(charter_id="charter-a"), record_id="r1")

    with pytest.raises(PolicyExclusivityError, match="cannot be described"):
        effective_claim_holders(
            records=(record,),
            adapters=AdapterRegistry((PLAIN,)),
            registry=world.registry,
        )


def test_resolution_reports_an_unreadable_incumbent_as_a_conflict():
    world = make_world()
    policy = make_charter(charter_id="charter-a")
    world.issue(policy, record_id="r1")
    other = make_charter(charter_id="charter-b", governs=("role-y",))
    world.issue(other, record_id="r2")

    # Resolve charter-b through a registry whose sibling record charter-a can no
    # longer be described: the answer is a refusal, never a pass.
    world.adapters = AdapterRegistry((CharterAdapter(),))

    class HalfBlindAdapter(CharterAdapter):
        def describe(self, artifact):
            if getattr(artifact, "charter_id", "") == "charter-a":
                raise UnsupportedPolicyArtifactError("no longer recognised")
            return super().describe(artifact)

    world.adapters = AdapterRegistry((HalfBlindAdapter(),))
    denied = world.resolve(ref(other))
    assert denied.reason is PolicyResolutionReason.EXCLUSIVITY_CONFLICT
    assert "cannot be described" in denied.detail


# --------------------------------------------------------------------------- #
# Resolution re-derives rather than trusting issuance
# --------------------------------------------------------------------------- #
def test_resolution_refuses_a_conflict_planted_past_the_issuance_gate():
    """Issuance-time enforcement alone would be a check at the door."""

    world = make_world()
    first = make_charter(charter_id="charter-a")
    second = make_charter(charter_id="charter-b")
    world.issue(first, record_id="r1")
    # Plant the second straight into the store, past issue_policy entirely.
    bypass = make_world()
    bypass.registry = world.registry
    record = issue_policy(
        policy=second, record_id="r2", approval=approval_evidence(),
        approval_verifier=world.approval, signer=world.signer,
        registry=InMemoryPolicyRegistry(), adapters=world.adapters,
        issued_at=T0, signature_verifier=world.key_ring,
    )
    world.registry.append_issuance(record)

    denied = world.resolve(ref(second))
    assert denied.status is PolicyResolutionStatus.UNRESOLVED
    assert denied.reason is PolicyResolutionReason.EXCLUSIVITY_CONFLICT
    assert "role-x" in denied.detail

    # And the incumbent is refused too: neither is silently preferred.
    assert world.resolve(ref(first)).reason is PolicyResolutionReason.EXCLUSIVITY_CONFLICT


def test_a_sole_claimant_resolves_normally():
    world = make_world()
    policy = make_charter()
    world.issue(policy, record_id="r1")
    assert world.resolve(ref(policy)).resolved


# --------------------------------------------------------------------------- #
# A family with no exclusivity semantics is untouched (`ACC-OVL-7`)
# --------------------------------------------------------------------------- #
def test_a_family_that_projects_nothing_is_entirely_unaffected():
    world = make_world()
    a = make_plain(plain_id="plain-a")
    b = make_plain(plain_id="plain-b")
    world.issue(a, record_id="r1")
    world.issue(b, record_id="r2")
    assert world.resolve(ref(a)).resolved
    assert world.resolve(ref(b)).resolved


def test_two_families_cannot_collide_across_namespaces():
    """Namespacing is what lets a second family adopt claims without a core change."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a", governs=("shared-name",)), record_id="r1")
    # A different namespace over the identical subject is a different claim.
    other = ExclusivityClaim(namespace="example.other/thing", subject="shared-name")
    mine = ExclusivityClaim(namespace=NAMESPACE, subject="shared-name")
    assert other != mine


# --------------------------------------------------------------------------- #
# The core never interprets a claim
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("subject", ["role-x", "urn:role:x", "  padded  ".strip(), "é"])
def test_the_subject_is_opaque_to_the_core(subject):
    """Any token works, and equality is the only comparison performed."""

    world = make_world()
    world.issue(make_charter(charter_id="charter-a", governs=(subject,)), record_id="r1")
    with pytest.raises(PolicyExclusivityError):
        world.issue(make_charter(charter_id="charter-b", governs=(subject,)), record_id="r2")


def test_a_duplicate_claim_on_one_artifact_is_refused():
    with pytest.raises(Exception, match="duplicate"):
        PolicyArtifactDescriptor(
            adapter_id="a", policy_type="t",
            coordinate=PolicyCoordinate(
                policy_family="F", policy_id="p", version="1",
                content_digest="0" * 64, scope="GLOBAL", tenant_id="",
            ),
            declared_content_digest="0" * 64,
            canonical_projection={},
            lifecycle_label="LIVE", lifecycle_is_active=True,
            exclusivity_claims=(
                ExclusivityClaim(namespace=NAMESPACE, subject="x"),
                ExclusivityClaim(namespace=NAMESPACE, subject="x"),
            ),
        )


def test_a_bare_string_cannot_claim_anything():
    with pytest.raises(Exception, match="ExclusivityClaim"):
        PolicyArtifactDescriptor(
            adapter_id="a", policy_type="t",
            coordinate=PolicyCoordinate(
                policy_family="F", policy_id="p", version="1",
                content_digest="0" * 64, scope="GLOBAL", tenant_id="",
            ),
            declared_content_digest="0" * 64,
            canonical_projection={},
            lifecycle_label="LIVE", lifecycle_is_active=True,
            exclusivity_claims=("role-x",),
        )


# --------------------------------------------------------------------------- #
# The interval rule itself
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "a_from,a_to,b_from,b_to,expected",
    [
        (T0, T2, T1, T3, True),      # partial overlap
        (T0, T1, T1, T2, False),     # clean handover, half-open
        (T1, T2, T0, T1, False),     # the same, reversed
        (None, None, T1, T2, True),  # open-ended covers everything
        (T0, None, T2, None, True),  # both open-ended at the top
        (T0, T1, T2, T3, False),     # disjoint
    ],
)
def test_half_open_interval_overlap(a_from, a_to, b_from, b_to, expected):
    assert intervals_overlap(a_from, a_to, b_from, b_to) is expected
    # Symmetric: overlap is a property of the pair, not of the argument order.
    assert intervals_overlap(b_from, b_to, a_from, a_to) is expected


# --------------------------------------------------------------------------- #
# The supersession exception — the only one (`ACC-OVL-8`)
# --------------------------------------------------------------------------- #
def test_a_successor_may_take_its_predecessors_claims():
    """The ratified exception: an explicitly verified supersession permits it.

    Without this, replacing a constitution would be impossible — the successor
    would collide with the incumbent it exists to replace.
    """

    world = make_world()
    first = make_charter(charter_id="charter-a", revision="1")
    world.issue(first, record_id="r1")

    successor = make_charter(
        charter_id="charter-a", revision="2", governs=("role-x",), supersedes=ref(first)
    )
    record = world.issue(successor, record_id="r2", issued_at=T1, supersession_id="sup-1")
    assert record.coordinate.version == "2"

    # The successor resolves; the predecessor is superseded, not conflicted.
    assert world.resolve(ref(successor), as_of=T2).resolved
    assert world.resolve(ref(first), as_of=T2).reason is PolicyResolutionReason.SUPERSEDED


def test_the_exception_reaches_only_the_declared_predecessor():
    """Superseding one incumbent does not license colliding with a third party."""

    world = make_world()
    first = make_charter(charter_id="charter-a", revision="1", governs=("role-x",))
    world.issue(first, record_id="r1")
    bystander = make_charter(charter_id="charter-c", revision="1", governs=("role-z",))
    world.issue(bystander, record_id="r2")

    # A successor to charter-a that also grabs the bystander's role is refused.
    greedy = make_charter(
        charter_id="charter-a", revision="2",
        governs=tuple(sorted(("role-x", "role-z"))), supersedes=ref(first),
    )
    with pytest.raises(PolicyExclusivityError, match="role-z"):
        world.issue(greedy, record_id="r3", issued_at=T1, supersession_id="sup-1")


def test_an_undeclared_successor_gets_no_exception():
    """The exception is the *declared, verified* relationship, not a resemblance.

    Same family, same policy_id, same claims — and still refused, because nothing
    signed says it replaces the incumbent.
    """

    world = make_world()
    world.issue(make_charter(charter_id="charter-a", revision="1"), record_id="r1")
    with pytest.raises(PolicyExclusivityError, match="already governed by"):
        world.issue(
            make_charter(charter_id="charter-a", revision="2"),
            record_id="r2", issued_at=T1,
        )

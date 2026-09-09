"""`ACC-SUSP-IA-7` — signed, reversible policy-version suspension, end to end.

The happy path (pause, then resume), the entitlement matrix, and — the reason
this round needed its own ballot — the **three ordering rules**, each proven in
both directions: refused at append time, and re-caught at resolution when a
defective history is planted directly in the store.

Driven through a **synthetic family**, on `test_second_adapter.py`'s and
`test_supersession.py`'s exact precedent: suspension is family-neutral core
behaviour, not a branch on any shipped family. Every key is ephemeral, minted at
run time from process randomness.

`[G]` Recorded rather than implied: nothing here issues, activates or suspends a
**genuine** constitution, and no `ACC-FC-5` gate is closed by any of it. Under
`ACC-SUSP-IA-4` this is exactly the intended mode of exercise until the custody
and approving-authority gates close.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from _authority_fixtures import RecordingApprovalVerifier, approval_evidence
from ugence_policy_authority.api import (
    AdapterRegistry,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyArtifactDescriptor,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    PolicySuspensionAction,
    PolicySuspensionError,
    PolicySuspensionRecord,
    SigningKey,
    UnsupportedPolicyArtifactError,
    issue_policy,
    reinstate_policy,
    resolve_policy,
    revoke_policy,
    suspend_policy,
)
from ugence_policy_authority.core.canonical import to_canonical_obj

ADAPTER_ID = "example.gate-policy-family/v1"

T_ISSUE = datetime(2026, 3, 1, tzinfo=timezone.utc)
T_PAUSE = datetime(2026, 4, 1, tzinfo=timezone.utc)
T_RESUME = datetime(2026, 5, 1, tzinfo=timezone.utc)
T_LATER = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2028, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# A synthetic family
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GateReference:
    gate_id: str
    revision: str
    body_digest: str
    region: str = "GLOBAL"
    tenant: str = ""


@dataclass(frozen=True)
class GatePolicy:
    gate_id: str
    revision: str
    declared_digest: str
    rules: tuple = ()
    state: str = "LIVE"
    region: str = "GLOBAL"
    tenant: str = ""
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None


class GateAdapter:
    @property
    def adapter_id(self) -> str:
        return ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is GatePolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, GateReference):
            return None
        return PolicyCoordinate(
            policy_family="GATE",
            policy_id=reference.gate_id,
            version=reference.revision,
            content_digest=reference.body_digest,
            scope=reference.region,
            tenant_id=reference.tenant,
        )

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if not self.recognizes(artifact):
            raise UnsupportedPolicyArtifactError("not a GatePolicy")
        projection = {
            k: v for k, v in to_canonical_obj(artifact).items() if k != "declared_digest"
        }
        return PolicyArtifactDescriptor(
            adapter_id=ADAPTER_ID,
            policy_type=type(artifact).__name__,
            coordinate=PolicyCoordinate(
                policy_family="GATE",
                policy_id=artifact.gate_id,
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
        )


ADAPTER = GateAdapter()


def make_gate(**overrides) -> GatePolicy:
    base = dict(
        gate_id="gate-1",
        revision="1",
        declared_digest="0" * 64,
        rules=("a", "b"),
        opens_at=T_ISSUE,
        closes_at=T_TO,
    )
    base.update(overrides)
    base["declared_digest"] = ADAPTER.describe(GatePolicy(**base)).body_digest()
    return GatePolicy(**base)


def reference_of(policy: GatePolicy) -> GateReference:
    return GateReference(
        gate_id=policy.gate_id,
        revision=policy.revision,
        body_digest=policy.declared_digest,
        region=policy.region,
        tenant=policy.tenant,
    )


@dataclass
class World:
    signer: Ed25519PolicySigner
    suspender: Ed25519PolicySigner
    revoker: Ed25519PolicySigner
    key_ring: PolicyKeyRing
    registry: InMemoryPolicyRegistry
    approval: RecordingApprovalVerifier
    adapters: AdapterRegistry

    def issue(self, policy, *, record_id="rec-1", issued_at=T_ISSUE):
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
        )

    def suspend(self, reference, *, suspension_id="susp-1", effective_at=T_PAUSE, signer=None):
        return suspend_policy(
            reference=reference,
            suspension_id=suspension_id,
            registry=self.registry,
            adapters=self.adapters,
            signer=signer or self.suspender,
            signature_verifier=self.key_ring,
            effective_at=effective_at,
        )

    def reinstate(self, reference, *, suspension_id="rein-1", effective_at=T_RESUME, signer=None):
        return reinstate_policy(
            reference=reference,
            suspension_id=suspension_id,
            registry=self.registry,
            adapters=self.adapters,
            signer=signer or self.suspender,
            signature_verifier=self.key_ring,
            effective_at=effective_at,
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
    """Ephemeral custody: every seed comes from process randomness."""

    signer = Ed25519PolicySigner(
        authority_id="ugence.policy-authority",
        key_id="issuance-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    suspender = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.suspension",
        key_id="suspension-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    revoker = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.revocation",
        key_id="revocation-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )
    return World(
        signer=signer,
        suspender=suspender,
        revoker=revoker,
        key_ring=PolicyKeyRing(
            [
                signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
                suspender.verification_key(entitlements=(KeyEntitlement.SUSPEND_POLICY,)),
                revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,)),
            ]
        ),
        registry=InMemoryPolicyRegistry(),
        approval=RecordingApprovalVerifier(),
        adapters=AdapterRegistry((ADAPTER,)),
    )


def signed_record(
    world: World, policy: GatePolicy, *, action, effective_at, suspension_id
) -> PolicySuspensionRecord:
    """A genuinely signed record, built without going through the append guard.

    Planting one of these isolates the **sequence** rules from the **signature**
    rule: a record made with ``dataclasses.replace`` would fail verification
    first, and the test would then prove nothing about ordering.
    """

    from ugence_policy_authority.core.payload import suspension_signing_payload

    coordinate = ADAPTER.describe(policy).coordinate
    signer = world.suspender
    return PolicySuspensionRecord(
        suspension_id=suspension_id,
        coordinate=coordinate,
        action=action,
        suspending_authority_id=signer.authority_id,
        key_id=signer.key_id,
        signature_alg=signer.signature_alg,
        signature=bytes(
            signer.sign(
                suspension_signing_payload(
                    suspension_id=suspension_id,
                    coordinate=coordinate,
                    action=action,
                    suspending_authority_id=signer.authority_id,
                    key_id=signer.key_id,
                    signature_alg=signer.signature_alg,
                    effective_at=effective_at,
                )
            )
        ),
        effective_at=effective_at,
    )


def plant(world: World, policy: GatePolicy, records) -> None:
    """Write a history straight into the store, past the append-time guard."""

    from ugence_policy_authority.core.canonical import canonical_bytes

    coordinate = ADAPTER.describe(policy).coordinate
    world.registry._suspensions[coordinate] = list(records)
    world.registry._suspension_bytes[coordinate] = [canonical_bytes(r) for r in records]


def issued_world() -> tuple:
    world = make_world()
    policy = make_gate()
    world.issue(policy)
    return world, policy


# --------------------------------------------------------------------------- #
# The happy path: pause, then resume
# --------------------------------------------------------------------------- #
def test_a_suspended_version_stops_resolving_from_its_signed_instant():
    world, policy = issued_world()
    assert world.resolve(reference_of(policy), as_of=T_PAUSE - timedelta(days=1)).resolved

    world.suspend(reference_of(policy))

    denied = world.resolve(reference_of(policy), as_of=T_LATER)
    assert denied.status is PolicyResolutionStatus.UNRESOLVED
    assert denied.reason is PolicyResolutionReason.SUSPENDED
    assert "2026-04-01" in denied.detail


def test_an_instant_before_the_pause_still_resolves():
    """A pause acts forward. It does not reach back and unmake the past."""

    world, policy = issued_world()
    world.suspend(reference_of(policy))
    assert world.resolve(reference_of(policy), as_of=T_PAUSE - timedelta(seconds=1)).resolved


def test_a_reinstatement_makes_the_version_resolve_again():
    world, policy = issued_world()
    world.suspend(reference_of(policy))
    world.reinstate(reference_of(policy))

    assert world.resolve(reference_of(policy), as_of=T_LATER).resolved
    # ...and the paused window is still paused, because the history is ordered.
    between = world.resolve(reference_of(policy), as_of=T_RESUME - timedelta(seconds=1))
    assert between.reason is PolicyResolutionReason.SUSPENDED


def test_the_suspended_version_stays_readable_and_its_history_is_kept():
    """`ACC-SUSP-2`: nothing is deleted, so the history of pauses stays legible."""

    world, policy = issued_world()
    coordinate = ADAPTER.describe(policy).coordinate
    world.suspend(reference_of(policy))
    world.reinstate(reference_of(policy))

    assert world.registry.get_issued(coordinate) is not None
    history = world.registry.suspensions_for(coordinate)
    assert [r.action for r in history] == [
        PolicySuspensionAction.SUSPEND,
        PolicySuspensionAction.REINSTATE,
    ]


def test_suspension_never_writes_a_lifecycle_state():
    """`ACC-SUSP-1`: the artifact keeps its issued label; only the store stops it."""

    world, policy = issued_world()
    world.suspend(reference_of(policy))
    record = world.registry.get_issued(ADAPTER.describe(policy).coordinate)
    assert ADAPTER.describe(record.policy).lifecycle_label == "LIVE"


# --------------------------------------------------------------------------- #
# Rule 1 — equal signed instants are ambiguous, and ambiguity refuses
# --------------------------------------------------------------------------- #
def test_a_distinct_record_at_the_same_instant_is_refused_at_append_time():
    world, policy = issued_world()
    world.suspend(reference_of(policy), suspension_id="susp-1", effective_at=T_PAUSE)

    with pytest.raises(PolicySuspensionError, match="may not share one instant"):
        world.reinstate(reference_of(policy), suspension_id="rein-1", effective_at=T_PAUSE)


def test_an_exact_replay_is_an_idempotent_no_op_not_a_second_append():
    """The distinction the ruling drew: same identity and payload is a repeat."""

    world, policy = issued_world()
    coordinate = ADAPTER.describe(policy).coordinate
    first = world.suspend(reference_of(policy))
    again = world.registry.append_suspension(first)

    assert again == first
    assert len(world.registry.suspensions_for(coordinate)) == 1


def test_an_equal_instant_collision_planted_in_the_store_fails_closed_at_resolution():
    """The append path cannot create this. A store filled another way still can."""

    world, policy = issued_world()
    plant(world, policy, [
        signed_record(world, policy, action=PolicySuspensionAction.SUSPEND,
                      effective_at=T_PAUSE, suspension_id="susp-1"),
        signed_record(world, policy, action=PolicySuspensionAction.REINSTATE,
                      effective_at=T_PAUSE, suspension_id="rein-1"),
    ])

    denied = world.resolve(reference_of(policy), as_of=T_LATER)
    assert denied.reason is PolicyResolutionReason.SUSPENSION_INTEGRITY_INVALID
    assert "share the signed instant" in denied.detail


# --------------------------------------------------------------------------- #
# Rule 2 — an earlier candidate is a retroactive insertion, and is refused
# --------------------------------------------------------------------------- #
def test_an_older_candidate_is_refused_rather_than_sorted_into_place():
    world, policy = issued_world()
    world.suspend(reference_of(policy), effective_at=T_RESUME)

    with pytest.raises(PolicySuspensionError, match="not strictly later"):
        world.reinstate(reference_of(policy), effective_at=T_PAUSE)


def test_delivery_order_cannot_decide_whether_a_reinstatement_is_an_orphan():
    """The ruling's own ground for refusing rather than sorting.

    Under a sort-on-read rule these two orderings of the *same two records* would
    disagree about whether the reinstatement has a prior suspension. Under
    append-forward they cannot: one order is accepted, the other refused, and the
    accepted history means the same thing either way it was delivered.
    """

    # Delivered in signed order: accepted, and the pause is real.
    ordered, policy = issued_world()
    ordered.suspend(reference_of(policy), effective_at=T_PAUSE)
    ordered.reinstate(reference_of(policy), effective_at=T_RESUME)
    assert ordered.resolve(reference_of(policy), as_of=T_LATER).resolved

    # Delivered reversed: the reinstatement arrives first and is refused as an
    # orphan — not held, not sorted, not later legitimised by the pause.
    reversed_world, policy2 = issued_world()
    with pytest.raises(PolicySuspensionError, match="valid only when"):
        reversed_world.reinstate(reference_of(policy2), effective_at=T_RESUME)


def test_a_non_monotonic_history_planted_in_the_store_fails_closed_at_resolution():
    world, policy = issued_world()
    plant(world, policy, [
        signed_record(world, policy, action=PolicySuspensionAction.SUSPEND,
                      effective_at=T_RESUME, suspension_id="susp-1"),
        signed_record(world, policy, action=PolicySuspensionAction.REINSTATE,
                      effective_at=T_PAUSE, suspension_id="rein-1"),
    ])

    denied = world.resolve(reference_of(policy), as_of=T_LATER)
    assert denied.reason is PolicyResolutionReason.SUSPENSION_INTEGRITY_INVALID
    assert "not strictly monotonic" in denied.detail


# --------------------------------------------------------------------------- #
# Rule 3 — a reinstatement cannot manufacture the transition it reverses
# --------------------------------------------------------------------------- #
def test_reinstating_a_version_that_was_never_suspended_is_refused():
    world, policy = issued_world()
    with pytest.raises(PolicySuspensionError, match="not suspended at all"):
        world.reinstate(reference_of(policy))


def test_reinstating_an_already_reinstated_version_is_refused():
    world, policy = issued_world()
    world.suspend(reference_of(policy))
    world.reinstate(reference_of(policy))

    with pytest.raises(PolicySuspensionError, match="not currently suspended"):
        world.reinstate(
            reference_of(policy), suspension_id="rein-2", effective_at=T_LATER
        )


def test_suspending_an_already_suspended_version_is_refused():
    world, policy = issued_world()
    world.suspend(reference_of(policy))
    with pytest.raises(PolicySuspensionError, match="already suspended"):
        world.suspend(
            reference_of(policy), suspension_id="susp-2", effective_at=T_RESUME
        )


def test_an_orphan_reinstatement_planted_in_the_store_fails_closed_at_resolution():
    world, policy = issued_world()
    plant(world, policy, [
        signed_record(world, policy, action=PolicySuspensionAction.REINSTATE,
                      effective_at=T_PAUSE, suspension_id="rein-1"),
    ])

    denied = world.resolve(reference_of(policy), as_of=T_LATER)
    assert denied.reason is PolicyResolutionReason.SUSPENSION_INTEGRITY_INVALID
    assert "opens with a REINSTATE" in denied.detail


# --------------------------------------------------------------------------- #
# Entitlement and signature — proven, never assumed
# --------------------------------------------------------------------------- #
def test_an_issuance_key_may_not_suspend():
    """`SUSPEND_POLICY` is its own entitlement: no existing key gained the power."""

    world, policy = issued_world()
    with pytest.raises(PolicySuspensionError, match="not authorized"):
        world.suspend(reference_of(policy), signer=world.signer)


def test_a_revocation_key_may_not_suspend():
    """The reason the entitlement was minted rather than reused."""

    world, policy = issued_world()
    with pytest.raises(PolicySuspensionError, match="not authorized"):
        world.suspend(reference_of(policy), signer=world.revoker)


def test_one_entitlement_covers_both_acts():
    """`ACC-SUSP-3`: an authority that may pause may unpause."""

    world, policy = issued_world()
    world.suspend(reference_of(policy))
    assert world.reinstate(reference_of(policy)).action is PolicySuspensionAction.REINSTATE


def test_a_tampered_stored_record_fails_closed_at_resolution():
    """A stored suspension is never trusted merely because it is stored."""

    world, policy = issued_world()
    coordinate = ADAPTER.describe(policy).coordinate
    stored = world.suspend(reference_of(policy))
    world.registry._suspensions[coordinate] = [replace(stored, suspension_id="tampered")]

    denied = world.resolve(reference_of(policy), as_of=T_LATER)
    assert denied.reason is PolicyResolutionReason.SUSPENSION_INTEGRITY_INVALID
    assert "does not verify" in denied.detail


def test_an_unsigned_suspension_record_is_unrepresentable():
    with pytest.raises(Exception, match="non-empty bytes"):
        PolicySuspensionRecord(
            suspension_id="s",
            coordinate=PolicyCoordinate(
                policy_family="GATE", policy_id="g", version="1",
                content_digest="0" * 64, scope="GLOBAL", tenant_id="",
            ),
            action=PolicySuspensionAction.SUSPEND,
            suspending_authority_id="a",
            key_id="k",
            signature_alg="ed25519",
            signature=b"",
            effective_at=T_PAUSE,
        )


# --------------------------------------------------------------------------- #
# Interaction with the two terminal stores
# --------------------------------------------------------------------------- #
def test_a_revoked_version_cannot_be_suspended():
    world, policy = issued_world()
    revoke_policy(
        reference=reference_of(policy),
        revocation_id="rev-1",
        reason_code=PolicyRevocationReasonCode.REPLACED,
        registry=world.registry,
        adapters=world.adapters,
        signer=world.revoker,
        signature_verifier=world.key_ring,
        revoked_at=T_PAUSE,
    )
    with pytest.raises(PolicySuspensionError, match="already revoked"):
        world.suspend(reference_of(policy), effective_at=T_RESUME)


def test_a_version_that_was_never_issued_cannot_be_suspended():
    world = make_world()
    with pytest.raises(PolicySuspensionError, match="never issued"):
        world.suspend(reference_of(make_gate()))


def test_revocation_outranks_suspension_when_both_apply():
    """Terminal beats reversible: the more informative answer is reported."""

    world, policy = issued_world()
    world.suspend(reference_of(policy), effective_at=T_PAUSE)
    revoke_policy(
        reference=reference_of(policy),
        revocation_id="rev-1",
        reason_code=PolicyRevocationReasonCode.REPLACED,
        registry=world.registry,
        adapters=world.adapters,
        signer=world.revoker,
        signature_verifier=world.key_ring,
        revoked_at=T_RESUME,
    )
    assert world.resolve(reference_of(policy), as_of=T_LATER).reason is (
        PolicyResolutionReason.REVOKED
    )


# --------------------------------------------------------------------------- #
# The durable registry keeps the same promises
# --------------------------------------------------------------------------- #
def test_the_sqlite_registry_holds_an_ordered_history_and_refuses_the_same_defects(tmp_path):
    from ugence_policy_authority.api import SqlitePolicyRegistry
    from ugence_policy_authority.core.errors import PolicyRegistryConflictError

    class Codec:
        def encode(self, policy):
            return to_canonical_obj(policy)

        def decode(self, *, adapter_id, policy_type, canonical):
            return GatePolicy(
                **{
                    k: (tuple(v) if k == "rules" else v)
                    for k, v in canonical.items()
                    if k != "__type__"
                }
            )

    world = make_world()
    world.registry = SqlitePolicyRegistry(str(tmp_path / "r.db"), codec=Codec())
    policy = make_gate()
    world.issue(policy)
    coordinate = ADAPTER.describe(policy).coordinate

    first = world.suspend(reference_of(policy), effective_at=T_PAUSE)
    world.reinstate(reference_of(policy), effective_at=T_RESUME)

    assert [r.action for r in world.registry.suspensions_for(coordinate)] == [
        PolicySuspensionAction.SUSPEND,
        PolicySuspensionAction.REINSTATE,
    ]
    # An exact replay is still idempotent across the durable boundary.
    assert world.registry.append_suspension(first) == first
    assert len(world.registry.suspensions_for(coordinate)) == 2
    # And the store itself refuses a retroactive insertion.
    with pytest.raises(PolicyRegistryConflictError, match="append-forward"):
        world.registry.append_suspension(replace(first, suspension_id="late"))

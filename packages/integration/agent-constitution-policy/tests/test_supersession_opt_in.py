"""`ACC-SU-IA-*` — the family's structured supersession opt-in, proven.

The three legs `ACC-SU-3` requires:

1. **digest invariance** — the ratified v1 content's body digest is byte-identical
   whether or not a predecessor is declared, and equal to a literal pinned here,
   so any *later* change to the projection fails loudly rather than only this one;
2. **the chain** — a v2 declaring v1 as its predecessor, driven through the
   shipped authority on ephemeral in-process keys: v2 resolves, v1 stops
   resolving as ``SUPERSEDED`` and keeps its record;
3. **the six refusals** of `ACC-LC-IA-3`, re-driven over this family.

`ACC-SU-2`'s exclusion is guarded by two *existing* tests, deliberately not
duplicated here: ``test_authority_registration`` pins this projection's metadata
key set closed, and ``test_artifact``'s ``test_every_body_field_moves_the_digest``
pins which fields move the digest. `ACC-SU-IA-2` requires both to stay green
unedited; this module adds the invariance leg they cannot express.

Every key is ephemeral, minted at run time from process randomness.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import ugence_agentic_proposer as ap
from _agent_constitution_fixtures import ADAPTER, T_MID
from _authority_fixtures import RecordingApprovalVerifier, approval_evidence
from ugence_agent_constitution_policy import (
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_GLOBAL,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyFamilyAdapter,
    AgentConstitutionPolicyMetadata,
    agent_constitution_coordinate,
)
from ugence_agent_constitution_policy.errors import AgentConstitutionFieldError
from ugence_policy_authority.api import (
    GLOBAL_TENANT,
    AdapterRegistry,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    PolicySupersessionError,
    SigningKey,
    issue_policy,
    resolve_policy,
    revoke_policy,
)

#: The ratified `ACC-FC-2`..`ACC-FC-4` content values.
POLICY_ID = "agent-constitution-ugence"
CONSTITUTION_REF = "ugence.agent-constitution/ugence/baseline/v1"
GOVERNED_ROLE_REF = "ugence.roles/ugence/invoice-reconciler/v1"
TOOL_SCOPES_BOUND = ("invoice.read", "ledger.read")

#: A fixed instant. The ratified window opens *at issuance*, which is not a
#: value; this fixture pins one so a digest literal is possible at all. It is a
#: fixture choice, not a ratified value.
T_V1 = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
T_V2 = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)
T_RESOLVE = datetime(2026, 11, 1, 9, 0, 0, tzinfo=timezone.utc)

#: `ACC-SU-IA-3`. The body digest of the ratified v1 content built below,
#: computed at implementation time and pinned. It moves only if the canonical
#: projection changes — which, after `ACC-SU-2`, would be a defect.
RATIFIED_V1_BODY_DIGEST = (
    "f2f29c956e26cf5c56932ac858987555671a8238567d1087cda8bdb9687c74f7"
)

_ADAPTER = AgentConstitutionPolicyFamilyAdapter()

_BODY = dict(
    agent_constitution_ref=CONSTITUTION_REF,
    governed_role_refs=(GOVERNED_ROLE_REF,),
    permitted_candidate_dispositions_bound=tuple(
        sorted(m.value for m in ap.CandidateDisposition)
    ),
    permitted_review_actions_bound=tuple(sorted(m.value for m in ap.ReviewAction)),
    permitted_tool_scopes_bound=TOOL_SCOPES_BOUND,
)


def _draft(**meta_overrides) -> AgentConstitutionPolicy:
    fields = dict(
        policy_id=POLICY_ID,
        version="1.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_GLOBAL,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=GLOBAL_TENANT,
        effective_from=T_V1,
        effective_to=None,
    )
    fields.update(meta_overrides)
    return AgentConstitutionPolicy(
        metadata=AgentConstitutionPolicyMetadata(**fields), **_BODY
    )


def make_constitution(**meta_overrides) -> AgentConstitutionPolicy:
    """Two passes, so ``content_digest`` genuinely binds the body."""

    digest = _ADAPTER.describe(_draft(**meta_overrides)).body_digest()
    return _draft(content_digest=digest, **meta_overrides)


# --------------------------------------------------------------------------- #
# Leg 1 — digest invariance (ACC-SU-2 / ACC-SU-IA-3)
# --------------------------------------------------------------------------- #
def test_the_ratified_v1_digest_equals_its_pinned_literal():
    """The literal is the tripwire: a later projection change fails here."""

    assert _ADAPTER.describe(_draft()).body_digest() == RATIFIED_V1_BODY_DIGEST


def test_declaring_a_predecessor_does_not_move_the_digest():
    """`ACC-SU-2`: what a version replaces is a claim about the registry, not
    part of the bytes it is identified by."""

    predecessor = agent_constitution_coordinate(make_constitution().metadata)
    with_predecessor = _draft(supersedes_coordinate=predecessor)

    assert _ADAPTER.describe(with_predecessor).body_digest() == (
        RATIFIED_V1_BODY_DIGEST
    )


def test_the_predecessor_is_absent_from_the_canonical_projection():
    predecessor = agent_constitution_coordinate(make_constitution().metadata)
    projection = _ADAPTER.describe(
        _draft(supersedes_coordinate=predecessor)
    ).canonical_projection

    assert "supersedes_coordinate" not in projection["metadata"]
    assert "content_digest" not in projection["metadata"]


def test_the_adapter_carries_the_predecessor_to_the_descriptor():
    """Excluded from the digest, but not from the descriptor: the authority
    reads it from there."""

    predecessor = agent_constitution_coordinate(make_constitution().metadata)
    descriptor = _ADAPTER.describe(_draft(supersedes_coordinate=predecessor))

    assert descriptor.supersedes_coordinate == predecessor
    assert descriptor.declares_structured_supersession is True


def test_a_constitution_declaring_nothing_declares_nothing():
    descriptor = _ADAPTER.describe(_draft())
    assert descriptor.supersedes_coordinate is None
    assert descriptor.declares_structured_supersession is False


def test_a_string_cannot_bind_an_exact_predecessor():
    with pytest.raises(AgentConstitutionFieldError):
        _draft(supersedes_coordinate="agent-constitution-ugence@1.0.0")


# --------------------------------------------------------------------------- #
# A wired world on ephemeral custody
# --------------------------------------------------------------------------- #
class World:
    def __init__(self) -> None:
        self.signer = Ed25519PolicySigner(
            authority_id="ugence.policy-authority",
            key_id="issuance-key-1",
            signing_key=SigningKey.from_seed(os.urandom(32)),
        )
        self.revoker = Ed25519PolicySigner(
            authority_id="ugence.policy-authority.revocation",
            key_id="revocation-key-1",
            signing_key=SigningKey.from_seed(os.urandom(32)),
        )
        self.key_ring = PolicyKeyRing(
            [
                self.signer.verification_key(
                    entitlements=(KeyEntitlement.ISSUE_POLICY,)
                ),
                self.revoker.verification_key(
                    entitlements=(KeyEntitlement.REVOKE_POLICY,)
                ),
            ]
        )
        self.registry = InMemoryPolicyRegistry()
        self.approval = RecordingApprovalVerifier()
        self.adapters = AdapterRegistry([ADAPTER])

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
            expected_reference_tenant_id=GLOBAL_TENANT,
            signature_verifier=self.key_ring,
            **kwargs,
        )

    def resolve(self, policy, *, as_of=T_RESOLVE):
        return resolve_policy(
            reference=policy.metadata,
            expected_reference_tenant_id=GLOBAL_TENANT,
            as_of=as_of,
            registry=self.registry,
            signature_verifier=self.key_ring,
            adapters=self.adapters,
        )


def _v1_and_v2(world):
    v1 = make_constitution()
    world.issue(v1, record_id="rec-v1")
    v2 = make_constitution(
        version="2.0.0",
        effective_from=T_V2,
        supersedes_coordinate=agent_constitution_coordinate(v1.metadata),
    )
    return v1, v2


# --------------------------------------------------------------------------- #
# Leg 2 — the chain, through the shipped authority
# --------------------------------------------------------------------------- #
def test_a_v2_supersedes_the_ratified_v1_in_one_act():
    world = World()
    v1, v2 = _v1_and_v2(world)

    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    assert world.resolve(v2).status is PolicyResolutionStatus.RESOLVED
    denied = world.resolve(v1)
    assert denied.status is PolicyResolutionStatus.UNRESOLVED
    assert denied.reason is PolicyResolutionReason.SUPERSEDED
    assert f"{POLICY_ID}@2.0.0" in denied.detail


def test_the_superseded_predecessor_keeps_its_record():
    world = World()
    v1, v2 = _v1_and_v2(world)
    coordinate = agent_constitution_coordinate(v1.metadata)
    before = world.registry.get_issued(coordinate)

    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    assert world.registry.get_issued(coordinate) is before


def test_the_supersession_record_names_both_constitutions():
    world = World()
    v1, v2 = _v1_and_v2(world)
    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    (record,) = world.registry.supersessions_for(
        agent_constitution_coordinate(v1.metadata)
    )
    assert record.coordinate == agent_constitution_coordinate(v1.metadata)
    assert record.successor_coordinate == agent_constitution_coordinate(v2.metadata)
    assert record.signature


# --------------------------------------------------------------------------- #
# Leg 3 — the six ACC-LC-IA-3 refusals, over this family
# --------------------------------------------------------------------------- #
def test_a_self_referential_predecessor_is_refused():
    world = World()
    v1 = make_constitution()
    world.issue(v1, record_id="rec-v1")
    own = agent_constitution_coordinate(v1.metadata)
    with pytest.raises(PolicySupersessionError):
        world.issue(
            make_constitution(supersedes_coordinate=own),
            record_id="rec-self",
            supersession_id="sup-1",
        )


def test_a_cross_scope_predecessor_is_refused():
    world = World()
    v1, _ = _v1_and_v2(world)
    elsewhere = PolicyCoordinate(
        policy_family=agent_constitution_coordinate(v1.metadata).policy_family,
        policy_id=POLICY_ID,
        version="1.0.0",
        content_digest=v1.metadata.content_digest,
        scope="TENANT",
        tenant_id="tenant-1",
    )
    v2 = make_constitution(
        version="2.0.0", effective_from=T_V2, supersedes_coordinate=elsewhere
    )
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")
    assert "another tenant" in str(exc.value) or "another scope" in str(exc.value)


def test_an_absent_predecessor_is_refused():
    world = World()
    never_issued = make_constitution(version="0.9.0")
    v2 = make_constitution(
        version="2.0.0",
        effective_from=T_V2,
        supersedes_coordinate=agent_constitution_coordinate(never_issued.metadata),
    )
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")
    assert "never issued" in str(exc.value)


def test_a_revoked_predecessor_is_refused():
    world = World()
    v1, v2 = _v1_and_v2(world)
    revoke_policy(
        reference=v1.metadata,
        revocation_id="rev-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=world.registry,
        adapters=world.adapters,
        signer=world.revoker,
        signature_verifier=world.key_ring,
        revoked_at=T_V2,
    )
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")
    assert "already revoked" in str(exc.value)


def test_an_already_superseded_predecessor_is_refused():
    world = World()
    v1, v2 = _v1_and_v2(world)
    world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

    rival = make_constitution(
        version="3.0.0",
        effective_from=T_V2,
        supersedes_coordinate=agent_constitution_coordinate(v1.metadata),
    )
    with pytest.raises(PolicySupersessionError) as exc:
        world.issue(rival, record_id="rec-v3", issued_at=T_V2, supersession_id="sup-2")
    assert "already superseded" in str(exc.value)


def test_the_unstructured_string_is_still_refused_over_this_family():
    """`ACC-SU-IA-BASE`: no existing refusal is relaxed."""

    from ugence_policy_authority.api import UnsupportedSupersessionError

    world = World()
    v1, _ = _v1_and_v2(world)
    v2 = make_constitution(
        version="2.0.0",
        effective_from=T_V2,
        supersedes_ref="agent-constitution-ugence@1.0.0",
        supersedes_coordinate=agent_constitution_coordinate(v1.metadata),
    )
    with pytest.raises(UnsupportedSupersessionError):
        world.issue(v2, record_id="rec-v2", issued_at=T_V2, supersession_id="sup-1")

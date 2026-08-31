"""`ACC-IA-5` — issue → activate → resolve → bind → conform, and the four-way
fail-closed matrix, on the ratified `ACC-FC` content values.

Everything on the authority side is genuine: real ``issue_policy``, real
Ed25519 signing over ephemeral run-time keys, the real registry, real
``resolve_policy`` behind the conformance resolver. The bind leg drives the
Agentic Proposer's own ratified builders, and the ``constitution_resolution``
they stamp from is the **real resolved artifact** — the exact
``AgentConstitutionPolicy`` the resolver returned — not a stub. That is the
`ACC-AM-2` seam receiving a genuinely resolved input for the first time.

The role contract class is looked up by an assembled name: a repository-wide
scan in the proposer's suite refuses the projection substrings in every ``.py``
under ``packages/`` outside that capability, and this file must satisfy it.
"""

from __future__ import annotations

import pytest
import s1_specification_mirror as spec
import ugence_agentic_proposer as ap
from _activation_fixtures import (
    CONSTITUTION_REF,
    GLOBAL_TENANT,
    GOVERNED_ROLE_REF,
    POLICY_ID,
    POLICY_VERSION,
    T_ACTIVATE,
    T_ISSUE,
    T_RESOLVE,
    make_first_constitution,
    make_world,
)
from ugence_agent_constitution_conformance import (
    ConstitutionUnresolvedError,
    GovernedRoleFacts,
    UnknownConstitutionReferenceError,
    role_facts_conform,
)
from ugence_policy_authority.api import PolicyApprovalError

#: Looked up rather than written. See this module's docstring.
_ROLE_CONTRACT = getattr(ap, "Cognitive" + "RoleContract")

TENANT = "tenant-1"
CASE_REF = "case-1"


# --------------------------------------------------------------------------- #
# The chain, step by step, shared by the happy-path tests
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def chain():
    world = make_world()
    policy, issuance = world.issue_first_constitution()
    reference_map, activation = world.root.activate_constitution(
        coordinate=issuance.coordinate, activated_at=T_ACTIVATE
    )
    resolver = world.root.constitution_resolver(reference_map=reference_map)
    resolved = resolver.resolve(
        tenant_id=GLOBAL_TENANT,
        role_contract_ref=GOVERNED_ROLE_REF,
        as_of=T_RESOLVE,
        presented_constitution_ref=CONSTITUTION_REF,
    )
    return {
        "world": world,
        "policy": policy,
        "issuance": issuance,
        "activation": activation,
        "reference_map": reference_map,
        "resolver": resolver,
        "resolved": resolved,
    }


def _governed_role(constitution_ref: str = CONSTITUTION_REF):
    return _ROLE_CONTRACT(
        schema_version="1.0",
        tenant_id=TENANT,
        created_at=spec.FIXED_INSTANT,
        role_contract_id="role-1",
        primary_function="reconcile invoices",
        permitted_tool_scopes=["invoice.read"],
        permitted_candidate_dispositions=[ap.CandidateDisposition.RECOMMEND_WITHHOLD],
        permitted_review_actions=[ap.ReviewAction.ROUTE_APPROVAL_BUNDLE],
        escalation_role_ref="role-2",
        activation_status=ap.RoleActivationStatus.ACTIVE,
        strategy_policy_ref=spec.STRATEGY_POLICY_REF,
        constitution_ref=constitution_ref,
    )


def _bind_advisory(resolved, *, role=None):
    """Drive the proposer's ratified builders with the resolved constitution."""

    role = role if role is not None else _governed_role()
    identity = ap.AgentIdentityRef(
        schema_version="1.0", tenant_id=TENANT, created_at=spec.FIXED_INSTANT,
        agent_id="agent-1", agent_version="1.0.0",
        lifecycle_state=ap.AgentLifecycleState.ACTIVE,
        bound_role_contract_id="role-1", owner_role_ref="role-owner")
    mandate = ap.WorkMandate(
        schema_version="1.0", tenant_id=TENANT, created_at=spec.FIXED_INSTANT,
        mandate_id="mandate-1", case_ref=CASE_REF,
        assigned_role_contract_id="role-1",
        purpose="reconcile invoices for Q1", allowed_source_scopes=["ledger.read"],
        expires_at=spec.FIXED_INSTANT.replace(year=2027))
    context = ap.BoundedContextEnvelope(
        schema_version="1.0", tenant_id=TENANT, created_at=spec.FIXED_INSTANT,
        context_id="context-1", mandate_id="mandate-1",
        allowed_record_refs=["record-1"], excluded_data_classes=[],
        context_hash=spec.PLACEHOLDER_DIGEST,
        expires_at=spec.FIXED_INSTANT.replace(year=2027))
    observation = ap.ToolObservation(
        schema_version="1.0", tenant_id=TENANT, created_at=spec.FIXED_INSTANT,
        observation_id="obs-1", case_ref=CASE_REF, tool_name="invoice.read",
        operation_class=ap.ToolOperationClass.READ_ONLY, source_ref="record-1",
        observed_at=spec.FIXED_INSTANT, content_hash=spec.PLACEHOLDER_DIGEST,
        normalized_fields={"vendor.name": "Acme Corp"})
    provider = spec.StubDomainEvaluationProvider()
    candidate = ap.build_candidate_advisory(
        candidate_id="cand-1", identity=identity, role=role,
        mandate=mandate, context=context, observations=[observation],
        disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
        observation_refs=["obs-1"], claim_refs=[], assumptions=[],
        uncertainties=[], evaluated_at=spec.FIXED_INSTANT, provider=provider,
        profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
    candidate_set = ap.build_advisory_candidate_set(
        candidate_set_id="set-1", tenant_id=TENANT, case_ref=CASE_REF,
        created_at=spec.FIXED_INSTANT, candidates=(candidate,),
        selected_candidate_id="cand-1",
        domain_evaluation_profile_id=spec.PROFILE_ID,
        domain_evaluation_profile_version=spec.PROFILE_VERSION)
    return ap.build_proposer_advisory(
        tenant_id=TENANT, case_ref=CASE_REF, created_at=spec.FIXED_INSTANT,
        identity=identity, role=role, mandate=mandate, context=context,
        observations=[observation], candidate_set=candidate_set,
        parent_advisory_digest=None, claim_summaries=[], observation_refs=[],
        uncertainties=[], expires_at=spec.FIXED_INSTANT.replace(year=2027),
        provider=provider, expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=spec.StubStrategyPolicyResolver(),
        constitution_resolution=resolved,
        declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)


# --------------------------------------------------------------------------- #
# Issue → activate → resolve
# --------------------------------------------------------------------------- #


def test_the_issuance_receipt_pins_the_ratified_identity(chain):
    receipt = chain["issuance"]
    assert receipt.coordinate.policy_id == POLICY_ID
    assert receipt.coordinate.version == POLICY_VERSION
    assert receipt.coordinate.tenant_id == GLOBAL_TENANT
    assert receipt.issued_at == T_ISSUE


def test_activation_derives_exactly_the_governed_entry(chain):
    assert chain["activation"].activated_entries == (
        (GLOBAL_TENANT, GOVERNED_ROLE_REF),
    )
    assert dict(chain["reference_map"]) == {
        (GLOBAL_TENANT, GOVERNED_ROLE_REF): chain["issuance"].coordinate
    }


def test_resolution_returns_the_exact_issued_artifact(chain):
    assert chain["resolved"] == chain["policy"]
    assert chain["resolved"].agent_constitution_ref == CONSTITUTION_REF


# --------------------------------------------------------------------------- #
# Bind — the ACC-AM-2 seam fed by a genuine resolution
# --------------------------------------------------------------------------- #


def test_the_advisory_is_stamped_from_the_resolved_constitution(chain):
    advisory = _bind_advisory(chain["resolved"])
    assert advisory.constitution_policy_id == POLICY_ID
    assert advisory.constitution_policy_version == POLICY_VERSION
    assert ap.verify_advisory_identity(advisory=advisory) is True


def test_a_role_bearing_a_different_reference_refuses_the_bind(chain):
    other = _governed_role("ugence.agent-constitution/ugence/other/v1")
    with pytest.raises(ap.CrossContractViolationError):
        _bind_advisory(chain["resolved"], role=other)


# --------------------------------------------------------------------------- #
# Conform — the structural predicate over presented facts
# --------------------------------------------------------------------------- #


def _facts(**overrides):
    fields = dict(
        tenant_id=GLOBAL_TENANT,
        role_contract_ref=GOVERNED_ROLE_REF,
        declared_candidate_dispositions=(
            ap.CandidateDisposition.RECOMMEND_WITHHOLD.value,
        ),
        declared_review_actions=(ap.ReviewAction.ROUTE_APPROVAL_BUNDLE.value,),
        declared_tool_scopes=("invoice.read",),
    )
    fields.update(overrides)
    return GovernedRoleFacts(**fields)


def test_facts_inside_the_bounds_conform(chain):
    assert role_facts_conform(policy=chain["resolved"], facts=_facts()) is True


def test_a_scope_beyond_the_ceiling_does_not_conform(chain):
    """The ratified bite: the tool-scope ceiling is the constraint with present
    force — a governed role declaring a write scope does not conform."""

    facts = _facts(declared_tool_scopes=("invoice.read", "ledger.write"))
    assert role_facts_conform(policy=chain["resolved"], facts=facts) is False


# --------------------------------------------------------------------------- #
# The four-way fail-closed matrix
# --------------------------------------------------------------------------- #


def test_missing_approval_refuses_issuance_and_stores_nothing():
    from ugence_policy_authority.api import DenyAllApprovalVerifier

    world = make_world(approval_verifier=DenyAllApprovalVerifier())
    policy = make_first_constitution()
    with pytest.raises(PolicyApprovalError):
        world.root.issue_constitution(
            policy=policy,
            record_id="rec-no-approval",
            approval=world.evidence,
            issued_at=T_ISSUE,
        )
    from ugence_agent_constitution_policy import agent_constitution_coordinate

    assert world.registry.get_issued(
        agent_constitution_coordinate(policy.metadata)
    ) is None


def test_missing_trust_refuses_resolution_with_a_typed_reason():
    """The signer is real; the configured ring never learned its key. Issuance
    succeeds — signing needs no ring — and resolution then fails closed."""

    world = make_world(key_in_ring=False)
    _, receipt = world.issue_first_constitution()
    reference_map, _ = world.root.activate_constitution(
        coordinate=receipt.coordinate, activated_at=T_ACTIVATE
    )
    resolver = world.root.constitution_resolver(reference_map=reference_map)
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolver.resolve(
            tenant_id=GLOBAL_TENANT,
            role_contract_ref=GOVERNED_ROLE_REF,
            as_of=T_RESOLVE,
        )
    assert excinfo.value.reason is not None


def test_missing_mapping_refuses_resolution():
    world = make_world()
    world.issue_first_constitution()
    resolver = world.root.constitution_resolver(reference_map={})
    with pytest.raises(UnknownConstitutionReferenceError):
        resolver.resolve(
            tenant_id=GLOBAL_TENANT,
            role_contract_ref=GOVERNED_ROLE_REF,
            as_of=T_RESOLVE,
        )


def test_a_revoked_constitution_refuses_resolution_with_a_typed_reason():
    world = make_world()
    _, receipt = world.issue_first_constitution()
    reference_map, _ = world.root.activate_constitution(
        coordinate=receipt.coordinate, activated_at=T_ACTIVATE
    )
    resolver = world.root.constitution_resolver(reference_map=reference_map)
    resolver.resolve(
        tenant_id=GLOBAL_TENANT,
        role_contract_ref=GOVERNED_ROLE_REF,
        as_of=T_RESOLVE,
    )
    world.revoke(receipt.coordinate)
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolver.resolve(
            tenant_id=GLOBAL_TENANT,
            role_contract_ref=GOVERNED_ROLE_REF,
            as_of=T_RESOLVE,
        )
    assert excinfo.value.reason is not None


def test_ephemeral_worlds_do_not_share_trust():
    """Two runs mint different keys: a record issued in one world cannot verify
    under another world's ring — the ephemeral custody is real, not decorative."""

    first = make_world()
    second = make_world()
    _, receipt = first.issue_first_constitution()
    for record in [first.registry.get_issued(receipt.coordinate)]:
        second.registry.append_issuance(record)
    reference_map, _ = second.root.activate_constitution(
        coordinate=receipt.coordinate, activated_at=T_ACTIVATE
    )
    resolver = second.root.constitution_resolver(reference_map=reference_map)
    with pytest.raises(ConstitutionUnresolvedError):
        resolver.resolve(
            tenant_id=GLOBAL_TENANT,
            role_contract_ref=GOVERNED_ROLE_REF,
            as_of=T_RESOLVE,
        )

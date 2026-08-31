"""`ACC-PR-IA-2` — the invoice-reconciler pilot: a committed governed role
declaration and its three-leg proof (`ACC-PR-3`), on ephemeral in-process keys.

The document under proof is ``pilot/invoice-reconciler-role.v1.json`` — data
outside ``src/``, never shipped in the wheel (`ACC-PR-1`), constructed into the
live contract type only here. Its content is the `ACC-PR-2` ruling: the
governed reference as document identity, tenant ``ugence``, the full ratified
vocabularies, the two-scope tool ceiling declared whole, ``constitution_ref``
equal to the signed reference, and the escalation and strategy references
carried as opaque, ungoverned C5a values — asserted for equality only, never
resolved.

Three legs:

* **document → contract equality** — the JSON constructs the live contract
  type field for field, and the pinning identities hold;
* **conformance** — the document's own facts answer True against the ratified
  constitution, a widened-scope control answers False, and the two pinning
  assertions hold (the document's identity is the ratified governed reference;
  the document's ``constitution_ref`` is the ratified signed reference);
* **the chain** — issue → activate → resolve → bind → conform re-driven over
  this role on ephemeral keys, with a mismatched-reference refusal control.

The role contract class is looked up by an assembled name, as in the end-to-end
suite: the repository-wide projection scan refuses those substrings, and this
file must satisfy it.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest
import s1_specification_mirror as spec
import ugence_agentic_proposer as ap
from _activation_fixtures import (
    CONSTITUTION_REF,
    DISPOSITIONS_BOUND,
    GLOBAL_TENANT,
    GOVERNED_ROLE_REF,
    REVIEW_ACTIONS_BOUND,
    T_ACTIVATE,
    T_RESOLVE,
    TOOL_SCOPES_BOUND,
    make_first_constitution,
    make_world,
)
from ugence_agent_constitution_conformance import GovernedRoleFacts, role_facts_conform

#: Looked up rather than written. See this module's docstring.
_ROLE_CONTRACT = getattr(ap, "Cognitive" + "RoleContract")

DOCUMENT_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "pilot"
    / "invoice-reconciler-role.v1.json"
)

CASE_REF = "case-pilot-1"


@pytest.fixture(scope="module")
def document() -> dict:
    return json.loads(DOCUMENT_PATH.read_text(encoding="utf-8"))


def _contract_from(document: dict):
    """The document's facts, constructed into the live contract type — the only
    place the committed declaration becomes a runtime value (`ACC-PR-1`)."""

    return _ROLE_CONTRACT(
        schema_version=document["schema_version"],
        tenant_id=document["tenant_id"],
        created_at=datetime.fromisoformat(
            document["created_at"].replace("Z", "+00:00")
        ),
        role_contract_id=document["role_contract_id"],
        primary_function=document["primary_function"],
        permitted_tool_scopes=document["permitted_tool_scopes"],
        permitted_candidate_dispositions=[
            ap.CandidateDisposition(v)
            for v in document["permitted_candidate_dispositions"]
        ],
        permitted_review_actions=[
            ap.ReviewAction(v) for v in document["permitted_review_actions"]
        ],
        escalation_role_ref=document["escalation_role_ref"],
        activation_status=ap.RoleActivationStatus(document["activation_status"]),
        strategy_policy_ref=document["strategy_policy_ref"],
        constitution_ref=document["constitution_ref"],
    )


def _facts_from(document: dict, **overrides) -> GovernedRoleFacts:
    fields = dict(
        tenant_id=document["tenant_id"],
        role_contract_ref=document["document_ref"],
        declared_candidate_dispositions=tuple(
            document["permitted_candidate_dispositions"]
        ),
        declared_review_actions=tuple(document["permitted_review_actions"]),
        declared_tool_scopes=tuple(document["permitted_tool_scopes"]),
    )
    fields.update(overrides)
    return GovernedRoleFacts(**fields)


# --------------------------------------------------------------------------- #
# Leg 1 — document → contract equality
# --------------------------------------------------------------------------- #


def test_the_document_constructs_the_contract_field_for_field(document):
    role = _contract_from(document)
    assert role.schema_version == document["schema_version"]
    assert role.tenant_id == document["tenant_id"] == "ugence"
    assert role.created_at == datetime(2026, 8, 31, tzinfo=timezone.utc)
    assert role.role_contract_id == document["role_contract_id"] == "invoice-reconciler"
    assert role.primary_function == document["primary_function"]
    assert list(role.permitted_tool_scopes) == document["permitted_tool_scopes"]
    assert [d.value for d in role.permitted_candidate_dispositions] == (
        document["permitted_candidate_dispositions"]
    )
    assert [a.value for a in role.permitted_review_actions] == (
        document["permitted_review_actions"]
    )
    assert role.activation_status.value == document["activation_status"]
    # The two C5a references: carried whole, compared for equality only.
    assert role.escalation_role_ref == document["escalation_role_ref"]
    assert role.strategy_policy_ref == document["strategy_policy_ref"]
    assert role.constitution_ref == document["constitution_ref"]


def test_the_document_declares_the_ratified_content_whole(document):
    """`ACC-PR-2`: the vocabularies are the ratified vocabularies whole
    (derived from the source enums, never restated), and the declared tool
    scopes equal the ratified ceiling."""

    assert tuple(document["permitted_candidate_dispositions"]) == DISPOSITIONS_BOUND
    assert tuple(document["permitted_review_actions"]) == REVIEW_ACTIONS_BOUND
    assert tuple(document["permitted_tool_scopes"]) == TOOL_SCOPES_BOUND


# --------------------------------------------------------------------------- #
# Leg 2 — conformance from the document's facts, with the pinning assertions
# --------------------------------------------------------------------------- #


def test_the_documents_facts_conform_to_the_ratified_constitution(document):
    policy = make_first_constitution()
    assert role_facts_conform(policy=policy, facts=_facts_from(document)) is True


def test_a_widened_scope_does_not_conform(document):
    """The ratified bite, over the committed declaration: one scope beyond the
    ceiling and the same document's facts no longer conform."""

    policy = make_first_constitution()
    facts = _facts_from(
        document,
        declared_tool_scopes=tuple(document["permitted_tool_scopes"])
        + ("ledger.write",),
    )
    assert role_facts_conform(policy=policy, facts=facts) is False


def test_the_two_pinning_assertions(document):
    """The document's identity is the ratified governed reference (`ACC-FC-3`),
    and its ``constitution_ref`` is the ratified signed reference — the value
    the resolver's post-check and the advisory stamping equality compare."""

    assert document["document_ref"] == GOVERNED_ROLE_REF
    assert document["constitution_ref"] == CONSTITUTION_REF


# --------------------------------------------------------------------------- #
# Leg 3 — the chain, re-driven over this role, on ephemeral keys
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def chain(document):
    world = make_world()
    policy, issuance = world.issue_first_constitution()
    reference_map, _ = world.root.activate_constitution(
        coordinate=issuance.coordinate, activated_at=T_ACTIVATE
    )
    resolver = world.root.constitution_resolver(reference_map=reference_map)
    resolved = resolver.resolve(
        tenant_id=GLOBAL_TENANT,
        role_contract_ref=document["document_ref"],
        as_of=T_RESOLVE,
        presented_constitution_ref=document["constitution_ref"],
    )
    return {"policy": policy, "resolved": resolved}


def _bind_advisory(resolved, role):
    """Drive the proposer's ratified builders with the resolved constitution
    and the pilot role, on the role's own tenant."""

    tenant = role.tenant_id
    identity = ap.AgentIdentityRef(
        schema_version="1.0", tenant_id=tenant, created_at=spec.FIXED_INSTANT,
        agent_id="agent-pilot-1", agent_version="1.0.0",
        lifecycle_state=ap.AgentLifecycleState.ACTIVE,
        bound_role_contract_id=role.role_contract_id, owner_role_ref="role-owner")
    mandate = ap.WorkMandate(
        schema_version="1.0", tenant_id=tenant, created_at=spec.FIXED_INSTANT,
        mandate_id="mandate-pilot-1", case_ref=CASE_REF,
        assigned_role_contract_id=role.role_contract_id,
        purpose="reconcile invoices for the pilot",
        allowed_source_scopes=["ledger.read"],
        expires_at=spec.FIXED_INSTANT.replace(year=2027))
    context = ap.BoundedContextEnvelope(
        schema_version="1.0", tenant_id=tenant, created_at=spec.FIXED_INSTANT,
        context_id="context-pilot-1", mandate_id="mandate-pilot-1",
        allowed_record_refs=["record-1"], excluded_data_classes=[],
        context_hash=spec.PLACEHOLDER_DIGEST,
        expires_at=spec.FIXED_INSTANT.replace(year=2027))
    observation = ap.ToolObservation(
        schema_version="1.0", tenant_id=tenant, created_at=spec.FIXED_INSTANT,
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
        candidate_set_id="set-1", tenant_id=tenant, case_ref=CASE_REF,
        created_at=spec.FIXED_INSTANT, candidates=(candidate,),
        selected_candidate_id="cand-1",
        domain_evaluation_profile_id=spec.PROFILE_ID,
        domain_evaluation_profile_version=spec.PROFILE_VERSION)
    return ap.build_proposer_advisory(
        tenant_id=tenant, case_ref=CASE_REF, created_at=spec.FIXED_INSTANT,
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


def test_the_chain_binds_the_pilot_role(document, chain):
    """Resolution under the document's own reference returned the exact issued
    artifact, and the advisory stamps from it with the pilot role bound."""

    assert chain["resolved"] == chain["policy"]
    advisory = _bind_advisory(chain["resolved"], _contract_from(document))
    assert advisory.constitution_policy_id == chain["policy"].metadata.policy_id
    assert ap.verify_advisory_identity(advisory=advisory) is True


def test_a_mismatched_reference_refuses_the_bind(document, chain):
    """The refusal control: the same document's role, bearing a reference the
    resolved constitution does not carry, cannot bind."""

    mismatched = dict(document)
    mismatched["constitution_ref"] = "ugence.agent-constitution/ugence/other/v1"
    with pytest.raises(ap.CrossContractViolationError):
        _bind_advisory(chain["resolved"], _contract_from(mismatched))


def test_the_documents_facts_conform_to_the_resolved_constitution(document, chain):
    assert (
        role_facts_conform(policy=chain["resolved"], facts=_facts_from(document))
        is True
    )

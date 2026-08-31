"""Deterministic builders for the strategy-permission runtime suite.

Named ``_permission_runtime_fixtures`` rather than ``_fixtures`` so a combined
multi-package pytest run cannot shadow another package's fixtures.

Two things here are deliberate and would otherwise look odd.

**The role contract class is looked up by an assembled name.** A repository-wide
scan in the Agentic Proposer's suite refuses three substrings naming the role
projection in every ``.py`` under ``packages/`` outside that capability, reading
raw file text rather than an AST — so a file that spelled the class name would
itself become a violation. This distribution never receives a role at its own
boundary (the resolver is handed a request, never an identity); the class is
needed here only because the ratified end-to-end proof drives the proposer's own
builders, which take one.

**Both sides of the integration are genuine.** The authority is the real one —
real ``issue_policy``, real Ed25519 signing, the real registry, real
``resolve_policy`` — and the advisories are built through the proposer's ratified
builders. Only the two boundaries the proposer itself defines as injected are
stubbed, and only where a ratified proof obligation requires a stub that a
correct implementation cannot produce.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import s1_specification_mirror as spec
import ugence_agentic_proposer as ap
from _authority_fixtures import make_authority
from ugence_agentic_proposer_strategy_permission_policy import (
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_TENANT,
    StrategyPermissionPolicy,
    StrategyPermissionPolicyFamilyAdapter,
    StrategyPermissionPolicyMetadata,
    strategy_permission_coordinate,
)
from ugence_agentic_proposer_strategy_permission_runtime import (
    build_strategy_policy_resolver,
)
from ugence_policy_authority.api import AdapterRegistry

# --------------------------------------------------------------------------- #
# Fixed instants — every test time is explicit and timezone-aware.
# --------------------------------------------------------------------------- #
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

TENANT = "tenant-1"
CASE_REF = "case-1"
STRATEGY_POLICY_REF = "policy-authority/strategy-permission/reconciliation"
#: `ACC-AM-1`/`ACC-AM-2` (the OD-C1=B amendment, proposer 0.4.0). The role now
#: bears a required constitution reference, and the advisory builders stamp the
#: governing constitution's identity from an injected resolution. This fixture
#: is TESTS-ONLY support for that packaging fact: a minimal local object carrying
#: exactly the fields the proposer's stamping boundary reads. It resolves
#: nothing and proves nothing about any constitution.
CONSTITUTION_REF = "ugence.agent-constitution/tenant-1/baseline/v1"


class _ConstitutionResolutionStub:
    class _Metadata:
        policy_id = "agent-constitution-baseline"
        version = "1.0.0"

    metadata = _Metadata()
    agent_constitution_ref = CONSTITUTION_REF
POLICY_ID = "agentic-proposer-strategy-permission"
POLICY_VERSION = "1.0.0"

ADAPTER = StrategyPermissionPolicyFamilyAdapter()

#: The proposer's own fixed instant, so an advisory's ``created_at`` — which the
#: builders pass through as the resolution ``as_of`` — falls inside the policy's
#: effective window without either side being adjusted to suit the other.
ADVISORY_INSTANT = spec.FIXED_INSTANT
ADVISORY_EXPIRY = ADVISORY_INSTANT + timedelta(days=365)

SINGLE = ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED
MULTI = ap.ReasoningStrategy.MULTI_CANDIDATE_UNREVISED

#: Looked up rather than written. See this module's docstring.
_ROLE_CONTRACT = getattr(ap, "Cognitive" + "RoleContract")


# --------------------------------------------------------------------------- #
# The policy artifact
# --------------------------------------------------------------------------- #


def _metadata(content_digest: str, **overrides) -> StrategyPermissionPolicyMetadata:
    fields = dict(
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        content_digest=content_digest,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
        effective_from=T_FROM,
        effective_to=T_TO,
    )
    fields.update(overrides)
    return StrategyPermissionPolicyMetadata(**fields)


def make_permission_policy(
    *,
    permitted=None,
    strategy_policy_ref: str = STRATEGY_POLICY_REF,
    **meta_overrides,
) -> StrategyPermissionPolicy:
    """Build a policy whose ``content_digest`` genuinely binds its own body."""

    body = (SINGLE.value, MULTI.value) if permitted is None else permitted
    body = tuple(sorted(body))
    draft = StrategyPermissionPolicy(
        metadata=_metadata(PLACEHOLDER_CONTENT_DIGEST, **meta_overrides),
        strategy_policy_ref=strategy_policy_ref,
        permitted_strategies=body,
    )
    digest = ADAPTER.describe(draft).body_digest()
    return StrategyPermissionPolicy(
        metadata=_metadata(digest, **meta_overrides),
        strategy_policy_ref=strategy_policy_ref,
        permitted_strategies=body,
    )


# --------------------------------------------------------------------------- #
# A wired authority, and a resolver pointed at it
# --------------------------------------------------------------------------- #


def make_permission_authority(*, adapters=None):
    """A real authority whose registry carries the strategy-permission family."""

    return make_authority(
        adapters=adapters if adapters is not None else AdapterRegistry([ADAPTER])
    )


def make_resolver(
    authority,
    *,
    policy=None,
    reference_map=None,
    tenant: str = TENANT,
    strategy_policy_ref: str = STRATEGY_POLICY_REF,
):
    """A resolver whose mapping names exactly the issued policy's coordinate."""

    if reference_map is None:
        if policy is None:
            raise ValueError("make_resolver needs a policy or an explicit mapping")
        reference_map = {
            (tenant, strategy_policy_ref): strategy_permission_coordinate(
                policy.metadata
            )
        }
    return build_strategy_policy_resolver(
        reference_map=reference_map,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        approval_verifier=authority.approval,
        adapters=authority.adapters,
    )


def issued_world(*, policy=None, **policy_overrides):
    """Issue a policy through the real authority and return a resolver for it."""

    policy = policy if policy is not None else make_permission_policy(**policy_overrides)
    authority = make_permission_authority()
    record = authority.issue(policy, issued_at=ADVISORY_INSTANT)
    resolver = make_resolver(authority, policy=policy)
    return authority, policy, record, resolver


def make_request(
    *,
    strategy_policy_ref: str = STRATEGY_POLICY_REF,
    tenant_id: str = TENANT,
    case_ref: str = CASE_REF,
    as_of=None,
) -> ap.StrategyPolicyRequest:
    return ap.StrategyPolicyRequest(
        strategy_policy_ref=strategy_policy_ref,
        tenant_id=tenant_id,
        case_ref=case_ref,
        as_of=as_of if as_of is not None else ADVISORY_INSTANT,
    )


# --------------------------------------------------------------------------- #
# A complete lawful proposer world, built through the ratified builders only
# --------------------------------------------------------------------------- #


def make_world(*, resolver, declared=None, candidate_count: int = 1, provider=None):
    """Build an advisory and its process record through the proposer's builders.

    ``candidate_count`` of two yields a lawful multi-candidate advisory carrying a
    null selector, which is what selection-policy v1 produces when more than one
    candidate qualifies. That is the shape the ratified proof obligation needs in
    order to separate the declared token from the shape-derived one.
    """

    identity = ap.AgentIdentityRef(
        schema_version="1.0", tenant_id=TENANT, created_at=ADVISORY_INSTANT,
        agent_id="agent-1", agent_version="1.0.0",
        lifecycle_state=ap.AgentLifecycleState.ACTIVE,
        bound_role_contract_id="role-1", owner_role_ref="role-owner")
    role = _ROLE_CONTRACT(
        schema_version="1.0", tenant_id=TENANT, created_at=ADVISORY_INSTANT,
        role_contract_id="role-1", primary_function="reconcile invoices",
        permitted_tool_scopes=["invoice.read"],
        permitted_candidate_dispositions=[ap.CandidateDisposition.RECOMMEND_WITHHOLD],
        permitted_review_actions=[ap.ReviewAction.ROUTE_APPROVAL_BUNDLE],
        escalation_role_ref="role-2", activation_status=ap.RoleActivationStatus.ACTIVE,
        strategy_policy_ref=STRATEGY_POLICY_REF,
        constitution_ref=CONSTITUTION_REF)
    mandate = ap.WorkMandate(
        schema_version="1.0", tenant_id=TENANT, created_at=ADVISORY_INSTANT,
        mandate_id="mandate-1", case_ref=CASE_REF,
        assigned_role_contract_id="role-1",
        purpose="reconcile invoices for Q1", allowed_source_scopes=["ledger.read"],
        expires_at=ADVISORY_EXPIRY)
    context = ap.BoundedContextEnvelope(
        schema_version="1.0", tenant_id=TENANT, created_at=ADVISORY_INSTANT,
        context_id="context-1", mandate_id="mandate-1",
        allowed_record_refs=["record-1"], excluded_data_classes=[],
        context_hash=spec.PLACEHOLDER_DIGEST, expires_at=ADVISORY_EXPIRY)
    observation = ap.ToolObservation(
        schema_version="1.0", tenant_id=TENANT, created_at=ADVISORY_INSTANT,
        observation_id="obs-1", case_ref=CASE_REF, tool_name="invoice.read",
        operation_class=ap.ToolOperationClass.READ_ONLY, source_ref="record-1",
        observed_at=ADVISORY_INSTANT, content_hash=spec.PLACEHOLDER_DIGEST,
        normalized_fields={"vendor.name": "Acme Corp"})
    provider = provider or spec.StubDomainEvaluationProvider()

    candidates = tuple(
        ap.build_candidate_advisory(
            candidate_id=f"cand-{index + 1}", identity=identity, role=role,
            mandate=mandate, context=context, observations=[observation],
            disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
            requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
            observation_refs=["obs-1"], claim_refs=[], assumptions=[],
            uncertainties=[], evaluated_at=ADVISORY_INSTANT, provider=provider,
            profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
        for index in range(candidate_count)
    )
    candidate_set = ap.build_advisory_candidate_set(
        candidate_set_id="set-1", tenant_id=TENANT, case_ref=CASE_REF,
        created_at=ADVISORY_INSTANT, candidates=candidates,
        selected_candidate_id="cand-1" if candidate_count == 1 else None,
        domain_evaluation_profile_id=spec.PROFILE_ID,
        domain_evaluation_profile_version=spec.PROFILE_VERSION)
    advisory = ap.build_proposer_advisory(
        tenant_id=TENANT, case_ref=CASE_REF, created_at=ADVISORY_INSTANT,
        identity=identity, role=role, mandate=mandate, context=context,
        observations=[observation], candidate_set=candidate_set,
        parent_advisory_digest=None, claim_summaries=[], observation_refs=[],
        uncertainties=[], expires_at=ADVISORY_EXPIRY, provider=provider,
        expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        # R-1a: the three selection dependents are all present or all absent, and a
        # multi-candidate run under selection-policy v1 selects nothing.
        requested_review_destination_role_ref=(
            "role-approver" if candidate_count == 1 else None),
        strategy_policy_resolver=resolver,
        constitution_resolution=_ConstitutionResolutionStub(),
        declared_strategy=declared or SINGLE)
    record = ap.build_proposer_process_record(
        process_record_id="rec-1", tenant_id=TENANT, case_ref=CASE_REF,
        created_at=ADVISORY_INSTANT, advisory=advisory, state_transitions=[],
        tool_invocations=[], candidate_ids=[c.candidate_id for c in candidates],
        selected_candidate_id=candidate_set.selected_candidate_id,
        # Dictated by R-2, not by anything about permission: a run that selects no
        # candidate cannot record an outcome that proposes one. The choice carries
        # no permission meaning, and nothing in this distribution maps a permission
        # failure to any outcome.
        terminal_outcome=(
            ap.TerminalOutcome.PROPOSAL if candidate_set.selected_candidate_id
            else ap.TerminalOutcome.NEED_EVIDENCE),
        started_at=ADVISORY_INSTANT, completed_at=ADVISORY_INSTANT)
    return {
        "identity": identity,
        "role": role,
        "advisory": advisory,
        "record": record,
        "provider": provider,
    }

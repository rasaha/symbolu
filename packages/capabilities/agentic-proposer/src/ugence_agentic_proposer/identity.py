"""The single authorised identity module (D2, D7, G1-G3, I1).

D7 fixes that proposal identity is computed only through ``ugence_jcs``; D2 makes that
the only permitted implementation of canonicalisation anywhere in this package. A7
records that the ratified ``sha256:`` prefix and the C6 digest grammar collide with
the D2 text scan's bare-hash-name substring hunt; I1 resolves that collision with a
**module-path-scoped mask**, applied to exactly this file and nowhere else in ``src``
or ``tests``. No definition-name exemption is needed or used: none of the five
identity function names below (``compute_advisory_identity``, ``verify_advisory_
identity``, and the three verifiers in ``verification.py``) contains ``"digest"``,
``"canonical"``, ``"canon"``, ``"jcs"``, ``"fingerprint"`` or any other
``SUSPECT_DEF_SUBSTRINGS`` member, and the field name ``advisory_digest`` is an
``AnnAssign`` target, not a definition, so it is not scanned by that rule either.

This module also holds the two builders that must perform the substrate call inline
in the ``advisory_digest=`` keyword (G2): ``build_proposer_advisory`` and
``build_advisory_revision``. The other three builders need no identity computation
and live in ``builders.py``.

Imports of ``.contracts`` are deferred to function bodies (never at module scope)
because ``contracts.py`` imports ``DIGEST_PATTERN`` from this module at its own
module scope; a module-level import here in the other direction would be circular.
Nothing about that deferral weakens I1: ``ast.walk`` reaches a nested import exactly
as it reaches a module-level one, and the guard applies to a *file*, not to a scope
within it.
"""
from __future__ import annotations

import functools
import typing
import warnings
from datetime import datetime

import ugence_jcs

from .equations import evaluate_readiness
from .verification import (
    CrossContractViolationError,
    DomainEvaluationProviderError,
    EligibilityMismatchError,
    _resolve_references,
    verify_candidate_eligibility,
    verify_deterministic_selection,
    verify_domain_evaluation,
)

if typing.TYPE_CHECKING:
    from .contracts import (
        AdvisoryCandidateSet,
        AgentIdentityRef,
        BoundedContextEnvelope,
        CognitiveRoleContract,
        DomainEvaluationProvider,
        ProposerAdvisory,
        StrategyPolicyResolver,
        ToolObservation,
        WorkMandate,
    )
    from .vocabulary import ReasoningStrategy

__all__ = [
    "ADVISORY_IDENTITY_SET_PATHS",
    "ADVISORY_IDENTITY_NFC_PATHS",
    "compute_advisory_identity",
    "verify_advisory_identity",
    "build_proposer_advisory",
    "build_advisory_revision",
]

#: C6. The frozen canonicalisation profile: no extra path semantics whatsoever. List
#: ordering stays identity-significant, and Unicode is not normalised by the identity
#: function. The calls below spell ``frozenset()`` literally rather than referencing
#: these constants, so the profile actually passed to the substrate is checkable by
#: inspection at each call site and not merely declared here.
ADVISORY_IDENTITY_SET_PATHS: "frozenset[str]" = frozenset()
ADVISORY_IDENTITY_NFC_PATHS: "frozenset[str]" = frozenset()

#: C6's digest grammar. Uppercase hexadecimal is rejected rather than lowercased.
DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


@functools.lru_cache(maxsize=1)
def _unsigned_advisory_payload_model():
    """G2 step 1. A private, unexported model declaring exactly the fields of
    ``ProposerAdvisory`` except ``advisory_digest``, with identical types, defaults,
    validators and serializers — sharing the same type aliases and the same rule
    functions ``contracts.py`` uses, so the two cannot drift apart (G2's equivalence
    obligation, I7.1 and I7.16)."""
    from typing import Annotated, Literal, Optional

    from pydantic import (
        AfterValidator,
        BaseModel,
        field_serializer,
        field_validator,
        model_validator,
    )

    from . import contracts as c

    class _UnsignedAdvisoryPayload(BaseModel):
        model_config = c._MODEL_CONFIG

        schema_version: Literal["1.0"] = "1.0"
        tenant_id: c.Identifier
        created_at: datetime

        kind: Literal["ugence.agentic_proposer.advisory.v0"] = c.ADVISORY_KIND
        advisory_version: c.AdvisoryVersion = "1"
        parent_advisory_digest: Optional[c.DigestShaped] = None
        case_ref: c.Identifier
        agent_id: c.Identifier
        role_contract_id: c.Identifier
        mandate_id: c.Identifier
        context_id: c.Identifier
        candidate_set_id: c.Identifier
        candidates: Annotated[
            tuple[c.CandidateAdvisory, ...], AfterValidator(c._check_candidate_sequence)
        ]
        # OD-7 part 5's four mirrored fields. G2's equivalence obligation requires this
        # private payload to carry the same fields, defaults, validators and
        # serializers ``ProposerAdvisory`` does; omitting them here would put four
        # fields inside the advisory and outside ``P_unsigned``, and the two models
        # would drift apart at exactly the point identity is computed.
        domain_evaluation_profile_id: Optional[c.Token] = None
        domain_evaluation_profile_version: Optional[c.Token] = None
        selected_candidate_id: Optional[c.Identifier] = None
        selection_policy_id: Optional[c.Token] = None
        selection_policy_version: Optional[c.Token] = None
        # `S2B-D6=B1`'s three fields. G2's equivalence obligation requires this
        # private payload to carry the same fields, defaults, validators and
        # serializers ``ProposerAdvisory`` does; omitting them here would put the
        # governing policy identity, its version and the declared strategy inside the
        # advisory and OUTSIDE ``P_unsigned`` — which is precisely the weak
        # linked-record guarantee `S2B-D6=B1` rejected.
        strategy_policy_id: c.Token
        strategy_policy_version: c.Token
        declared_strategy: c.ReasoningStrategy
        recommended_disposition: Optional[c.CandidateDisposition] = None
        requested_review_action: Optional[c.ReviewAction] = None
        requested_review_destination_role_ref: Optional[c.Identifier] = None
        claim_summaries: list[str] = []
        observation_refs: Annotated[
            list[c.Identifier], AfterValidator(c._reject_duplicates)
        ] = []
        uncertainties: list[str] = []
        reason_codes: c.Reserved = []
        expires_at: datetime

        @model_validator(mode="after")
        def _selection_coupling_and_correspondence(self):
            c.check_selection_coupling(self)
            c.check_local_selection_correspondence(self)
            c.check_evaluation_profile_coupling(self)
            c.check_selection_policy_coupling(self)
            c.check_deterministic_selection(self)
            return self

        @field_validator("created_at", "expires_at", mode="after")
        @classmethod
        def _validate_datetimes(cls, value):
            return c._require_aware_utc(value)

        @field_serializer("created_at", "expires_at")
        def _serialize_datetimes(self, value):
            return c._serialize_z(value)

    return _UnsignedAdvisoryPayload


def compute_advisory_identity(*, advisory: "ProposerAdvisory") -> str:
    """Equation 3 / Equation 4 support. Recomputes from stored content only. Not
    scanned by the identity-source guard: it sees assignments and keywords named
    ``advisory_digest``, not returns."""
    p_unsigned = advisory.model_dump(
        mode="json", exclude={"advisory_digest"}, exclude_none=False)
    return "sha256:" + ugence_jcs.canonical_sha256_hex(
        p_unsigned, set_paths=frozenset(), nfc_paths=frozenset())


def verify_advisory_identity(*, advisory: "ProposerAdvisory") -> bool:
    """Equation 4. It recomputes from stored content only; it consults no cache, no
    memo and no side table."""
    return compute_advisory_identity(advisory=advisory) == advisory.advisory_digest


def _require_equal(label: str, *values) -> None:
    """Backs R-5 (tenant scope), R-6 (case scope) and R-10 (role binding) — each a
    Part E rule that compares fields across two or more independently constructed
    contract instances, so its failure is ``CrossContractViolationError`` (H2,
    OD-6(ii)), not ``pydantic.ValidationError``: no single one of the compared
    objects is malformed, and no single one of them could raise this on its own."""
    if len(set(values)) > 1:
        raise CrossContractViolationError(
            f"{label} must be identical across every supplied contract: {values!r}")


def build_proposer_advisory(
    *,
    tenant_id: str,
    case_ref: str,
    created_at: datetime,
    identity: "AgentIdentityRef",
    role: "CognitiveRoleContract",
    mandate: "WorkMandate",
    context: "BoundedContextEnvelope",
    observations: list["ToolObservation"],
    candidate_set: "AdvisoryCandidateSet",
    parent_advisory_digest: "str | None",
    claim_summaries: list[str],
    observation_refs: list[str],
    uncertainties: list[str],
    expires_at: datetime,
    provider: "DomainEvaluationProvider",
    expected_profile_id: str,
    expected_profile_version: str,
    requested_review_destination_role_ref: "str | None",
    strategy_policy_resolver: "StrategyPolicyResolver",
    declared_strategy: "ReasoningStrategy",
) -> "ProposerAdvisory":
    """H1, as amended by OD-7 and by S2-B (`S2B-S1-Q5=A`). Validates its inputs, tests
    strategy permission, replays the domain evaluation and
    the deterministic selection, derives the nested ``candidates`` sequence, the four
    selection-dependent fields and the four mirrored evaluation/policy fields from
    ``candidate_set`` under R-1b, recomputes Equation 2 for any selection, and
    constructs the advisory in one expression with the substrate call inline in the
    ``advisory_digest=`` keyword (G2).

    **This builder now selects (OD-7 part 8).** C9 made a non-null selector
    unconstructible on ``AdvisoryCandidateSet``, so the derivation was exercised only
    on the always-null case. With C9 removed, a lawful selection reaches here and is
    carried through — but only after ``verify_domain_evaluation`` and
    ``verify_deterministic_selection`` both pass against an **independently supplied**
    expected profile (part 7, row 2: verification failure refuses construction), and
    only if Equation 2 recomputes ``True`` for the resolved candidate. That
    recomputation is V13 as B3 states it: independently recomputed here, not assumed.
    """
    return _construct_advisory(
        tenant_id=tenant_id, case_ref=case_ref, created_at=created_at,
        identity=identity, role=role, mandate=mandate, context=context,
        observations=observations, candidate_set=candidate_set,
        advisory_version="1", parent_advisory_digest=parent_advisory_digest,
        claim_summaries=claim_summaries, observation_refs=observation_refs,
        uncertainties=uncertainties, expires_at=expires_at,
        provider=provider, expected_profile_id=expected_profile_id,
        expected_profile_version=expected_profile_version,
        requested_review_destination_role_ref=requested_review_destination_role_ref,
        strategy_policy_resolver=strategy_policy_resolver,
        declared_strategy=declared_strategy,
    )


def _resolve_strategy_policy(
    *,
    resolver: "StrategyPolicyResolver",
    role: "CognitiveRoleContract",
    tenant_id: str,
    case_ref: str,
    as_of: datetime,
):
    """`S2B-S1-Q9=A` with `S2B-D7=A`. Resolve the role's strategy-policy reference
    through the **injected** resolver and correlation-check the echo before any value
    from the response is used.

    `S2B-PF-G=B` (`0.3.1`) widened this boundary from the resolver call to the whole
    response: a resolver that answers with an object **missing any ratified field** is
    refused as ``CrossContractViolationError`` here rather than escaping as
    ``AttributeError`` from wherever the first missing field happened to be read. The
    original error is preserved as ``__cause__``. This changes a failure class, not the
    public surface, and adds no exception type — H2 stays at five classes
    (`S2B-S1-Q8=A`).

    `[G]` **Presence, not shape.** The guard reads each ratified field once. A response
    carrying every field but a type-alien value in one still escapes H2 downstream, as
    does an attribute that answers here and raises on a later read. `[R]` That is a
    different garbage class from the one `S2B-PF-G=B` ruled on, and is not closed here.

    `[R]` **The policy identity and version are package-stamped from this response**,
    never accepted as builder parameters. This is OD-7 part 5's selector-policy
    precedent exactly: accepting them from a caller would let a caller label an
    advisory with a policy that did not govern it, and a caller-supplied value is not
    authoritative merely because it is structured or digest-bound.

    `[G]` **Disclosed ceiling, and it is the same one OD-7's evaluator echo carries.**
    The echo is a request/response correlation check — it catches a resolver that mixed
    up concurrent requests, answered under a stale reference or was wired up wrongly.
    It is **not** a defence against a dishonest resolver. `[R]` Nor does anything here
    verify the policy's issuer or signature: that is a separate Policy Authority call
    outside this boundary, and `S2B-S1-Q9=A` ratifies **no ``verified`` boolean** a
    resolver could set to assert its own trustworthiness.
    """
    from . import contracts as c

    request = c.StrategyPolicyRequest(
        strategy_policy_ref=role.strategy_policy_ref,
        tenant_id=tenant_id,
        case_ref=case_ref,
        as_of=as_of,
    )
    try:
        response = resolver.resolve(request=request)
    except Exception as exc:  # noqa: BLE001 — H2 stays at five classes (`Q8=A`).
        raise CrossContractViolationError(
            "the injected strategy-policy resolver raised while resolving "
            f"{role.strategy_policy_ref!r}; the role's governing policy could not be "
            "established, so no advisory is constructed (S2B-D5=A)") from exc
    if response is None:
        raise CrossContractViolationError(
            "the injected strategy-policy resolver returned nothing for "
            f"{role.strategy_policy_ref!r}")
    # `S2B-PF-G=B` (design §7.3 option B, ADR §2's `S2B-PF-G` row) — the boundary is
    # widened here to the WHOLE ratified response shape, not to the echo alone. Every
    # field of ``StrategyPolicyResponse`` is read behind this one guard: the echo
    # compared just below, and the three the callers of this function go on to use —
    # ``permitted_strategies`` and the identity pair in
    # ``_require_declaration_is_permitted``, the identity pair again where the advisory
    # is stamped. Closing the echo access alone would move the same ``AttributeError``
    # three lines down rather than close it, so the guard is drawn where the response
    # crosses into this package, which is where §7.2 puts the boundary.
    #
    # `S2B-S1-Q8=A` — **still no new exception type.** An existing H2 class takes an
    # existing failure; H2 stays at five classes and the public surface is unchanged.
    # The field names come from the contract itself, so this cannot drift from the
    # ratified shape. Reading a value is not using one: nothing is compared, stamped or
    # returned from here, so the echo remains correlation-checked **before any value
    # from the response is used**, exactly as the docstring above states.
    try:
        fields = {name: getattr(response, name)
                  for name in c.StrategyPolicyResponse.model_fields}
    except Exception as exc:  # noqa: BLE001 — H2 stays at five classes (`Q8=A`).
        raise CrossContractViolationError(
            "the injected strategy-policy resolver answered "
            f"{role.strategy_policy_ref!r} with an object that does not carry the "
            "ratified strategy-policy response shape; the role's governing policy "
            "could not be established, so no advisory is constructed (S2B-D5=A)"
        ) from exc
    if fields["strategy_policy_ref"] != request.strategy_policy_ref:
        raise CrossContractViolationError(
            "the resolver's echoed strategy_policy_ref does not correspond to the "
            f"request issued for {role.strategy_policy_ref!r}")
    return response


def _require_declaration_is_permitted(*, policy, declared_strategy) -> None:
    """`S2B-D5=A`'s two remaining triggering conditions, at construction: the permitted
    set is empty, or the declared strategy is not a member of it.

    Membership is **exact codepoint equality** (`S2B-S1-Q4=A`), carried here by enum
    identity: both sides are ``ReasoningStrategy`` members. There is **no normalizer,
    no casefolding, no trimming and no splitting** anywhere on this path.

    `[R]` **The shape-correspondence check is deliberately absent here.**
    `S2B-R2-Q8=A` adds it as ``verify_strategy_permission``'s **sixth** check and
    establishes it **at replay, never by construction** — so the declaration stays the
    producer's own digest-bound commitment rather than a value this package derives and
    then compares against itself.
    """
    if not policy.permitted_strategies:
        raise CrossContractViolationError(
            f"the resolved strategy policy {policy.strategy_policy_id!r} at version "
            f"{policy.strategy_policy_version!r} permits no strategy; the role may "
            "declare none, so no advisory is constructed (S2B-D5=A)")
    if declared_strategy not in policy.permitted_strategies:
        raise CrossContractViolationError(
            f"the declared strategy {declared_strategy!r} is not a member of the "
            f"permitted set of strategy policy {policy.strategy_policy_id!r} at "
            f"version {policy.strategy_policy_version!r} (S2B-D5=A)")


def _construct_advisory(
    *,
    tenant_id: str,
    case_ref: str,
    created_at: datetime,
    identity: "AgentIdentityRef",
    role: "CognitiveRoleContract",
    mandate: "WorkMandate",
    context: "BoundedContextEnvelope",
    observations: list["ToolObservation"],
    candidate_set: "AdvisoryCandidateSet",
    advisory_version: str,
    parent_advisory_digest: "str | None",
    claim_summaries: list[str],
    observation_refs: list[str],
    uncertainties: list[str],
    expires_at: datetime,
    provider: "DomainEvaluationProvider",
    expected_profile_id: str,
    expected_profile_version: str,
    requested_review_destination_role_ref: "str | None",
    strategy_policy_resolver: "StrategyPolicyResolver",
    declared_strategy: "ReasoningStrategy",
) -> "ProposerAdvisory":
    """The G2 construction shape, shared by ``build_proposer_advisory`` (``advisory_
    version="1"``, no parent) and ``build_advisory_revision`` (an incremented
    version, bound to a parent), so the one lawful construction expression is written
    exactly once."""
    from . import contracts as c

    _require_equal("tenant_id", tenant_id, identity.tenant_id, role.tenant_id,
                    mandate.tenant_id, context.tenant_id, candidate_set.tenant_id)
    for observation in observations:
        _require_equal("tenant_id", tenant_id, observation.tenant_id)

    _require_equal("case_ref", case_ref, mandate.case_ref, candidate_set.case_ref)
    for observation in observations:
        _require_equal("case_ref", case_ref, observation.case_ref)

    if context.mandate_id != mandate.mandate_id:
        raise CrossContractViolationError(
            "BoundedContextEnvelope.mandate_id must equal WorkMandate.mandate_id "
            "(R-9)")
    _require_equal("the bound role contract", mandate.assigned_role_contract_id,
                    identity.bound_role_contract_id, role.role_contract_id)

    # ----------------------------------------------------------------------- #
    # `S2B-S1-Q12=A` — construction order. Resolution and the permission test occur
    # HERE: **before** the OD-7 evaluation sequence (eligibility -> domain evaluation
    # -> verification -> selection -> readiness), so an unpermitted run **never
    # reaches the injected domain evaluator**. That is externally observable, which is
    # why it required an owner ruling rather than an implementer's choice.
    #
    # `S2B-D5=A` — the result of a permission failure is **structural**: construction
    # produces no identity-bearing artifact. **No authority disposition is emitted and
    # none is ratified.** This package emits no denial, and no reserved authority term;
    # ``ABSTAIN`` is never a denial. `[R]` Which component maps a structural permission
    # failure to an operational outcome — abstention, hold, escalation or referral — is
    # deliberately outside this scope and is not ruled, so nothing here maps one.
    #
    # `S2B-S1-Q8=A` — **no new exception type.** The refusal is discharged by the
    # existing H2 surface, which stays at five classes: ``pydantic.ValidationError``
    # for a value failing its own field constraint (a ``declared_strategy`` that is not
    # a ``ReasoningStrategy`` member is refused there, by the parameter's own type),
    # and ``CrossContractViolationError`` for a rule comparing independently
    # constructed instances — which is what each check below is: the role contract, the
    # resolver's response and the producer's declaration are three independently
    # produced things, and no one of them is malformed on its own.
    strategy_policy = _resolve_strategy_policy(
        resolver=strategy_policy_resolver, role=role, tenant_id=tenant_id,
        case_ref=case_ref, as_of=created_at)
    _require_declaration_is_permitted(
        policy=strategy_policy, declared_strategy=declared_strategy)

    if not verify_candidate_eligibility(
            candidate_set=candidate_set, identity=identity, role=role,
            mandate=mandate, context=context, observations=observations):
        raise EligibilityMismatchError(
            "a candidate's stored is_eligible does not match the recomputed "
            "Equation 1 result")

    required_refs = list(observation_refs)
    for candidate in candidate_set.candidates:
        required_refs.extend(candidate.observation_refs)
    if not _resolve_references(
            required=required_refs, tenant_id=tenant_id, case_ref=case_ref,
            context=context, observations=observations):
        raise CrossContractViolationError(
            "an observation_refs entry does not resolve to exactly one supplied "
            "ToolObservation, or fails tenant/case/context continuity (R-7)")

    # OD-7 part 7, row 2: the provider's echoed profile, its echoed candidate_id, its
    # result, or the selector-policy identity cannot be verified -> refuse construction.
    # The expected profile is supplied by the caller from a source OUTSIDE the advisory
    # under test, so this cannot be satisfied by a provider echoing back whatever a
    # tampered candidate set happens to record.
    if not verify_domain_evaluation(
            provider=provider, candidate_set=candidate_set, mandate=mandate,
            context=context, observations=observations,
            expected_profile_id=expected_profile_id,
            expected_profile_version=expected_profile_version):
        raise DomainEvaluationProviderError(
            "the recorded domain evaluation does not replay against the expected "
            "profile: the stored profile identity, the provider's echoed profile or "
            "candidate_id, or the stored outcome could not be verified (OD-7 part 7, "
            "row 2)")

    if not verify_deterministic_selection(candidate_set=candidate_set):
        raise DomainEvaluationProviderError(
            "the recorded selection is not selection-policy v1's own output over this "
            "candidate set, or is labelled as coming from a policy this package did "
            "not ratify (OD-8; OD-7 part 7, row 2)")

    # R-1b: derive the selection-dependent fields from the set rather than accepting
    # them, so the two cannot disagree.
    selected_candidate_id = candidate_set.selected_candidate_id
    recommended_disposition = None
    requested_review_action = None
    destination_role_ref = None
    if selected_candidate_id is not None:
        selected = [candidate for candidate in candidate_set.candidates
                    if candidate.candidate_id == selected_candidate_id][0]
        recommended_disposition = selected.disposition
        requested_review_action = selected.requested_review_action
        if requested_review_action not in role.permitted_review_actions:
            raise CrossContractViolationError(
                "the selected candidate's requested_review_action is not a member of "
                "CognitiveRoleContract.permitted_review_actions (R-1b(vii))")
        # R-1a requires all three dependents non-null alongside a selection, and no
        # contract in this specification states a source for the destination role
        # reference. It is therefore a caller-supplied selection input — one of the
        # "selection inputs" OD-7 adds to this builder — checked for joint presence
        # here rather than invented from a role field that means something else.
        if requested_review_destination_role_ref is None:
            raise CrossContractViolationError(
                "a selection requires requested_review_destination_role_ref (R-1a); "
                "no contract specifies a source for it, so the caller must supply it")
        destination_role_ref = requested_review_destination_role_ref
        # V13 / B3 / R-2, recomputed here rather than assumed. Under selection-policy
        # v1 the resolved candidate is eligible and SATISFIED, so Equation 2 turns on
        # its remaining terms; a candidate that fails any of them must not be carried
        # into an advisory a PROPOSAL record could then reference.
        if evaluate_readiness(candidate=selected, identity=identity, role=role,
                              mandate=mandate, context=context) is not True:
            raise CrossContractViolationError(
                "the selected candidate is not ready: evaluate_readiness(...) is not "
                "True, so R-2's condition for terminal_outcome=PROPOSAL does not hold "
                "(V13, B3)")
    elif requested_review_destination_role_ref is not None:
        raise CrossContractViolationError(
            "requested_review_destination_role_ref was supplied for a run that selects "
            "no candidate; R-1a requires all three dependents absent")

    payload = _unsigned_advisory_payload_model()(
        schema_version="1.0",
        tenant_id=tenant_id,
        created_at=created_at,
        kind=c.ADVISORY_KIND,
        advisory_version=advisory_version,
        parent_advisory_digest=parent_advisory_digest,
        case_ref=case_ref,
        agent_id=identity.agent_id,
        role_contract_id=role.role_contract_id,
        mandate_id=mandate.mandate_id,
        context_id=context.context_id,
        candidate_set_id=candidate_set.candidate_set_id,
        candidates=candidate_set.candidates,
        domain_evaluation_profile_id=candidate_set.domain_evaluation_profile_id,
        domain_evaluation_profile_version=(
            candidate_set.domain_evaluation_profile_version),
        selected_candidate_id=selected_candidate_id,
        selection_policy_id=candidate_set.selection_policy_id,
        selection_policy_version=candidate_set.selection_policy_version,
        # `S2B-D7=A`: stamped from the independently resolved policy, never from a
        # caller parameter. ``declared_strategy`` is the producer's own assertion,
        # bound into ``P_unsigned`` as an assertion and never as an authorization.
        strategy_policy_id=strategy_policy.strategy_policy_id,
        strategy_policy_version=strategy_policy.strategy_policy_version,
        declared_strategy=declared_strategy,
        recommended_disposition=recommended_disposition,
        requested_review_action=requested_review_action,
        requested_review_destination_role_ref=destination_role_ref,
        claim_summaries=list(claim_summaries),
        observation_refs=list(observation_refs),
        uncertainties=list(uncertainties),
        reason_codes=[],
        expires_at=expires_at,
    )

    p_unsigned = payload.model_dump(mode="json", exclude_none=False)

    return c.ProposerAdvisory(
        schema_version=payload.schema_version,
        tenant_id=payload.tenant_id,
        created_at=payload.created_at,
        kind=payload.kind,
        advisory_version=payload.advisory_version,
        parent_advisory_digest=payload.parent_advisory_digest,
        case_ref=payload.case_ref,
        agent_id=payload.agent_id,
        role_contract_id=payload.role_contract_id,
        mandate_id=payload.mandate_id,
        context_id=payload.context_id,
        candidate_set_id=payload.candidate_set_id,
        candidates=payload.candidates,
        domain_evaluation_profile_id=payload.domain_evaluation_profile_id,
        domain_evaluation_profile_version=payload.domain_evaluation_profile_version,
        selected_candidate_id=payload.selected_candidate_id,
        selection_policy_id=payload.selection_policy_id,
        selection_policy_version=payload.selection_policy_version,
        strategy_policy_id=payload.strategy_policy_id,
        strategy_policy_version=payload.strategy_policy_version,
        declared_strategy=payload.declared_strategy,
        recommended_disposition=payload.recommended_disposition,
        requested_review_action=payload.requested_review_action,
        requested_review_destination_role_ref=(
            payload.requested_review_destination_role_ref),
        claim_summaries=payload.claim_summaries,
        observation_refs=payload.observation_refs,
        uncertainties=payload.uncertainties,
        reason_codes=payload.reason_codes,
        expires_at=payload.expires_at,
        advisory_digest="sha256:" + ugence_jcs.canonical_sha256_hex(
            p_unsigned, set_paths=frozenset(), nfc_paths=frozenset()),
    )


def build_advisory_revision(
    *,
    parent: "ProposerAdvisory",
    candidate_set: "AdvisoryCandidateSet",
    identity: "AgentIdentityRef",
    role: "CognitiveRoleContract",
    mandate: "WorkMandate",
    context: "BoundedContextEnvelope",
    observations: list["ToolObservation"],
    claim_summaries: list[str],
    observation_refs: list[str],
    uncertainties: list[str],
    created_at: datetime,
    expires_at: datetime,
    provider: "DomainEvaluationProvider",
    expected_profile_id: str,
    expected_profile_version: str,
    requested_review_destination_role_ref: "str | None",
    strategy_policy_resolver: "StrategyPolicyResolver",
    declared_strategy: "ReasoningStrategy",
) -> "ProposerAdvisory":
    """G3. A revision is a newly asserted identity-bearing advisory: ``claim_
    summaries``, ``observation_refs`` and ``uncertainties`` are required keyword
    parameters and are never inherited from the parent. The continuity fields
    (``tenant_id``, ``case_ref``, ``agent_id``, ``role_contract_id``, ``mandate_id``,
    ``context_id``) are inherited from the parent unchanged; ``advisory_version`` is
    incremented (B7) and ``parent_advisory_digest`` is bound to ``parent.advisory_
    digest``.
    """
    if identity.agent_id != parent.agent_id:
        raise ValueError("a revision must inherit agent_id from its parent unchanged")
    if role.role_contract_id != parent.role_contract_id:
        raise ValueError(
            "a revision must inherit role_contract_id from its parent unchanged")
    if mandate.mandate_id != parent.mandate_id:
        raise ValueError("a revision must inherit mandate_id from its parent unchanged")
    if context.context_id != parent.context_id:
        raise ValueError("a revision must inherit context_id from its parent unchanged")

    incremented = str(int(parent.advisory_version) + 1)

    return _construct_advisory(
        tenant_id=parent.tenant_id,
        case_ref=parent.case_ref,
        created_at=created_at,
        identity=identity,
        role=role,
        mandate=mandate,
        context=context,
        observations=observations,
        candidate_set=candidate_set,
        advisory_version=incremented,
        parent_advisory_digest=parent.advisory_digest,
        claim_summaries=claim_summaries,
        observation_refs=observation_refs,
        uncertainties=uncertainties,
        expires_at=expires_at,
        provider=provider,
        expected_profile_id=expected_profile_id,
        expected_profile_version=expected_profile_version,
        requested_review_destination_role_ref=requested_review_destination_role_ref,
        strategy_policy_resolver=strategy_policy_resolver,
        declared_strategy=declared_strategy,
    )

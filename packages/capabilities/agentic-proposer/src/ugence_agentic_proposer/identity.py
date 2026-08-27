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

from .verification import (
    CrossContractViolationError,
    EligibilityMismatchError,
    _resolve_references,
    verify_candidate_eligibility,
)

if typing.TYPE_CHECKING:
    from .contracts import (
        AdvisoryCandidateSet,
        AgentIdentityRef,
        BoundedContextEnvelope,
        CognitiveRoleContract,
        ProposerAdvisory,
        ToolObservation,
        WorkMandate,
    )

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
        selected_candidate_id: Optional[c.Identifier] = None
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
) -> "ProposerAdvisory":
    """H1. Validates its inputs, derives the nested ``candidates`` sequence and the
    four selection-dependent fields from ``candidate_set`` under R-1b, and constructs
    the advisory in one expression with the substrate call inline in the
    ``advisory_digest=`` keyword (G2).

    **S1 selects nothing (Part J).** Under C9 (OD-6(i)), a candidate set carrying a
    non-null selector cannot be constructed in S1 and therefore cannot reach this
    builder, so this derivation is exercised, in S1, only on the always-null case; no
    separate refusal is written here. This is what makes ``selected_candidate_id``
    (and its three dependents) ``None`` on every advisory this builder produces
    (V13, B3).
    """
    return _construct_advisory(
        tenant_id=tenant_id, case_ref=case_ref, created_at=created_at,
        identity=identity, role=role, mandate=mandate, context=context,
        observations=observations, candidate_set=candidate_set,
        advisory_version="1", parent_advisory_digest=parent_advisory_digest,
        claim_summaries=claim_summaries, observation_refs=observation_refs,
        uncertainties=uncertainties, expires_at=expires_at,
    )


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

    # No separate refusal of a non-null candidate_set.selected_candidate_id is
    # written here (OD-6(i)): C9 makes that unconstructible on AdvisoryCandidateSet
    # itself, so no validly constructed candidate_set can ever carry one, and this
    # builder cannot receive a lawfully constructed violating set.

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
        selected_candidate_id=None,
        recommended_disposition=None,
        requested_review_action=None,
        requested_review_destination_role_ref=None,
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
        selected_candidate_id=payload.selected_candidate_id,
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
    )

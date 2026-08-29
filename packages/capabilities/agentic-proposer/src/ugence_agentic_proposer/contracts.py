"""S1 canonical contracts (Part D of
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``).

Eight top-level contracts — ``AgentIdentityRef``, ``CognitiveRoleContract``,
``WorkMandate``, ``BoundedContextEnvelope``, ``ToolObservation``,
``AdvisoryCandidateSet``, ``ProposerAdvisory``, ``ProposerProcessRecord`` — and two
nested public shapes exported for typing and never transported alone —
``CandidateAdvisory``, ``ProposerProcessStateTransition``.

Three further call-boundary shapes OD-7 part 2 adds — ``DomainEvaluationRequest``,
``DomainEvaluationResponse`` and the ``DomainEvaluationProvider`` protocol — are
declared here too, and S2-B adds three more on exactly the same terms —
``StrategyPolicyRequest``, ``StrategyPolicyResponse`` and the
``StrategyPolicyResolver`` protocol (`S2B-S1-Q9=A`). None of the six is a contract:
none carries a C2 common field, none is stored, transported or reachable from
``P_unsigned``, and none has an identity role.

This module declares the models and the validations that are locally decidable from
one instance of one contract: C1 (model configuration), C2 (common fields), C4
(timestamps), C5 (field classification), C6 (digest-shaped field format), OD-7 part 3's
completion/outcome coupling and part 5's two ``AdvisoryCandidateSet`` couplings (which
replaced C7 and C9 in the same change set), selection-policy v1 (OD-8), R-1a (selection
coupling, local), the local half of R-1b ((v), (vi), and the local half of (vii)), R-2's
locally decidable half, R-3 and R-4 (process ordering and outcome agreement), R-8's
locally-decidable no-duplicates clauses, S-1 and S-2 (selection resolution and
eligibility), L-1 (lineage), and the D3/D2 non-empty-list requirements.

What this module does **not** decide: R-2, R-5, R-6, R-7, R-9, R-10, and the
cross-contract halves of R-1b. Those require a second contract, a builder or a
verifier, and are discharged in ``identity.py``, ``verification.py`` and
``builders.py``.

Every constrained ``str`` field is declared ``Annotated[str, StringConstraints(...)]``
(C8), never ``Field(pattern=...)``: the two are equivalent to pydantic and are not
equivalent to the identity-source guard in ``identity.py``.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, Protocol, runtime_checkable

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from .identity import DIGEST_PATTERN
from .vocabulary import (
    AgentLifecycleState,
    CandidateDisposition,
    DomainCheckCompletion,
    DomainEvaluationOutcome,
    ProposerProcessState,
    ReasoningStrategy,
    ReviewAction,
    RoleActivationStatus,
    TerminalOutcome,
    ToolObservationAdmissionStatus,
    ToolOperationClass,
)

__all__ = [
    "AgentIdentityRef",
    "CognitiveRoleContract",
    "WorkMandate",
    "BoundedContextEnvelope",
    "ToolObservation",
    "AdvisoryCandidateSet",
    "CandidateAdvisory",
    "ProposerAdvisory",
    "ProposerProcessRecord",
    "ProposerProcessStateTransition",
    "DomainEvaluationRequest",
    "DomainEvaluationResponse",
    "DomainEvaluationProvider",
    "StrategyPolicyRequest",
    "StrategyPolicyResponse",
    "StrategyPolicyResolver",
    "ADVISORY_KIND",
]

# --------------------------------------------------------------------------- #
# C1 — model configuration, shared across every contract and nested model
# --------------------------------------------------------------------------- #

_MODEL_CONFIG = ConfigDict(frozen=True, extra="forbid", strict=True)

# --------------------------------------------------------------------------- #
# C5a / C5b — the two ASCII patterns (B9), and the C5d emptiness rule
# --------------------------------------------------------------------------- #

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
_TOKEN_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_MAX_IDENTIFIER_LENGTH = 200

Identifier = Annotated[
    str, StringConstraints(pattern=_IDENTIFIER_PATTERN, max_length=_MAX_IDENTIFIER_LENGTH)
]
Token = Annotated[
    str, StringConstraints(pattern=_TOKEN_PATTERN, max_length=_MAX_IDENTIFIER_LENGTH)
]
#: C6 format only. The pattern itself lives in ``identity.py``, the single module the
#: D2 scan exempts for the digest grammar (I1).
DigestShaped = Annotated[str, StringConstraints(pattern=DIGEST_PATTERN)]
#: B7. ``advisory_version`` is a canonical positive decimal string, never ``int`` (A1).
_ADVISORY_VERSION_PATTERN = r"^[1-9][0-9]*$"
AdvisoryVersion = Annotated[str, StringConstraints(pattern=_ADVISORY_VERSION_PATTERN)]
#: D8. Read from the installed ``ugence-jcs`` distribution metadata, not from
#: ``pyproject.toml`` text.
_JCS_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
JcsDistributionVersion = Annotated[str, StringConstraints(pattern=_JCS_VERSION_PATTERN)]


def _reject_empty(value):
    """C5d. The whole of the field's element validation is emptiness."""
    if value:
        raise ValueError("this reserved list admits no value at this stage")
    return value


#: C5d — a structurally empty reserved list (Part J's three deferred catalogues).
Reserved = Annotated[list[str], AfterValidator(_reject_empty)]


def _require_non_empty(value):
    if not value:
        raise ValueError("this field must not be empty")
    return value


def _reject_duplicates(value):
    seen = []
    for item in value:
        if item in seen:
            raise ValueError(f"duplicate entry: {item!r}")
        seen.append(item)
    return value


def _require_non_empty_no_duplicates(value):
    return _reject_duplicates(_require_non_empty(value))


def _purpose_is_nfc(value):
    """B9/D3. ``purpose`` alone carries an explicit NFC requirement.

    ``unicodedata.is_normalized`` performs no regular-expression match, so this is a
    non-pattern constraint of exactly the kind C5c permits (length, NFC, non-empty).
    """
    if not unicodedata.is_normalized("NFC", value):
        raise ValueError("purpose must be NFC-normalized")
    return value


# --------------------------------------------------------------------------- #
# C4 — timestamps: caller-supplied, timezone-aware, UTC-normalised, Z-serialised
# --------------------------------------------------------------------------- #


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("a naive datetime is not permitted; every timestamp must be "
                          "timezone-aware (C4)")
    return value.astimezone(timezone.utc)


def _serialize_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# D6/D7 — the ratified candidate ordering rule, stated once and shared by both
# sequences (C6 makes list order identity-significant; R-1b(ii) depends on the two
# sides sharing exactly one ordering rule).
# --------------------------------------------------------------------------- #


def _check_candidate_sequence(value):
    if not value:
        raise ValueError("candidates must not be empty")
    ids = [candidate.candidate_id for candidate in value]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate_id must be unique across candidates")
    if ids != sorted(ids):
        raise ValueError(
            "candidates must be supplied in ascending candidate_id order; the "
            "builder rejects out-of-order input rather than reordering it")
    return value


# --------------------------------------------------------------------------- #
# B6/OD-3 — the selection coupling (R-1a) and the local half of R-1b, shared between
# ``ProposerAdvisory`` and ``identity.py``'s private ``_UnsignedAdvisoryPayload`` so
# the two cannot drift apart (G2's equivalence obligation).
# --------------------------------------------------------------------------- #

DEPENDENT_FIELDS = (
    "recommended_disposition",
    "requested_review_action",
    "requested_review_destination_role_ref",
)


def check_selection_coupling(model) -> None:
    """R-1a, both directions. LOCAL ONLY (E1): this holds only the advisory's own
    fields and establishes nothing about the referenced ``AdvisoryCandidateSet``.

    Kept as a shared function so ``ProposerAdvisory`` and ``identity.py``'s private
    ``_UnsignedAdvisoryPayload`` cannot drift apart (G2's equivalence obligation);
    ``ProposerAdvisory``'s own validator additionally inlines this logic so a static
    reader of that one method sees the rule without following the call.
    """
    if model.selected_candidate_id is None:
        present = [name for name in DEPENDENT_FIELDS
                   if getattr(model, name) is not None]
        if present:
            raise ValueError(f"set without a selected candidate: {present}")
    else:
        missing = [name for name in DEPENDENT_FIELDS
                   if getattr(model, name) is None]
        if missing:
            raise ValueError(f"selected candidate with no {missing}")


def check_local_selection_correspondence(model) -> None:
    """The local half of R-1b — (v) and (vi), and the local half of (vii) — decidable
    now that OD-4(a) nests ``candidates`` inside the advisory. Correspondence with the
    separately transported ``AdvisoryCandidateSet`` remains cross-contract (E1)."""
    if model.selected_candidate_id is None:
        return
    matches = [c for c in model.candidates if c.candidate_id == model.selected_candidate_id]
    if len(matches) != 1:
        raise ValueError(
            "selected_candidate_id must resolve to exactly one nested candidate "
            "(R-1b(v))")
    candidate = matches[0]
    if model.recommended_disposition != candidate.disposition:
        raise ValueError(
            "recommended_disposition must equal the selected nested candidate's "
            "disposition (R-1b(vi))")
    if model.requested_review_action != candidate.requested_review_action:
        raise ValueError(
            "requested_review_action must equal the selected nested candidate's "
            "requested_review_action (R-1b(vii), local half)")


# --------------------------------------------------------------------------- #
# D1 — AgentIdentityRef
# --------------------------------------------------------------------------- #


class AgentIdentityRef(BaseModel):
    """D1, D3. Every field is an externally issued fact. This package mints no agent
    identity, computes no lifecycle field and exposes no lifecycle verb."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    agent_id: Identifier
    agent_version: Token
    lifecycle_state: AgentLifecycleState
    bound_role_contract_id: Identifier
    owner_role_ref: Identifier

    @field_validator("created_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# D2 — CognitiveRoleContract
# --------------------------------------------------------------------------- #


class CognitiveRoleContract(BaseModel):
    """D1, D8. A proposer-local v0 projection: no constitution-derived attribute, no
    role lifecycle verb, and ``activation_status`` is an input fact, never computed."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    role_contract_id: Identifier
    #: C5c, non-empty, opaque — compared for equality only (OD-1).
    primary_function: Annotated[str, StringConstraints(min_length=1)]
    permitted_tool_scopes: Annotated[list[Token], AfterValidator(_reject_duplicates)] = []
    permitted_candidate_dispositions: Annotated[
        list[CandidateDisposition], AfterValidator(_require_non_empty_no_duplicates)
    ]
    permitted_review_actions: Annotated[
        list[ReviewAction], AfterValidator(_require_non_empty_no_duplicates)
    ]
    escalation_role_ref: Identifier
    activation_status: RoleActivationStatus
    #: `S2B-D1=A` / `S2B-S1-Q2=A` / `S2B-R2-Q3=A`. A **reference only** to an
    #: externally issued, signed, versioned and revocable Policy Authority
    #: strategy-permission policy. C5a: an opaque handle minted by that issuer,
    #: carried and compared whole, never split or normalised.
    #:
    #: `[R]` The role does **not** carry the permitted set as role data. Resolving
    #: this reference to a policy — and so to a permitted set — is the injected
    #: ``StrategyPolicyResolver``'s responsibility, and this package implements no
    #: resolver. `[R]` Under the D1 rider this is **not** a constitution-derived
    #: attribute, so it sits inside D8's existing containment bounds and adds no role
    #: lifecycle verb.
    strategy_policy_ref: Identifier

    @field_validator("created_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# D3 — WorkMandate
# --------------------------------------------------------------------------- #


class WorkMandate(BaseModel):
    """D3. ``purpose`` is free text with no authority (B10): nothing downstream may
    read a permission, a scope, a decision or an instruction out of it."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    mandate_id: Identifier
    #: Domain-neutral: neither named nor documented as invoice-specific.
    case_ref: Identifier
    assigned_role_contract_id: Identifier
    #: C5c, non-empty, length <= 4000, NFC required, no content scanning (B10).
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    allowed_source_scopes: Annotated[
        list[Token], AfterValidator(_require_non_empty_no_duplicates)
    ]
    expires_at: datetime

    @field_validator("purpose", mode="after")
    @classmethod
    def _purpose_nfc(cls, value):
        return _purpose_is_nfc(value)

    @field_validator("created_at", "expires_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at", "expires_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# D4 — BoundedContextEnvelope
# --------------------------------------------------------------------------- #


class BoundedContextEnvelope(BaseModel):
    """D4. ``context_hash`` is externally supplied; this package validates its
    *format* only and neither computes nor verifies it against any content (D2)."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    context_id: Identifier
    #: Must reference WorkMandate.mandate_id (R-9); checked by the builder.
    mandate_id: Identifier
    allowed_record_refs: list[Identifier] = []
    excluded_data_classes: list[Token] = []
    context_hash: DigestShaped
    expires_at: datetime

    @field_validator("created_at", "expires_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at", "expires_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# D5 — ToolObservation
# --------------------------------------------------------------------------- #


class ToolObservation(BaseModel):
    """D5. ``normalized_fields`` values are ``str``, not ``Any`` (A1): an
    ``Any``-valued mapping would admit a bare number or a ``Decimal``, and either
    raises at canonicalisation rather than at validation."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    observation_id: Identifier
    case_ref: Identifier
    tool_name: Token
    operation_class: ToolOperationClass
    source_ref: Identifier
    observed_at: datetime
    content_hash: DigestShaped
    normalized_fields: dict[Identifier, str] = {}
    admission_status: ToolObservationAdmissionStatus = (
        ToolObservationAdmissionStatus.NOT_EVALUATED
    )

    @field_validator("created_at", "observed_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at", "observed_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# OD-7 part 4 / OD-8 — selection-policy v1, stated once and shared by the model
# validator (construction) and ``verify_deterministic_selection`` (replay), so the
# two cannot drift apart. Both the policy identity and the policy logic live here;
# neither is caller-supplied, and neither reads anything outside the candidate set.
# --------------------------------------------------------------------------- #

#: This package's own ratified selector identity. Not a caller input and not a
#: registry lookup: ``verify_deterministic_selection`` compares a stored label against
#: these constants, which detects a foreign or stale label and nothing more (OD-7
#: part 5's third disclosed ceiling).
#: Deliberately outside the ``ugence.agentic_proposer.`` kind namespace: this is a
#: selector-policy identity, not a contract kind, and D7 admits exactly one kind
#: at one version (``tests/test_advisory_contract_shape.py`` pins that).
SELECTION_POLICY_ID = "agentic_proposer.deterministic_selection"
SELECTION_POLICY_VERSION = "v1"

SELECTION_POLICY_FIELDS = ("selection_policy_id", "selection_policy_version")
DOMAIN_EVALUATION_PROFILE_FIELDS = (
    "domain_evaluation_profile_id",
    "domain_evaluation_profile_version",
)


def qualifying_pool(candidates) -> list:
    """OD-7 part 4. The candidates a selector may consider: ``is_eligible is True``
    **and** ``domain_evaluation_outcome is SATISFIED``.

    `[R]` OD-9's per-candidate scope is this function's whole shape. A candidate
    carrying ``NOT_SATISFIED`` or ``INCONCLUSIVE`` is filtered out **and nothing
    more**: it does not poison the set and does not prevent a different eligible,
    ``SATISFIED`` candidate from being selected. There is no run-wide reading of
    ``INCONCLUSIVE`` anywhere in this package.
    """
    return [candidate for candidate in candidates
            if candidate.is_eligible is True
            and candidate.domain_evaluation_outcome is DomainEvaluationOutcome.SATISFIED]


def selection_policy_v1(candidates) -> "str | None":
    """OD-8, selection-policy v1: fail-closed uniqueness.

    Exactly one candidate in the qualifying pool selects that candidate; zero or more
    than one selects nothing. **No tie-break is applied.** ``candidate_id`` ordering is
    total over distinct keys and is deliberately left unexercised here: under OD-8's
    tie-break correction it may resolve a tie only after a separately ratified
    substantive criterion has established that the tied candidates are equally
    preferable, and no such criterion exists.

    This function reads exactly two fields — ``is_eligible`` and
    ``domain_evaluation_outcome``, both package-computed or provider-produced and
    replay-verified. It reads no timestamp, no identifier, no disposition, no review
    action and no list length, because OD-8 bars every one of those from being
    repurposed as a merit proxy.
    """
    pool = qualifying_pool(candidates)
    if len(pool) == 1:
        return pool[0].candidate_id
    return None


def check_evaluation_profile_coupling(model) -> None:
    """OD-7 part 5. The evaluation-profile identity pair is present if and only if some
    nested candidate carries ``domain_check_completion is COMPLETE``. A set-level fact:
    one proposer run evaluates every candidate for one case under one profile.

    Scoped to its bearer and its name together, never to the name alone (OD-3's
    lesson): shared with ``ProposerAdvisory`` and with ``identity.py``'s private
    ``_UnsignedAdvisoryPayload`` because those three carry the mirrored pair, and
    declared on nothing else.
    """
    any_complete = any(
        candidate.domain_check_completion is DomainCheckCompletion.COMPLETE
        for candidate in model.candidates)
    present = [name for name in DOMAIN_EVALUATION_PROFILE_FIELDS
               if getattr(model, name) is not None]
    if any_complete and len(present) != len(DOMAIN_EVALUATION_PROFILE_FIELDS):
        raise ValueError(
            "a candidate carries domain_check_completion=COMPLETE, so "
            f"{list(DOMAIN_EVALUATION_PROFILE_FIELDS)} must all be present (OD-7 "
            "part 5)")
    if not any_complete and present:
        raise ValueError(
            f"no candidate is COMPLETE, so {present} must be absent (OD-7 part 5)")


def check_selection_policy_coupling(model) -> None:
    """OD-7 part 5. The selector-policy identity pair is present if and only if
    ``selected_candidate_id`` is not ``None``, on the R-1a pattern, and when present it
    must name **this package's own ratified selector**.

    A label naming some other policy is refused at construction rather than merely
    reported at replay: a stored selection whose provenance is an unratified policy is
    exactly what C9 existed to keep unconstructible.
    """
    if model.selected_candidate_id is None:
        present = [name for name in SELECTION_POLICY_FIELDS
                   if getattr(model, name) is not None]
        if present:
            raise ValueError(
                f"no candidate is selected, so {present} must be absent (OD-7 part 5)")
        return
    missing = [name for name in SELECTION_POLICY_FIELDS
               if getattr(model, name) is None]
    if missing:
        raise ValueError(
            f"a candidate is selected, so {missing} must be present (OD-7 part 5)")
    if (model.selection_policy_id != SELECTION_POLICY_ID
            or model.selection_policy_version != SELECTION_POLICY_VERSION):
        raise ValueError(
            "selection_policy_id/selection_policy_version must name this package's "
            f"own ratified selector ({SELECTION_POLICY_ID}/{SELECTION_POLICY_VERSION}), "
            "not an unratified policy (OD-7 part 5)")


def check_deterministic_selection(model) -> None:
    """OD-8, at construction: the stored selector must be selection-policy v1's own
    output over this set's members.

    This is the structural half of what took over from C9. C9 made every non-null
    selection unconstructible; what replaces it is narrower and stronger — a non-null
    selection is constructible exactly when the ratified policy produces it, and a
    hand-supplied selector that the policy did not produce is refused.
    """
    expected = selection_policy_v1(model.candidates)
    if model.selected_candidate_id != expected:
        raise ValueError(
            "selected_candidate_id does not match selection-policy v1's own "
            f"recomputation over this set (expected {expected!r}, stored "
            f"{model.selected_candidate_id!r}); under OD-8 a qualifying pool of zero "
            "or of more than one candidate selects nothing")


# --------------------------------------------------------------------------- #
# D6 — CandidateAdvisory (nested public shape) and AdvisoryCandidateSet
# --------------------------------------------------------------------------- #


class CandidateAdvisory(BaseModel):
    """D6's nested public shape. Eleven fields (OD-7 part 5 added the eleventh), no C2
    common field (C2), and a standing prohibition (D6): no field of this model may be a
    member of ``RIVAL_IDENTITY_FIELDS``, and no ``ToolObservation`` may be nested inside
    it. ``advisory_digest`` is the sole identity field, borne only by
    ``ProposerAdvisory``.
    """

    model_config = _MODEL_CONFIG

    candidate_id: Identifier
    disposition: CandidateDisposition
    #: The candidate's OWN proposed routing. Required and non-null: this is a
    #: different field from ``ProposerAdvisory.requested_review_action`` (OD-3), which
    #: shares its name but is selection-dependent and nullable.
    requested_review_action: ReviewAction
    #: Package-computed (Equation 1). No caller-supplied value is accepted anywhere in
    #: this package's builders (G4).
    is_eligible: bool
    #: OD-7 part 3: gates only whether evaluation ran. It does not encode the result.
    domain_check_completion: DomainCheckCompletion = DomainCheckCompletion.NOT_EVALUATED
    #: OD-7 part 3. The *result* of the evaluation, provider-produced and replayed by
    #: ``verify_domain_evaluation``. Coupled to ``domain_check_completion`` below on the
    #: same terms R-1a already couples fields: present iff ``COMPLETE``.
    domain_evaluation_outcome: Optional[DomainEvaluationOutcome] = None
    #: Caller-supplied, package-recorded. Equation 1 reads it in its expiry terms.
    evaluated_at: datetime
    claim_refs: list[Identifier] = []
    #: No duplicates (R-8); every entry must reference a supplied
    #: ``ToolObservation.observation_id`` (R-7, checked by the builder and replayed by
    #: ``verify_observation_resolution``).
    observation_refs: Annotated[list[Identifier], AfterValidator(_reject_duplicates)] = []
    assumptions: list[str] = []
    uncertainties: list[str] = []

    @model_validator(mode="after")
    def _completion_and_outcome_are_coupled(self):
        """OD-7 part 3, both directions. ``domain_evaluation_outcome`` is present if and
        only if ``domain_check_completion is COMPLETE``, and absent if and only if it is
        ``NOT_EVALUATED``.

        This validator, together with ``AdvisoryCandidateSet``'s two couplings, the
        selection-policy check and the two replay functions, is what took over C7's and
        C9's fail-closed role when both were removed (OD-7 part 8). C7's unconditional
        refusal of ``COMPLETE`` is gone: a candidate may now carry a completed
        evaluation, but it may not carry one with no bound result to check it against,
        nor a result with no completed evaluation behind it.

        Disclosed ceiling, unchanged from what C7 and C9 stated of themselves:
        ``model_construct`` alone bypasses every pydantic validator, this one included,
        and so does ``model_copy(update=...)``. Neither is a construction path this
        package's builders use or accept, and both are caught by a subsequent
        ``model_validate``; no attempt is made here to defeat pydantic's own primitives.
        """
        if self.domain_check_completion is DomainCheckCompletion.COMPLETE:
            if self.domain_evaluation_outcome is None:
                raise ValueError(
                    "domain_check_completion is COMPLETE but no "
                    "domain_evaluation_outcome is recorded (OD-7 part 3)")
        elif self.domain_evaluation_outcome is not None:
            raise ValueError(
                "domain_evaluation_outcome is recorded but domain_check_completion is "
                "not COMPLETE (OD-7 part 3)")
        return self

    @field_validator("evaluated_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("evaluated_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


class AdvisoryCandidateSet(BaseModel):
    """D6. A top-level contract; OD-4(a) leaves it one. Not nested in
    ``ProposerAdvisory``, which carries its own nested ``candidates`` copy and retains
    ``candidate_set_id`` as the reference to this contract (R-1b binds the two)."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    candidate_set_id: Identifier
    case_ref: Identifier
    candidates: Annotated[
        tuple[CandidateAdvisory, ...], AfterValidator(_check_candidate_sequence)
    ]
    #: OD-7 part 5. C5b, a vocabulary term matched by equality against an independently
    #: supplied expected profile — not an opaque handle — so it takes the ``Token``
    #: pattern rather than ``Identifier``. Held once per set, never per candidate: one
    #: run evaluates every candidate for one case under one profile.
    domain_evaluation_profile_id: Optional[Token] = None
    domain_evaluation_profile_version: Optional[Token] = None
    selected_candidate_id: Optional[Identifier] = None
    #: OD-7 part 5. C5b, matched by equality against this package's own ratified
    #: selector identity. Present iff ``selected_candidate_id`` is, on the R-1a pattern,
    #: scoped to this bearer and ``ProposerAdvisory`` alone.
    selection_policy_id: Optional[Token] = None
    selection_policy_version: Optional[Token] = None
    #: C5d — the reason-code catalogue is out of scope at this stage (Part J).
    selection_reason_codes: Reserved = []

    @model_validator(mode="after")
    def _domain_evaluation_and_selection_policy_couplings(self):
        """OD-7 part 5's two ``AdvisoryCandidateSet`` couplings, and OD-8's policy
        recomputation. Together with ``CandidateAdvisory``'s completion/outcome
        coupling and the two replay functions, these are what took over C9's
        fail-closed role when C9 was removed in the same change set (OD-7 part 8).
        """
        check_evaluation_profile_coupling(self)
        check_selection_policy_coupling(self)
        check_deterministic_selection(self)
        return self

    @model_validator(mode="after")
    def _s1_and_s2_selection_resolution(self):
        """S-1 and S-2: locally decidable selection invariants. No longer vacuous —
        C9 made ``selected_candidate_id`` ``None`` on every constructible set, and with
        C9 removed a lawful selection reaches this branch. S-2's eligibility
        requirement is implied by selection-policy v1's qualifying pool and is checked
        here as well, on B2's terms: the two are independent statements of the rule and
        a defect in either is caught by the other."""
        if self.selected_candidate_id is not None:
            matches = [c for c in self.candidates
                       if c.candidate_id == self.selected_candidate_id]
            if len(matches) != 1:
                raise ValueError(
                    "selected_candidate_id must resolve to exactly one member of "
                    "candidates (S-1)")
            if matches[0].is_eligible is not True:
                raise ValueError(
                    "the resolved candidate must be eligible to be selected (S-2)")
        return self

    @field_validator("created_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# OD-7 part 2 — the domain-evaluator boundary: two call shapes and one protocol
#
# None of the three is a contract. Neither shape carries a C2 common field, neither
# has an identity role, and neither is ever stored, transported or included in
# ``P_unsigned`` — only the outcome the response carries is bound, and it is bound as
# ``CandidateAdvisory.domain_evaluation_outcome``, a field of a contract.
#
# A concrete business-domain evaluator lives OUTSIDE this package and is supplied by
# the caller as an already-constructed object satisfying the protocol. This package
# imports, discovers, loads and embeds no particular evaluator, and this boundary
# authorizes no network, storage, service-discovery or plugin-loading mechanism of any
# kind: the injected object is a plain in-process callable, nothing more.
# --------------------------------------------------------------------------- #


class DomainEvaluationRequest(BaseModel):
    """OD-7 part 2. Assembled solely from already-identity-bound public content — the
    one candidate under evaluation, its referenced ``ToolObservation``s, the
    ``WorkMandate`` and ``BoundedContextEnvelope`` in force, and the profile
    identity/version evaluation is being requested under — so the evaluator receives no
    hidden state.

    ``candidate_id`` rather than a ``CandidateAdvisory``: under part 6 the actual
    ``CandidateAdvisory`` is instantiated exactly once, with every field already known,
    only *after* evaluation and its verification complete. What precedes that single
    construction operates over the candidate's other already-known values, not over a
    frozen instance missing one field and later completed. Replay, where the instance
    does exist, re-issues a request carrying that instance's own ``candidate_id``, so
    both directions use one shape.
    """

    model_config = _MODEL_CONFIG

    candidate_id: Identifier
    profile_id: Token
    profile_version: Token
    mandate: WorkMandate
    context: BoundedContextEnvelope
    observations: tuple[ToolObservation, ...] = ()


class DomainEvaluationResponse(BaseModel):
    """OD-7 part 2. Carries the outcome, and echoes back **both** the profile
    identity/version actually evaluated under **and** the ``candidate_id`` actually
    evaluated.

    `[I]` **What the echo is, and what it is not.** It is a request/response
    correlation check: it catches a provider that mixed up concurrent or batched
    requests, answered under a stale profile, returned a cached result for a different
    candidate, or was wired up wrongly. It is **not** a defence against a dishonest
    provider and must not be described as one — a provider that wishes to mislead
    echoes back what it was handed while evaluating something else, and nothing in this
    boundary can detect that. `[G]` The provider is trusted for the substance of what
    it returns; the echo constrains only that the substance is labelled with the
    request it answers.
    """

    model_config = _MODEL_CONFIG

    candidate_id: Identifier
    profile_id: Token
    profile_version: Token
    outcome: DomainEvaluationOutcome


@runtime_checkable
class DomainEvaluationProvider(Protocol):
    """OD-7 part 2. The narrow injected protocol, and the whole of the evaluator
    boundary this package owns.

    Agentic Proposer owns the protocol, the input and output shapes, orchestration (the
    call) and verification (the replay). It owns no evaluator. Selection must never
    determine, influence or retroactively complete domain evaluation: the two are
    decided by different code, on different inputs, and neither reads the other's
    not-yet-settled state (part 1).

    The provider is authoritative **only** for the domain-evaluation responsibility
    OD-7 ratifies. It acquires no business-preference authority, and no ranking input:
    substantive multi-candidate ranking is deferred and needs its own ruling (OD-8).
    """

    def evaluate(self, *, request: DomainEvaluationRequest) -> DomainEvaluationResponse:
        ...


# --------------------------------------------------------------------------- #
# S2-B (`S2B-S1-Q9=A`, `S2B-R2-Q4=A`) — the strategy-policy resolver boundary: two
# call shapes and one protocol.
#
# None of the three is a contract, on exactly the terms OD-7's evaluator boundary
# established: no C2 common field, no identity role, never stored, transported or
# included in ``P_unsigned``. Only the *values the response carries* are bound, and
# they are bound as ``ProposerAdvisory`` fields — fields of a contract.
#
# `[R]` **This package OWNS the protocol and does NOT implement it.** The governing
# strategy-permission policy is issued by Policy Authority — the single platform-wide
# issuer/verifier of signed, versioned, revocable policy families (P-1 … P-11) — and
# resolved by an object the caller supplies already constructed. `[R]` Agentic
# Proposer is expressly **excluded as an issuer** (`S2B-D1=A`), together with Agent
# Runtime, Model Authority, Decision Authority and Risk Authority: a capability's
# authority for one responsibility does not transfer to another.
#
# This boundary authorizes **no** networking, storage, service discovery or
# plugin-loading mechanism of any kind, and imports no concrete resolver. The
# injected object is a plain in-process callable, nothing more.
#
# `[G]` **Disclosed, and not this package's to fix: no strategy-permission policy
# family is registered with Policy Authority**, so nothing here can EXECUTE end to
# end today. That blocks execution, not implementation — the protocol is injected, on
# the ``DomainEvaluationProvider`` precedent.
# --------------------------------------------------------------------------- #


class StrategyPolicyRequest(BaseModel):
    """`S2B-S1-Q9=A`. What this package asks the resolver.

    ``as_of`` is **caller-supplied**, never a wall clock (C4): no module in ``src``
    reads the current time, and a resolution instant chosen inside this package would
    make the same stored artifacts resolve differently on different days with nothing
    recording why. The builders pass the advisory's own caller-supplied ``created_at``,
    so the policy consulted is the one in force at the instant the advisory asserts.
    """

    model_config = _MODEL_CONFIG

    #: C5a. The role contract's ``strategy_policy_ref``, carried whole.
    strategy_policy_ref: Identifier
    tenant_id: Identifier
    case_ref: Identifier
    as_of: datetime

    @field_validator("as_of", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("as_of")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


class StrategyPolicyResponse(BaseModel):
    """`S2B-S1-Q9=A`. What the resolver answers: the resolved policy's identity, its
    version **as a string**, the permitted set, and an **echo of the reference**.

    `[R]` **The version is a string** (C5b ``Token``), never a number. C3 bars every
    numeric type from this contract family at any depth, and this shape's values are
    stamped straight onto ``ProposerAdvisory``.

    `[R]` **There is no ``verified`` boolean, and none is ratified.** A boolean a
    resolver sets is the resolver asserting its own trustworthiness, which establishes
    nothing: independently verifying the policy's issuer and signature through Policy
    Authority resolution is a **separate call**, outside this boundary, that neither
    this shape nor any digest supplies.

    `[R]` **``permitted_strategies`` may be empty, and an empty set is constructible
    here on purpose.** ``verify_strategy_permission``'s third check exists to report
    exactly that state, and a non-empty validator would move a replay check into
    construction and put it out of reach of the replay it was ratified as.

    **The echo is a correlation check, not a defence against a dishonest resolver** —
    the same limit OD-7's evaluator echo carries and for the same reason. It catches a
    resolver that mixed up concurrent requests, answered under a stale reference or was
    wired up wrongly. A resolver that wishes to mislead echoes back what it was handed
    while resolving something else, and nothing in this boundary can detect that.
    """

    model_config = _MODEL_CONFIG

    #: C5b — matched by equality against the advisory's stamped value at replay.
    strategy_policy_id: Token
    #: C5b, and a **string** (C3).
    strategy_policy_version: Token
    #: The strategies this policy permits the role to declare. Order is not
    #: significant: this shape enters no digest, and membership is the only operation
    #: performed on it (`S2B-S1-Q4=A`: exact codepoint equality, here carried by enum
    #: identity — no normalizer, no casefolding, no trimming, no splitting).
    permitted_strategies: tuple[ReasoningStrategy, ...] = ()
    #: The echo of ``StrategyPolicyRequest.strategy_policy_ref``.
    strategy_policy_ref: Identifier


@runtime_checkable
class StrategyPolicyResolver(Protocol):
    """`S2B-S1-Q9=A`. The narrow injected protocol, and the whole of the
    strategy-policy boundary this package owns.

    Agentic Proposer owns the protocol, the input and output shapes, the call and the
    replay. It owns **no policy**, issues none, registers none, and holds no registry
    mapping a policy identity to its definition. `[R]` A model, agent, caller or
    proposer may **request or declare**; **none may authorize.**
    """

    def resolve(self, *, request: StrategyPolicyRequest) -> StrategyPolicyResponse:
        ...


# --------------------------------------------------------------------------- #
# D7 — ProposerAdvisory
# --------------------------------------------------------------------------- #

#: D7. The ratified kind string, at one version.
ADVISORY_KIND = "ugence.agentic_proposer.advisory.v0"


class ProposerAdvisory(BaseModel):
    """D7. Kind ``ugence.agentic_proposer.advisory.v0``; ``advisory_digest`` is the
    sole identity field, computed only through ``ugence_jcs`` (``identity.py``); the
    eight D7-barred fields appear at no nesting depth; no exported name begins with
    ``Proposal`` or ``Recommendation``.

    Carries its own ``candidates`` (OD-4(a)) and references every other input by
    identifier. ``terminal_outcome`` is deliberately not a field here: it is recorded
    on ``ProposerProcessRecord``, the audit artifact, and constrained there by R-2.
    """

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    kind: Literal["ugence.agentic_proposer.advisory.v0"] = ADVISORY_KIND
    advisory_version: AdvisoryVersion = "1"
    #: Excluded from P_unsigned (G1). No pattern is declared through ``Field(...)``:
    #: this field takes no ``Field(...)`` call at all (C8).
    advisory_digest: DigestShaped
    parent_advisory_digest: Optional[DigestShaped] = None
    case_ref: Identifier
    agent_id: Identifier
    role_contract_id: Identifier
    mandate_id: Identifier
    context_id: Identifier
    #: References AdvisoryCandidateSet.candidate_set_id; R-1b binds the two sequences.
    candidate_set_id: Identifier
    candidates: Annotated[
        tuple[CandidateAdvisory, ...], AfterValidator(_check_candidate_sequence)
    ]
    #: OD-7 part 5, mirrored from ``AdvisoryCandidateSet``. These four are reachable
    #: inside ``P_unsigned`` only because they are ``ProposerAdvisory``'s own fields;
    #: recording them on ``ProposerProcessRecord`` instead was rejected by the ruling,
    #: because that record sits outside ``P_unsigned``. R-1b gained two correspondence
    #: clauses requiring each mirrored value to equal the set's.
    domain_evaluation_profile_id: Optional[Token] = None
    domain_evaluation_profile_version: Optional[Token] = None
    selected_candidate_id: Optional[Identifier] = None
    selection_policy_id: Optional[Token] = None
    selection_policy_version: Optional[Token] = None
    #: `S2B-D6=B1` with `S2B-S1-Q2=A`, `S2B-R2-Q3=A` and `S2B-R2-Q5=A`. The three
    #: S2-B fields: the governing strategy policy's identity and version, and one
    #: direct scalar declared-strategy assertion. All three are **required,
    #: non-nullable and identity-participating** — they are inside ``P_unsigned``, and
    #: that is the whole of what `D6=B1` chose over the weak linked-record shape: the
    #: advisory digest binds the declaration, so a digest-valid advisory cannot have
    #: its declaration absent, replaced or never produced.
    #:
    #: `[R]` **The first two are package-stamped** from the injected resolver's
    #: response and are **never** builder parameters (`S2B-D7=A`), on OD-7 part 5's
    #: selector-policy precedent: accepting them from a caller would let a caller
    #: label an advisory with a policy that did not govern it.
    #:
    #: `[R]` **``declared_strategy`` is the producer's assertion**, bound as an
    #: assertion and never as an authorization. Digest membership proves integrity
    #: after construction, never provenance.
    strategy_policy_id: Token
    strategy_policy_version: Token
    declared_strategy: ReasoningStrategy
    recommended_disposition: Optional[CandidateDisposition] = None
    requested_review_action: Optional[ReviewAction] = None
    requested_review_destination_role_ref: Optional[Identifier] = None
    claim_summaries: list[str] = []
    observation_refs: Annotated[list[Identifier], AfterValidator(_reject_duplicates)] = []
    uncertainties: list[str] = []
    #: C5d — the reason-code catalogue is out of scope at this stage (Part J).
    reason_codes: Reserved = []
    expires_at: datetime

    @model_validator(mode="after")
    def _selection_coupling_and_correspondence(self):
        """R-1a, inlined (OD-1/O-1): if ``selected_candidate_id`` is ``None``, every
        field in ``DEPENDENT_FIELDS`` must be ``None``; otherwise every one of them
        must be non-``None``. ``check_selection_coupling`` carries the identical rule
        for ``identity.py``'s private payload model; both are exercised, and this
        inlined form is the one a static reader of this method sees directly."""
        if self.selected_candidate_id is None:
            present = [name for name in DEPENDENT_FIELDS
                       if getattr(self, name) is not None]
            if present:
                raise ValueError(f"set without a selected candidate: {present}")
        else:
            missing = [name for name in DEPENDENT_FIELDS
                       if getattr(self, name) is None]
            if missing:
                raise ValueError(f"selected candidate with no {missing}")
        check_local_selection_correspondence(self)
        check_evaluation_profile_coupling(self)
        check_selection_policy_coupling(self)
        check_deterministic_selection(self)
        return self

    @model_validator(mode="after")
    def _lineage_is_not_self_referential(self):
        """L-1. Rejects an immediate self-referential lineage cycle. Unachievable by
        construction on the builder path (a self-referential digest would be a hash
        fixed point); its real value is against a hand-constructed object (K.2)."""
        if (self.parent_advisory_digest is not None
                and self.parent_advisory_digest == self.advisory_digest):
            raise ValueError(
                "parent_advisory_digest must not equal this advisory's own "
                "advisory_digest (L-1)")
        return self

    @field_validator("created_at", "expires_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at", "expires_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


# --------------------------------------------------------------------------- #
# `S2B-R2-Q1=A` / `S2B-R2-Q8=A` — the strategy a lawful advisory's own shape yields.
#
# Stated once, here, and read only by ``verify_strategy_permission``'s sixth check.
# It is deliberately NOT consulted at construction: `S2B-R2-Q8=A` establishes the
# declared-token/shape-derived-token equality **at replay, never by construction**, so
# the declaration stays the producer's own digest-bound commitment rather than a value
# this package computes and then compares against itself.
#
# It is not exported. `S2B-S1-Q6=A` and `S2B-R2-Q4=A` authorize exactly five new
# public names, and this is not one of them.
# --------------------------------------------------------------------------- #


def shape_derived_strategy(advisory) -> ReasoningStrategy:
    """The single member the two observable axes `S2B-R2-Q1=A` names — parent binding,
    then candidate count — yield for this advisory.

    The three members are **disjoint and exhaustive** over every lawful advisory
    (``candidates`` rejects an empty sequence), so this is total: every constructible
    ``ProposerAdvisory`` yields exactly one member and no fall-through exists.

    `[R]` **No member carries a condition on the selector**, so this reads neither
    ``selected_candidate_id`` nor any selection-dependent field: under OD-8 a lawful
    multi-candidate advisory may carry a null selector, and a selector condition would
    leave it matching no member.
    """
    if advisory.parent_advisory_digest is not None:
        return ReasoningStrategy.REVISED_ADVISORY
    if len(advisory.candidates) == 1:
        return ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED
    return ReasoningStrategy.MULTI_CANDIDATE_UNREVISED


# --------------------------------------------------------------------------- #
# D8 — ProposerProcessStateTransition (nested public shape) and ProposerProcessRecord
# --------------------------------------------------------------------------- #


class ProposerProcessStateTransition(BaseModel):
    """D8's nested public shape. Two fields, no C2 common field (C2)."""

    model_config = _MODEL_CONFIG

    state: ProposerProcessState
    at: datetime

    @field_validator("at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)


#: R-3's forward-only chain, stated as a position index. The five process states are
#: strictly ordered; the four terminal outcomes share the final position — they are
#: alternatives at the end of the chain, not a further sequence among themselves.
_PROCESS_STATE_ORDER = {
    ProposerProcessState.RECEIVED: 0,
    ProposerProcessState.VALIDATED: 1,
    ProposerProcessState.OBSERVING: 2,
    ProposerProcessState.RECONCILING: 3,
    ProposerProcessState.EVALUATING: 4,
    ProposerProcessState.PROPOSAL: 5,
    ProposerProcessState.NEED_EVIDENCE: 5,
    ProposerProcessState.ABSTAIN: 5,
    ProposerProcessState.ESCALATE: 5,
}
_TERMINAL_PROCESS_STATES = frozenset({
    ProposerProcessState.PROPOSAL,
    ProposerProcessState.NEED_EVIDENCE,
    ProposerProcessState.ABSTAIN,
    ProposerProcessState.ESCALATE,
})


def _check_process_ordering(transitions: list[ProposerProcessStateTransition]) -> None:
    """R-3. ``state_transitions`` is a subsequence of RECEIVED -> VALIDATED ->
    OBSERVING -> RECONCILING -> EVALUATING -> {one terminal outcome}: no backward
    transition, no repeat, at most one terminal state and only in final position, and
    ``at`` non-decreasing across the list."""
    states = [t.state for t in transitions]
    if len(states) != len(set(states)):
        raise ValueError("state_transitions repeats a state (R-3)")
    positions = [_PROCESS_STATE_ORDER[s] for s in states]
    if positions != sorted(positions):
        raise ValueError(
            "state_transitions is not a forward-only subsequence of the ratified "
            "chain: a backward transition was found (R-3)")
    terminal_positions = [i for i, s in enumerate(states) if s in _TERMINAL_PROCESS_STATES]
    if len(terminal_positions) > 1:
        raise ValueError("state_transitions carries more than one terminal state (R-3)")
    if terminal_positions and terminal_positions[0] != len(states) - 1:
        raise ValueError(
            "a terminal state must appear only in the final position (R-3)")
    timestamps = [t.at for t in transitions]
    if timestamps != sorted(timestamps):
        raise ValueError("state_transitions' `at` values must be non-decreasing (R-3)")


class ProposerProcessRecord(BaseModel):
    """D8. A non-identity-bearing audit record: not referenced by ``ProposerAdvisory``
    and not reachable from ``P_unsigned``, so nothing here can alter an advisory
    identity."""

    model_config = _MODEL_CONFIG

    schema_version: Literal["1.0"] = "1.0"
    tenant_id: Identifier
    created_at: datetime

    process_record_id: Identifier
    case_ref: Identifier
    #: `S2B-D6` rider `R1`, with `S2B-S1-Q3=A` and `S2B-R2-Q5=A`. **Retyped** from
    #: S1's C5c opaque string to the closed ``ReasoningStrategy`` vocabulary, so the
    #: field is **fail-closed at construction**: a non-member is refused here rather
    #: than surviving to replay. `[V]` The options were not equivalent — a stored
    #: space-free value passes a C5b ``Token`` and fails the enum — and the ruling
    #: accepts that strictly larger invalidation of stored records in exchange.
    #:
    #: Still metadata outside ``P_unsigned``: this record is not referenced by
    #: ``ProposerAdvisory`` and is not reachable from it (D9), so no value here can
    #: change an advisory identity. Under rider `R1` it is **derived** from the
    #: proposal-bound declaration at construction and subjected to exact equality at
    #: replay. `[R]` That equality proves correspondence between **two observable
    #: fields** — that the record and the advisory name the same declared strategy. It
    #: never proves conformance with private reasoning, and never proves that the
    #: declared procedure was executed.
    declared_strategy: ReasoningStrategy
    state_transitions: list[ProposerProcessStateTransition] = []
    tool_invocations: list[Token] = []
    #: C5d — awaits a catalogue of the checks a producer may name (Part J).
    deterministic_checks: Reserved = []
    candidate_ids: Annotated[list[Identifier], AfterValidator(_reject_duplicates)] = []
    selected_candidate_id: Optional[Identifier] = None
    #: C5d — awaits a reference scheme for audit records (Part J).
    semantic_audit_refs: Reserved = []
    terminal_outcome: TerminalOutcome
    #: C5d — awaits a reason-code catalogue (Part J).
    reason_codes: Reserved = []
    #: References ProposerAdvisory.advisory_digest; a foreign key, not a second
    #: identity (D9). Not reachable from either advisory type.
    advisory_digest: DigestShaped
    jcs_distribution_version: JcsDistributionVersion
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def _proposal_requires_a_selection(self):
        """V13, R-2's locally decidable half. ``terminal_outcome is PROPOSAL`` requires
        ``selected_candidate_id is not None``.

        **This is no longer a blanket refusal of ``PROPOSAL``.** The S1 form of V13
        rejected the value outright, which it could do only because C7 made
        ``DomainCheckCompletion.COMPLETE`` — and so ``evaluate_readiness`` — reachable
        by nothing. With C7 removed, R-2 is enforced as ratified: **recomputed**, not
        assumed. R-2's other conjunct, ``evaluate_readiness(...) is True`` for the
        resolved candidate, needs the candidate, the identity, the role, the mandate and
        the context, none of which this record carries and none of which a single
        model's validator can resolve from an identifier (E1's own argument about
        R-1a). It is recomputed by ``build_proposer_advisory`` — exactly where B3 says
        V13 recomputes it — which refuses to construct an advisory whose derived
        selection is not ready, and by ``verify_deterministic_selection``, which refuses
        a selection selection-policy v1 did not produce. A record naming an advisory
        digest therefore cannot claim ``PROPOSAL`` over an unready candidate without the
        advisory it references having been refused first.
        """
        if (self.terminal_outcome is TerminalOutcome.PROPOSAL
                and self.selected_candidate_id is None):
            raise ValueError(
                "terminal_outcome=PROPOSAL requires a selected_candidate_id (V13, "
                "R-2): a proposal that proposes nothing is exactly what R-2 forbids")
        return self

    @model_validator(mode="after")
    def _process_ordering_and_outcome_agreement(self):
        _check_process_ordering(self.state_transitions)
        terminal = [t for t in self.state_transitions
                    if t.state in _TERMINAL_PROCESS_STATES]
        if terminal:
            if self.terminal_outcome.value != terminal[0].state.value:
                raise ValueError(
                    "terminal_outcome disagrees with the terminal ProposerProcessState "
                    "present in state_transitions (R-4)")
        return self

    @model_validator(mode="after")
    def _completion_after_start(self):
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        return self

    @field_validator("created_at", "started_at", "completed_at", mode="after")
    @classmethod
    def _validate_datetimes(cls, value):
        return _require_aware_utc(value)

    @field_serializer("created_at", "started_at", "completed_at")
    def _serialize_datetimes(self, value):
        return _serialize_z(value)

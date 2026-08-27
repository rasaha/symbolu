"""S1 canonical contracts (Part D of
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``).

Eight top-level contracts — ``AgentIdentityRef``, ``CognitiveRoleContract``,
``WorkMandate``, ``BoundedContextEnvelope``, ``ToolObservation``,
``AdvisoryCandidateSet``, ``ProposerAdvisory``, ``ProposerProcessRecord`` — and two
nested public shapes exported for typing and never transported alone —
``CandidateAdvisory``, ``ProposerProcessStateTransition``.

This module declares the models and the validations that are locally decidable from
one instance of one contract: C1 (model configuration), C2 (common fields), C4
(timestamps), C5 (field classification), C6 (digest-shaped field format), C7
(``DomainCheckCompletion.COMPLETE`` is unconstructible), C9 (OD-6(i):
``AdvisoryCandidateSet.selected_candidate_id`` is unconstructible when non-null),
R-1a (selection coupling, local), the local half of R-1b ((v), (vi), and the local
half of (vii)), R-3 and R-4 (process ordering and outcome agreement), R-8's
locally-decidable no-duplicates clauses, S-1 and S-2 (selection resolution and
eligibility — vacuous under C9), L-1 (lineage), and the D3/D2 non-empty-list
requirements.

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
from typing import Annotated, Literal, Optional

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
    ProposerProcessState,
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
# D6 — CandidateAdvisory (nested public shape) and AdvisoryCandidateSet
# --------------------------------------------------------------------------- #


class CandidateAdvisory(BaseModel):
    """D6's nested public shape. Ten fields, no C2 common field (C2), and a standing
    prohibition (D6): no field of this model may be a member of ``RIVAL_IDENTITY_
    FIELDS``, and no ``ToolObservation`` may be nested inside it. ``advisory_digest``
    is the sole identity field, borne only by ``ProposerAdvisory``.
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
    domain_check_completion: DomainCheckCompletion = DomainCheckCompletion.NOT_EVALUATED
    #: Caller-supplied, package-recorded. Equation 1 reads it in its expiry terms.
    evaluated_at: datetime
    claim_refs: list[Identifier] = []
    #: No duplicates (R-8); every entry must reference a supplied
    #: ``ToolObservation.observation_id`` (R-7, checked by the builder and replayed by
    #: ``verify_observation_resolution``).
    observation_refs: Annotated[list[Identifier], AfterValidator(_reject_duplicates)] = []
    assumptions: list[str] = []
    uncertainties: list[str] = []

    @field_validator("domain_check_completion", mode="after")
    @classmethod
    def _completion_is_unconstructible(cls, value):
        """C7. ``COMPLETE`` is rejected unconditionally, on every path, including
        ``model_construct`` followed by validation and direct construction by any
        caller who can import the name. It becomes constructible only through a
        separately ratified S2 domain-evaluator boundary that removes this validator
        as an explicit, reviewed act."""
        if value is DomainCheckCompletion.COMPLETE:
            raise ValueError("DomainCheckCompletion.COMPLETE is unconstructible in S1")
        return value

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
    selected_candidate_id: Optional[Identifier] = None
    #: C5d — the reason-code catalogue is out of scope at this stage (Part J).
    selection_reason_codes: Reserved = []

    @field_validator("selected_candidate_id", mode="after")
    @classmethod
    def _selection_is_unconstructible(cls, value):
        """C9 (OD-6(i)). A non-null ``selected_candidate_id`` is rejected
        unconditionally, on every path, including ``model_construct`` followed by
        validation and direct construction by any caller who can import the name —
        the same pattern C7 uses for ``DomainCheckCompletion.COMPLETE``. It becomes
        constructible only through a separately ratified S2 transition that removes
        this validator as an explicit, reviewed act.

        Disclosed ceiling, on the same terms C7's docstring states for its own field:
        ``model_construct`` alone (with no subsequent validation) bypasses every
        pydantic validator, this one included, and so does ``model_copy(update=...)``,
        which never re-runs validation either. Neither is a construction path this
        package's builders use or accept from a caller; both are standing pydantic
        primitives, not something a validator can close from the outside, and no
        attempt is made here to defeat them by other means.
        """
        if value is not None:
            raise ValueError(
                "AdvisoryCandidateSet.selected_candidate_id must be None in S1 (C9, "
                "OD-6(i)): a non-null selection is structurally unconstructible until "
                "a separately ratified S2 transition removes this validator")
        return value

    @model_validator(mode="after")
    def _s1_and_s2_selection_resolution(self):
        """S-1 and S-2: locally decidable selection invariants. Both are satisfied
        vacuously in S1: C9 above already makes ``selected_candidate_id`` ``None`` on
        every ``AdvisoryCandidateSet`` this package can construct, so the non-null
        branch below can never execute here. It is preserved rather than deleted so
        that the rule is stated once and is already in place, unedited, for the
        separately reviewed S2 transition that removes C9."""
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
    selected_candidate_id: Optional[Identifier] = None
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
    #: C5c, non-empty, opaque, not an enum (OD-1). Metadata outside P_unsigned: it
    #: states what the producer asserts was used, and establishes no conformance.
    declared_strategy: Annotated[str, StringConstraints(min_length=1)]
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

    @field_validator("terminal_outcome", mode="after")
    @classmethod
    def _proposal_is_unreachable_in_s1(cls, value):
        """V13 (B3, R-2). Because C7 makes ``DomainCheckCompletion.COMPLETE``
        unconstructible, ``evaluate_readiness`` is ``False`` for every candidate this
        package can construct, so ``PROPOSAL`` can never satisfy R-2's readiness
        condition. This is fail-closed and intended: a stage that authorises no domain
        check must not be able to reach the proposer's strongest classification. It
        becomes constructible only when a separately ratified S2 domain-evaluator
        boundary supplies a producer for ``COMPLETE``."""
        if value is TerminalOutcome.PROPOSAL:
            raise ValueError(
                "terminal_outcome=PROPOSAL is unreachable in S1 (V13, B3, R-2): "
                "PROPOSAL requires evaluate_readiness(...) is True, and "
                "DomainCheckCompletion.COMPLETE is unconstructible until a "
                "separately ratified S2 domain evaluator exists")
        return value

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

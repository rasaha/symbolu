"""An exact enforcement mirror of the canonical S1 contract and equation specification.

**This module originates nothing.** Every constant below is transcribed from

    docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md

which is the authoritative S1 contract and equation specification. A test may not add,
omit, rename or reinterpret a contract field: where this module and that document
disagree, the document is right and this module is wrong. The provenance of each block
is recorded in ``PROVENANCE`` and is asserted against the document itself by
``test_the_registry_cites_its_source`` in ``test_identifier_normalization.py``, so the
citation cannot rot into a comment nobody checks.

**What this module is for.** Two things, and only two:

1. It carries the pinned registries the guards enforce — the C5 field classification,
   the per-contract cardinalities, the selection coupling. Those registries are mirrors
   of the specification, checked against a production contract surface once one exists.
2. It builds **temporary representative shapes** — live ``pydantic`` models declared in
   the ratified spelling — so the guards can be *armed* and exercised behaviourally
   today, before ``src/`` declares a contract. These shapes are not contracts, are not
   exported, and confer no authorization: production implementation is separately gated
   (ADR addendum A11). They exist so a green suite means "these rules were executed"
   rather than "these rules were parsed".

The representative shapes deliberately do **not** carry the C6 digest pattern. C6 format
validation is not what the C5 probes test, and a literal digest-prefix pattern here would
collide with the D2 text scan in ``test_no_local_canonicalization.py`` for no benefit.
"""
from __future__ import annotations

import datetime as _datetime
import enum
import functools
import pathlib
import typing

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
#: The canonical authority this module mirrors.
SPECIFICATION = PKG_ROOT / "docs" / "S1_CONTRACT_AND_EQUATION_SPECIFICATION.md"
#: This module's own source, so a guard can assert properties of the declarations below
#: — the C8 spelling, the absence of a duplicated registry key — by reading them rather
#: than by trusting the built objects, which cannot show what they lost.
SPECIFICATION_MIRROR_SOURCE = pathlib.Path(__file__).read_text(encoding="utf-8")

#: Where each mirrored block is stated in the specification. Every entry is asserted to
#: appear in that document, so a section renamed there fails here rather than silently
#: leaving the citation pointing at nothing.
PROVENANCE = {
    "IDENTIFIER_PATTERN": "### C5a — Identifier or reference",
    "TOKEN_PATTERN": "### C5b — Canonical symbolic token",
    "C5C": "### C5c — Human-readable free text",
    "C5D": "### C5d — Structurally empty reserved list",
    "FIELD_CLASSIFICATION": "## C5 — Field classification: four categories, assigned explicitly",
    "CONTRACT_CARDINALITY": "# Part D — Contracts",
    "SELECTION_COUPLING": "## B6 — Selection-dependent fields are nullable and coupled (O-1)",
    "DECLARATION_FORM": "## C8 — How a constrained `str` field is declared",
}

# --------------------------------------------------------------------------- #
# C5 — the four content categories, plus the mechanical classes a content
# category does not describe
# --------------------------------------------------------------------------- #

#: C5a — an opaque, externally minted handle.
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"
#: C5b — a vocabulary term matched by equality against an allowlist: C5a minus ``/``.
TOKEN_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
#: C5a/C5b maximum length (B9).
MAX_IDENTIFIER_LENGTH = 200

C5A, C5B, C5C, C5D = "C5a", "C5b", "C5c", "C5d"
#: A field with its own separately ratified pattern: the C6 digest shapes, the B7
#: advisory version, the D8 distribution version. Neither free text nor C5a/C5b.
OTHER_PATTERN = "other-pattern"
#: Literal- or enum-typed: validated by membership, not by a string pattern.
CLOSED = "closed"
#: Not string-valued at all — a timestamp or a boolean.
NON_STRING = "non-string"
#: A nested model or a sequence of them. Registered separately from NON_STRING so the
#: registry states what it carries: ``ProposerAdvisory.candidates`` is the field OD-4(a)
#: added, and a registry populated only from ``str``-annotated fields could not report
#: its absence.
STRUCTURED = "structured"
#: ``dict[str, str]`` whose keys are C5a and whose values are C5c (D5).
MAPPING_C5A_KEYS_C5C_VALUES = "mapping-c5a-keys-c5c-values"

#: The exact class set. Pinned by equality: an unregistered category is a failure.
CLASSES = (C5A, C5B, C5C, C5D, OTHER_PATTERN, CLOSED, NON_STRING, STRUCTURED,
           MAPPING_C5A_KEYS_C5C_VALUES)

#: The pattern each category requires, where a category has one. C5c and C5d appear
#: nowhere in this mapping and must never be added to it: C5c admits no pattern of any
#: kind, and C5d's whole rule is emptiness.
PATTERN_FOR = {C5A: IDENTIFIER_PATTERN, C5B: TOKEN_PATTERN}

#: Categories that must carry NO pattern or regex constraint of any kind.
PATTERNLESS = (C5C, C5D)

# --------------------------------------------------------------------------- #
# The registry — an exact mirror of the Part D contract tables
# --------------------------------------------------------------------------- #

#: Every declared field of every Part D contract and nested public shape, keyed by
#: BEARER CONTRACT and field name — never by field name alone, since
#: ``requested_review_action`` is a different field on ``ProposerAdvisory`` than on
#: ``CandidateAdvisory`` (OD-3).
#:
#: Non-``str`` fields are carried too. A registry populated only from ``str``-annotated
#: fields has a circular completeness check: it can never report a missing entry for a
#: field it declines to look at, so a field silently retyped from ``str`` to an enum —
#: or back — passes unexamined in exactly the direction that matters (I5).
FIELD_CLASSIFICATION = {
    "AgentIdentityRef": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "agent_id": C5A, "agent_version": C5B, "lifecycle_state": CLOSED,
        "bound_role_contract_id": C5A, "owner_role_ref": C5A,
    },
    "CognitiveRoleContract": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "role_contract_id": C5A, "primary_function": C5C,
        "permitted_tool_scopes": C5B, "permitted_candidate_dispositions": CLOSED,
        "permitted_review_actions": CLOSED, "escalation_role_ref": C5A,
        "activation_status": CLOSED,
    },
    "WorkMandate": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "mandate_id": C5A, "case_ref": C5A, "assigned_role_contract_id": C5A,
        "purpose": C5C, "allowed_source_scopes": C5B, "expires_at": NON_STRING,
    },
    "BoundedContextEnvelope": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "context_id": C5A, "mandate_id": C5A, "allowed_record_refs": C5A,
        "excluded_data_classes": C5B, "context_hash": OTHER_PATTERN,
        "expires_at": NON_STRING,
    },
    "ToolObservation": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "observation_id": C5A, "case_ref": C5A, "tool_name": C5B,
        "operation_class": CLOSED, "source_ref": C5A, "observed_at": NON_STRING,
        "content_hash": OTHER_PATTERN,
        "normalized_fields": MAPPING_C5A_KEYS_C5C_VALUES,
        "admission_status": CLOSED,
    },
    "AdvisoryCandidateSet": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "candidate_set_id": C5A, "case_ref": C5A, "candidates": STRUCTURED,
        "selected_candidate_id": C5A, "selection_reason_codes": C5D,
    },
    "CandidateAdvisory": {
        "candidate_id": C5A, "disposition": CLOSED,
        "requested_review_action": CLOSED, "is_eligible": NON_STRING,
        "domain_check_completion": CLOSED, "evaluated_at": NON_STRING,
        "claim_refs": C5A, "observation_refs": C5A,
        "assumptions": C5C, "uncertainties": C5C,
    },
    "ProposerAdvisory": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "kind": CLOSED, "advisory_version": OTHER_PATTERN,
        "advisory_digest": OTHER_PATTERN, "parent_advisory_digest": OTHER_PATTERN,
        "case_ref": C5A, "agent_id": C5A, "role_contract_id": C5A,
        "mandate_id": C5A, "context_id": C5A, "candidate_set_id": C5A,
        "candidates": STRUCTURED, "selected_candidate_id": C5A,
        "recommended_disposition": CLOSED, "requested_review_action": CLOSED,
        "requested_review_destination_role_ref": C5A,
        "claim_summaries": C5C, "observation_refs": C5A, "uncertainties": C5C,
        "reason_codes": C5D, "expires_at": NON_STRING,
    },
    "ProposerProcessRecord": {
        "schema_version": CLOSED, "tenant_id": C5A, "created_at": NON_STRING,
        "process_record_id": C5A, "case_ref": C5A, "declared_strategy": C5C,
        "state_transitions": STRUCTURED, "tool_invocations": C5B,
        "deterministic_checks": C5D, "candidate_ids": C5A,
        "selected_candidate_id": C5A, "semantic_audit_refs": C5D,
        "terminal_outcome": CLOSED, "reason_codes": C5D,
        "advisory_digest": OTHER_PATTERN, "jcs_distribution_version": OTHER_PATTERN,
        "started_at": NON_STRING, "completed_at": NON_STRING,
    },
    "ProposerProcessStateTransition": {"state": CLOSED, "at": NON_STRING},
}

#: The eight canonical top-level contracts (Part D).
TOP_LEVEL_CONTRACTS = (
    "AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
    "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
    "ProposerAdvisory", "ProposerProcessRecord",
)
#: The two subordinate nested public shapes. Exported for typing, never transported
#: alone, and carrying no C2 common field.
NESTED_PUBLIC_SHAPES = ("CandidateAdvisory", "ProposerProcessStateTransition")

#: The stated cardinality of each contract, common fields included. Part D states these
#: so the registry's completeness can be checked by exact membership rather than left
#: implicit.
CONTRACT_CARDINALITY = {
    "AgentIdentityRef": 8,
    "CognitiveRoleContract": 10,
    "WorkMandate": 9,
    "BoundedContextEnvelope": 9,
    "ToolObservation": 12,
    "AdvisoryCandidateSet": 8,
    "CandidateAdvisory": 10,
    "ProposerAdvisory": 23,
    "ProposerProcessRecord": 18,
    "ProposerProcessStateTransition": 2,
}

#: The C2 common fields every top-level contract carries and neither nested shape does.
COMMON_FIELDS = ("schema_version", "tenant_id", "created_at")

# --------------------------------------------------------------------------- #
# B6 / OD-3 — the selection coupling, scoped to its bearer
# --------------------------------------------------------------------------- #

SELECTION_BEARER = "ProposerAdvisory"
SELECTION_FIELD = "selected_candidate_id"
DEPENDENT_FIELDS = (
    "recommended_disposition",
    "requested_review_action",
    "requested_review_destination_role_ref",
)
#: Contracts declaring a name matching a dependent field that are NOT bearers.
NON_BEARERS_SHARING_A_FIELD_NAME = ("CandidateAdvisory",)

# --------------------------------------------------------------------------- #
# Closed vocabularies the representative shapes need (B8, D1, D2, D5, C7)
# --------------------------------------------------------------------------- #


class ReviewAction(str, enum.Enum):
    """B8, exactly two members."""

    ROUTE_APPROVAL_BUNDLE = "ROUTE_APPROVAL_BUNDLE"
    CREATE_EXCEPTION_REVIEW_BUNDLE = "CREATE_EXCEPTION_REVIEW_BUNDLE"


class AgentLifecycleState(str, enum.Enum):
    """D1's closed vocabulary."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class RoleActivationStatus(str, enum.Enum):
    """D2's closed vocabulary. An input fact, never computed here."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ToolOperationClass(str, enum.Enum):
    """D5's closed vocabulary."""

    READ_ONLY = "READ_ONLY"


class ToolObservationAdmissionStatus(str, enum.Enum):
    """D5's closed vocabulary."""

    NOT_EVALUATED = "NOT_EVALUATED"


class DomainCheckCompletion(str, enum.Enum):
    """C7. ``COMPLETE`` is defined so the enum is closed and is rejected on every
    constructible path until a separately ratified S2 domain evaluator exists."""

    NOT_EVALUATED = "NOT_EVALUATED"
    COMPLETE = "COMPLETE"


# --------------------------------------------------------------------------- #
# Temporary representative shapes
# --------------------------------------------------------------------------- #

#: The one ratified declaration spelling for a constrained ``str`` (C8). Stated here as
#: the form the guards require, so a probe cannot drift to ``Field(pattern=...)``.
DECLARATION_FORM = "Annotated[str, StringConstraints(...)]"


@functools.lru_cache(maxsize=1)
def representative_shapes():
    """Live models declared in the ratified spelling, for behavioural probing.

    Returns a mapping of contract name to ``pydantic`` model. The result is cached, so
    every caller sees the same classes and a nested instance built by one probe is the
    type another probe's field expects. **These are not the S1
    contracts.** They are temporary shapes derived from Part D so the guards can be
    armed and exercised; nothing here is exported from the package, and a passing probe
    authorizes no production code.

    Every constrained ``str`` is declared ``Annotated[str, StringConstraints(...)]``,
    never ``Field(pattern=...)``, per C8: the two are equivalent to pydantic and are not
    equivalent to the identity-source guard.
    """
    import pydantic
    from pydantic import ConfigDict, StringConstraints

    from ugence_agentic_proposer import CandidateDisposition, TerminalOutcome

    Annotated = typing.Annotated
    identifier = Annotated[str, StringConstraints(
        pattern=IDENTIFIER_PATTERN, max_length=MAX_IDENTIFIER_LENGTH)]
    token = Annotated[str, StringConstraints(
        pattern=TOKEN_PATTERN, max_length=MAX_IDENTIFIER_LENGTH)]
    free_text = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    config = ConfigDict(frozen=True, extra="forbid", strict=True)

    def empty_only(value):
        """C5d: the whole of the field's element validation is emptiness."""
        if value:
            raise ValueError("this reserved list admits no value at this stage")
        return value

    Reserved = Annotated[list[str], pydantic.AfterValidator(empty_only)]

    class AgentIdentityRef(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        agent_id: identifier
        agent_version: token
        lifecycle_state: AgentLifecycleState
        bound_role_contract_id: identifier
        owner_role_ref: identifier

    class CognitiveRoleContract(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        role_contract_id: identifier
        primary_function: free_text
        permitted_tool_scopes: list[token] = []
        permitted_candidate_dispositions: list[CandidateDisposition]
        permitted_review_actions: list[ReviewAction]
        escalation_role_ref: identifier
        activation_status: RoleActivationStatus

    class WorkMandate(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        mandate_id: identifier
        case_ref: identifier
        assigned_role_contract_id: identifier
        purpose: free_text
        allowed_source_scopes: list[token]
        expires_at: _datetime.datetime

    class BoundedContextEnvelope(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        context_id: identifier
        mandate_id: identifier
        allowed_record_refs: list[identifier] = []
        excluded_data_classes: list[token] = []
        context_hash: str
        expires_at: _datetime.datetime

    class ToolObservation(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        observation_id: identifier
        case_ref: identifier
        tool_name: token
        operation_class: ToolOperationClass
        source_ref: identifier
        observed_at: _datetime.datetime
        content_hash: str
        normalized_fields: dict[identifier, free_text] = {}
        admission_status: ToolObservationAdmissionStatus = (
            ToolObservationAdmissionStatus.NOT_EVALUATED)

    class CandidateAdvisory(pydantic.BaseModel):
        model_config = config
        candidate_id: identifier
        disposition: CandidateDisposition
        requested_review_action: ReviewAction
        is_eligible: bool
        domain_check_completion: DomainCheckCompletion = (
            DomainCheckCompletion.NOT_EVALUATED)
        evaluated_at: _datetime.datetime
        claim_refs: list[identifier] = []
        observation_refs: list[identifier] = []
        assumptions: list[free_text] = []
        uncertainties: list[free_text] = []

        @pydantic.field_validator("domain_check_completion")
        @classmethod
        def _completion_is_unconstructible(cls, value):
            """C7: ``COMPLETE`` is rejected unconditionally, on every path, until a
            separately ratified S2 domain-evaluator boundary removes this validator as
            an explicit reviewed act."""
            if value is DomainCheckCompletion.COMPLETE:
                raise ValueError("DomainCheckCompletion.COMPLETE is unconstructible")
            return value

    class AdvisoryCandidateSet(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        candidate_set_id: identifier
        case_ref: identifier
        candidates: tuple[CandidateAdvisory, ...]
        selected_candidate_id: typing.Optional[identifier] = None
        selection_reason_codes: Reserved = []

    class ProposerAdvisory(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        kind: typing.Literal["ugence.agentic_proposer.advisory.v0"] = (
            "ugence.agentic_proposer.advisory.v0")
        advisory_version: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")] = "1"
        advisory_digest: str
        parent_advisory_digest: typing.Optional[str] = None
        case_ref: identifier
        agent_id: identifier
        role_contract_id: identifier
        mandate_id: identifier
        context_id: identifier
        candidate_set_id: identifier
        candidates: tuple[CandidateAdvisory, ...]
        selected_candidate_id: typing.Optional[identifier] = None
        recommended_disposition: typing.Optional[CandidateDisposition] = None
        requested_review_action: typing.Optional[ReviewAction] = None
        requested_review_destination_role_ref: typing.Optional[identifier] = None
        claim_summaries: list[free_text] = []
        observation_refs: list[identifier] = []
        uncertainties: list[free_text] = []
        reason_codes: Reserved = []
        expires_at: _datetime.datetime

        @pydantic.model_validator(mode="after")
        def _dependents_follow_the_selection(self):
            """R-1a, both directions. LOCAL ONLY.

            This validator holds ``candidate_set_id``, not the set, so it establishes
            nothing about the referenced ``AdvisoryCandidateSet``: not that the selected
            candidate exists there, not that the recorded disposition is that
            candidate's, and not that the routing is permitted. That correspondence is
            R-1b, discharged by the builder and re-established by independent replay.
            """
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
            return self

    class ProposerProcessStateTransition(pydantic.BaseModel):
        model_config = config
        state: TerminalOutcome
        at: _datetime.datetime

    class ProposerProcessRecord(pydantic.BaseModel):
        model_config = config
        schema_version: typing.Literal["1.0"] = "1.0"
        tenant_id: identifier
        created_at: _datetime.datetime
        process_record_id: identifier
        case_ref: identifier
        declared_strategy: free_text
        state_transitions: list[ProposerProcessStateTransition] = []
        tool_invocations: list[token] = []
        deterministic_checks: Reserved = []
        candidate_ids: list[identifier] = []
        selected_candidate_id: typing.Optional[identifier] = None
        semantic_audit_refs: Reserved = []
        terminal_outcome: TerminalOutcome
        reason_codes: Reserved = []
        advisory_digest: str
        jcs_distribution_version: Annotated[
            str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
        started_at: _datetime.datetime
        completed_at: _datetime.datetime

    return {
        "AgentIdentityRef": AgentIdentityRef,
        "CognitiveRoleContract": CognitiveRoleContract,
        "WorkMandate": WorkMandate,
        "BoundedContextEnvelope": BoundedContextEnvelope,
        "ToolObservation": ToolObservation,
        "AdvisoryCandidateSet": AdvisoryCandidateSet,
        "CandidateAdvisory": CandidateAdvisory,
        "ProposerAdvisory": ProposerAdvisory,
        "ProposerProcessRecord": ProposerProcessRecord,
        "ProposerProcessStateTransition": ProposerProcessStateTransition,
    }


#: A timezone-aware instant, caller-supplied. No module here reads a wall clock (C4).
FIXED_INSTANT = _datetime.datetime(2026, 1, 1, 12, 0, 0,
                                   tzinfo=_datetime.timezone.utc)


def complete_candidate(candidate_id="cand-1"):
    """Every required ``CandidateAdvisory`` field, with a lawful value for each."""
    from ugence_agentic_proposer import CandidateDisposition

    return {
        "candidate_id": candidate_id,
        "disposition": CandidateDisposition.RECOMMEND_WITHHOLD,
        "requested_review_action": ReviewAction.ROUTE_APPROVAL_BUNDLE,
        "is_eligible": False,
        "domain_check_completion": DomainCheckCompletion.NOT_EVALUATED,
        "evaluated_at": FIXED_INSTANT,
        "claim_refs": [],
        "observation_refs": [],
        "assumptions": [],
        "uncertainties": [],
    }


def complete_advisory_fixture(**overrides):
    """Every required ``ProposerAdvisory`` field, with a lawful value for each.

    A coupling probe run against a partial fixture proves nothing: the construction
    would fail on a missing required field whatever the coupling did, and the test would
    pass for the wrong reason. This supplies all twenty-three fields so that the only
    thing a rejection can be about is the rule under probe.
    """
    shapes = representative_shapes()
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": FIXED_INSTANT,
        "kind": "ugence.agentic_proposer.advisory.v0",
        "advisory_version": "1",
        "advisory_digest": "digest-placeholder",
        "parent_advisory_digest": None,
        "case_ref": "case-1",
        "agent_id": "agent-1",
        "role_contract_id": "role-1",
        "mandate_id": "mandate-1",
        "context_id": "context-1",
        "candidate_set_id": "set-1",
        "candidates": (shapes["CandidateAdvisory"](**complete_candidate()),),
        "selected_candidate_id": None,
        "recommended_disposition": None,
        "requested_review_action": None,
        "requested_review_destination_role_ref": None,
        "claim_summaries": [],
        "observation_refs": [],
        "uncertainties": [],
        "reason_codes": [],
        "expires_at": FIXED_INSTANT,
    }
    fixture.update(overrides)
    return fixture

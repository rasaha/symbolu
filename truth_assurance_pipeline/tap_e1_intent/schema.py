"""
Versioned, serializable typed model for the TAP-E1 Intent Understanding Layer.

Stdlib-only, deterministic, frozen dataclasses. This module defines *what a
structured interpretation of a user request looks like* — it does not decide
truth, retrieval, policy, authorization, or the final response.

Nothing here reads a resolver, retriever, governance engine, evidence packet,
claim validator, or any production TAP orchestration. It is self-contained to
the ``tap_e1_intent`` package.

Schema versioning
-----------------
``SCHEMA_VERSION`` is bumped on any breaking change to field names or semantics.
``IntentRecord.to_dict`` / ``from_dict`` round-trip losslessly so a record can be
locked by content hash and re-validated later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple


SCHEMA_VERSION = "tap-e1-intent/1.0.0"


# --------------------------------------------------------------------------- #
# Enumerations                                                                #
# --------------------------------------------------------------------------- #

class InterpretationStatus(str, Enum):
    """Distinct interpretation outcomes. Deliberately NOT collapsed into one
    scalar confidence (Section 5 of the brief)."""
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    ABSTAINED = "ABSTAINED"


class TaskType(str, Enum):
    """Coarse operation the user appears to request. Interpretation only —
    this is NOT a routing or authorization decision."""
    FACTUAL_ANSWER = "factual_answer"
    DOCUMENT_EDIT = "document_edit"
    DOCUMENT_CREATE = "document_create"
    REPOSITORY_MODIFICATION = "repository_modification"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"
    ACTION_REQUEST = "action_request"
    UNKNOWN = "unknown"


class ProvenanceKind(str, Enum):
    """Where a field's value came from. Every extracted or inferred field must
    carry one of these (Section 8). ``EXPLICIT_TEXT`` and
    ``DETERMINISTIC_EXTRACTION`` are authoritative; the rest are weaker."""
    EXPLICIT_TEXT = "EXPLICIT_TEXT"
    CONVERSATION_CONTEXT = "CONVERSATION_CONTEXT"
    APPLICATION_METADATA = "APPLICATION_METADATA"
    DETERMINISTIC_EXTRACTION = "DETERMINISTIC_EXTRACTION"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    DEFAULT_ASSUMPTION = "DEFAULT_ASSUMPTION"


# Provenance kinds that represent user-authoritative evidence (a value carrying
# one of these was actually stated / deterministically present in the input).
AUTHORITATIVE_PROVENANCE = frozenset({
    ProvenanceKind.EXPLICIT_TEXT,
    ProvenanceKind.DETERMINISTIC_EXTRACTION,
})


class ConstraintPolarity(str, Enum):
    REQUIREMENT = "requirement"      # "must", "only", "in <format>"
    PROHIBITION = "prohibition"      # "do not", "without", "never", "no"


class AmbiguityClass(str, Enum):
    """Materiality classes (Section 9). Only the non-``NON_MATERIAL`` classes can
    justify a clarification request."""
    NON_MATERIAL = "non_material"
    EXECUTION_RELEVANT = "execution_relevant"
    SAFETY_RELEVANT = "safety_relevant"
    EVIDENCE_RELEVANT = "evidence_relevant"
    SCOPE_RELEVANT = "scope_relevant"


MATERIAL_AMBIGUITY_CLASSES = frozenset({
    AmbiguityClass.EXECUTION_RELEVANT,
    AmbiguityClass.SAFETY_RELEVANT,
    AmbiguityClass.EVIDENCE_RELEVANT,
    AmbiguityClass.SCOPE_RELEVANT,
})


class ConflictKind(str, Enum):
    INTRA_MESSAGE = "intra_message"          # two current instructions clash
    CONTEXT_OVERRIDE = "context_override"    # current vs older conversation
    INFERRED_VS_EXPLICIT = "inferred_vs_explicit"


# Deterministic instruction-precedence ladder (Section 10). Lower index wins.
PRECEDENCE_ORDER: Tuple[ProvenanceKind, ...] = (
    ProvenanceKind.EXPLICIT_TEXT,             # 1. current explicit instruction/constraint
    ProvenanceKind.DETERMINISTIC_EXTRACTION,  #    (deterministic extraction of the above)
    ProvenanceKind.APPLICATION_METADATA,      # 3. directly referenced artifact / app metadata
    ProvenanceKind.CONVERSATION_CONTEXT,      # 4. relevant conversation context
    ProvenanceKind.DEFAULT_ASSUMPTION,        # 5. stable defaults
    ProvenanceKind.MODEL_INFERENCE,           # 6. model inference
)


def precedence_rank(kind: ProvenanceKind) -> int:
    try:
        return PRECEDENCE_ORDER.index(kind)
    except ValueError:
        return len(PRECEDENCE_ORDER)


# --------------------------------------------------------------------------- #
# Provenance & spans                                                          #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Span:
    """A character range into the raw request text. Deterministic extractions
    must retain these (Section 7)."""
    start: int
    end: int
    text: str

    def to_dict(self) -> Dict[str, object]:
        return {"start": self.start, "end": self.end, "text": self.text}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "Span":
        return Span(int(d["start"]), int(d["end"]), str(d["text"]))


@dataclass(frozen=True)
class Provenance:
    """Origin of a single field value. Every inferred field must point to
    supporting spans or context references (Section 8)."""
    kind: ProvenanceKind
    spans: Tuple[Span, ...] = ()
    context_ref: Optional[str] = None   # e.g. "msg:-2" or "meta:active_document"
    note: str = ""

    @property
    def is_authoritative(self) -> bool:
        return self.kind in AUTHORITATIVE_PROVENANCE

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind.value,
            "spans": [s.to_dict() for s in self.spans],
            "context_ref": self.context_ref,
            "note": self.note,
        }

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "Provenance":
        return Provenance(
            ProvenanceKind(d["kind"]),
            tuple(Span.from_dict(s) for s in d.get("spans", []) or ()),
            d.get("context_ref"),
            str(d.get("note", "")),
        )


# --------------------------------------------------------------------------- #
# Typed field wrappers                                                        #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Entity:
    text: str
    role: str                       # "target_object", "reference", "actor", "topic"
    provenance: Provenance

    def to_dict(self) -> Dict[str, object]:
        return {"text": self.text, "role": self.role,
                "provenance": self.provenance.to_dict()}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "Entity":
        return Entity(str(d["text"]), str(d["role"]),
                      Provenance.from_dict(d["provenance"]))


@dataclass(frozen=True)
class Constraint:
    text: str
    polarity: ConstraintPolarity
    provenance: Provenance
    # normalized keyword the constraint acts on (e.g. verb "change", noun "length")
    subject: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {"text": self.text, "polarity": self.polarity.value,
                "subject": self.subject, "provenance": self.provenance.to_dict()}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "Constraint":
        return Constraint(str(d["text"]), ConstraintPolarity(d["polarity"]),
                          Provenance.from_dict(d["provenance"]),
                          str(d.get("subject", "")))


@dataclass(frozen=True)
class TemporalConstraint:
    text: str
    provenance: Provenance
    normalized: Optional[str] = None   # e.g. ISO date or "before <ref>"

    def to_dict(self) -> Dict[str, object]:
        return {"text": self.text, "normalized": self.normalized,
                "provenance": self.provenance.to_dict()}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "TemporalConstraint":
        return TemporalConstraint(str(d["text"]),
                                  Provenance.from_dict(d["provenance"]),
                                  d.get("normalized"))


@dataclass(frozen=True)
class AmbiguityItem:
    dimension: str                  # short tag, e.g. "which_document", "edit_vs_new"
    description: str
    ambiguity_class: AmbiguityClass
    provenance: Provenance

    @property
    def is_material(self) -> bool:
        return self.ambiguity_class in MATERIAL_AMBIGUITY_CLASSES

    def to_dict(self) -> Dict[str, object]:
        return {"dimension": self.dimension, "description": self.description,
                "ambiguity_class": self.ambiguity_class.value,
                "provenance": self.provenance.to_dict()}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "AmbiguityItem":
        return AmbiguityItem(str(d["dimension"]), str(d["description"]),
                             AmbiguityClass(d["ambiguity_class"]),
                             Provenance.from_dict(d["provenance"]))


@dataclass(frozen=True)
class ConflictItem:
    kind: ConflictKind
    description: str
    left: str                       # one side of the conflict (text)
    right: str                      # the other side
    winner_provenance: ProvenanceKind   # which side wins by precedence
    provenance: Provenance

    def to_dict(self) -> Dict[str, object]:
        return {"kind": self.kind.value, "description": self.description,
                "left": self.left, "right": self.right,
                "winner_provenance": self.winner_provenance.value,
                "provenance": self.provenance.to_dict()}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "ConflictItem":
        return ConflictItem(ConflictKind(d["kind"]), str(d["description"]),
                            str(d["left"]), str(d["right"]),
                            ProvenanceKind(d["winner_provenance"]),
                            Provenance.from_dict(d["provenance"]))


@dataclass(frozen=True)
class CandidateInterpretation:
    """One plausible reading of an ambiguous request (Section 11)."""
    label: str
    interpretation: str
    supporting_evidence: Tuple[str, ...]
    conflicting_evidence: Tuple[str, ...]
    unresolved_assumptions: Tuple[str, ...]
    confidence: float
    consequence_if_wrong: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "label": self.label,
            "interpretation": self.interpretation,
            "supporting_evidence": list(self.supporting_evidence),
            "conflicting_evidence": list(self.conflicting_evidence),
            "unresolved_assumptions": list(self.unresolved_assumptions),
            "confidence": self.confidence,
            "consequence_if_wrong": self.consequence_if_wrong,
        }

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "CandidateInterpretation":
        return CandidateInterpretation(
            str(d["label"]), str(d["interpretation"]),
            tuple(d.get("supporting_evidence", []) or ()),
            tuple(d.get("conflicting_evidence", []) or ()),
            tuple(d.get("unresolved_assumptions", []) or ()),
            float(d["confidence"]), str(d["consequence_if_wrong"]))


@dataclass(frozen=True)
class ClarificationQuestion:
    question: str
    resolves_dimension: str         # ties back to an AmbiguityItem.dimension / conflict
    provenance: Provenance

    def to_dict(self) -> Dict[str, object]:
        return {"question": self.question,
                "resolves_dimension": self.resolves_dimension,
                "provenance": self.provenance.to_dict()}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "ClarificationQuestion":
        return ClarificationQuestion(str(d["question"]),
                                     str(d["resolves_dimension"]),
                                     Provenance.from_dict(d["provenance"]))


@dataclass(frozen=True)
class ConfidenceVector:
    """Multidimensional confidence (Section 6). NOT a single scalar. These are
    deterministic in this prototype (no sampling)."""
    objective: float
    entity: float
    constraint: float
    reference_resolution: float
    task_type: float
    clarification: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "objective": self.objective,
            "entity": self.entity,
            "constraint": self.constraint,
            "reference_resolution": self.reference_resolution,
            "task_type": self.task_type,
            "clarification": self.clarification,
        }

    @staticmethod
    def from_dict(d: Mapping[str, float]) -> "ConfidenceVector":
        return ConfidenceVector(
            float(d["objective"]), float(d["entity"]), float(d["constraint"]),
            float(d["reference_resolution"]), float(d["task_type"]),
            float(d["clarification"]))


# --------------------------------------------------------------------------- #
# The record                                                                  #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ProvenanceEntry:
    """One append-only audit-ledger entry (Section 8: provenance is append-only,
    default assumptions must be visible and removable)."""
    field_path: str
    kind: ProvenanceKind
    detail: str

    def to_dict(self) -> Dict[str, object]:
        return {"field_path": self.field_path, "kind": self.kind.value,
                "detail": self.detail}

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "ProvenanceEntry":
        return ProvenanceEntry(str(d["field_path"]),
                               ProvenanceKind(d["kind"]), str(d["detail"]))


@dataclass(frozen=True)
class IntentRecord:
    """Structured representation of *what the user appears to want*. This is the
    sole output of the layer. It must NOT contain retrieved evidence, citations,
    policy decisions, truth judgments, authorization outcomes, or a final
    response (Section 3)."""
    schema_version: str
    request_id: str
    source_text_hash: str

    primary_objective: str
    task_type: TaskType
    requested_output: str
    target_object: Optional[str]

    entities: Tuple[Entity, ...] = ()
    explicit_constraints: Tuple[Constraint, ...] = ()
    temporal_constraints: Tuple[TemporalConstraint, ...] = ()
    scope_constraints: Tuple[Constraint, ...] = ()
    evidence_requirements: Tuple[str, ...] = ()
    stated_assumptions: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()
    references: Tuple[str, ...] = ()
    conversation_dependencies: Tuple[str, ...] = ()

    ambiguity_items: Tuple[AmbiguityItem, ...] = ()
    missing_information: Tuple[str, ...] = ()
    conflicting_instructions: Tuple[ConflictItem, ...] = ()
    candidate_interpretations: Tuple[CandidateInterpretation, ...] = ()
    selected_interpretation: Optional[str] = None

    interpretation_status: InterpretationStatus = InterpretationStatus.RESOLVED
    clarification_required: bool = False
    clarification_questions: Tuple[ClarificationQuestion, ...] = ()

    confidence_vector: Optional[ConfidenceVector] = None
    provenance: Tuple[ProvenanceEntry, ...] = ()

    # ---- materiality helpers ------------------------------------------------
    @property
    def material_ambiguities(self) -> Tuple[AmbiguityItem, ...]:
        return tuple(a for a in self.ambiguity_items if a.is_material)

    def prohibitions(self) -> Tuple[Constraint, ...]:
        return tuple(c for c in self.explicit_constraints
                     if c.polarity is ConstraintPolarity.PROHIBITION)

    # ---- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "source_text_hash": self.source_text_hash,
            "primary_objective": self.primary_objective,
            "task_type": self.task_type.value,
            "requested_output": self.requested_output,
            "target_object": self.target_object,
            "entities": [e.to_dict() for e in self.entities],
            "explicit_constraints": [c.to_dict() for c in self.explicit_constraints],
            "temporal_constraints": [t.to_dict() for t in self.temporal_constraints],
            "scope_constraints": [c.to_dict() for c in self.scope_constraints],
            "evidence_requirements": list(self.evidence_requirements),
            "stated_assumptions": list(self.stated_assumptions),
            "dependencies": list(self.dependencies),
            "references": list(self.references),
            "conversation_dependencies": list(self.conversation_dependencies),
            "ambiguity_items": [a.to_dict() for a in self.ambiguity_items],
            "missing_information": list(self.missing_information),
            "conflicting_instructions": [c.to_dict()
                                         for c in self.conflicting_instructions],
            "candidate_interpretations": [c.to_dict()
                                          for c in self.candidate_interpretations],
            "selected_interpretation": self.selected_interpretation,
            "interpretation_status": self.interpretation_status.value,
            "clarification_required": self.clarification_required,
            "clarification_questions": [q.to_dict()
                                        for q in self.clarification_questions],
            "confidence_vector": (self.confidence_vector.to_dict()
                                  if self.confidence_vector else None),
            "provenance": [p.to_dict() for p in self.provenance],
        }

    @staticmethod
    def from_dict(d: Mapping[str, object]) -> "IntentRecord":
        cv = d.get("confidence_vector")
        return IntentRecord(
            schema_version=str(d["schema_version"]),
            request_id=str(d["request_id"]),
            source_text_hash=str(d["source_text_hash"]),
            primary_objective=str(d["primary_objective"]),
            task_type=TaskType(d["task_type"]),
            requested_output=str(d["requested_output"]),
            target_object=d.get("target_object"),
            entities=tuple(Entity.from_dict(x) for x in d.get("entities", []) or ()),
            explicit_constraints=tuple(Constraint.from_dict(x)
                                       for x in d.get("explicit_constraints", []) or ()),
            temporal_constraints=tuple(TemporalConstraint.from_dict(x)
                                       for x in d.get("temporal_constraints", []) or ()),
            scope_constraints=tuple(Constraint.from_dict(x)
                                    for x in d.get("scope_constraints", []) or ()),
            evidence_requirements=tuple(d.get("evidence_requirements", []) or ()),
            stated_assumptions=tuple(d.get("stated_assumptions", []) or ()),
            dependencies=tuple(d.get("dependencies", []) or ()),
            references=tuple(d.get("references", []) or ()),
            conversation_dependencies=tuple(d.get("conversation_dependencies", []) or ()),
            ambiguity_items=tuple(AmbiguityItem.from_dict(x)
                                  for x in d.get("ambiguity_items", []) or ()),
            missing_information=tuple(d.get("missing_information", []) or ()),
            conflicting_instructions=tuple(ConflictItem.from_dict(x)
                                           for x in d.get("conflicting_instructions", []) or ()),
            candidate_interpretations=tuple(CandidateInterpretation.from_dict(x)
                                            for x in d.get("candidate_interpretations", []) or ()),
            selected_interpretation=d.get("selected_interpretation"),
            interpretation_status=InterpretationStatus(d["interpretation_status"]),
            clarification_required=bool(d["clarification_required"]),
            clarification_questions=tuple(ClarificationQuestion.from_dict(x)
                                          for x in d.get("clarification_questions", []) or ()),
            confidence_vector=ConfidenceVector.from_dict(cv) if cv else None,
            provenance=tuple(ProvenanceEntry.from_dict(x)
                             for x in d.get("provenance", []) or ()),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------- #
# Inputs                                                                      #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ConversationTurn:
    role: str                       # "user" | "assistant"
    text: str


@dataclass(frozen=True)
class RawUserRequest:
    request_id: str
    text: str
    conversation: Tuple[ConversationTurn, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def text_hash(self) -> str:
        return stable_hash(self.text)


# --------------------------------------------------------------------------- #
# Schema validity check + hashing                                             #
# --------------------------------------------------------------------------- #

def validate_schema(record: IntentRecord) -> Tuple[bool, Tuple[str, ...]]:
    """Structural validity: required fields present, enums valid, provenance on
    every non-empty typed field, round-trip stable. Returns (ok, problems)."""
    problems: List[str] = []

    if record.schema_version != SCHEMA_VERSION:
        problems.append(f"schema_version mismatch: {record.schema_version!r}")
    if not record.request_id:
        problems.append("empty request_id")
    if not record.source_text_hash:
        problems.append("empty source_text_hash")
    if not isinstance(record.task_type, TaskType):
        problems.append("task_type not a TaskType")
    if not isinstance(record.interpretation_status, InterpretationStatus):
        problems.append("interpretation_status not an InterpretationStatus")

    # abstention must not carry a committed interpretation
    if (record.interpretation_status is InterpretationStatus.ABSTAINED
            and record.selected_interpretation):
        problems.append("ABSTAINED record has a selected_interpretation")

    # every typed field carrying provenance must have a valid kind
    for e in record.entities:
        if not isinstance(e.provenance.kind, ProvenanceKind):
            problems.append(f"entity {e.text!r} bad provenance")
    for c in record.explicit_constraints + record.scope_constraints:
        if not isinstance(c.provenance.kind, ProvenanceKind):
            problems.append(f"constraint {c.text!r} bad provenance")

    # round-trip stability
    try:
        rt = IntentRecord.from_dict(json.loads(record.to_json()))
        if rt.to_json() != record.to_json():
            problems.append("round-trip mismatch")
    except Exception as exc:  # pragma: no cover - defensive
        problems.append(f"round-trip raised {exc!r}")

    return (len(problems) == 0, tuple(problems))


def stable_hash(obj: object) -> str:
    """Deterministic content hash for locks/manifests."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

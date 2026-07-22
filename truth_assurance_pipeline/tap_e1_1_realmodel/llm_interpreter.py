"""
Compose a real-model interpretation core with the FROZEN TAP-E1 deterministic layers.

The model produces an interpretation *core* (objective, task, entities, constraints,
status, …). The baselines add, in code, the exact same frozen TAP-E1 machinery:

  A  raw            : model free-text intent only (no schema discipline)
  B  + schema       : model fills the IntentRecord core (no det. extraction/provenance)
  C  + extraction   : B + TAP-E1 deterministic extraction (authoritative spans merged)
  D  + provenance   : C + TAP-E1 append-only provenance ledger
  E  + ambiguity    : D + TAP-E1 ambiguity/conflict detection (+ candidate readings)
  F  + clarification: E + TAP-E1 clarification/abstention policy

Nothing in TAP-E1 is modified; its modules are imported and reused verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent import (
    ambiguity as amb, clarification as clar, conflicts as conf, extraction as ext,
)
from truth_assurance_pipeline.tap_e1_intent.clarification import Decision
from truth_assurance_pipeline.tap_e1_intent.provenance import ProvenanceLedger
from truth_assurance_pipeline.tap_e1_intent.schema import (
    SCHEMA_VERSION, AmbiguityItem, CandidateInterpretation, ConfidenceVector,
    Constraint, ConstraintPolarity, ConflictItem, Entity, IntentRecord,
    InterpretationStatus, Provenance, ProvenanceKind, RawUserRequest, Span,
    TaskType, TemporalConstraint,
)


@dataclass(frozen=True)
class BaselineConfig:
    name: str
    schema: bool
    extraction: bool
    provenance: bool
    ambiguity: bool
    clarification: bool
    description: str


BASELINES: Tuple[BaselineConfig, ...] = (
    BaselineConfig("A", False, False, False, False, False,
                   "raw LLM interpretation (free text)"),
    BaselineConfig("B", True, False, False, False, False,
                   "LLM + IntentRecord schema"),
    BaselineConfig("C", True, True, False, False, False,
                   "LLM + deterministic extraction"),
    BaselineConfig("D", True, True, True, False, False,
                   "LLM + deterministic extraction + provenance"),
    BaselineConfig("E", True, True, True, True, False,
                   "LLM + extraction + provenance + ambiguity/conflict"),
    BaselineConfig("F", True, True, True, True, True,
                   "LLM + extraction + provenance + ambiguity + clarification"),
)


def baseline(name: str) -> BaselineConfig:
    for b in BASELINES:
        if b.name == name:
            return b
    raise KeyError(name)


# --------------------------------------------------------------------------- #
# coercion helpers                                                            #
# --------------------------------------------------------------------------- #

def _task(core: Mapping[str, object]) -> TaskType:
    v = str(core.get("task_type", "") or "").strip()
    try:
        return TaskType(v)
    except ValueError:
        return TaskType.UNKNOWN


def _status(core: Mapping[str, object]) -> InterpretationStatus:
    v = str(core.get("interpretation_status", "") or "").strip()
    try:
        return InterpretationStatus(v)
    except ValueError:
        return InterpretationStatus.RESOLVED


def _find_span(text: str, needle: str) -> Optional[Span]:
    if not needle:
        return None
    i = text.lower().find(needle.lower())
    if i < 0:
        return None
    return Span(i, i + len(needle), text[i:i + len(needle)])


def _model_entities(core, text, ledger, record_prov) -> List[Entity]:
    out: List[Entity] = []
    for i, e in enumerate(core.get("entities", []) or []):
        etext = str(e)
        span = _find_span(text, etext)
        prov = Provenance(ProvenanceKind.MODEL_INFERENCE,
                          (span,) if span else ())
        out.append(Entity(etext, "topic", prov))
        if record_prov:
            ledger.record(f"entity[{i}]", ProvenanceKind.MODEL_INFERENCE, etext)
    return out


def _model_constraints(core, text) -> List[Constraint]:
    out: List[Constraint] = []
    for c in core.get("explicit_constraints", []) or []:
        if isinstance(c, Mapping):
            ctext = str(c.get("text", ""))
            pol = str(c.get("polarity", "requirement"))
        else:
            ctext, pol = str(c), "requirement"
        try:
            polarity = ConstraintPolarity(pol)
        except ValueError:
            polarity = ConstraintPolarity.REQUIREMENT
        span = _find_span(text, ctext)
        prov = Provenance(ProvenanceKind.MODEL_INFERENCE, (span,) if span else ())
        out.append(Constraint(ctext, polarity, prov))
    return out


def _norm(s: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower())
            if t not in ("the", "a", "an", "to", "of", "and", "any", "all")}


# --------------------------------------------------------------------------- #
# baseline A (raw)                                                            #
# --------------------------------------------------------------------------- #

def _raw_record(core, request: RawUserRequest) -> IntentRecord:
    text = request.text
    raw = str(core.get("raw_intent") or core.get("primary_objective") or text)
    task = _task(core)
    # naive entity parse of the free-text intent (to expose invented entities / answers)
    ents = []
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9_.]+\b", raw):
        ents.append(Entity(m.group(0), "topic",
                           Provenance(ProvenanceKind.MODEL_INFERENCE)))
    return IntentRecord(
        schema_version=SCHEMA_VERSION, request_id=request.request_id,
        source_text_hash=request.text_hash, primary_objective=raw,
        task_type=task, requested_output=str(core.get("requested_output", "")),
        target_object=(core.get("target_object")),
        entities=tuple(ents), interpretation_status=InterpretationStatus.RESOLVED,
        selected_interpretation=raw, clarification_required=False,
        confidence_vector=None, provenance=())


# --------------------------------------------------------------------------- #
# baselines B-F (structured)                                                  #
# --------------------------------------------------------------------------- #

def build_record(core: Mapping[str, object], request: RawUserRequest,
                 cfg: BaselineConfig) -> IntentRecord:
    if not cfg.schema:
        return _raw_record(core, request)

    text = request.text
    ledger = ProvenanceLedger()
    det = ext.run_extraction(text) if cfg.extraction else None

    # objective / task / output from the model
    objective = str(core.get("primary_objective") or core.get("raw_intent") or text)
    task = _task(core)
    requested_output = str(core.get("requested_output", ""))

    # entities: model + (C+) deterministic authoritative spans
    entities = _model_entities(core, text, ledger, cfg.provenance)
    if det is not None:
        seen = {e.text.lower() for e in entities}
        for s in list(det.filenames) + list(det.identifiers):
            if s.text.lower() not in seen:
                seen.add(s.text.lower())
                idx = len(entities)
                entities.append(Entity(s.text, "target_object",
                                       Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION, (s,))))
                if cfg.provenance:
                    ledger.record(f"entity[{idx}]",
                                  ProvenanceKind.DETERMINISTIC_EXTRACTION, s.text)

    # constraints: model + (C+) deterministic authoritative constraints (merged)
    constraints = _model_constraints(core, text)
    temporal: List[TemporalConstraint] = []
    for t in core.get("temporal_constraints", []) or []:
        span = _find_span(text, str(t))
        temporal.append(TemporalConstraint(
            str(t), Provenance(ProvenanceKind.MODEL_INFERENCE, (span,) if span else ())))
    if det is not None:
        have = [_norm(c.text) for c in constraints]
        for dc in det.constraints:
            if not any(_norm(dc.text) & h for h in have):
                constraints.append(dc)     # authoritative; not silently dropped
                have.append(_norm(dc.text))
        ht = [_norm(x.text) for x in temporal]
        for dt in det.temporal:
            if not any(_norm(dt.text) & h for h in ht):
                temporal.append(dt)
                ht.append(_norm(dt.text))

    if cfg.provenance:
        ledger.record("primary_objective", ProvenanceKind.MODEL_INFERENCE, objective)
        ledger.record("task_type", ProvenanceKind.MODEL_INFERENCE, task.value)
        ro_kind = (ProvenanceKind.DETERMINISTIC_EXTRACTION
                   if det is not None and det.output_formats
                   else ProvenanceKind.MODEL_INFERENCE)
        ledger.record("requested_output", ro_kind, requested_output)
        for i, c in enumerate(constraints):
            ledger.record(f"constraint[{i}]", c.provenance.kind, c.text)

    # status / ambiguity / conflict / clarification
    status = _status(core)
    ambiguity_items: Tuple[AmbiguityItem, ...] = ()
    conflict_items: Tuple[ConflictItem, ...] = ()
    candidates: Tuple[CandidateInterpretation, ...] = ()
    clarification_required = False
    clar_questions = ()
    assumptions = tuple(str(a) for a in core.get("stated_assumptions", []) or ())
    missing: Tuple[str, ...] = ()

    amb_res = None
    conf_res = None
    if cfg.ambiguity:
        amb_res = amb.detect(text, request.conversation,
                             task_is_document_edit=(task is TaskType.DOCUMENT_EDIT))
        conf_res = conf.detect(text, tuple(constraints), request.conversation)
        ambiguity_items = amb_res.items
        conflict_items = conf_res.items
        missing = tuple(a.dimension for a in amb_res.material)
        if amb_res.material or conf_res.items:
            candidates = _candidates(objective, amb_res, conf_res)
            status = (InterpretationStatus.CONFLICTING if conf_res.items
                      else InterpretationStatus.AMBIGUOUS)

    if cfg.clarification:
        actionable = bool(re.search(r"[A-Za-z]", text))
        references_prior = _references_prior(text)
        outcome = clar.decide(
            amb_res if amb_res is not None else amb.AmbiguityResult((), ()),
            conf_res if conf_res is not None else conf.ConflictResult(()),
            request.conversation, has_actionable_content=actionable,
            references_prior_context=references_prior)
        status = outcome.status
        clarification_required = outcome.clarification_required
        clar_questions = outcome.questions
        assumptions = assumptions + outcome.assumptions

    committed = status in (InterpretationStatus.RESOLVED,
                           InterpretationStatus.PARTIALLY_RESOLVED)
    selected = objective if (committed and not clarification_required) else None

    return IntentRecord(
        schema_version=SCHEMA_VERSION, request_id=request.request_id,
        source_text_hash=request.text_hash, primary_objective=objective,
        task_type=task, requested_output=requested_output,
        target_object=core.get("target_object"),
        entities=tuple(entities),
        explicit_constraints=tuple(constraints),
        temporal_constraints=tuple(temporal),
        stated_assumptions=assumptions,
        references=tuple(str(r) for r in core.get("references", []) or ()),
        ambiguity_items=ambiguity_items, missing_information=missing,
        conflicting_instructions=conflict_items,
        candidate_interpretations=candidates, selected_interpretation=selected,
        interpretation_status=status, clarification_required=clarification_required,
        clarification_questions=clar_questions,
        confidence_vector=_confidence(cfg, det, entities, constraints, task),
        provenance=ledger.entries())


def _candidates(objective, amb_res, conf_res) -> Tuple[CandidateInterpretation, ...]:
    dim = (amb_res.material[0].dimension if amb_res.material
           else conf_res.items[0].kind.value)
    return (
        CandidateInterpretation("A", objective, ("model primary reading",),
                                (f"unresolved: {dim}",), (dim,), 0.5,
                                "acts on the wrong target/scope"),
        CandidateInterpretation("B", f"alternative reading given {dim}",
                                (f"ambiguity on {dim}",), ("model reading",),
                                (dim,), 0.5, "performs a different operation"),
    )


def _references_prior(text: str) -> bool:
    low = text.lower()
    return bool(re.search(r"\b(it|them|that|this|the same|change back|the usual)\b", low))


def _confidence(cfg, det, entities, constraints, task) -> ConfidenceVector:
    det_on = cfg.extraction and det is not None
    return ConfidenceVector(
        objective=0.85, entity=0.85 if (det_on and entities) else 0.6,
        constraint=0.9 if (det_on and constraints) else 0.6,
        reference_resolution=0.8, task_type=0.9 if task is not TaskType.UNKNOWN else 0.4,
        clarification=0.9 if cfg.clarification else 0.7)

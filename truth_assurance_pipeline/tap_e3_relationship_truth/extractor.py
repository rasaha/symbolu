"""
The Relationship Truth extraction pipeline + the A-F baseline configuration.

Typed, independently testable stages (Section 9), producing an append-only
``processing_trace``. Deterministic-first (Section 10): lexical predicate maps,
passive-voice normalization, negation/modal/temporal markers, condition/exception
patterns, deterministic entity matching (using the evidence unit's known entities), and
explicit tie-breaking. No model-based interpretation in this phase.

Consumes an IntentRecord (TAP-E1) and a RetrievalRecord (TAP-E2) through their public
interfaces; it does not retrieve, mutate evidence, or repair upstream gaps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    RetrievalRecord, GapType as E2GapType,
)
from truth_assurance_pipeline.tap_e3_relationship_truth import (
    confidence as conf_mod, conflict as conflict_mod, modality as modality_mod,
    polarity as polarity_mod, temporality as temporality_mod,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.normalization import (
    normalize_entity, resolve_direction,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import (
    ONTOLOGY_VERSION, PREDICATE_LEXICON, Form, RelationshipType,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    SCHEMA_VERSION, AssertionStatus, Direction, EvidenceRole, Explicitness, GapCode,
    Modality, Polarity, RelationshipAssertion, RelationshipConflict, RelationshipGap,
    RelationshipRecord, SourceProvenance, Temporality,
)

CREATED_AT = "N/A (deterministic run)"
_ATTRIBUTION = {RelationshipType.ALLEGES, RelationshipType.CLAIMS, RelationshipType.REPORTS}


@dataclass(frozen=True)
class ExtractionConfig:
    name: str
    cooccurrence_only: bool     # A
    predicate_keyword: bool     # B+
    normalize: bool             # C+ (active/passive, ontology, direction)
    polarity_modality: bool     # D+
    temporal_scope_cond: bool   # E+
    consolidate: bool           # F (cross-evidence, conflict, gaps, confidence, trace)
    description: str


BASELINES: Tuple[ExtractionConfig, ...] = (
    ExtractionConfig("A", True, False, False, False, False, False,
                     "entity co-occurrence"),
    ExtractionConfig("B", False, True, False, False, False, False,
                     "predicate keyword matching"),
    ExtractionConfig("C", False, True, True, False, False, False,
                     "normalized deterministic extraction (active/passive, ontology, direction)"),
    ExtractionConfig("D", False, True, True, True, False, False,
                     "C + polarity and modality"),
    ExtractionConfig("E", False, True, True, True, True, False,
                     "D + temporality, scope, conditions, exceptions"),
    ExtractionConfig("F", False, True, True, True, True, True,
                     "full TAP-E3 (consolidation, conflict, confidence, gaps, provenance, trace)"),
)


def config(name: str) -> ExtractionConfig:
    for c in BASELINES:
        if c.name == name:
            return c
    raise KeyError(name)


# --------------------------------------------------------------------------- #
# clause / entity helpers                                                     #
# --------------------------------------------------------------------------- #

def _entity_positions(text: str, entities: Tuple[str, ...]) -> List[Tuple[int, int, str]]:
    low = text.lower()
    out = []
    for e in entities:
        i = low.find(e.lower())
        if i >= 0:
            out.append((i, i + len(e), e))
    out.sort()
    return out


def _find_predicate(clause: str) -> Optional[Tuple[str, RelationshipType, Form, int, int]]:
    low = clause.lower()
    for phrase, rtype, form in PREDICATE_LEXICON:
        m = re.search(r"\b" + re.escape(phrase) + r"\b", low)
        if m:
            return (phrase, rtype, form, m.start(), m.end())
    return None


def _split_segments(text: str) -> List[Tuple[str, bool]]:
    """Split on temporal-contrast 'but now'; mark the earlier segment historical."""
    if " but now " in text.lower():
        idx = text.lower().index(" but now ")
        return [(text[:idx], True), (text[idx + len(" but now "):], False)]
    return [(text, False)]


def _split_coord(segment: str) -> List[str]:
    parts = re.split(r"\s+and\s+", segment)
    return [p.strip() for p in parts if p.strip()]


def _extract_scope(clause: str) -> Dict[str, str]:
    scope: Dict[str, str] = {}
    low = clause.lower()
    m = re.search(r"applies to ([\w\s]+?) (?:only|\.|$)", low)
    if m:
        scope["applicability"] = m.group(1).strip()
    for geo in ("european", "europe", "eu", "us", "united states", "uk", "global"):
        if re.search(r"\b" + re.escape(geo) + r"\b", low):
            scope["geography"] = geo
            break
    for env in ("production", "staging", "development", "sandbox"):
        if re.search(r"\b" + env + r"\b", low):
            scope["environment"] = env
            break
    for role in ("contractors", "administrators", "employees", "vendors", "staff"):
        if re.search(r"\b" + role + r"\b", low):
            scope["user_role"] = role
            break
    # explicit numeric value / time-bound (used by VALUE_CONFLICT detection)
    m = re.search(r"within (\d+)\s*(hours?|minutes?|days?)", low)
    if m:
        scope["value"] = f"{m.group(1)} {m.group(2)}"
    else:
        m2 = re.search(r"(?:at least |minimum of |)(\d+)\s*(characters?|days?|hours?)", low)
        if m2:
            scope["value"] = f"{m2.group(1)} {m2.group(2)}"
    return scope


def _extract_conditions(clause: str) -> Tuple[str, ...]:
    out = []
    m = re.search(r"\bif ([^,.;]+)", clause, re.I)
    if m:
        out.append(m.group(1).strip())
    m2 = re.search(r"\bwhen ([^,.;]+)", clause, re.I)
    if m2:
        out.append(m2.group(1).strip())
    return tuple(out)


def _extract_exceptions(clause: str) -> Tuple[str, ...]:
    out = []
    m = re.search(r"\bexcept (?:for )?([^,.;]+)", clause, re.I)
    if m:
        out.append(m.group(1).strip())
    m2 = re.search(r"\bunless ([^,.;]+)", clause, re.I)
    if m2:
        out.append(m2.group(1).strip())
    return tuple(out)


# --------------------------------------------------------------------------- #
# the layer                                                                   #
# --------------------------------------------------------------------------- #

class RelationshipTruthLayer:
    def __init__(self, cfg: ExtractionConfig):
        self.cfg = cfg

    def extract(self, intent: IntentRecord, retrieval: RetrievalRecord
                ) -> RelationshipRecord:
        trace: List[str] = ["input_validation"]
        assertions: List[RelationshipAssertion] = []
        gaps: List[RelationshipGap] = []

        trace.append("evidence_unit_normalization")
        counter = 0
        for rank, cand in enumerate(retrieval.candidates):
            unit = cand.unit
            unit_assertions, unit_gap = self._extract_unit(
                unit, rank, retrieval.retrieval_id, counter)
            counter += len(unit_assertions)
            assertions.extend(unit_assertions)
            if unit_gap is not None and self.cfg.temporal_scope_cond:
                gaps.append(unit_gap)

        trace.extend(["entity_candidate_detection", "predicate_candidate_detection",
                      "direction_resolution", "polarity_detection", "modality_detection",
                      "temporal_scope_extraction", "condition_exception_extraction",
                      "relationship_normalization"])

        conflicts: List[RelationshipConflict] = []
        if self.cfg.consolidate:
            trace.append("cross_evidence_consolidation")
            assertions = self._consolidate(assertions)
            trace.append("conflict_detection")
            conflicts = list(conflict_mod.detect_conflicts(assertions))
            if conflicts:
                cids = sorted({aid for c in conflicts for aid in c.assertion_ids})
                gaps.append(RelationshipGap(
                    GapCode.CONFLICTING_RELATIONSHIPS,
                    "assertions conflict", {"assertion_ids": cids}))
            trace.append("confidence_assignment")
            assertions = [self._finalize_status(a, conflicts) for a in assertions]

        # preserve upstream retrieval gaps (never converted to certainty)
        if self.cfg.temporal_scope_cond:
            trace.append("gap_detection")
            for g in retrieval.gaps:
                if g.gap_type in (E2GapType.INSUFFICIENT_EVIDENCE,
                                  E2GapType.NO_AUTHORITATIVE_SOURCE,
                                  E2GapType.MISSING_ENTITY):
                    gaps.append(RelationshipGap(
                        GapCode.INSUFFICIENT_RETRIEVAL_EVIDENCE,
                        f"upstream retrieval gap preserved: {g.gap_type.value}",
                        {"upstream_gap": g.gap_type.value}))
            for a in assertions:
                if a.explicitness is Explicitness.UNSUPPORTED_INFERENCE:
                    gaps.append(RelationshipGap(
                        GapCode.UNSUPPORTED_INFERENCE,
                        f"assertion {a.assertion_id} rests on unsupported inference",
                        {"assertion_id": a.assertion_id}))

        trace.append("relationship_record_generation")
        prov_summary = {
            "assertions_with_provenance": sum(1 for a in assertions if a.source_provenance),
            "total_assertions": len(assertions),
            "provenance_complete": all(p.is_complete() for a in assertions
                                       for p in a.source_provenance),
        }
        conf_summary = self._confidence_summary(assertions)
        return RelationshipRecord(
            schema_version=SCHEMA_VERSION, ontology_version=ONTOLOGY_VERSION,
            relationship_record_id=f"rel::{intent.request_id}::{self.cfg.name}",
            intent_record_id=intent.request_id,
            retrieval_record_id=retrieval.retrieval_id, created_at=CREATED_AT,
            relationship_assertions=tuple(assertions),
            relationship_conflicts=tuple(conflicts),
            unresolved_relationship_gaps=tuple(_dedupe_gaps(gaps)),
            provenance_summary=prov_summary, confidence_summary=conf_summary,
            processing_trace=tuple(trace))

    # -- per-unit extraction --------------------------------------------------
    def _extract_unit(self, unit, rank: int, retrieval_id: str, base_counter: int
                      ) -> Tuple[List[RelationshipAssertion], Optional[RelationshipGap]]:
        text = unit.text
        ents = _entity_positions(text, unit.entities)

        # Baseline A: co-occurrence -> one generic (unsupported) relationship
        if self.cfg.cooccurrence_only:
            if len(ents) >= 2:
                a = self._build(unit, rank, retrieval_id, base_counter,
                                subj=ents[0][2], obj=ents[1][2],
                                rtype=RelationshipType.OTHER, form=Form.ACTIVE,
                                clause=text, explicit=Explicitness.UNSUPPORTED_INFERENCE)
                return [a], None
            return [], None

        results: List[RelationshipAssertion] = []
        idx = base_counter
        prev_subject = None                  # persists across 'but now' segments
        for segment, hist in _split_segments(text):
            for clause in _split_coord(segment):
                pred = _find_predicate(clause)
                if pred is None:
                    continue
                phrase, rtype, form, ps, pe = pred
                cents = _entity_positions(clause, unit.entities)
                left = next((e[2] for e in reversed(cents) if e[1] <= ps + 3), None)
                right = next((e[2] for e in cents if e[0] >= pe - 3), None)
                if left is None and prev_subject is not None:
                    left = prev_subject      # subject inheritance in coordination

                attribution = rtype in _ATTRIBUTION
                if attribution:
                    inner = clause[pe:]
                    a = self._attributed(unit, rank, retrieval_id, idx, left, inner, hist)
                    if a is not None:
                        results.append(a); idx += 1
                        prev_subject = a.subject
                    continue

                a = self._build(unit, rank, retrieval_id, idx,
                                subj=left, obj=right, rtype=rtype, form=form,
                                clause=clause, phrase=phrase, span=(ps, pe),
                                historical=hist)
                results.append(a); idx += 1
                prev_subject = a.subject

        # unit-level co-occurrence: >=2 entities but no relationship predicate anywhere
        gap = None
        if not results and len(ents) >= 2 and _find_predicate(text) is None:
            gap = RelationshipGap(GapCode.NO_RELATIONSHIP_ESTABLISHED,
                                  f"unit {unit.unit_id}: entities co-occur but no predicate",
                                  {"unit_id": unit.unit_id})
        return results, gap

    def _attributed(self, unit, rank, retrieval_id, idx, source, inner, hist):
        pred = _find_predicate(inner)
        if pred is None:
            return None
        phrase, rtype, form, ps, pe = pred
        cents = _entity_positions(inner, unit.entities)
        left = next((e[2] for e in reversed(cents) if e[1] <= ps + 3), source)
        right = next((e[2] for e in cents if e[0] >= pe - 3), None)
        return self._build(unit, rank, retrieval_id, idx, subj=left, obj=right,
                           rtype=rtype, form=form, clause=inner, phrase=phrase,
                           span=(ps, pe), historical=hist, force_modality=Modality.ALLEGED)

    def _build(self, unit, rank: int, retrieval_id: str, idx: int, *, subj, obj,
               rtype: RelationshipType, form: Form, clause: str, phrase: str = "",
               span: Tuple[int, int] = (0, 0), historical: bool = False,
               explicit: Optional[Explicitness] = None,
               force_modality: Optional[Modality] = None) -> RelationshipAssertion:
        cfg = self.cfg

        # direction (C+) vs raw order (B)
        if cfg.normalize:
            s, o, direction = resolve_direction(form, subj, obj)
        else:
            s, o, direction = subj, obj, Direction.SUBJECT_TO_OBJECT
        s = s if s is not None else (subj or "")
        o = o if o is not None else (obj or "")

        norm_pred = rtype if cfg.normalize else rtype
        norm_subj = normalize_entity(s) if cfg.normalize else (s or "").lower()
        norm_obj = normalize_entity(o) if cfg.normalize else (o or "").lower()

        # polarity & modality (D+)
        if cfg.polarity_modality:
            polarity = polarity_mod.detect_polarity(clause)
            # a predicate phrase that itself encodes negation ("not authorized to")
            if "not " in phrase:
                polarity = Polarity.NEGATED
            has_cond = bool(_extract_conditions(clause)) if cfg.temporal_scope_cond else False
            modality = (force_modality if force_modality is not None
                        else modality_mod.detect_modality(clause, has_condition=has_cond))
        else:
            polarity, modality = Polarity.UNKNOWN, Modality.UNKNOWN

        # temporality, scope, conditions, exceptions (E+)
        valid_from = valid_until = None
        scope: Dict[str, str] = {}
        conditions: Tuple[str, ...] = ()
        exceptions: Tuple[str, ...] = ()
        if cfg.temporal_scope_cond:
            is_superseded = (rtype is RelationshipType.SUPERSEDES and False)
            tr = temporality_mod.detect_temporality(clause, is_superseded=historical or False)
            if historical:
                temporality = Temporality.HISTORICAL
            else:
                temporality = tr.temporality
            valid_from, valid_until = tr.valid_from, tr.valid_until
            scope = _extract_scope(clause)
            conditions = _extract_conditions(clause)
            exceptions = _extract_exceptions(clause)
        else:
            temporality = Temporality.UNRESOLVED

        explicitness = explicit if explicit is not None else (
            Explicitness.EXPLICIT if phrase else Explicitness.STRUCTURALLY_INFERRED)

        prov = SourceProvenance(
            evidence_unit_id=unit.unit_id, source_id=unit.doc_id,
            source_location=unit.location, retrieval_record_id=retrieval_id,
            retrieval_rank=rank, retrieval_method="tap-e2",
            extraction_span=span, extraction_method="deterministic_pattern",
            role=EvidenceRole.PRIMARY_SUPPORT)

        cv = conf_mod.assess(cfg, s, o, rtype, direction, polarity, modality,
                             temporality, scope, conditions, prov)

        status = (AssertionStatus.SUPPORTED if explicitness is Explicitness.EXPLICIT
                  else AssertionStatus.PARTIALLY_SUPPORTED
                  if explicitness is Explicitness.STRUCTURALLY_INFERRED
                  else AssertionStatus.UNRESOLVED)

        return RelationshipAssertion(
            assertion_id=f"A{idx}", subject=s or "", predicate=phrase or "cooccurrence",
            object=o or "", normalized_subject=norm_subj,
            normalized_predicate=norm_pred, normalized_object=norm_obj,
            relationship_type=rtype, direction=direction, polarity=polarity,
            modality=modality, temporality=temporality, scope=scope,
            conditions=conditions, exceptions=exceptions, explicitness=explicitness,
            evidence_unit_ids=(unit.unit_id,), source_provenance=(prov,),
            extraction_method="deterministic_pattern", confidence_vector=cv,
            ambiguities=(), conflicts=(), status=status,
            valid_from=valid_from, valid_until=valid_until)

    # -- consolidation (F) ----------------------------------------------------
    def _consolidate(self, assertions: List[RelationshipAssertion]
                     ) -> List[RelationshipAssertion]:
        by_key: Dict[Tuple, RelationshipAssertion] = {}
        order: List[Tuple] = []
        for a in assertions:
            key = (a.normalized_subject, a.normalized_predicate.value, a.normalized_object,
                   a.polarity.value, a.modality.value,
                   tuple(sorted(a.scope.items())))   # keep different-value assertions apart
            if key not in by_key:
                by_key[key] = a
                order.append(key)
            else:
                # merge provenance (duplicate evidence consolidation)
                ex = by_key[key]
                merged = tuple(dict.fromkeys(ex.evidence_unit_ids + a.evidence_unit_ids))
                by_key[key] = _replace_prov(ex, merged, ex.source_provenance + a.source_provenance)
        return [by_key[k] for k in order]

    def _finalize_status(self, a: RelationshipAssertion,
                         conflicts: List[RelationshipConflict]) -> RelationshipAssertion:
        involved = {aid for c in conflicts for aid in c.assertion_ids}
        if a.assertion_id in involved:
            return _with_status(a, AssertionStatus.CONTRADICTED,
                                tuple(c.conflict_id for c in conflicts
                                      if a.assertion_id in c.assertion_ids))
        return a

    def _confidence_summary(self, assertions) -> Dict[str, object]:
        if not assertions:
            return {"n_assertions": 0, "bands": {}}
        bands: Dict[str, int] = {}
        for a in assertions:
            b = a.confidence_vector.band()
            bands[b] = bands.get(b, 0) + 1
        return {"n_assertions": len(assertions), "bands": bands}


# --- small immutable helpers ------------------------------------------------

def _replace_prov(a: RelationshipAssertion, eu_ids, provs) -> RelationshipAssertion:
    import dataclasses
    return dataclasses.replace(a, evidence_unit_ids=eu_ids, source_provenance=provs)


def _with_status(a: RelationshipAssertion, status, conflicts) -> RelationshipAssertion:
    import dataclasses
    return dataclasses.replace(a, status=status, conflicts=conflicts)


def _dedupe_gaps(gaps: List[RelationshipGap]) -> List[RelationshipGap]:
    seen = set()
    out = []
    for g in gaps:
        key = (g.gap_code.value, str(sorted(g.detail.items())))
        if key not in seen:
            seen.add(key)
            out.append(g)
    return out

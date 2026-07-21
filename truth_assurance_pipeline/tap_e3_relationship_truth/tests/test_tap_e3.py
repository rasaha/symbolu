"""
TAP-E3 behavioral tests (Section 21).

Cover active/passive, inverse normalization, negation, modality, conditions,
exceptions, temporality/supersession/historical, scope, coordination, attribution,
allegation-vs-fact, co-occurrence, conflicts, duplicate consolidation, provenance,
upstream-gap preservation, determinism, schema validation, invalid-input rejection.
TAP-E1/E2 are consumed through frozen public interfaces only.
"""

import json

import pytest

from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1c
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    AuthorityLevel, DocumentType, EvidenceUnit,
)
from truth_assurance_pipeline.tap_e3_relationship_truth import (
    BASELINES, RelationshipTruthLayer, config, validate_record,
)
from truth_assurance_pipeline.tap_e3_relationship_truth import harness, loader, metrics
from truth_assurance_pipeline.tap_e3_relationship_truth.corpus import cases as corpus
from truth_assurance_pipeline.tap_e3_relationship_truth.corpus.cases import (
    build_retrieval_record,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import (
    INVERSES, RelationshipType,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    Direction, GapCode, Modality, Polarity, Temporality,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.validator import (
    InvalidInput, validate_inputs,
)

_E1 = IntentUnderstandingLayer(e1c("V4"))


_UID = [0]


def _unit(text, entities, dt=DocumentType.POLICY):
    _UID[0] += 1
    uid = f"D{_UID[0]}"
    return EvidenceUnit(f"{uid}#s1", uid, text, "s1", dt, AuthorityLevel.OFFICIAL_POLICY,
                        2025, entities=tuple(entities))


def _rec_from_units(units, cfg="F", gaps=()):
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
        RankedCandidate, RankingSignals, RetrievalConfidence, RetrievalQuery,
        RetrievalRecord,
    )
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
        EvidenceProvenance, ExtractionMethod, RetrievalMethod,
    )
    cands = []
    for r, u in enumerate(units):
        prov = EvidenceProvenance(u.doc_id, u.location, ("candidate_retrieval",),
                                  RetrievalMethod.HYBRID, 1.0, ExtractionMethod.SENTENCE_SPLIT)
        cands.append(RankedCandidate(u, prov, RankingSignals(1, 1, 1, 1, 1, 1, 0), 1.0))
    rr = RetrievalRecord("tap-e2-retrieval/1.0.0", "ret::t", "t", "obj",
                         RetrievalQuery((), (), (), None, True), tuple(cands),
                         RetrievalConfidence(1, 1, 1, 1, 1, 1), tuple(gaps), 0.0)
    intent = _E1.interpret(RawUserRequest("t", "q"))
    return RelationshipTruthLayer(config(cfg)).extract(intent, rr)


def _one(text, entities, cfg="F"):
    rec = _rec_from_units([_unit(text, entities)], cfg)
    return rec.relationship_assertions[0]


# --- active / passive / direction -------------------------------------------

def test_active_direction():
    a = _one("Acme owns System B.", ["Acme", "System B"])
    assert a.relationship_type is RelationshipType.OWNS
    assert a.normalized_subject == "acme" and a.normalized_object == "system b"


def test_passive_direction_resolved():
    a = _one("System B is operated by Acme.", ["System B", "Acme"])
    assert a.relationship_type is RelationshipType.OPERATES
    assert a.normalized_subject == "acme" and a.normalized_object == "system b"
    assert a.direction is Direction.SUBJECT_TO_OBJECT


def test_passive_reversed_without_normalization():
    # baseline B (no normalization) puts the subject/object in raw order
    a = _one("System B is operated by Acme.", ["System B", "Acme"], cfg="B")
    assert a.normalized_subject == "system b"   # not resolved -> reversed vs gold


def test_inverse_defined_in_ontology():
    assert INVERSES[RelationshipType.OWNS] is RelationshipType.OWNED_BY
    assert INVERSES[RelationshipType.PART_OF] is RelationshipType.CONTAINS


# --- negation / modality ----------------------------------------------------

def test_negation_preserved():
    a = _one("Contractors are not authorized to access production.",
             ["Contractors", "production"])
    assert a.polarity is Polarity.NEGATED


def test_modal_must_vs_may_distinct():
    must = _one("Vendors must access the portal.", ["Vendors", "portal"])
    may = _one("Vendors may access the portal.", ["Vendors", "portal"])
    assert must.modality is Modality.REQUIRED
    assert may.modality is Modality.PERMITTED
    assert must.modality is not may.modality


def test_modality_unknown_without_module():
    a = _one("Vendors must access the portal.", ["Vendors", "portal"], cfg="C")
    assert a.modality is Modality.UNKNOWN


# --- conditions / exceptions ------------------------------------------------

def test_condition_captured():
    a = _one("Support must escalate the incident if severity is critical.",
             ["Support", "incident"])
    assert any("severity" in c for c in a.conditions)


def test_exception_captured():
    a = _one("All staff must use MFA except break-glass administrators.",
             ["staff", "MFA"])
    assert any("break-glass" in e for e in a.exceptions)


# --- temporality ------------------------------------------------------------

def test_supersession():
    a = _one("Policy B supersedes Policy A from June 1 2025.", ["Policy B", "Policy A"])
    assert a.relationship_type is RelationshipType.SUPERSEDES
    assert a.valid_from is not None


def test_historical_and_current_split():
    rec = _rec_from_units([_unit("System A previously depended on Library B but now uses Library C.",
                                 ["System A", "Library B", "Library C"])])
    temps = {(x.relationship_type, x.temporality) for x in rec.relationship_assertions}
    assert (RelationshipType.DEPENDS_ON, Temporality.HISTORICAL) in temps
    assert (RelationshipType.USES, Temporality.CURRENT) in temps


# --- scope / coordination / attribution -------------------------------------

def test_scope_extracted():
    a = _one("Policy A applies to European employees only.", ["Policy A", "European employees"])
    assert a.scope.get("geography") == "european"


def test_coordination_multiple_relationships():
    rec = _rec_from_units([_unit("Acme owns Platform B and licenses Module C to Vendor D.",
                                 ["Acme", "Platform B", "Module C", "Vendor D"])])
    types = {x.relationship_type for x in rec.relationship_assertions}
    assert RelationshipType.OWNS in types and RelationshipType.LICENSES in types


def test_allegation_not_treated_as_fact():
    a = _one("The audit alleges that Vendor A caused the outage.", ["Vendor A", "outage"])
    assert a.relationship_type is RelationshipType.CAUSES
    assert a.modality is Modality.ALLEGED       # not asserted as fact


def test_distributes_not_owns():
    a = _one("Acme distributes Product X in Europe.", ["Acme", "Product X"])
    assert a.relationship_type is RelationshipType.DISTRIBUTES
    assert a.relationship_type is not RelationshipType.OWNS


# --- co-occurrence / gaps / conflict / duplicate ----------------------------

def test_cooccurrence_no_relationship():
    rec = _rec_from_units([_unit("Acme and Product X are discussed together.",
                                 ["Acme", "Product X"], DocumentType.MANUAL)])
    assert rec.relationship_assertions == ()
    assert any(g.gap_code is GapCode.NO_RELATIONSHIP_ESTABLISHED
               for g in rec.unresolved_relationship_gaps)


def test_conflict_detected_value():
    rec = _rec_from_units([
        _unit("The vendor must notify the customer within 24 hours.", ["vendor", "customer"]),
        _unit("The vendor must notify the customer within 72 hours.", ["vendor", "customer"]),
    ])
    assert rec.relationship_conflicts
    assert any(g.gap_code is GapCode.CONFLICTING_RELATIONSHIPS
               for g in rec.unresolved_relationship_gaps)


def test_duplicate_consolidation():
    rec = _rec_from_units([_unit("Acme owns System B.", ["Acme", "System B"]),
                           _unit("Acme owns System B.", ["Acme", "System B"])])
    owns = [a for a in rec.relationship_assertions
            if a.relationship_type is RelationshipType.OWNS]
    assert len(owns) == 1                       # consolidated
    assert len(owns[0].evidence_unit_ids) == 2  # both sources preserved


def test_upstream_gap_preserved():
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
        RetrievalGap, GapType as E2Gap,
    )
    rec = _rec_from_units([_unit("Widget Z is mentioned.", ["Widget Z"])],
                          gaps=(RetrievalGap(E2Gap.INSUFFICIENT_EVIDENCE, "x"),))
    assert any(g.gap_code is GapCode.INSUFFICIENT_RETRIEVAL_EVIDENCE
               for g in rec.unresolved_relationship_gaps)


# --- provenance / schema / determinism / invalid input ----------------------

def test_every_assertion_has_provenance():
    rec = _rec_from_units([_unit("Acme owns System B.", ["Acme", "System B"])])
    for a in rec.relationship_assertions:
        assert a.source_provenance and all(p.is_complete() for p in a.source_provenance)
    ok, problems = validate_record(rec)
    assert ok, problems


def test_processing_trace_present():
    rec = _rec_from_units([_unit("Acme owns System B.", ["Acme", "System B"])])
    assert "relationship_record_generation" in rec.processing_trace


def test_invalid_input_rejected():
    ok, problems = validate_inputs("not-an-intent", "not-a-retrieval")
    assert not ok and problems


def test_deterministic_and_stable_ordering():
    txt = "Acme owns Platform B and licenses Module C to Vendor D."
    ents = ["Acme", "Platform B", "Module C", "Vendor D"]
    _UID[0] = 500
    r1 = _rec_from_units([_unit(txt, ents)])
    _UID[0] = 500                       # same unit id -> identical inputs
    r2 = _rec_from_units([_unit(txt, ents)])
    assert r1.to_json() == r2.to_json()


def test_all_baselines_valid_schema():
    units = [_unit("Acme owns System B.", ["Acme", "System B"])]
    for cfg in BASELINES:
        rec = RelationshipTruthLayer(cfg).extract(
            _E1.interpret(RawUserRequest("t", "q")),
            build_retrieval_record(corpus.cases_for_split("dev")[0]))
        assert isinstance(rec.schema_version, str)


# --- leakage / harness ------------------------------------------------------

def test_public_loader_hides_gold():
    for pub in loader.public_cases("eval"):
        assert set(pub.keys()) == {"case_id", "split", "request_text", "units"}


def test_harness_reproducible_and_pass():
    a = json.dumps(harness.run_all(), sort_keys=True, default=str)
    b = json.dumps(harness.run_all(), sort_keys=True, default=str)
    assert a == b
    r = harness.run_all()
    assert r["gates"]["all_pass"]
    assert r["verdict"] == "PASS_WITH_LIMITED_CLAIM"
    assert r["selection"]["selected_config"] in {c.name for c in BASELINES}


def test_severe_zero_on_selected():
    r = harness.run_all()
    sel = r["selection"]["selected_config"]
    assert r["metrics"]["eval_locked"][sel]["severe_critical_failure_count"] == 0

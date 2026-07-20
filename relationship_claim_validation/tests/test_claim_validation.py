"""
Relationship Claim Validation v0.1 — deterministic curation/calibration tests.

No resolver, governance, or other track is imported or run. These tests exercise
the layer, the ablations, determinism, leakage control, and package isolation.
"""

import ast
import pathlib

from relationship_claim_validation import corpus, loader, runner
from relationship_claim_validation.model import ClaimStatus, RecommendedAction
from relationship_claim_validation.validator import ABLATIONS, ClaimValidationLayer


def _v(name):
    return next(c for c in ABLATIONS if c.name == name)


# --- calibration: disabled layer is identity pass-through --------------------

def test_v0_disabled_is_identity_retain_all():
    docs, claims, gold = corpus.documents(), corpus.claims(), corpus.gold()
    recs = {r.relationship_id: r for r in
            ClaimValidationLayer(_v("V0"), docs).validate_corpus(claims)}
    assert all(r.validation_status == ClaimStatus.SUPPORTED for r in recs.values())
    assert all(r.recommended_action == RecommendedAction.RETAIN for r in recs.values())
    assert len(recs) == len(gold)


# --- deterministic pre-judge removals ---------------------------------------

def test_deterministic_removes_illegal_and_duplicate_and_bad_citation():
    docs, claims = corpus.documents(), corpus.claims()
    recs = {r.relationship_id: r for r in
            ClaimValidationLayer(_v("V4"), docs).validate_corpus(claims)}
    # illegal type, duplicate, self-loop -> deterministically removed
    for rid in ("U5", "U4", "U6"):
        assert recs[rid].deterministic_removed, rid
        assert recs[rid].recommended_action == RecommendedAction.REMOVE
    # missing doc / missing span / no-citation -> deterministically abstained
    for rid in ("I3", "I4", "I5"):
        assert recs[rid].deterministic_removed, rid
        assert recs[rid].validation_status == ClaimStatus.INSUFFICIENT_EVIDENCE


# --- full system matches gold on the clear cases ----------------------------

def test_v4_status_matches_gold_on_clear_families():
    docs, claims, gold = corpus.documents(), corpus.claims(), corpus.gold()
    recs = {r.relationship_id: r for r in
            ClaimValidationLayer(_v("V4"), docs).validate_corpus(claims)}
    # every SUPPORTED-gold clear case is retained
    for rid, g in gold.items():
        if g.gold_status == ClaimStatus.SUPPORTED:
            assert recs[rid].validation_status == ClaimStatus.SUPPORTED, rid
    # contradiction + unknown families resolve as designed
    assert recs["C0"].validation_status == ClaimStatus.CONTRADICTED
    assert recs["K0"].validation_status == ClaimStatus.UNKNOWN
    assert recs["K0"].adjudicated


# --- Judge C strictly changes UNKNOWN cases vs V3 ---------------------------

def test_judge_c_improves_unknown_over_v3():
    docs, claims, gold = corpus.documents(), corpus.claims(), corpus.gold()
    v3 = {r.relationship_id: r for r in
          ClaimValidationLayer(_v("V3"), docs).validate_corpus(claims)}
    v4 = {r.relationship_id: r for r in
          ClaimValidationLayer(_v("V4"), docs).validate_corpus(claims)}
    unknown_ids = [rid for rid, g in gold.items()
                   if g.gold_status == ClaimStatus.UNKNOWN]
    assert unknown_ids
    for rid in unknown_ids:
        assert v3[rid].validation_status != ClaimStatus.UNKNOWN     # v3 cannot reach it
        assert v4[rid].validation_status == ClaimStatus.UNKNOWN     # v4 (with C) does


# --- Judge B is what catches contradictions (V2 cannot) ---------------------

def test_v2_without_challenger_misses_contradictions():
    docs, claims, gold = corpus.documents(), corpus.claims(), corpus.gold()
    v2 = {r.relationship_id: r for r in
          ClaimValidationLayer(_v("V2"), docs).validate_corpus(claims)}
    v4 = {r.relationship_id: r for r in
          ClaimValidationLayer(_v("V4"), docs).validate_corpus(claims)}
    contra_ids = [rid for rid, g in gold.items()
                  if g.gold_status == ClaimStatus.CONTRADICTED]
    # V2 (advocate only) accepts at least one contradiction that V4 rejects
    assert any(v2[rid].recommended_action != RecommendedAction.REMOVE
               for rid in contra_ids)
    assert all(v4[rid].recommended_action == RecommendedAction.REMOVE
               for rid in contra_ids)


# --- primary endpoint direction: V4 beats V0 with net positive fixes --------

def test_v4_net_fixes_positive():
    r = runner.run_all()
    p = r["paired_vs_V0"]["V4"]
    assert p["n_fixes"] > 0
    assert p["net"] > 0
    assert p["net"] == p["n_fixes"] - p["n_breaks"]


# --- determinism: two full runs are byte-identical --------------------------

def test_two_runs_match():
    import json
    a = json.dumps(runner.run_all(), sort_keys=True)
    b = json.dumps(runner.run_all(), sort_keys=True)
    assert a == b


# --- leakage: public projection exposes no gold/family/difficulty -----------

def test_public_projection_has_no_leakage():
    for c in loader.public_claims():
        for k in ("gold", "gold_status", "difficulty", "family", "rationale"):
            assert k not in c
    for rec in loader.validate_public("V4"):
        for k in ("gold", "gold_status", "difficulty", "family", "rationale"):
            assert k not in rec


# --- isolation: package imports nothing from other tracks -------------------

def test_package_is_self_contained():
    root = pathlib.Path(__file__).resolve().parents[1]
    banned = ("agentic", "cyber_security", "symbolu", "cer_", "jepa", "sovereign",
              "trading", "enterprise_governance", "action_gate", "resolver")
    offenders = []
    for py in root.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(), filename=str(py))):
            mod = None
            if isinstance(node, ast.Import):
                mod = " ".join(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            if not mod:
                continue
            for b in banned:
                if b in mod and "relationship_claim_validation" not in mod:
                    offenders.append(f"{py.name}: {mod}")
    assert not offenders, f"unexpected imports: {offenders}"

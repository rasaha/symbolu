"""Completeness + determinism tests for the missing-inventory architecture decision. NO network, NO model.

Proves: all 18 missing units covered; every role/provenance value is from the allowed vocabulary; the role matrix
contains NO semantic glosses (no binding/liberating words); no unit is silently activated; deterministic outputs.
Structure, not validated meaning.
"""
import hashlib
import json
import pathlib

import b1_missing_inventory_architecture as A

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "missing_inventory_architecture"
FILES = ("role_matrix.json", "model_comparison.json", "source_claim_ledger.json",
         "unresolved_questions.json", "provenance_policy.json")


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def test_all_18_units_covered():
    A.build()
    rm = json.load(open(OUT / "role_matrix.json", encoding="utf-8"))
    cats = [u["category"] for u in rm["units"]]
    assert cats.count("vowel") == 14
    assert cats.count("anusvara") == 1 and cats.count("visarga") == 1
    assert cats.count("candrabindu") == 1 and cats.count("retroflex_lateral") == 1
    assert len(rm["units"]) == 18


def test_roles_and_provenance_allowed():
    rm = json.load(open(OUT / "role_matrix.json", encoding="utf-8"))
    for u in rm["units"]:
        assert u["recommended_role"] in A.CANDIDATE_ROLES
        assert u["role_provenance"] in A.PROV_CLASSES
        for r in u["candidate_roles"]:
            assert r in A.CANDIDATE_ROLES


def test_no_semantic_glosses_in_role_matrix():
    blob = (OUT / "role_matrix.json").read_text().lower()
    for banned in ("binding", "liberating", "genutility", "ontological_signal"):
        assert banned not in blob


def test_no_unit_silently_activated():
    rm = json.load(open(OUT / "role_matrix.json", encoding="utf-8"))
    for u in rm["units"]:
        # no missing unit may be granted an independent semantic entry in this decision
        assert u["independent_semantic_entry_allowed"] is False
        # polarity is never simply "YES" for any missing unit here
        assert u["polarity_allowed"] in ("UNRESOLVED", "NO")


def test_authored_provisional_not_admitted_to_confirmatory():
    pol = json.load(open(OUT / "provenance_policy.json", encoding="utf-8"))
    assert pol["authored_provisional_permitted_in_confirmatory_stage1"] is False
    assert "AUTHORED_PROVISIONAL" not in pol["confirmatory_mechanism_admits"]


def test_verdicts_are_from_allowed_sets():
    res = A.build()
    assert res["architecture_verdict"] in {
        "RECOMMEND_TYPED_MIXED_INVENTORY", "RECOMMEND_FULL_PRIMITIVE_INVENTORY",
        "RECOMMEND_AKSHARA_LEVEL_INVENTORY", "RECOMMEND_CONSONANT_ONLY_SEMANTIC_CORE",
        "ARCHITECTURE_DECISION_BLOCKED_BY_SOURCE_AMBIGUITY"}
    assert res["readiness_verdict"] in {
        "READY_FOR_MISSING_INVENTORY_PROVENANCE_STUDY", "READY_FOR_COMPOSITION_ARCHITECTURE_PREREG",
        "BLOCKED_BY_UNRESOLVED_UNIT_ROLES", "BLOCKED_BY_SOURCE_CONTRADICTIONS"}
    # must NOT declare readiness for semantic word testing
    assert "SEMANTIC_WORD_TESTING" not in res["readiness_verdict"]


def test_ledger_provenance_labelled():
    led = json.load(open(OUT / "source_claim_ledger.json", encoding="utf-8"))["ledger"]
    assert len(led) >= 5
    for e in led:
        assert e["provenance"] in A.PROV_CLASSES
        assert e["location"] and e["inference_label"]   # every claim has a location + inference label


def test_models_A_through_E_present():
    mc = json.load(open(OUT / "model_comparison.json", encoding="utf-8"))
    assert {m["id"] for m in mc["models"]} == {"A", "B", "C", "D", "E"}
    assert len(mc["criteria"]) == 10


def test_deterministic():
    A.build(); h1 = {f: _sha(OUT / f) for f in FILES}
    A.build(); h2 = {f: _sha(OUT / f) for f in FILES}
    assert h1 == h2


def test_no_table_or_parser_touched():
    # decision must not import the polarity table content, scorer, or parser mutation surface
    src = (HERE / "b1_missing_inventory_architecture.py").read_text()
    for banned in ("import torch", "transformers", "word_to_varnas", "VARNA_PLAIN", "def parse("):
        assert banned not in src

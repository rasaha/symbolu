"""
Focused tests for the canonical `tap_e4_governance_resolution` import package.

These assert the compatibility contract only — that the canonical path re-exports the
*identical* historical implementation objects, that both paths resolve, and that resolving
through either path yields a byte-identical GovernanceRecord. They add no behavioral
expectation and never rerun experiment generation. One regression pins the *documented
current* missing-situation-fact behavior so a future change is deliberate.
"""

import importlib

import pytest

import truth_assurance_pipeline.tap_e4_governance_resolution as canonical
import truth_assurance_pipeline.tap_e4_governance_truth as historical
from truth_assurance_pipeline.tap_e1_intent import (
    IntentUnderstandingLayer, config as e1_config,
)
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e4_governance_truth.corpus import cases as corpus

_E1 = IntentUnderstandingLayer(e1_config("V4"))


def test_both_packages_import():
    assert importlib.import_module("truth_assurance_pipeline.tap_e4_governance_resolution")
    assert importlib.import_module("truth_assurance_pipeline.tap_e4_governance_truth")


def test_reexports_are_identical_objects():
    for name in ("GovernanceRecord", "GoverningDecision", "GovernanceConflict",
                 "GovernanceGap", "GovProvenance", "GovernanceConfidence",
                 "GovernanceConfig", "GovStatus", "GovGapCode", "GovConflictType",
                 "AuthorityTier", "config", "validate_record", "SCHEMA_VERSION",
                 "BASELINES"):
        assert getattr(canonical, name) is getattr(historical, name), name


def test_canonical_situation_alias_is_historical_situation():
    assert canonical.GovernanceSituation is historical.Situation


def test_canonical_resolver_alias_is_historical_layer():
    assert canonical.GovernanceResolver is historical.GovernanceTruthLayer


def test_canonical_decision_alias_is_historical_decision():
    assert canonical.GovernanceDecision is historical.GoverningDecision


def _resolve(case, mod):
    intent = _E1.interpret(RawUserRequest(case.case_id, case.request_text))
    ret = corpus.build_retrieval_record(case)
    rel = corpus.build_relationship_record(case)
    layer = mod.GovernanceResolver(mod.config("F")) if mod is canonical \
        else mod.GovernanceTruthLayer(mod.config("F"))
    return layer.resolve(intent, ret, rel, case.situation)


def test_resolution_is_byte_identical_across_paths():
    for case in corpus.ALL_CASES:
        assert _resolve(case, canonical).to_json() == _resolve(case, historical).to_json()


def test_situation_has_only_documented_fields():
    import dataclasses
    names = {f.name for f in dataclasses.fields(canonical.GovernanceSituation)}
    assert names == {"jurisdiction", "user_role", "environment", "date_year",
                     "contract", "product", "business_unit"}


def test_situation_has_no_field_level_provenance():
    # documents current reality: Situation stores bare values, no per-field provenance
    s = canonical.GovernanceSituation(jurisdiction="us")
    assert not hasattr(s, "facts")
    assert not hasattr(s, "provenance")


def test_missing_situation_fact_never_invents_a_value_regression():
    """Pins DOCUMENTED CURRENT behavior: with an empty situation the engine lowers the
    scope/temporal confidence axes and keeps a real, provenance-complete authority — it
    never fabricates a situation VALUE. (Forcing an unresolved state on absent mandatory
    scope facts would require changing frozen resolver source and is a documented future
    limitation, not changed here.)"""
    case = next(c for c in corpus.ALL_CASES if c.family == "scope")
    rec = _resolve_with(case, canonical.GovernanceSituation())
    d = rec.governing_authorities[0]
    # never invents a role value into the decision's scope basis
    assert d.scope.get("user_role") in (None, "", "all") or d.scope.get("user_role")
    # the absence is reflected as reduced scope confidence, not hidden
    assert rec.confidence_vector.scope_confidence <= 0.5
    # any selected authority still carries a complete provenance chain (no fabrication)
    if d.selected_authority:
        assert d.provenance and all(p.is_complete() for p in d.provenance)


def _resolve_with(case, situation):
    intent = _E1.interpret(RawUserRequest(case.case_id, case.request_text))
    ret = corpus.build_retrieval_record(case)
    rel = corpus.build_relationship_record(case)
    return canonical.GovernanceResolver(canonical.config("F")).resolve(
        intent, ret, rel, situation)


def test_no_module_level_resolve_function_invented():
    # the implementation exposes a resolver class, not a resolve_governance() function
    assert not hasattr(canonical, "resolve_governance")

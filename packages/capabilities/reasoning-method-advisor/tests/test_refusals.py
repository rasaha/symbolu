"""Specification §7 refusal rows R-a to R-k, plus the public-API pins."""

from __future__ import annotations

import dataclasses
import re

import pytest

import matrix_fixtures as fx
import rule_fixtures as rf
from ugence_reasoning_method_advisor import api
from ugence_reasoning_method_advisor.api import (
    AdvisorError,
    AdvisorErrorCode as A,
    AdvisoryClassification,
    AdvisoryEligibility,
    AdvisoryLabel,
    NoPrimaryReason,
    Predicate,
    PredicateKind,
    QualifyingTradeOff,
    ReasoningMethodAdvisory,
    Rule,
    RuleKind,
    RuleOutcome,
    RuleSet,
    advise,
    validate_against_rule_set,
)
from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode as C


def refuses(code, fn):
    with pytest.raises((AdvisorError, ContractError)) as ei:
        fn()
    assert ei.value.code is code, f"expected {code.value}, got {ei.value.code.value}: {ei.value.detail}"


def test_r_a_scalar_label_field_refused_at_class_definition():
    for name in ("score", "rank", "probability", "cost", "latency_class"):
        with pytest.raises(ContractError) as ei:
            type("Bad", (RuleOutcome,), {"__annotations__": {name: str}})
        assert ei.value.code is C.SCALAR_LABEL_FIELD_PRESENT, name


def test_r_b_rule_naming_unknown_method():
    rs = rf.research_rules_v0(extra=(rf.signal_rule("comparison_request", "not_a_method", suffix=".x"),))
    refuses(A.RULE_METHOD_UNKNOWN, lambda: advise(rf.request(("comparison_request",), rule_set=rs), advised_at=fx.NOW))


def test_r_c_non_signal_token_predicate():
    refuses(C.SIGNAL_TOKEN_UNKNOWN, lambda: Predicate(PredicateKind.STRUCTURAL_TOKEN_PRESENT, ("not_a_signal",)))


def test_r_d_class_missing_profile_token():
    from ugence_reasoning_method_advisor.api import ADVISORY_REQUEST_SCHEMA_VERSION, ReasoningMethodAdvisoryRequest

    refuses(
        A.PROFILE_CLASS_MISMATCH,
        lambda: ReasoningMethodAdvisoryRequest(ADVISORY_REQUEST_SCHEMA_VERSION, "r", rf.profile(("comparison_request", "ambiguity_detected")), rf.governed_class(("comparison_request",)), fx.c4_catalog(), rf.research_rules_v0()),
    )


def _kwargs(adv):
    return {f.name: getattr(adv, f.name) for f in dataclasses.fields(adv) if f.name != "advisory_digest"}


def test_r_e_primary_without_sole_qualifier():
    two = advise(rf.request(("comparison_request", "ambiguity_detected")), advised_at=fx.NOW)
    kw = _kwargs(two)
    kw.update(primary=two.qualifying[0].method, primary_basis="SOLE_QUALIFYING_METHOD", no_primary_reason=None)
    refuses(A.PRIMARY_WITHOUT_SOLE_QUALIFIER, lambda: ReasoningMethodAdvisory(**kw))
    one = advise(rf.request(("comparison_request",)), advised_at=fx.NOW)
    kw1 = _kwargs(one)
    kw1.update(primary=None, primary_basis=None, no_primary_reason=NoPrimaryReason.NO_QUALIFYING_METHOD)
    refuses(A.PRIMARY_WITHOUT_SOLE_QUALIFIER, lambda: ReasoningMethodAdvisory(**kw1))


def test_r_i_trade_off_cardinality():
    one = advise(rf.request(("comparison_request",)), advised_at=fx.NOW)
    kw = _kwargs(one)
    kw["trade_offs"] = (QualifyingTradeOff(one.qualifying[0].method, (), ()),)
    refuses(A.TRADE_OFF_CARDINALITY, lambda: ReasoningMethodAdvisory(**kw))
    two = advise(rf.request(("comparison_request", "ambiguity_detected")), advised_at=fx.NOW)
    kw2 = _kwargs(two)
    kw2["trade_offs"] = two.trade_offs[:1]
    refuses(A.TRADE_OFF_CARDINALITY, lambda: ReasoningMethodAdvisory(**kw2))
    kw3 = _kwargs(two)
    excluded_method = two.excluded[0].method
    kw3["trade_offs"] = tuple(sorted((QualifyingTradeOff(excluded_method, (), ()), two.trade_offs[1]), key=lambda t: t.method.sort_key))
    refuses(A.TRADE_OFF_CARDINALITY, lambda: ReasoningMethodAdvisory(**kw3))


def test_r_j_rule_outcome_version_mismatch():
    rs = rf.research_rules_v0()
    adv = advise(rf.request(("comparison_request",), rule_set=rs), advised_at=fx.NOW)
    q = adv.qualifying[0]
    forged = dataclasses.replace(q.inclusion_reasons[0], rule_version="9")
    kw = _kwargs(adv)
    kw["qualifying"] = (dataclasses.replace(q, inclusion_reasons=(forged,)),)
    bad = ReasoningMethodAdvisory(**kw)
    refuses(A.RULE_OUTCOME_VERSION_MISMATCH, lambda: validate_against_rule_set(bad, rs))
    validate_against_rule_set(adv, rs)


def test_r_k_duplicate_rule_id():
    rs = rf.research_rules_v0()
    dup = rs.rules + (rs.rules[0],)
    refuses(A.RULE_DUPLICATE_ID, lambda: RuleSet(rs.schema_version, rs.rule_set_id, rs.rule_set_version, rs.admissibility, tuple(sorted(dup, key=lambda r: r.rule_id)), rs.provenance_ref, rs.issuer_identity, rs.issued_at))


def test_r_g_classification_inconsistent():
    adv = advise(rf.request(("comparison_request",), governed=False), advised_at=fx.NOW)
    kw = _kwargs(adv)
    kw["classification"] = AdvisoryClassification.GOVERNED_TASK_CLASS
    refuses(A.CLASSIFICATION_INCONSISTENT, lambda: ReasoningMethodAdvisory(**kw))
    kw2 = _kwargs(adv)
    kw2["eligibility"] = AdvisoryEligibility.JOINABLE_BY_TASK_CLASS_DIGEST
    refuses(A.CLASSIFICATION_INCONSISTENT, lambda: ReasoningMethodAdvisory(**kw2))


def test_r_h_blank_rule_version_or_rationale():
    refuses(C.REF_BLANK_FIELD, lambda: Rule("r", "", RuleKind.SUPPORT, Predicate(PredicateKind.STRUCTURAL_TOKEN_PRESENT, ("comparison_request",)), ("map_reduce",), "ref", "why"))
    refuses(C.REF_BLANK_FIELD, lambda: Rule("r", "0", RuleKind.SUPPORT, Predicate(PredicateKind.STRUCTURAL_TOKEN_PRESENT, ("comparison_request",)), ("map_reduce",), "ref", ""))


def test_r_f_benchmark_derived_is_not_a_label():
    with pytest.raises(ValueError):
        AdvisoryLabel("BENCHMARK_DERIVED")
    assert [m.value for m in AdvisoryLabel] == ["RULE_DERIVED", "COMPARISON_EVIDENCE_ABSENT"]


def test_public_api_and_version_pin():
    for n in api.__all__:
        assert hasattr(api, n), n
    assert {m.value for m in A} == {"PROFILE_CLASS_MISMATCH", "RULE_METHOD_UNKNOWN", "PRIMARY_WITHOUT_SOLE_QUALIFIER", "CLASSIFICATION_INCONSISTENT", "TRADE_OFF_CARDINALITY", "RULE_OUTCOME_VERSION_MISMATCH", "RULE_SET_UNSORTED", "RULE_DUPLICATE_ID"}
    import pathlib

    text = (pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == api.__version__


def test_no_numeric_defaults_and_no_numeric_fields():
    for n in api.__all__:
        obj = getattr(api, n)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                assert f.default is dataclasses.MISSING or f.default is None or f.default == () or isinstance(f.default, str), f"{n}.{f.name}"
                assert "int" not in str(f.type) and "float" not in str(f.type) and "Decimal" not in str(f.type), f"{n}.{f.name} is numeric"


def test_signal_map_transcription_matches_runtime_selector_when_loadable():
    """Provenance pin: the fixture transcribes SIGNAL_MAP verbatim. Skipped when the
    runtime tree cannot import (it needs numpy); never a runtime dependency."""
    rw = pytest.importorskip("agentic.agentic_framework.reasoning_workflows")
    live = {sig.value: wf.value for sig, wf in rw.WorkflowSelector.SIGNAL_MAP.items()}
    assert live == rf.SIGNAL_MAP_TRANSCRIPTION

"""Specification §7 profile rows P1–P14."""

from __future__ import annotations

import dataclasses
import random

import pytest

import matrix_fixtures as fx
import rule_fixtures as rf
from ugence_reasoning_method_advisor.api import (
    ADVISOR_IDENTITY,
    SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS,
    SYNTHETIC_NO_SUPPORTING_RULE,
    AdvisorError,
    AdvisorErrorCode,
    AdvisoryClassification,
    AdvisoryEligibility,
    AdvisoryLabel,
    NoPrimaryReason,
    ReasoningMethodAdvisory,
    ReasoningMethodAdvisoryRequest,
    RuleSet,
    TraversalOrder,
    advise,
)
from ugence_reasoning_method_governance.api import CATALOG_SCHEMA_VERSION, ConsequenceClass, ImplementationEvidence, ImplementationEvidenceKind, ReasoningMethodCatalog, TaskReversibility


def run(req, **kw):
    return advise(req, advised_at=fx.NOW, **kw)


def q_ids(adv):
    return [q.method.method_id for q in adv.qualifying]


def test_p1_single_qualifier_is_primary_and_governed():
    adv = run(rf.request(("comparison_request",)))
    assert q_ids(adv) == ["map_reduce"]
    assert adv.primary.method_id == "map_reduce" and adv.primary_basis == "SOLE_QUALIFYING_METHOD"
    assert adv.no_primary_reason is None and adv.trade_offs == ()
    assert adv.classification is AdvisoryClassification.GOVERNED_TASK_CLASS
    assert adv.eligibility is AdvisoryEligibility.JOINABLE_BY_TASK_CLASS_DIGEST
    assert adv.evidence_status == "COMPARISON_EVIDENCE_ABSENT" and adv.usage_scope == "RESEARCH_ONLY"
    assert adv.advisor_identity == ADVISOR_IDENTITY
    assert all(q.label is AdvisoryLabel.RULE_DERIVED for q in adv.qualifying) and all(e.label is AdvisoryLabel.RULE_DERIVED for e in adv.excluded)
    assert len(adv.qualifying) + len(adv.excluded) == 7


def test_p2_two_qualifiers_no_primary_with_trade_offs():
    adv = run(rf.request(("comparison_request", "ambiguity_detected")))
    assert q_ids(adv) == ["map_reduce", "tree_of_thought"]
    assert adv.primary is None and adv.no_primary_reason is NoPrimaryReason.MULTIPLE_QUALIFYING_METHODS
    assert [t.method.method_id for t in adv.trade_offs] == ["map_reduce", "tree_of_thought"]
    assert [r.rule_id for r in adv.trade_offs[0].distinguishing_reasons] == ["research.signal.comparison_request"]
    assert [r.rule_id for r in adv.trade_offs[1].distinguishing_reasons] == ["research.signal.ambiguity_detected"]


def test_p3_no_tokens_nothing_qualifies():
    adv = run(rf.request(()))
    assert adv.qualifying == () and adv.primary is None and adv.no_primary_reason is NoPrimaryReason.NO_QUALIFYING_METHOD
    assert len(adv.excluded) == 7
    assert all(e.exclusion_reasons[0].rule_id == SYNTHETIC_NO_SUPPORTING_RULE for e in adv.excluded)


def test_p4_exclude_rule_removes_debate_for_severe():
    rs = rf.research_rules_v0(extra=(rf.exclude_rule("exclude.debate.severe", "debate", ConsequenceClass.SEVERE),))
    adv = run(rf.request(("conditional_logic", "causal_reasoning"), rule_set=rs, consequence=ConsequenceClass.SEVERE))
    assert q_ids(adv) == ["linear_chain"] and adv.primary.method_id == "linear_chain"
    debate = next(e for e in adv.excluded if e.method.method_id == "debate")
    assert [r.rule_id for r in debate.exclusion_reasons] == ["exclude.debate.severe"]
    assert debate.exclusion_reasons[0].matched_tokens == ("SEVERE",)


def test_p5_and_p14_same_reason_two_qualifiers_and_rule_count_never_wins():
    # P14 reads P5 as "two qualifiers supported by the same rule": the comparison_request
    # rule names both methods, so neither has a distinguishing reason.
    same_rule = rf.signal_rule("comparison_request", method_ids=("map_reduce", "debate"))
    rs = rf.research_rules_v0(replace=(same_rule,))
    adv = run(rf.request(("comparison_request",), rule_set=rs))
    assert q_ids(adv) == ["debate", "map_reduce"] and adv.primary is None
    assert all(t.distinguishing_reasons == () for t in adv.trade_offs)
    assert {f.name for f in dataclasses.fields(adv.trade_offs[0])} == {"method", "distinguishing_reasons", "distinguishing_requirement_refs"}
    # Adding further SUPPORT rules for debate on the same token never manufactures a winner.
    rs3 = rf.research_rules_v0(replace=(same_rule,), extra=(rf.signal_rule("comparison_request", "debate", suffix=".alt"), rf.signal_rule("comparison_request", "debate", suffix=".alt2")))
    adv3 = run(rf.request(("comparison_request",), rule_set=rs3))
    assert adv3.primary is None and q_ids(adv3) == ["debate", "map_reduce"]
    debate = next(q for q in adv3.qualifying if q.method.method_id == "debate")
    assert len(debate.inclusion_reasons) == 3


def test_p6_inadmissible_entry_is_excluded_synthetically():
    entries = []
    for e in fx.c4_catalog().entries:
        if e.method_id == "map_reduce":
            e = fx.c3_entry("map_reduce", evidence=(ImplementationEvidence(ImplementationEvidenceKind.UNIT_TESTS_PRESENT, "tests", fx.NOW),))
        entries.append(e)
    cat = ReasoningMethodCatalog(CATALOG_SCHEMA_VERSION, "cat.rm", "1", tuple(sorted(entries, key=lambda x: x.sort_key)), "issuer:test", fx.NOW)
    adv = run(rf.request(("comparison_request",), catalog=cat))
    assert adv.qualifying == ()
    mr = next(e for e in adv.excluded if e.method.method_id == "map_reduce")
    assert mr.exclusion_reasons[0].rule_id == SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS


def test_p7_unclassified_request_is_exploratory_only():
    adv = run(rf.request(("comparison_request",), governed=False))
    assert q_ids(adv) == ["map_reduce"] and adv.task_class_digest is None
    assert adv.classification is AdvisoryClassification.UNCLASSIFIED_EXPLORATORY
    assert adv.eligibility is AdvisoryEligibility.INELIGIBLE_UNCLASSIFIED
    assert adv.evidence_status == "COMPARISON_EVIDENCE_ABSENT"


def test_p8_no_comparison_field_exists():
    for cls in (ReasoningMethodAdvisoryRequest, ReasoningMethodAdvisory):
        assert not any("comparison" in f.name for f in dataclasses.fields(cls)), cls.__name__


def test_p9_undetermined_reversibility_profile_is_allowed():
    adv = run(rf.request(("comparison_request",), governed=False, reversibility=TaskReversibility.UNDETERMINED))
    assert q_ids(adv) == ["map_reduce"]


def test_p10_digest_stable_and_sensitive_to_rule_set_version():
    a, b = run(rf.request(("comparison_request",))), run(rf.request(("comparison_request",)))
    c = run(rf.request(("comparison_request",), rule_set=rf.research_rules_v0(version="1")))
    assert a.advisory_digest == b.advisory_digest != c.advisory_digest


def test_p11_evaluator_order_independence():
    req = rf.request(("comparison_request", "ambiguity_detected"))
    base = run(req)
    rng = random.Random("seeded-permutation")
    traversals = [
        TraversalOrder(rules=lambda s: list(reversed(s))),
        TraversalOrder(entries=lambda s: list(reversed(s))),
        TraversalOrder(qualifying=lambda s: rng.sample(list(s), len(s))),
        TraversalOrder(rules=lambda s: list(reversed(s)), entries=lambda s: list(reversed(s)), qualifying=lambda s: list(reversed(s))),
    ]
    for t in traversals:
        other = run(req, _traversal=t)
        assert other.qualifying == base.qualifying and other.excluded == base.excluded
        assert other.trade_offs == base.trade_offs and other.primary == base.primary
        assert other.advisory_digest == base.advisory_digest


def test_p12_unsorted_rules_are_refused():
    rs = rf.research_rules_v0()
    with pytest.raises(AdvisorError) as ei:
        RuleSet(rs.schema_version, rs.rule_set_id, rs.rule_set_version, rs.admissibility, tuple(reversed(rs.rules)), rs.provenance_ref, rs.issuer_identity, rs.issued_at)
    assert ei.value.code is AdvisorErrorCode.RULE_SET_UNSORTED
    assert RuleSet(rs.schema_version, rs.rule_set_id, rs.rule_set_version, rs.admissibility, rs.rules, rs.provenance_ref, rs.issuer_identity, rs.issued_at).rule_set_digest == rs.rule_set_digest


def test_p13_trade_off_cardinality_matches_qualifying():
    adv = run(rf.request(("comparison_request", "ambiguity_detected")))
    assert len(adv.trade_offs) == len(adv.qualifying) == 2
    assert [t.method for t in adv.trade_offs] == [q.method for q in adv.qualifying]
    assert not ({t.method for t in adv.trade_offs} & {e.method for e in adv.excluded})


def test_cross_process_digest_stability(tmp_path):
    import subprocess, sys, pathlib

    here = pathlib.Path(__file__).resolve().parent
    code = (
        "import sys; sys.path[:0]=[%r,%r]\n"
        "import matrix_fixtures as fx, rule_fixtures as rf\n"
        "from ugence_reasoning_method_advisor.api import advise\n"
        "print(advise(rf.request(('comparison_request','ambiguity_detected')), advised_at=fx.NOW).advisory_digest)\n"
    ) % (str(here), str(here.parents[1] / "reasoning-method-governance" / "tests"))
    outs = {subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True, env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin", "PYTHONPATH": ":".join(sys.path)}).stdout.strip() for seed in ("1", "2")}
    assert len(outs) == 1

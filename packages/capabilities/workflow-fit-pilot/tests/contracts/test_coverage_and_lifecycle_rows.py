"""§8 rows A21–A25, A27–A29: coverage report, anti-gaming rule, synthetic engine fixture,
lifecycle transitions, revision lineage, constants."""

from __future__ import annotations

import dataclasses

import pytest

import matrix_fixtures as fx
import pilot_fixtures as pf
from ugence_reasoning_method_governance.api import FitOutcome, ReasoningMethodRef
from ugence_workflow_fit_pilot.api import (
    ChallengerCoverageReport,
    LifecycleEvent,
    PilotConfigurationState as S,
    PilotConfigurationStateRecord,
    PilotError,
    PilotErrorCode as E,
    RevisionScope,
    build_coverage_report,
    derive_revision_scope,
    propose,
    render,
    run_pilot,
    success_summary,
    transition,
    validate_lineage,
    validate_manifest,
)


def refuses(code, fn):
    with pytest.raises(PilotError) as ei:
        fn()
    assert ei.value.code is code, f"expected {code.value}, got {ei.value.code.value}: {ei.value.detail}"


def _validated(m, adv):
    return validate_manifest(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv)


def test_a21_coverage_counts_three_qualified_over_seven():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    v = _validated(m, adv)
    all_methods = tuple(a.method for a in m.methods)
    c = build_coverage_report(m, v, all_methods)
    assert (c.admissible_method_count, c.methods_assigned, c.qualified_declared, c.challengers_declared) == (7, 7, 3, 4)
    assert c.methods_with_record == 7 and c.qualified_with_record == 3 and c.challengers_with_record == 4 and c.baseline_has_record and c.summary_permitted
    outcomes = {m_: FitOutcome.SUFFICIENT_RESOURCE_DOMINATED for m_ in all_methods}
    outcomes[all_methods[1]] = FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    s = success_summary(c, m, outcomes)
    assert s is not None and s.qualified_declared == 3 and "set precision" in s.line() and "qualifying-set size 3/7" in s.line()


def test_a22_missing_records_forbid_the_summary_and_precision_denominator_is_declared():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    v = _validated(m, adv)
    qualified = m.methods_with_role(__import__("ugence_workflow_fit_pilot.api", fromlist=["PilotRole"]).PilotRole.ADVISOR_QUALIFIED)
    without_q = tuple(a.method for a in m.methods if a.method != qualified[0])
    c = build_coverage_report(m, v, without_q)
    assert not c.summary_permitted and c.qualified_with_record == 2 and c.methods_without_record == (qualified[0],)
    assert success_summary(c, m, {}) is None
    challenger = next(a.method for a in m.methods if a.method.method_id == "metacognitive")
    c2 = build_coverage_report(m, v, tuple(a.method for a in m.methods if a.method != challenger))
    assert not c2.summary_permitted and c2.challengers_with_record == 3 and c2.methods_without_record == (challenger,)
    refuses(E.COUNT_INVALID, lambda: dataclasses.replace(c, qualified_with_record=-1))
    refuses(E.COUNT_INVALID, lambda: dataclasses.replace(c, methods_with_record=1.5))  # type: ignore[arg-type]
    refuses(E.COUNT_INVALID, lambda: dataclasses.replace(c, summary_permitted=True))


def test_a23_empty_qualifying_set_runs_baseline_and_challengers():
    tc = pf.task_class(tokens=())
    adv = pf.advisory(tc, tokens=())
    m = pf.manifest(adv=adv, tc=tc, methods=pf.assignments(adv))
    res = run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=pf.FakeExecutor(pf.DEFAULT_CALLS), scorer=pf.KeywordScorer(),
                    identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env())
    assert res.coverage.qualified_declared == 0 and res.coverage.challengers_declared == 7 and res.coverage.summary_permitted
    text = render(res)
    assert "NO_QUALIFYING_METHOD" in text and "primary" not in text.lower()


def test_a24_transitions_and_outcome_line_wording():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    method = m.methods[0].method
    now = pf.clock()
    p = propose(m, method, recorded_by="r", recorded_at=now())
    refuses(E.STATE_TRANSITION_INVALID, lambda: transition(p, LifecycleEvent.RESULT_ASSESSED, manifest=m, result=None, recorded_by="r", recorded_at=now()))
    u = transition(p, LifecycleEvent.OBSERVATION_VALIDATED, manifest=m, recorded_by="r", recorded_at=now())
    assert u.state is S.UNDER_TEST and u.predecessor_state_digest == p.state_digest
    # hand-built EVALUATED with the wrong outcome or no outcome
    kw = {f.name: getattr(u, f.name) for f in dataclasses.fields(u) if f.name != "state_digest"}
    refuses(E.STATE_TRANSITION_INVALID, lambda: PilotConfigurationStateRecord(**{**kw, "state": S.EVALUATED, "fit_outcome": None, "result_digest": "a" * 64}))
    refuses(E.STATE_TRANSITION_INVALID, lambda: PilotConfigurationStateRecord(**{**kw, "state": S.EVALUATED, "fit_outcome": FitOutcome.COMPARISON_EVIDENCE_ABSENT, "result_digest": "a" * 64}))
    refuses(E.STATE_TRANSITION_INVALID, lambda: PilotConfigurationStateRecord(**{**kw, "state": S.INCONCLUSIVE, "fit_outcome": None, "refusal_codes": ()}))
    ev = PilotConfigurationStateRecord(**{**kw, "state": S.EVALUATED, "fit_outcome": FitOutcome.SUFFICIENT_RESOURCE_DOMINATED, "result_digest": "a" * 64})
    refuses(E.STATE_TRANSITION_INVALID, lambda: transition(ev, LifecycleEvent.RESULT_INCONCLUSIVE, manifest=m, result=None, recorded_by="r", recorded_at=now()))
    refuses(E.STATE_TRANSITION_INVALID, lambda: transition(ev, LifecycleEvent.OBSERVATION_VALIDATED, manifest=m, recorded_by="r", recorded_at=now()))
    # outcome lines never render the dominated outcome as qualified or success; the role label is permitted
    from ugence_workflow_fit_pilot.report import _outcome_line

    line = _outcome_line("x", FitOutcome.SUFFICIENT_RESOURCE_DOMINATED).lower()
    assert "qualified" not in line and "success" not in line
    assert "ADVISOR_QUALIFIED" in [r.value for r in m.methods[1].roles]


def test_a25_synthetic_engine_coverage_fixture_reaches_all_four_outcomes():
    import importlib, pathlib, sys

    eng_tests = pathlib.Path(__file__).resolve().parents[3] / "readiness-comparison" / "tests" / "engine"
    sys.path.insert(0, str(eng_tests))
    four = importlib.import_module("test_four_outcomes_pr1566")
    from ugence_readiness_comparison import compare

    easy = compare(four.request("easy", [(four.LC, "0.92", 1), (four.TOT, "0.94", 4), (four.DEB, "0.95", 5)]), produced_at=fx.NOW)
    hard = compare(four.request("hard", [(four.LC, "0.72", 1), (four.TOT, "0.91", 4), (four.DEB, "0.93", 5)]), produced_at=fx.NOW)
    absent = compare(four.request("absent", [(four.LC, "0.95", 1)]), produced_at=fx.NOW)
    seen = {a.outcome for r in (easy, hard, absent) for a in r.assessments}
    assert seen == set(FitOutcome)
    again = compare(four.request("easy", [(four.LC, "0.92", 1), (four.TOT, "0.94", 4), (four.DEB, "0.95", 5)]), produced_at=fx.NOW)
    assert again.result_digest == easy.result_digest


def _successor(m, adv, **changes):
    return pf.manifest(adv=adv, **changes)


def test_a27_a28_revision_lineage_one_way_derived_scope_and_drift():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    now = pf.clock()
    # every scope, one at a time
    variants = {
        RevisionScope.CONFIGURATION: pf.manifest(adv=adv, bnd=pf.binding("c" * 64)),
        RevisionScope.BENCHMARK_MANIFEST: None,  # built below (also changes task class)
        RevisionScope.EVALUATOR: pf.manifest(adv=adv, evaluator=pf.evaluator_decl(identity="evaluator:other")),
        RevisionScope.CAPTURE_BOUNDARY: pf.manifest(adv=adv, boundary=pf.boundary_decl(identity="boundary:other")),
        RevisionScope.AGGREGATION: pf.manifest(adv=adv, resource_agg=dataclasses.replace(pf.RESOURCE_AGG, aggregation_method_version="1")),
    }
    for scope, succ in variants.items():
        if succ is None:
            continue
        assert derive_revision_scope(m, succ) == (scope,), scope
    bm2 = pf.benchmark(extra_case="f" * 64)
    tc2 = pf.task_class(bm2)
    adv2 = pf.advisory(tc2)
    succ_bm = pf.manifest(adv=adv2, tc=tc2, bm=bm2)
    scopes = derive_revision_scope(m, succ_bm)
    assert RevisionScope.BENCHMARK_MANIFEST in scopes and RevisionScope.TASK_CLASS in scopes and RevisionScope.ADVICE in scopes
    tc3 = pf.task_class(rule_version="1")
    adv3 = pf.advisory(tc3)
    assert RevisionScope.SUFFICIENCY_RULE in derive_revision_scope(m, pf.manifest(adv=adv3, tc=tc3))
    adv4 = pf.advisory(tokens=("comparison_request",))
    tc4 = pf.task_class(tokens=("comparison_request",))
    assert RevisionScope.ADVICE in derive_revision_scope(m, pf.manifest(adv=adv4, tc=tc4, methods=pf.assignments(adv4)))
    # full supersession chain: predecessor REVISED for every method, successor PROPOSED for every method
    succ = variants[RevisionScope.CONFIGURATION]
    records = []
    for a in m.methods:
        p = propose(m, a.method, recorded_by="r", recorded_at=now())
        r = transition(p, LifecycleEvent.SUPERSEDED, manifest=m, successor_manifest=succ, recorded_by="r", recorded_at=now())
        assert r.successor_manifest_digest == succ.manifest_digest and r.revision_scope == (RevisionScope.CONFIGURATION,)
        sp = propose(succ, a.method, recorded_by="r", recorded_at=now(), predecessor=r, predecessor_manifest=m)
        assert sp.predecessor_state_digest == r.state_digest and sp.predecessor_manifest_digest == m.manifest_digest and sp.revision_scope == r.revision_scope
        records += [p, r, sp]
    validate_lineage(records, [m, succ])
    # method dropped by the successor: REVISED still valid, terminal; new method: PROPOSED without predecessor state
    dropped_succ = pf.manifest(adv=adv4, tc=tc4, methods=pf.assignments(adv4), bnd=pf.binding("d" * 64))
    recs2 = []
    for a in m.methods:
        p = propose(m, a.method, recorded_by="r", recorded_at=now())
        r = transition(p, LifecycleEvent.SUPERSEDED, manifest=m, successor_manifest=dropped_succ, recorded_by="r", recorded_at=now())
        recs2 += [p, r]
        sp = propose(dropped_succ, a.method, recorded_by="r", recorded_at=now(), predecessor=r, predecessor_manifest=m)
        recs2.append(sp)
    validate_lineage(recs2, [m, dropped_succ])
    # A28: no change, asserted scope, incomplete supersession, impossible record
    refuses(E.REVISION_WITHOUT_CHANGE, lambda: derive_revision_scope(m, m))
    forged = dataclasses.replace(records[1], revision_scope=(RevisionScope.EVALUATOR,), state_digest="")
    refuses(E.REVISION_SCOPE_MISMATCH, lambda: validate_lineage([records[0], forged], [m, succ]))
    refuses(E.LINEAGE_INCOMPLETE, lambda: validate_lineage(records[:3], [m, succ]))
    impossible = dataclasses.replace(records[2], state=S.EVALUATED, fit_outcome=FitOutcome.INSUFFICIENT_QUALITY, result_digest="a" * 64, revision_scope=(), predecessor_manifest_digest=None, state_digest="")
    refuses(E.LINEAGE_INCOMPLETE, lambda: validate_lineage([records[0], impossible], [m, succ]))  # the fabricated result is not supplied
    # a hand-built EVALUATED around a fabricated result digest, following a genuine UNDER_TEST record
    p0 = propose(m, m.methods[0].method, recorded_by="r", recorded_at=now())
    u0 = transition(p0, LifecycleEvent.OBSERVATION_VALIDATED, manifest=m, recorded_by="r", recorded_at=now())
    kw = {f.name: getattr(u0, f.name) for f in dataclasses.fields(u0) if f.name != "state_digest"}
    forged = PilotConfigurationStateRecord(**{**kw, "state": S.EVALUATED, "fit_outcome": FitOutcome.SUFFICIENT_PARETO_EFFICIENT, "result_digest": "b" * 64, "predecessor_state_digest": u0.state_digest})
    refuses(E.LINEAGE_INCOMPLETE, lambda: validate_lineage([p0, u0, forged], [m]))
    # with a genuine result that gives the method a different outcome
    res = run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=pf.FakeExecutor(pf.DEFAULT_CALLS), scorer=pf.KeywordScorer(),
                    identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env())
    validate_lineage(res.states, [m], [res.result])
    refuses(E.LINEAGE_INCOMPLETE, lambda: validate_lineage(res.states, [m]))
    ev = next(x for x in res.states if x.state is S.EVALUATED and x.fit_outcome is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED)
    lied = dataclasses.replace(ev, fit_outcome=FitOutcome.SUFFICIENT_PARETO_EFFICIENT, state_digest="")
    refuses(E.STATE_TRANSITION_INVALID, lambda: validate_lineage([x for x in res.states if x is not ev] + [lied], [m], [res.result]))
    # a GENUINE result from another manifest (different binding), same method and outcome, is not this manifest's
    other = pf.manifest(adv=adv, bnd=pf.binding("c" * 64))
    res_other = run_pilot(other, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=pf.FakeExecutor(pf.DEFAULT_CALLS), scorer=pf.KeywordScorer(),
                          identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env())
    cross = dataclasses.replace(ev, result_digest=res_other.result.result_digest, state_digest="")
    refuses(E.STATE_TRANSITION_INVALID, lambda: validate_lineage([x for x in res.states if x is not ev] + [cross], [m], [res.result, res_other.result]))


def test_a29_state_record_constants_and_no_approval_field():
    adv = pf.advisory()
    m = pf.manifest(adv=adv)
    p = propose(m, m.methods[0].method, recorded_by="r", recorded_at=pf.NOW)
    assert p.approval_status == "NONE" and p.usage_scope == "RESEARCH_ONLY"
    names = {f.name for f in dataclasses.fields(PilotConfigurationStateRecord)}
    assert not names & {"approved", "eligible", "qualified", "production", "approval"}
    assert not {s.value for s in S} & {o.value for o in FitOutcome}
    from ugence_reasoning_method_governance.api import ContractError

    with pytest.raises(ContractError):
        dataclasses.replace(p, approval_status="APPROVED", state_digest="")

"""§11 engine rows: R21–R49 and R51, plus C22 and C24.

The engine never raises on a governed input; it refuses. Each test asserts the
named code and, where the row says so, the resulting outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import matrix_fixtures as fx
from ugence_governance_contracts.api import AttestationStatus, VerificationStatus
from ugence_readiness_comparison import ENGINE_IDENTITY, compare
from ugence_reasoning_method_governance.api import (
    AUTHORITY_RESOLUTION_BASIS_V1,
    FitOutcome,
    RefusalCode as R,
    ResolvedAdmission,
    ResolvedAuthority,
    ResourceDimension,
    SufficiencyKind,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator

LC, TOT = fx.c2_ref("linear_chain"), fx.c2_ref("tree_of_thought")


def run(req):
    return compare(req, produced_at=fx.NOW)


def codes(res):
    return [r.code for r in res.refusals]


def outcome(res, method):
    return next(a.outcome for a in res.assessments if a.method == method)


def test_c22_two_method_request_assesses_without_refusal():
    res = run(fx.two_method_request())
    assert codes(res) == []
    assert outcome(res, LC) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert outcome(res, TOT) is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED
    assert len(res.evidence_status) == 2
    assert all(v.attestation_status is AttestationStatus.UNATTESTED and v.verification_status is VerificationStatus.UNVERIFIED for v in res.evidence_status)
    assert res.authority_resolution_basis == AUTHORITY_RESOLUTION_BASIS_V1
    assert res.engine_identity == ENGINE_IDENTITY
    assert all(a.usage_scope == "RESEARCH_ONLY" and a.assessor_identity == ENGINE_IDENTITY for a in res.assessments)
    tot = next(a for a in res.assessments if a.method == TOT)
    assert tot.quality_margin == "0.04"
    assert [(d.dimension, d.relative_to, d.delta) for d in tot.deltas_vs_baseline] == [(ResourceDimension.LLM_CALLS, LC, "3")]
    assert [(x.dominator, [d.delta for d in x.deltas], x.quality_delta) for x in tot.dominated_by] == [(LC, ["3"], None)]


def test_r21_unit_mismatch():
    q = (fx.c17_quality(LC, "0.92", unit="other.unit", claim_ref="claim.lc"), fx.c17_quality(TOT, "0.94", claim_ref="claim.tot"))
    res = run(fx.two_method_request(quality_results=q))
    assert R.UNIT_MISMATCH in codes(res)
    assert all(a.outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT for a in res.assessments)


def test_r22_eq_comparator_unsupported():
    tc = fx.c10_class(policy=fx.c8_policy(rule=fx.c6_rule(thr=fx.threshold(ComparisonOperator.EQ))))
    res = run(fx.two_method_request(task_class=tc))
    assert R.UNSUPPORTED_COMPARATOR in codes(res)


def test_r23_nan_quality_value():
    q = (fx.c17_quality(LC, "NaN", claim_ref="claim.lc"), fx.c17_quality(TOT, "0.94", claim_ref="claim.tot"))
    res = run(fx.two_method_request(quality_results=q))
    assert R.SCALE_UNSUPPORTED in codes(res)


def test_r24_two_quality_results_one_method_no_aggregation():
    q = (fx.c17_quality(LC, "0.92", claim_ref="claim.lc"), fx.c17_quality(LC, "0.93", claim_ref="claim.lc2"), fx.c17_quality(TOT, "0.94", claim_ref="claim.tot"))
    res = run(fx.two_method_request(quality_results=q))
    assert R.AGGREGATION_UNDECLARED in codes(res)


def test_r25_two_records_one_method_slice_1():
    tc = fx.c10_class()
    recs = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc"), fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot"), fx.c15_record(TOT, fx.c12_telemetry(5), tc, "rec.tot2"))
    res = run(fx.two_method_request(task_class=tc, records=recs))
    assert R.RESOURCE_AGGREGATION_UNDECLARED in codes(res)
    assert outcome(res, TOT) is FitOutcome.COMPARISON_EVIDENCE_ABSENT
    assert outcome(res, LC) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT, "per-method absence leaves the other candidate unaffected"


def test_r26_required_tokens_missing_no_fallback():
    tc = fx.c10_class(policy=fx.c8_policy(dims=(ResourceDimension.LLM_CALLS, ResourceDimension.TOTAL_TOKENS)))
    res = run(fx.two_method_request(task_class=tc, baseline_telemetry=fx.c13_telemetry_tokens(1, 100), candidate_telemetry=fx.c12_telemetry(4)))
    assert R.DIMENSION_UNAVAILABLE in codes(res)
    assert all(a.outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT for a in res.assessments)
    both = run(fx.two_method_request(task_class=tc, baseline_telemetry=fx.c13_telemetry_tokens(1, 100), candidate_telemetry=fx.c13_telemetry_tokens(4, 900)))
    assert codes(both) == [] and [d.dimension for d in next(a for a in both.assessments if a.method == TOT).deltas_vs_baseline] == [ResourceDimension.LLM_CALLS, ResourceDimension.TOTAL_TOKENS]


def test_r27_task_class_mismatch():
    tc, other = fx.c10_class(), fx.c10_class(task_class_id="class.other")
    recs = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc"), fx.c15_record(TOT, fx.c12_telemetry(4), other, "rec.tot"))
    res = run(fx.two_method_request(task_class=tc, records=recs))
    assert R.TASK_CLASS_MISMATCH in codes(res)


def test_r28_baseline_absent():
    tc = fx.c10_class()
    res = run(fx.two_method_request(task_class=tc, records=(fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot"),)))
    assert R.BASELINE_ABSENT in codes(res)
    assert all(a.outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT for a in res.assessments)


def test_r29_quality_claim_not_independent():
    req = fx.two_method_request()
    rec_tot = next(r for r in req.records if r.method == TOT)
    tainted = fx.claim("claim.tot", "0.94", input_refs=(f"{rec_tot.record_digest}#self_reported_quality",), calculated=True)
    res = run(fx.two_method_request(quality_claims=(fx.claim("claim.lc", "0.92"), tainted)))
    assert R.QUALITY_CLAIM_NOT_INDEPENDENT in codes(res)
    assert outcome(res, TOT) is FitOutcome.COMPARISON_EVIDENCE_ABSENT


def test_r30_r31_high_consequence_needs_matching_resolved_admission():
    hc = fx.c11_class_hc()
    res = run(fx.two_method_request(task_class=hc))
    assert R.THRESHOLD_ONLY_NOT_ADMITTED in codes(res)
    wrong = ResolvedAdmission("authority:evidence", "result:admit-1", fx.HEX_D)
    res2 = run(fx.two_method_request(task_class=hc, resolved_admissions=(wrong,), resolved_authorities=(ResolvedAuthority("authority:evidence", "res:1"),)))
    assert R.THRESHOLD_ONLY_NOT_ADMITTED in codes(res2)
    right = ResolvedAdmission("authority:evidence", "result:admit-1", fx.HEX_C)
    res3 = run(fx.two_method_request(task_class=hc, resolved_admissions=(right,), resolved_authorities=(ResolvedAuthority("authority:evidence", "res:1"),)))
    assert R.THRESHOLD_ONLY_NOT_ADMITTED not in codes(res3)
    unresolved = run(fx.two_method_request(task_class=hc, resolved_admissions=(right,)))
    assert R.THRESHOLD_ONLY_NOT_ADMITTED in codes(unresolved), "an admission whose authority is not resolved admits nothing"


def test_r32_two_records_in_one_lineage():
    tc = fx.c10_class()
    parent = fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot")
    child = fx.c15_record(TOT, fx.c12_telemetry(3), tc, "rec.tot.child", parent=parent.record_digest)
    recs = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc"), parent, child)
    res = run(fx.two_method_request(task_class=tc, records=recs))
    assert R.LINEAGE_UNRESOLVED in codes(res)


def _request_with_attestation(attester="cm-ta1", resolved=(), requester="requester:study", verifier=None):
    req = fx.two_method_request(requester_identity=requester)
    rec = next(r for r in req.records if r.method == TOT)
    att = fx.c19_attestation(rec, attester=attester)
    vers = (fx.c20_verification(rec, att, verifier=verifier),) if verifier else ()
    return fx.two_method_request(attestation_envelopes=(att,), verification_envelopes=vers, resolved_authorities=resolved, requester_identity=requester), rec, att


def test_r33_unresolved_attester_is_ignored():
    req, rec, att = _request_with_attestation()
    res = run(req)
    view = next(v for v in res.evidence_status if v.record_digest == rec.record_digest)
    assert view.attestation_status is AttestationStatus.UNATTESTED
    assert att.envelope_digest in res.ignored_envelopes
    assert codes(res) == []


def test_r34_resolved_attester_attests_named_fields_only():
    req, rec, att = _request_with_attestation(resolved=(ResolvedAuthority("cm-ta1", "res:cm"),))
    res = run(req)
    view = next(v for v in res.evidence_status if v.record_digest == rec.record_digest)
    assert view.attestation_status is AttestationStatus.ATTESTED
    assert view.attested_fields == ("telemetry.llm_calls",)
    assert view.verification_status is VerificationStatus.UNVERIFIED
    assert res.ignored_envelopes == ()


def test_r35_self_attestation_by_issuer():
    req, _, _ = _request_with_attestation(attester="adapter:study")
    assert R.SELF_ATTESTATION in codes(run(req))


def test_r48_self_attestation_by_requester():
    req, _, _ = _request_with_attestation(attester="requester:study")
    assert R.SELF_ATTESTATION in codes(run(req))


def test_r36_verification_without_attestation():
    req = fx.two_method_request()
    rec = next(r for r in req.records if r.method == TOT)
    ver = fx.c20_verification(rec, None)
    res = run(fx.two_method_request(verification_envelopes=(ver,)))
    assert R.VERIFICATION_WITHOUT_ATTESTATION in codes(res)


def test_r37_orphan_envelope():
    req = fx.two_method_request()
    rec = next(r for r in req.records if r.method == TOT)
    orphan = fx.c19_attestation(rec, record_digest=fx.HEX_B)
    assert R.ENVELOPE_ORPHAN in codes(run(fx.two_method_request(attestation_envelopes=(orphan,))))


def test_r38_r45_unsupported_schema_versions():
    assert R.UNSUPPORTED_SCHEMA_VERSION in codes(run(fx.two_method_request(schema_version="readiness_comparison.request.v0")))
    tc = fx.c10_class()
    recs = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc", schema_version="reasoning_method.execution_record.v0"), fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot"))
    res = run(fx.two_method_request(task_class=tc, records=recs))
    assert R.UNSUPPORTED_SCHEMA_VERSION in codes(res) and all(r.method is None for r in res.refusals)


def test_r39_equal_calls_are_not_domination():
    res = run(fx.two_method_request(baseline_calls=4, candidate_calls=4))
    assert outcome(res, LC) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert outcome(res, TOT) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert all(a.dominated_by == () for a in res.assessments)


def test_r40_improvement_valued_cheaper_but_worse_does_not_dominate():
    tc = fx.c10_class(policy=fx.c8_policy(rule=fx.c6_rule(kind=SufficiencyKind.IMPROVEMENT_VALUED)))
    res = run(fx.two_method_request(task_class=tc, baseline_calls=1, candidate_calls=4, baseline_quality="0.92", candidate_quality="0.94"))
    assert outcome(res, LC) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    assert outcome(res, TOT) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    equal = run(fx.two_method_request(task_class=tc, baseline_calls=1, candidate_calls=4, baseline_quality="0.94", candidate_quality="0.94"))
    tot = next(a for a in equal.assessments if a.method == TOT)
    assert tot.outcome is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED and tot.dominated_by[0].quality_delta == "0.00"


def test_r42_r43_per_method_absence():
    tc = fx.c10_class()
    only_lc = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc"),)
    res = run(fx.two_method_request(task_class=tc, records=only_lc))
    assert R.METHOD_RECORDS_ABSENT in codes(res) and outcome(res, TOT) is FitOutcome.COMPARISON_EVIDENCE_ABSENT and outcome(res, LC) is FitOutcome.SUFFICIENT_PARETO_EFFICIENT
    q = (fx.c17_quality(LC, "0.92", claim_ref="claim.lc"),)
    res2 = run(fx.two_method_request(quality_results=q))
    assert R.QUALITY_RESULT_ABSENT in codes(res2) and outcome(res2, TOT) is FitOutcome.COMPARISON_EVIDENCE_ABSENT


def test_r44_benchmark_threshold_unresolvable():
    from ugence_governance_contracts.api import BenchmarkReference
    from ugence_uvi_policy_contracts.api import GovernedThreshold

    thr = GovernedThreshold("thr.bench", fx.UNIT, ComparisonOperator.GTE, benchmark_ref=BenchmarkReference("bench.1", "1", fx.HEX_A))
    tc = fx.c10_class(policy=fx.c8_policy(rule=fx.c6_rule(thr=thr)))
    res = run(fx.two_method_request(task_class=tc))
    assert R.THRESHOLD_UNRESOLVABLE in codes(res) and all(a.outcome is FitOutcome.COMPARISON_EVIDENCE_ABSENT for a in res.assessments)


def test_r46_candidates_empty():
    res = run(fx.two_method_request(candidates=()))
    assert R.CANDIDATES_EMPTY in codes(res) and res.assessments == ()


def test_r47_and_c24_aggregated_result_needs_declared_policy_aggregation():
    agg = (fx.c17_quality(LC, "0.92", claim_ref="claim.lc"), fx.c18_quality_agg(TOT, "0.94", claim_ref="claim.tot"))
    claims = (fx.claim("claim.lc", "0.92"), fx.claim("claim.tot", "0.94", input_refs=("case:1", "case:2"), calculated=True))
    res = run(fx.two_method_request(quality_results=agg, quality_claims=claims))
    assert R.AGGREGATION_UNDECLARED in codes(res)
    tc = fx.c10_class(policy=fx.c24_policy_agg())
    ok = run(fx.two_method_request(task_class=tc, quality_results=agg, quality_claims=claims))
    assert codes(ok) == [] and outcome(ok, TOT) is FitOutcome.SUFFICIENT_RESOURCE_DOMINATED


def test_r49_self_verification():
    for verifier in ("adapter:study", "cm-ta1", "requester:study"):
        req, _, _ = _request_with_attestation(resolved=(ResolvedAuthority("cm-ta1", "res:cm"), ResolvedAuthority(verifier, "res:v")), verifier=verifier)
        assert R.SELF_VERIFICATION in codes(run(req)), verifier
    req, rec, _ = _request_with_attestation(resolved=(ResolvedAuthority("cm-ta1", "res:cm"), ResolvedAuthority("tev", "res:tev")), verifier="tev")
    res = run(req)
    view = next(v for v in res.evidence_status if v.record_digest == rec.record_digest)
    assert view.verification_status is VerificationStatus.VERIFIED and view.attestation_status is AttestationStatus.ATTESTED


def test_r51_output_ordering_makes_result_digest_input_order_independent():
    req = fx.two_method_request()
    a = run(req)
    reversed_req = fx.two_method_request(candidates=(TOT, LC), records=tuple(reversed(req.records)), quality_results=tuple(reversed(req.quality_results)))
    b = compare(reversed_req, produced_at=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert a.result_digest == b.result_digest
    assert [x.method for x in b.assessments] == [LC, TOT]


def test_engine_never_reads_self_reported_quality():
    tc = fx.c10_class()
    low = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc", self_quality="0.0"), fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot", self_quality="0.0"))
    high = (fx.c15_record(LC, fx.c12_telemetry(1), tc, "rec.lc", self_quality="1.0"), fx.c15_record(TOT, fx.c12_telemetry(4), tc, "rec.tot", self_quality="1.0"))
    ra, rb = run(fx.two_method_request(task_class=tc, records=low)), run(fx.two_method_request(task_class=tc, records=high))
    assert [(x.outcome, x.quality_margin, x.deltas_vs_baseline) for x in ra.assessments] == [(x.outcome, x.quality_margin, x.deltas_vs_baseline) for x in rb.assessments]


def test_engine_refuses_non_request_input():
    with pytest.raises(TypeError):
        compare("not a request")  # type: ignore[arg-type]

"""Slice 3 — comparison evidence, the admission record, the product gate, the bridge.

Every fit assessment here is a SYNTHETIC FIXTURE: it proves the mechanism, not that
any method is fit for any task. Real evidence comes from a comparison study.
"""

from __future__ import annotations

import dataclasses

import pytest

import matrix_fixtures as fx
import rule_fixtures as rf
from ugence_reasoning_method_advisor.api import (
    COMPARISON_ENGINE_IDENTITY,
    AdvisorError,
    AdvisorErrorCode as A,
    ComparisonEvidence,
    ReasoningMethodAdvisoryAdmission,
    admit,
    advise,
    to_proposer_input,
    validate_admission,
)
from ugence_reasoning_method_governance.api import (
    AUTHORITY_RESOLUTION_BASIS_V1,
    COMPARISON_RESULT_SCHEMA_VERSION,
    EVIDENCE_STATUS_SOURCE_V1,
    FIT_SCHEMA_VERSION,
    USAGE_SCOPE_RESEARCH_ONLY,
    ContractError,
    ContractErrorCode as C,
    FitOutcome,
    ReadinessComparisonResult,
    ReasoningMethodFitAssessment,
    ReasoningMethodRef,
    ResourceDimension,
)

ENGINE_VERSION = "0.1.0"

ONE = ("comparison_request",)                      # sole qualifier: map_reduce
TWO = ("comparison_request", "causal_reasoning")   # map_reduce and linear_chain


def assessment(method_id, request, *, outcome=FitOutcome.SUFFICIENT_PARETO_EFFICIENT, assessment_id="a.1", class_digest=None, catalog_ref=None, engine=COMPARISON_ENGINE_IDENTITY):
    cref = catalog_ref or request.catalog.ref()
    tc = request.task_class or rf.governed_class(ONE)
    return ReasoningMethodFitAssessment(
        FIT_SCHEMA_VERSION, assessment_id, tc.task_class_id, class_digest or tc.task_class_digest, fx.HEX_D, "",
        ReasoningMethodRef(cref, method_id, "1"), ReasoningMethodRef(cref, "linear_chain", "1"),
        outcome, None, None, (), (), (ResourceDimension.LLM_CALLS,), "pol.cmp", "1", "",
        (), EVIDENCE_STATUS_SOURCE_V1, USAGE_SCOPE_RESEARCH_ONLY, engine, ENGINE_VERSION, fx.NOW, "synthetic fixture",
    )


def result(*assessments, engine=COMPARISON_ENGINE_IDENTITY, schema=COMPARISON_RESULT_SCHEMA_VERSION):
    """A hand-built engine result: the SHAPE the engine emits, with synthetic content."""
    ordered = tuple(sorted(assessments, key=lambda a: a.method.sort_key))
    return ReadinessComparisonResult(schema, "cmp.synthetic", fx.HEX_A, ordered, (), (), (), AUTHORITY_RESOLUTION_BASIS_V1, engine, ENGINE_VERSION, fx.NOW)


def evidence(request, *assessments, class_digest=None, catalog_ref=None):
    tc = request.task_class or rf.governed_class(ONE)
    return ComparisonEvidence(class_digest or tc.task_class_digest, catalog_ref or request.catalog.ref(), tuple(assessments))


def world(tokens, *method_ids, governed=True, **kw):
    rq = rf.request(tokens, governed=governed)
    adv = advise(rq, advised_at=fx.NOW)
    res = result(*[assessment(m, rq, assessment_id=f"a.{i}", **kw) for i, m in enumerate(method_ids, 1)]) if method_ids else None
    return rq, adv, res


def refuses(code, thunk):
    with pytest.raises((AdvisorError, ContractError)) as info:
        thunk()
    assert info.value.code is code, info.value


# ------------------------------------------------------------------ the advisory is untouched

def test_the_slice_2_advisory_is_still_research_only_by_construction():
    _, adv, _ = world(ONE)
    assert adv.evidence_status == "COMPARISON_EVIDENCE_ABSENT" and adv.usage_scope == "RESEARCH_ONLY"
    assert not any(f.name in ("evidence_refs", "comparison_evidence", "admission_digest") for f in dataclasses.fields(adv))


# ------------------------------------------------------------------ admission

def test_sufficient_evidence_for_the_sole_qualifier_admits():
    rq, adv, res = world(ONE, "map_reduce")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    assert isinstance(adm, ReasoningMethodAdvisoryAdmission)
    assert adm.advisory_digest == adv.advisory_digest and adm.request_digest == adv.request_digest
    assert adm.primary is not None and adm.primary.method_id == "map_reduce"
    assert adm.evidence_status == "COMPARISON_EVIDENCE_PRESENT" and adm.usage_scope == "ADVISORY_INPUT"
    assert adm.evidence_refs == (res.assessments[0].assessment_digest,)
    assert adm.comparison_result_digest == res.result_digest
    assert len(adm.admission_digest) == 64
    validate_admission(adm, adv, res)


def test_evidence_for_every_qualifier_admits_and_cites_each_assessment():
    rq, adv, res = world(TWO, "map_reduce", "linear_chain")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    assert [m.method_id for m in adm.qualifying] == ["linear_chain", "map_reduce"] and adm.primary is None
    assert adm.evidence_refs == tuple(sorted(a.assessment_digest for a in res.assessments))


def test_resource_dominated_still_counts_as_sufficient():
    rq, adv, res = world(ONE, "map_reduce", outcome=FitOutcome.SUFFICIENT_RESOURCE_DOMINATED)
    assert admit(adv, rq, res, admitted_at=fx.NOW).evidence_refs


def test_admission_is_deterministic_and_time_sensitive():
    rq, adv, res = world(ONE, "map_reduce")
    a, b = admit(adv, rq, res, admitted_at=fx.NOW), admit(adv, rq, res, admitted_at=fx.NOW)
    later = admit(adv, rq, res, admitted_at=fx.NOW.replace(hour=13))
    assert a == b and a.admission_digest != later.admission_digest


# ------------------------------------------------------------------ refusals: the product gate

def test_the_fixture_without_evidence_cannot_be_admitted():
    rq, adv, _ = world(ONE)
    refuses(A.RESEARCH_ONLY_REFUSED_IN_PRODUCT, lambda: admit(adv, rq, result(assessment("tree_of_thought", rq)), admitted_at=fx.NOW))


def test_partial_coverage_is_refused_as_research_only():
    rq, adv, res = world(TWO, "map_reduce")
    refuses(A.RESEARCH_ONLY_REFUSED_IN_PRODUCT, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_evidence_absent_outcome_is_not_evidence():
    rq, adv, res = world(ONE, "map_reduce", outcome=FitOutcome.COMPARISON_EVIDENCE_ABSENT)
    refuses(A.RESEARCH_ONLY_REFUSED_IN_PRODUCT, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_nothing_qualifying_cannot_be_admitted():
    rq, adv, _ = world(())
    assert adv.qualifying == ()
    refuses(A.RESEARCH_ONLY_REFUSED_IN_PRODUCT, lambda: admit(adv, rq, result(assessment("map_reduce", rq)), admitted_at=fx.NOW))


def test_insufficient_quality_for_a_qualifier_contradicts_the_rule_set():
    rq, adv, res = world(ONE, "map_reduce", outcome=FitOutcome.INSUFFICIENT_QUALITY)
    refuses(A.COMPARISON_EVIDENCE_CONTRADICTED, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_contradiction_beats_partial_coverage():
    rq, adv, res = world(TWO, "map_reduce", outcome=FitOutcome.INSUFFICIENT_QUALITY)
    refuses(A.COMPARISON_EVIDENCE_CONTRADICTED, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_an_unclassified_advisory_is_never_admitted():
    rq, adv, _ = world(ONE, governed=False)
    res = result(assessment("map_reduce", rq))
    refuses(A.CLASSIFICATION_INCONSISTENT, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_evidence_for_another_task_class_is_unbound():
    rq, adv, _ = world(ONE)
    res = result(assessment("map_reduce", rq, class_digest=fx.HEX_C))
    refuses(A.COMPARISON_EVIDENCE_UNBOUND, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_evidence_over_another_catalog_is_unbound():
    rq, adv, _ = world(ONE)
    res = result(assessment("map_reduce", rq, catalog_ref=fx.c1_catalog_ref(fx.HEX_C)))
    refuses(A.COMPARISON_EVIDENCE_UNBOUND, lambda: admit(adv, rq, res, admitted_at=fx.NOW))


def test_an_assessment_for_another_class_inside_the_bundle_is_unbound():
    rq, _, _ = world(ONE)
    refuses(A.COMPARISON_EVIDENCE_UNBOUND, lambda: evidence(rq, assessment("map_reduce", rq, class_digest=fx.HEX_C)))


def test_an_assessment_presented_twice_is_unbound():
    rq, _, _ = world(ONE)
    refuses(A.COMPARISON_EVIDENCE_UNBOUND, lambda: evidence(rq, assessment("map_reduce", rq), assessment("map_reduce", rq)))


def test_an_advisory_cannot_be_admitted_against_a_request_it_did_not_answer():
    rq, adv, res = world(ONE, "map_reduce")
    other = rf.request(ONE, request_id="req.other")
    with pytest.raises((AdvisorError, ContractError)):
        admit(adv, other, res, admitted_at=fx.NOW)


# ------------------------------------------------------------------ provenance: the result, never a bundle

def test_a_hand_built_bundle_of_assessments_can_no_longer_admit():
    rq, adv, _ = world(ONE)
    bundle = evidence(rq, assessment("map_reduce", rq))
    with pytest.raises(TypeError):
        admit(adv, rq, bundle, admitted_at=fx.NOW)
    with pytest.raises(TypeError):
        admit(adv, rq, (assessment("map_reduce", rq),), admitted_at=fx.NOW)


def test_a_result_from_any_other_engine_is_unbound():
    rq, adv, _ = world(ONE)
    foreign = result(assessment("map_reduce", rq, engine="someone-else"), engine="someone-else")
    refuses(A.COMPARISON_EVIDENCE_UNBOUND, lambda: admit(adv, rq, foreign, admitted_at=fx.NOW))


def test_an_empty_result_admits_nothing():
    rq, adv, _ = world(ONE)
    refuses(A.RESEARCH_ONLY_REFUSED_IN_PRODUCT, lambda: admit(adv, rq, result(), admitted_at=fx.NOW))


def test_the_admission_cites_the_result_and_replay_binds_to_it():
    rq, adv, res = world(ONE, "map_reduce")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    assert adm.comparison_result_digest == res.result_digest
    other = result(assessment("map_reduce", rq, assessment_id="a.other"))
    assert other.result_digest != res.result_digest
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(adm, adv, other))
    swapped = _rebuild(adm, comparison_result_digest=fx.HEX_A)
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(swapped, adv, res))


# ------------------------------------------------------------------ the record's own invariants

def _rebuild(adm, **over):
    fields = {f: getattr(adm, f) for f in adm.__dataclass_fields__ if f != "admission_digest"}
    fields.update(over)
    return ReasoningMethodAdvisoryAdmission(**fields)


def test_an_admission_exists_only_in_the_admitted_state():
    rq, adv, res = world(ONE, "map_reduce")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    refuses(C.REF_BLANK_FIELD, lambda: _rebuild(adm, evidence_status="COMPARISON_EVIDENCE_ABSENT"))
    refuses(C.REF_BLANK_FIELD, lambda: _rebuild(adm, usage_scope="RESEARCH_ONLY"))
    refuses(C.REF_BLANK_FIELD, lambda: _rebuild(adm, evidence_refs=()))
    refuses(A.PRIMARY_WITHOUT_SOLE_QUALIFIER, lambda: _rebuild(adm, primary=None))


def test_replay_refuses_a_tampered_admission():
    rq, adv, res = world(TWO, "map_reduce", "linear_chain")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    narrowed = _rebuild(adm, qualifying=adm.qualifying[:1], primary=adm.qualifying[0])
    refuses(A.CLASSIFICATION_INCONSISTENT, lambda: validate_admission(narrowed, adv, res))
    foreign = _rebuild(adm, evidence_refs=(fx.HEX_A,))
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(foreign, adv, res))
    thinner = result(res.assessments[0])
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(adm, adv, thinner))


def test_no_scalar_label_field_on_either_slice_3_type():
    for cls in (ComparisonEvidence, ReasoningMethodAdvisoryAdmission):
        for f in dataclasses.fields(cls):
            assert "int" not in str(f.type) and "float" not in str(f.type) and "Decimal" not in str(f.type), f"{cls.__name__}.{f.name}"


# ------------------------------------------------------------------ the bridge

def test_the_bridge_refuses_a_research_only_advisory():
    _, adv, _ = world(ONE)
    refuses(A.RESEARCH_ONLY_REFUSED_IN_PRODUCT, lambda: to_proposer_input(adv))


def test_the_bridge_carries_references_and_no_authority_term():
    rq, adv, res = world(ONE, "map_reduce")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    mapping = to_proposer_input(adm)
    assert mapping["reasoning_advisory_digest"] == "sha256:" + adv.advisory_digest and mapping["admission_digest"] == "sha256:" + adm.admission_digest
    assert mapping["qualifying_method_ids"] == ["map_reduce"] and mapping["primary_method_id"] == "map_reduce"
    assert mapping["evidence_refs"] == ["sha256:" + d for d in adm.evidence_refs]
    assert mapping["evidence_status"] == "COMPARISON_EVIDENCE_PRESENT" and mapping["usage_scope"] == "ADVISORY_INPUT"
    flat = " ".join(str(v) for v in mapping.values())
    for term in ("CLEAR", "HOLD", "BLOCK", "AUTHORIZED", "DENIED", "PROPOSAL"):
        assert term not in flat


def test_the_bridge_mapping_validates_as_the_proposer_input():
    ap = pytest.importorskip("ugence_agentic_proposer")
    if not hasattr(ap, "ReasoningMethodAdvisoryInput"):
        pytest.skip("installed proposer predates the typed input")
    if "result_signature_receipt_digest" not in ap.ReasoningMethodAdvisoryInput.model_fields:
        pytest.skip("installed proposer predates the signature receipt field (0.6.0)")
    rq, adv, res = world(TWO, "map_reduce", "linear_chain")
    model = ap.ReasoningMethodAdvisoryInput.model_validate(to_proposer_input(admit(adv, rq, res, admitted_at=fx.NOW)))
    assert model.primary_method_id is None and sorted(model.qualifying_method_ids) == ["linear_chain", "map_reduce"]


# ------------------------------------------------------------------ SCR-1: the signed-result posture

from ugence_reasoning_method_advisor.api import ADMISSION_SCHEMA_VERSION, VerifiedResultSignature  # noqa: E402


def verified_for(res, *, signer=COMPARISON_ENGINE_IDENTITY, receipt=fx.HEX_B, result_digest=None):
    """The typed fact a composition root constructs after running the attestation
    package's verifier; this suite never runs one, and the advisor never imports it."""
    return VerifiedResultSignature(
        result_digest=result_digest or res.result_digest, signer_identity=signer, signer_key_id="engine-key-1",
        verification_receipt_digest=receipt, verifier_identity="ugence-reasoning-method-result-attestation",
        verified_at=fx.NOW,
    )


def test_the_admission_schema_is_v3_and_the_research_posture_cites_no_signature():
    rq, adv, res = world(ONE, "map_reduce")
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    assert ADMISSION_SCHEMA_VERSION == "reasoning_method.advisory_admission.v3" == adm.schema_version
    assert adm.result_signature_receipt_digest is None
    assert to_proposer_input(adm)["result_signature_receipt_digest"] is None
    validate_admission(adm, adv, res)


def test_requiring_a_signature_refuses_an_unsigned_result():
    rq, adv, res = world(ONE, "map_reduce")
    refuses(A.COMPARISON_RESULT_UNSIGNED, lambda: admit(adv, rq, res, admitted_at=fx.NOW, require_signature=True))
    adm = admit(adv, rq, res, admitted_at=fx.NOW)
    refuses(A.COMPARISON_RESULT_UNSIGNED, lambda: validate_admission(adm, adv, res, require_signature=True))


def test_a_verified_signature_for_this_result_admits_and_is_cited():
    rq, adv, res = world(ONE, "map_reduce")
    v = verified_for(res)
    adm = admit(adv, rq, res, admitted_at=fx.NOW, verified=v, require_signature=True)
    assert adm.result_signature_receipt_digest == fx.HEX_B
    assert adm.comparison_result_digest == res.result_digest == v.result_digest
    unsigned = admit(adv, rq, res, admitted_at=fx.NOW)
    assert adm.admission_digest != unsigned.admission_digest
    validate_admission(adm, adv, res, verified=v, require_signature=True)
    mapping = to_proposer_input(adm)
    assert mapping["result_signature_receipt_digest"] == "sha256:" + fx.HEX_B


def test_a_signature_over_another_result_is_a_mismatch():
    rq, adv, res = world(ONE, "map_reduce")
    other = result(assessment("map_reduce", rq, assessment_id="a.other"))
    refuses(A.COMPARISON_RESULT_SIGNATURE_MISMATCH,
            lambda: admit(adv, rq, res, admitted_at=fx.NOW, verified=verified_for(other), require_signature=True))
    # Checked whenever a record is handed in, required or not.
    refuses(A.COMPARISON_RESULT_SIGNATURE_MISMATCH, lambda: admit(adv, rq, res, admitted_at=fx.NOW, verified=verified_for(other)))


def test_a_signature_by_any_other_signer_is_unbound():
    rq, adv, res = world(ONE, "map_reduce")
    refuses(A.COMPARISON_EVIDENCE_UNBOUND,
            lambda: admit(adv, rq, res, admitted_at=fx.NOW, verified=verified_for(res, signer="someone-else"), require_signature=True))


def test_a_signature_record_that_is_not_the_typed_fact_is_a_type_error():
    rq, adv, res = world(ONE, "map_reduce")
    with pytest.raises(TypeError):
        admit(adv, rq, res, admitted_at=fx.NOW, verified={"result_digest": res.result_digest})
    with pytest.raises(TypeError):
        admit(adv, rq, res, admitted_at=fx.NOW, require_signature="yes")


def test_the_typed_fact_is_shape_checked():
    rq, adv, res = world(ONE, "map_reduce")
    refuses(C.DIGEST_MALFORMED, lambda: verified_for(res, receipt="sha256:" + fx.HEX_B))
    refuses(C.DIGEST_MALFORMED, lambda: verified_for(res, result_digest="short"))
    refuses(C.REF_BLANK_FIELD, lambda: verified_for(res, signer=" "))
    refuses(C.DATETIME_NAIVE, lambda: VerifiedResultSignature(res.result_digest, COMPARISON_ENGINE_IDENTITY, "k", fx.HEX_B, "v", fx.NOW.replace(tzinfo=None)))


def test_replay_binds_the_cited_signature_record():
    rq, adv, res = world(ONE, "map_reduce")
    v = verified_for(res)
    adm = admit(adv, rq, res, admitted_at=fx.NOW, verified=v, require_signature=True)
    # Replayed without the record: the admission cites one the replay was not handed.
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(adm, adv, res))
    # Replayed with a different record: the citation does not match.
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(adm, adv, res, verified=verified_for(res, receipt=fx.HEX_C)))
    # A tampered citation on the admission.
    forged = _rebuild(adm, result_signature_receipt_digest=fx.HEX_C)
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(forged, adv, res, verified=v))
    refuses(C.DIGEST_MALFORMED, lambda: _rebuild(adm, result_signature_receipt_digest="not-a-digest"))
    # An unsigned admission replayed with a record it never cited.
    unsigned = admit(adv, rq, res, admitted_at=fx.NOW)
    refuses(C.DIGEST_MALFORMED, lambda: validate_admission(unsigned, adv, res, verified=v))


def test_the_typed_fact_carries_no_scalar_label():
    for f in dataclasses.fields(VerifiedResultSignature):
        assert "int" not in str(f.type) and "float" not in str(f.type) and "Decimal" not in str(f.type), f.name


def test_the_bridge_mapping_with_a_signature_validates_as_the_proposer_input():
    ap = pytest.importorskip("ugence_agentic_proposer")
    if "result_signature_receipt_digest" not in ap.ReasoningMethodAdvisoryInput.model_fields:
        pytest.skip("installed proposer predates the signature receipt field")
    rq, adv, res = world(ONE, "map_reduce")
    adm = admit(adv, rq, res, admitted_at=fx.NOW, verified=verified_for(res), require_signature=True)
    model = ap.ReasoningMethodAdvisoryInput.model_validate(to_proposer_input(adm))
    assert model.result_signature_receipt_digest == "sha256:" + fx.HEX_B

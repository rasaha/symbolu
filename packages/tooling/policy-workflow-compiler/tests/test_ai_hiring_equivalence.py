"""AI Hiring reference-equivalence tests (decision D3, the second domain).

Skipped when ugence-ai-hiring is not installed (the 'ai-hiring-reference' extra),
exactly as the Procurement harness is. The D3 gate requires EQUIVALENT.
"""

from __future__ import annotations

import pytest

ai_hiring = pytest.importorskip("ugence_ai_hiring")

import ugence_policy_workflow_compiler.api as api  # noqa: E402
from ugence_policy_workflow_compiler.approval.records import (  # noqa: E402
    build_approval_record,
)
from ugence_policy_workflow_compiler.reference.ai_hiring import (  # noqa: E402
    GATE_FACT_KEYS,
    MIN_CONFIDENCE_PERCENT_FOR_ADVANCE,
    MIN_SCORE_FOR_ADVANCE,
    PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE,
    PRODUCT_MIN_SCORE_FOR_ADVANCE,
    build_ai_hiring_policy_pack,
)
from ugence_policy_workflow_compiler.reference.ai_hiring_equivalence import (  # noqa: E402
    ADVISORY_SCENARIOS,
    EQUIVALENT,
    GATE_SCENARIOS,
    _pack_disposition,
    _pack_eligibility,
    _reference_disposition,
    _reference_eligibility,
    run_equivalence,
)

PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"


# -- the D3 gate ---------------------------------------------------------------


def test_the_equivalence_gate_is_achieved():
    result = run_equivalence()
    assert result.classification == EQUIVALENT, result.to_dict()
    assert result.equivalent


def test_every_dimension_is_equivalent_and_checks_something():
    result = run_equivalence()
    assert len(result.dimensions) == 5
    for dimension in result.dimensions:
        assert dimension.classification == EQUIVALENT, dimension
        assert dimension.checked > 0, dimension
        assert dimension.mismatches == ()


def test_the_dimensions_suit_this_domain_not_procurement():
    # D3 chose AI Hiring because its shape differs; copying Procurement's
    # authorization dimensions would test the harness rather than the domain.
    names = {d.dimension for d in run_equivalence().dimensions}
    assert names == {
        "eligibility_derivation",
        "advisory_disposition",
        "advisory_binding_separation",
        "compatibility_not_eligibility",
        "deterministic_threshold_translation",
    }


# -- the behaviours themselves -------------------------------------------------


def test_eligibility_is_non_compensatory_and_fail_closed():
    for scenario in GATE_SCENARIOS:
        pack_answer = _pack_eligibility(build_ai_hiring_policy_pack(), scenario)
        assert pack_answer == _reference_eligibility(scenario), scenario.name
    # The orderings that matter, stated directly.
    by_name = {s.name: s for s in GATE_SCENARIOS}
    pack = build_ai_hiring_policy_pack()
    assert _pack_eligibility(pack, by_name["all_pass"]) == "ELIGIBLE"
    assert _pack_eligibility(pack, by_name["one_fail"]) == "NOT_ELIGIBLE"
    assert _pack_eligibility(pack, by_name["one_indeterminate"]) == "ELIGIBILITY_PENDING"
    # A FAIL outranks an INDETERMINATE; both block.
    assert _pack_eligibility(pack, by_name["fail_precedes_indeterminate"]) == "NOT_ELIGIBLE"


def test_advisory_floors_agree_at_and_below_the_boundary():
    pack = build_ai_hiring_policy_pack()
    for scenario in ADVISORY_SCENARIOS:
        assert _pack_disposition(pack, scenario) == _reference_disposition(scenario), (
            scenario.name
        )


def test_insufficient_evidence_holds_rather_than_declines():
    pack = build_ai_hiring_policy_pack()
    scenario = next(s for s in ADVISORY_SCENARIOS if s.insufficient)
    assert _pack_disposition(pack, scenario) == "HOLD"
    assert _reference_disposition(scenario) == "HOLD"


def test_a_binding_decision_is_reserved_for_a_human():
    authority = build_ai_hiring_policy_pack().authority_requirements[0]
    assert authority.authority_type.value == "HUMAN_APPROVER"
    assert authority.allow_non_human is False


def test_no_eligibility_object_reads_a_score():
    # Compatibility never becomes eligibility.
    for condition in build_ai_hiring_policy_pack().prohibited_conditions:
        for predicate in condition.conditions:
            assert predicate.fact_key in GATE_FACT_KEYS


def test_the_float_floors_translate_exactly():
    assert MIN_SCORE_FOR_ADVANCE == PRODUCT_MIN_SCORE_FOR_ADVANCE
    assert MIN_CONFIDENCE_PERCENT_FOR_ADVANCE == round(
        PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE * 100
    )


# -- the pack is a real pack ---------------------------------------------------


def test_the_reference_pack_validates_and_compiles():
    pack = build_ai_hiring_policy_pack()
    assert api.validate_policy_pack(pack).ok
    approval = build_approval_record(
        approval_id="approval-ai-hiring",
        pack=pack,
        reviewer_id="reviewer-1",
        reviewer_role="hiring_manager",
        is_fixture=True,
    )
    result = api.compile_policy_pack(pack, approval)
    assert result.success, [d.message for d in result.validation_report.diagnostics]


def test_a_second_domain_moves_no_procurement_digest():
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )
    from ugence_policy_workflow_compiler.semantics import compile_workflow_v2

    pack = build_procurement_policy_pack()
    approval = build_procurement_approval_fixture(pack)
    assert api.compile_policy_pack(pack, approval).logical_digest == PINNED_V1_RELEASE_DIGEST
    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_maturity_reports_the_second_domain():
    info = api.version_info().to_dict()
    assert info["procurement_reference_equivalence_verified"] is True
    assert info["ai_hiring_reference_equivalence_verified"] is True
    # The gate D3 blocks remains unearned until the rest of its evidence exists.
    assert info["pilot_validated"] is False

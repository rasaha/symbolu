"""Assurance-generation tests: coverage, categories, determinism."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import GovernedWorkflowCompiler, TestCategory
from ugence_policy_workflow_compiler.compiler.assurance_generation import AssuranceGenerator


def test_every_required_object_covered(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    assert manifest.coverage_matrix.complete
    assert not manifest.coverage_matrix.uncovered_object_ids


def test_legitimate_counterexample_generates_must_allow(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    ce_tests = [s for s in manifest.scenarios if s.category is TestCategory.LEGITIMATE_COUNTEREXAMPLE]
    assert ce_tests
    assert all(t.expected_outcome.terminal_state == "ADVANCE_AUTHORIZED" for t in ce_tests)


def test_missing_evidence_generates_fail_closed(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    me = [s for s in manifest.scenarios if s.category is TestCategory.MISSING_EVIDENCE]
    assert me
    assert all(t.expected_outcome.terminal_state in ("BLOCKED", "ESCALATED") for t in me)


def test_override_valid_and_invalid(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    cats = {s.category for s in manifest.scenarios}
    assert TestCategory.OVERRIDE_VALID in cats
    assert TestCategory.OVERRIDE_INVALID in cats


def test_authority_conflict_and_sod(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    cats = {s.category for s in manifest.scenarios}
    assert TestCategory.AUTHORITY_CONFLICT in cats
    assert TestCategory.SEGREGATION_OF_DUTIES in cats


def test_replay_case_present(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    assert manifest.replay_cases


def test_exception_and_action_and_indeterminate(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    cats = {s.category for s in manifest.scenarios}
    for c in (TestCategory.EXCEPTION, TestCategory.ACTION_CONSTRAINT,
              TestCategory.INDETERMINATE, TestCategory.TIMEOUT, TestCategory.UNKNOWN_STATE):
        assert c in cats


def test_assurance_is_deterministic(synthetic_pack):
    a = AssuranceGenerator().generate(synthetic_pack)
    b = AssuranceGenerator().generate(synthetic_pack)
    assert [s.object_id for s in a.scenarios] == [s.object_id for s in b.scenarios]


def test_every_test_has_expected_outcome(synthetic_pack):
    manifest = AssuranceGenerator().generate(synthetic_pack)
    for s in manifest.scenarios:
        assert s.expected_outcome.terminal_state
    for r in manifest.replay_cases:
        assert r.expected_outcome.terminal_state


def test_incomplete_coverage_fails_compilation():
    """A pack whose only decision rule cannot be covered fails Stage 4."""
    # Build a pack with an object type that requires coverage but craft the
    # generator to leave it uncovered by disabling the rule's link. Simplest: a
    # decision rule with a distinct id and no test referencing it can't happen via
    # the generator (positive test always covers rules), so instead assert the
    # coverage checker flags a synthetic uncovered id.
    from ugence_policy_workflow_compiler.models.assurance import AssuranceManifest, CoverageMatrix
    from ugence_policy_workflow_compiler.validation.coverage import check_coverage
    from ugence_policy_workflow_compiler.api import PolicyPack, ProhibitedCondition, Predicate, Comparator

    cond = ProhibitedCondition(
        object_id="proh.x", name="x", provenance_refs=("s",),
        conditions=(Predicate(fact_key="b", comparator=Comparator.IS_TRUE),),
    )
    pack = PolicyPack(pack_id="p", name="n", prohibited_conditions=(cond,))
    empty = AssuranceManifest(
        policy_pack_id="p", policy_pack_version=1,
        coverage_matrix=CoverageMatrix(uncovered_object_ids=("proh.x",)),
    )
    diags = check_coverage(pack, empty)
    assert any(d.code == "INCOMPLETE_COVERAGE" for d in diags)

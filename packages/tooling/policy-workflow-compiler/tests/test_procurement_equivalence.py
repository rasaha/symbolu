"""Procurement reference-equivalence tests.

Skipped when ugence-procurement is not installed (the 'procurement-reference'
extra). The Phase 1 success gate requires EQUIVALENT for the frozen matrix.
"""

from __future__ import annotations

import pytest

procurement = pytest.importorskip("ugence_procurement")

from ugence_policy_workflow_compiler.reference.procurement_equivalence import (  # noqa: E402
    EQUIVALENT,
    FROZEN_SCENARIOS,
    REJECTION_SCENARIOS,
    run_equivalence,
    _pack_authorize,
    _reference_authorize,
    _pack_assessment_blocked,
    _reference_assessment_blocked,
    _pack_rejects,
    _reference_rejects,
)
from ugence_policy_workflow_compiler.reference.procurement import (  # noqa: E402
    build_procurement_policy_pack,
)


def test_overall_equivalent():
    result = run_equivalence()
    assert result.classification == EQUIVALENT, result.to_dict()


def test_every_dimension_equivalent():
    result = run_equivalence()
    for d in result.dimensions:
        assert d.classification == EQUIVALENT, (d.dimension, d.mismatches)


@pytest.mark.parametrize("scenario", FROZEN_SCENARIOS, ids=lambda s: s.name)
def test_authorization_matches_reference(scenario):
    pack = build_procurement_policy_pack()
    assert _pack_authorize(pack, scenario) == _reference_authorize(scenario)


@pytest.mark.parametrize("scenario", FROZEN_SCENARIOS, ids=lambda s: s.name)
def test_assessment_blocking_matches(scenario):
    pack = build_procurement_policy_pack()
    assert _pack_assessment_blocked(pack, scenario) == _reference_assessment_blocked(scenario)


@pytest.mark.parametrize("rs", REJECTION_SCENARIOS, ids=lambda s: s.name)
def test_fail_closed_matches(rs):
    pack = build_procurement_policy_pack()
    assert _pack_rejects(pack, rs) == _reference_rejects(rs)


def test_hard_limit_denies_but_boundary_allowed():
    from ugence_policy_workflow_compiler.reference.procurement_equivalence import Scenario, HARD_LIMIT

    pack = build_procurement_policy_pack()
    over = Scenario("over", "s", "b", HARD_LIMIT + 1)
    at = Scenario("at", "s", "b", HARD_LIMIT)
    assert _pack_authorize(pack, over) == "DENIED" == _reference_authorize(over)
    assert _pack_authorize(pack, at) != "DENIED"
    assert _reference_authorize(at) != "DENIED"


def test_threshold_requires_constraints():
    from ugence_policy_workflow_compiler.reference.procurement_equivalence import Scenario

    pack = build_procurement_policy_pack()
    elevated = Scenario("elevated", "s", "b", 2_000_000)
    assert _pack_authorize(pack, elevated) == "AUTHORIZED_WITH_CONSTRAINTS"
    assert _reference_authorize(elevated) == "AUTHORIZED_WITH_CONSTRAINTS"


def test_supplier_rejection_requires_compensation_not_success():
    from ugence_procurement.suppliers.outcomes import SUPPLIER_TO_BUSINESS, SupplierOutcome

    assert SUPPLIER_TO_BUSINESS[SupplierOutcome.REJECTED].value == "REJECTED"
    assert SUPPLIER_TO_BUSINESS[SupplierOutcome.REJECTED].value != "SUCCEEDED"

"""Assurance-coverage validation.

The coverage invariant: every decision rule, prohibited condition, exception,
override, authority requirement, action constraint, and legitimate counterexample
must be referenced by at least one generated test. A pack whose compilation would
leave any of these untested fails Stage 4 — silent under-coverage is a defect.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..models.assurance import AssuranceManifest, CoverageMatrix
from ..models.common import ObjectType
from ..models.policy_pack import PolicyPack
from .errors import Severity, ValidationDiagnostic

#: Object types that must receive at least one generated test.
COVERAGE_REQUIRED_TYPES: Tuple[ObjectType, ...] = (
    ObjectType.DECISION_RULE,
    ObjectType.PROHIBITED_CONDITION,
    ObjectType.EXCEPTION_RULE,
    ObjectType.OVERRIDE_RULE,
    ObjectType.AUTHORITY_REQUIREMENT,
    ObjectType.ACTION_CONSTRAINT,
    ObjectType.LEGITIMATE_COUNTEREXAMPLE,
)


def required_coverage_ids(pack: PolicyPack) -> Tuple[str, ...]:
    ids = [
        obj.object_id
        for obj in pack.all_objects()
        if obj.object_type in COVERAGE_REQUIRED_TYPES and obj.enabled
    ]
    return tuple(sorted(ids))


def build_coverage_matrix(pack: PolicyPack, manifest: AssuranceManifest) -> CoverageMatrix:
    """Compute object -> covering test ids and the uncovered set."""
    coverage: Dict[str, List[str]] = {}
    for scenario in manifest.scenarios:
        for oid in scenario.source_object_ids:
            coverage.setdefault(oid, []).append(scenario.object_id)
    for replay in manifest.replay_cases:
        for oid in replay.source_object_ids:
            coverage.setdefault(oid, []).append(replay.object_id)

    required = required_coverage_ids(pack)
    uncovered = tuple(oid for oid in required if oid not in coverage)
    categories = tuple(sorted({s.category.value for s in manifest.scenarios}))
    frozen_coverage = {oid: tuple(sorted(tests)) for oid, tests in sorted(coverage.items())}
    return CoverageMatrix(
        coverage=frozen_coverage,
        uncovered_object_ids=uncovered,
        categories_present=categories,
    )


def check_coverage(pack: PolicyPack, manifest: AssuranceManifest) -> List[ValidationDiagnostic]:
    matrix = manifest.coverage_matrix
    out: List[ValidationDiagnostic] = []
    for oid in matrix.uncovered_object_ids:
        out.append(
            ValidationDiagnostic(
                code="INCOMPLETE_COVERAGE",
                severity=Severity.ERROR,
                object_id=oid,
                message=f"object '{oid}' requires assurance coverage but received none",
                suggested_remediation="add or generate a test that references this object",
            )
        )
    return out

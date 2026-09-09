"""RA-01 regression: catalog presence never creates a requirement (§6).

The GV-3R-b audit ruled out an "all three indicator families must be present"
heuristic. M-3R.3 introduces exactly the artifact that would make such a
heuristic tempting again — three named catalogs — so this module exists to prove
it did **not** come back through the side door.

The rule under test, stated once:

    Readiness requirements come from the resolved ``ReadinessPolicy``'s gates.
    Binding an Intelligence, Capability or Adoption catalog creates **no**
    requirement for that family, for any other family, or for indicators at all.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_agent_value_readiness as R
from ugence_agent_value_readiness.api import (
    GateStatus,
    ReadinessAssessmentStatus,
    ReadinessClassification,
    ReadinessIndicatorCatalogSet,
    ReadinessTrustGapCode,
    assess_readiness,
)

from _orchestration_fixtures import (  # noqa: E402
    BOTH,
    MANDATORY,
    StubConditionVerifier,
    StubGateVerifier,
    binding,
    catalogs,
    context,
    gate,
    gate_result,
    indicators,
    issued_resolver,
    readiness_policy,
    request,
)

_G = ReadinessTrustGapCode
PKG_ROOT = pathlib.Path(R.__file__).resolve().parent


def _wired(req, policy):
    return assess_readiness(
        req,
        policy_resolver=issued_resolver(policy),
        gate_verifier=StubGateVerifier(),
        condition_verifier=StubConditionVerifier(),
    )


def _gate_complete_policy():
    return readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))


def _passing_gates(policy):
    return (gate_result(policy, "g1", GateStatus.PASS),)


# --------------------------------------------------------------------------- #
# Zero indicators still evaluates
# --------------------------------------------------------------------------- #
def test_zero_indicators_with_a_gate_complete_policy_is_still_deployment_ready():
    policy = _gate_complete_policy()
    req = request(policy=policy, gate_results=_passing_gates(policy), with_indicators=False)
    outcome = _wired(req, policy)

    assert outcome.status is ReadinessAssessmentStatus.EVALUATED
    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.indicator_admissions == ()


def test_zero_indicators_with_all_three_catalogs_bound_is_still_deployment_ready():
    """Binding every catalog does not conjure a requirement for any of them."""

    policy = _gate_complete_policy()
    req = request(
        policy=policy,
        gate_results=_passing_gates(policy),
        with_indicators=False,
        indicator_catalogs=catalogs(),
    )
    outcome = _wired(req, policy)

    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.trace.catalog_families_bound == (
        "INTELLIGENCE",
        "CAPABILITY",
        "ADOPTION",
    )
    assert outcome.trace.excluded_indicator_result_ids == ()
    # No "family missing" gap exists, because no such concept exists.
    assert not any("FAMILY_REQUIRED" in c for c in outcome.trust_gap_codes)
    assert not any("MISSING_INDICATOR" in c for c in outcome.trust_gap_codes)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"intelligence": True, "capability": False, "adoption": False},
        {"intelligence": False, "capability": True, "adoption": False},
        {"intelligence": False, "capability": False, "adoption": True},
        {"intelligence": True, "capability": True, "adoption": False},
    ],
)
def test_a_sparse_catalog_set_requires_nothing_of_the_absent_families(kwargs):
    policy = _gate_complete_policy()
    req = request(
        policy=policy,
        gate_results=_passing_gates(policy),
        with_indicators=False,
        indicator_catalogs=catalogs(**kwargs),
    )
    outcome = _wired(req, policy)
    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY


def test_binding_one_family_does_not_require_a_result_from_that_family():
    """A bound Intelligence catalog with no Intelligence result is fine."""

    policy = _gate_complete_policy()
    req = request(
        policy=policy,
        gate_results=_passing_gates(policy),
        with_indicators=False,
        indicator_catalogs=catalogs(capability=False, adoption=False),
    )
    outcome = _wired(req, policy)

    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.trace.catalog_families_bound == ("INTELLIGENCE",)


def test_a_policy_with_no_intelligence_gate_requires_no_intelligence_result():
    """The exact RA-01 wording, executed."""

    policy = _gate_complete_policy()
    assert all("intelligence" not in g.gate_id.lower() for g in policy.gates)

    req = request(
        policy=policy,
        gate_results=_passing_gates(policy),
        with_indicators=False,
        indicator_catalogs=catalogs(),
    )
    assert _wired(req, policy).classification is ReadinessClassification.DEPLOYMENT_READY


# --------------------------------------------------------------------------- #
# A catalog cannot unlock, and cannot block
# --------------------------------------------------------------------------- #
def test_a_catalog_cannot_unlock_a_tier():
    """Catalogs and indicators cannot rescue a missing required gate result."""

    policy = _gate_complete_policy()
    without = request(policy=policy, gate_results=(), with_indicators=False)
    with_everything = request(policy=policy, gate_results=(), with_indicators=True)

    assert _wired(without, policy).classification is ReadinessClassification.NOT_ASSESSABLE
    assert (
        _wired(with_everything, policy).classification is ReadinessClassification.NOT_ASSESSABLE
    )


def test_a_favourable_indicator_cannot_override_gate_precedence():
    policy = _gate_complete_policy()
    failing = request(
        policy=policy,
        gate_results=(gate_result(policy, "g1", GateStatus.FAIL),),
        with_indicators=True,
    )
    outcome = _wired(failing, policy)

    assert outcome.classification is ReadinessClassification.NOT_READY
    assert outcome.trace.admitted_indicator_result_ids == ("ar1", "cr1", "ir1")


def test_an_excluded_indicator_does_not_degrade_a_gate_complete_assessment():
    """Exclusion is subtraction, never a penalty."""

    policy = _gate_complete_policy()
    ctx = context(policy)
    bind = binding(ctx=ctx)
    intel, _c, _a = indicators(context_id=ctx.context_id, system_binding=bind)

    base = request(
        policy=policy,
        ctx=ctx,
        gate_results=_passing_gates(policy),
        system_binding=bind,
        indicator_catalogs=ReadinessIndicatorCatalogSet(),
    )
    with_excluded = type(base)(
        **{
            **{f: getattr(base, f) for f in base.__dataclass_fields__},
            "intelligence_results": intel,
        }
    )
    outcome = _wired(with_excluded, policy)

    assert _G.INDICATOR_CATALOG_MISSING.value in outcome.trust_gap_codes
    # Excluded — and the headline is exactly what it was without the record.
    assert outcome.classification is ReadinessClassification.DEPLOYMENT_READY
    assert outcome.evaluation.determination.intelligence_results == ()
    assert (
        outcome.evaluation.classification
        is _wired(
            request(policy=policy, ctx=ctx, gate_results=_passing_gates(policy), system_binding=bind),
            policy,
        ).evaluation.classification
    )


# --------------------------------------------------------------------------- #
# Structural: the heuristic does not exist in the source
# --------------------------------------------------------------------------- #
def test_no_module_counts_indicator_families_to_decide_anything():
    """A structural guard, so a future edit fails here rather than in production.

    Nothing may branch on how many of the three families are present. The only
    permitted family logic is per-family lookup and per-result admission.
    """

    banned_patterns = ("len(self.families_present)", "len(catalogs.catalogs)")
    for path in (p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts):
        text = path.read_text()
        for pattern in banned_patterns:
            assert pattern not in text, (path.name, pattern)


def test_no_comparison_against_three_families_exists_in_the_orchestrator():
    """No ``== 3`` / ``>= 3`` family-count comparison anywhere in the package."""

    offenders = []
    for path in (p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and comparator.value == 3:
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, offenders


def test_the_evaluator_source_never_mentions_a_catalog():
    """M-3R.3 wires catalogs into orchestration only — the evaluator is untouched."""

    for name in ("evaluator.py", "case.py", "codes.py", "trace.py", "errors.py"):
        text = (PKG_ROOT / "evaluation" / name).read_text().lower()
        assert "catalog" not in text, name
        assert "assessedsystembinding" not in text.replace("_", ""), name

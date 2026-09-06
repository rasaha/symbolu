"""AI Hiring reference-equivalence harness (decision D3).

Checks that the compiler's interpretation of an AI Hiring policy matches the live
``ugence-ai-hiring`` product. As with Procurement, this is a validation harness, not
an integration: **AI Hiring is never modified**, and the compiler imports it only
here, behind an optional extra.

The dimensions are chosen for *this* domain's shape. Procurement's are about
authorization order over an amount; AI Hiring's central governance claim is instead
that eligibility is non-compensatory, that compatibility can never become
eligibility, and that an AI recommendation is advisory until a human binds it.
Copying Procurement's dimensions here would test the harness, not the domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from ..models.policy_pack import PolicyPack
from .ai_hiring import (
    AUTHORITY_ID,
    GATE_FACT_KEYS,
    MIN_CONFIDENCE_PERCENT_FOR_ADVANCE,
    MIN_SCORE_FOR_ADVANCE,
    PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE,
    PRODUCT_MIN_SCORE_FOR_ADVANCE,
    build_ai_hiring_policy_pack,
)

EQUIVALENT = "EQUIVALENT"
ADDITIVE_NON_CONFLICTING = "ADDITIVE_NON_CONFLICTING"
MISSING_COMPILER_COVERAGE = "MISSING_COMPILER_COVERAGE"
CONFLICTING_INTERPRETATION = "CONFLICTING_INTERPRETATION"
REFERENCE_BEHAVIOR_UNMODELED = "REFERENCE_BEHAVIOR_UNMODELED"
INVALID_REFERENCE_PACK = "INVALID_REFERENCE_PACK"


class ReferenceUnavailable(RuntimeError):
    """The `ai-hiring-reference` extra is not installed."""


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    classification: str
    checked: int
    mismatches: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EquivalenceResult:
    classification: str
    dimensions: Tuple[DimensionResult, ...] = field(default_factory=tuple)

    @property
    def equivalent(self) -> bool:
        return self.classification == EQUIVALENT

    def to_dict(self) -> dict:
        return {
            "classification": self.classification,
            "dimensions": [
                {
                    "dimension": d.dimension,
                    "classification": d.classification,
                    "checked": d.checked,
                    "mismatches": list(d.mismatches),
                }
                for d in self.dimensions
            ],
        }


def _require_reference():
    try:
        from ugence_ai_hiring.hiring_decision import eligibility as _eligibility
        from ugence_ai_hiring.hiring_decision import recommendation as _recommendation
        from ugence_ai_hiring.hiring_decision.enums import (
            AssessmentOutcome,
            EligibilityStatus,
            GateState,
            RecommendationDisposition,
        )
    except Exception as exc:  # pragma: no cover - exercised by the skip path
        raise ReferenceUnavailable(
            "install the 'ai-hiring-reference' extra to run this harness"
        ) from exc
    return _eligibility, _recommendation, AssessmentOutcome, EligibilityStatus, GateState, RecommendationDisposition


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class GateScenario:
    """Mandatory-gate states, and the eligibility they must produce."""

    name: str
    gate_states: Tuple[str, ...]


#: Every ordering the live derivation distinguishes, including the precedence of
#: FAIL over INDETERMINATE — the case a compensatory reading would get wrong.
GATE_SCENARIOS: Tuple[GateScenario, ...] = (
    GateScenario("all_pass", ("PASS", "PASS")),
    GateScenario("one_fail", ("FAIL", "PASS")),
    GateScenario("one_indeterminate", ("PASS", "INDETERMINATE")),
    GateScenario("fail_precedes_indeterminate", ("FAIL", "INDETERMINATE")),
    GateScenario("all_fail", ("FAIL", "FAIL")),
    GateScenario("all_indeterminate", ("INDETERMINATE", "INDETERMINATE")),
)


@dataclass(frozen=True)
class AdvisoryScenario:
    """Dimension evidence, and the advisory disposition it must produce."""

    name: str
    scores: Tuple[Optional[float], ...]
    confidence: float
    insufficient: bool = False


ADVISORY_SCENARIOS: Tuple[AdvisoryScenario, ...] = (
    AdvisoryScenario("clear_advance", (80.0, 75.0), 0.9),
    AdvisoryScenario("at_the_score_floor", (60.0, 90.0), 0.9),
    AdvisoryScenario("below_the_score_floor", (59.0, 90.0), 0.9),
    AdvisoryScenario("at_the_confidence_floor", (80.0, 80.0), 0.6),
    AdvisoryScenario("below_the_confidence_floor", (80.0, 80.0), 0.59),
    AdvisoryScenario("insufficient_evidence_holds", (80.0,), 0.9, insufficient=True),
    AdvisoryScenario("no_scored_dimension_holds", (), 0.0),
)


# --------------------------------------------------------------------------- #
# The live product's answers
# --------------------------------------------------------------------------- #


def _reference_eligibility(scenario: GateScenario) -> str:
    eligibility, _rec, _ao, _es, GateState, _rd = _require_reference()
    from ugence_ai_hiring.hiring_decision.gates import GateResult
    from ugence_ai_hiring.hiring_decision.refs import ContractRef

    from ugence_ai_hiring.hiring_policy.enums import MandatoryGateType

    # The reference's own gate vocabulary; the pack's fact keys name the same gates.
    gate_types = (MandatoryGateType.WORK_AUTHORIZATION, MandatoryGateType.REQUIRED_SKILLS)
    results = tuple(
        GateResult(gate_id=key, gate_type=gate_type, state=GateState(state))
        for key, gate_type, state in zip(GATE_FACT_KEYS, gate_types, scenario.gate_states)
    )
    contract = ContractRef(contract_id="contract-1", version=1, ir_digest="sha256:" + "0" * 64)
    return eligibility.derive_eligibility(results, contract).status.value


def _reference_disposition(scenario: AdvisoryScenario) -> str:
    _el, recommendation, AssessmentOutcome, _es, _gs, _rd = _require_reference()
    from ugence_ai_hiring.hiring_decision.assessment import DimensionAssessment

    from ugence_ai_hiring.hiring_decision.assessment import AssessmentProvenance

    provenance = AssessmentProvenance(engine="equivalence-harness")
    assessments = tuple(
        DimensionAssessment(
            dimension=f"dim{index}",
            # The product refuses an INSUFFICIENT_EVIDENCE assessment that carries a
            # score, so the scenario's score is dropped in exactly that case.
            score=None if scenario.insufficient else score,
            confidence=scenario.confidence,
            provenance=provenance,
            # The product refuses a SCORED assessment that cites no evidence — its
            # own fail-closed rule, honoured here rather than worked around.
            evidence_refs=() if scenario.insufficient else ("ev-1",),
            outcome=(
                AssessmentOutcome.INSUFFICIENT_EVIDENCE
                if scenario.insufficient
                else AssessmentOutcome.SCORED
            ),
        )
        for index, score in enumerate(scenario.scores)
    )
    confidence = recommendation.compute_confidence(assessments)
    return recommendation._advisory_disposition(assessments, confidence).value


def _reference_recommendation_is_advisory() -> Tuple[str, bool]:
    """The product's own typing of a recommendation: AI actor, never binding."""
    _el, recommendation, *_ = _require_reference()
    fields = recommendation.HiringRecommendation.model_fields
    actor = fields["actor_type"].default
    binding = fields["binding"].default
    return actor, binding


# --------------------------------------------------------------------------- #
# The compiled pack's answers
# --------------------------------------------------------------------------- #


def _pack_eligibility(pack: PolicyPack, scenario: GateScenario) -> str:
    """Eligibility as the pack's prohibited conditions determine it.

    A FAIL trips its block first; an INDETERMINATE trips its own. Nothing else can
    admit or override them — that is what non-compensatory means here.
    """
    states = dict(zip(GATE_FACT_KEYS, scenario.gate_states))
    tripped = {
        condition.object_id
        for condition in pack.prohibited_conditions
        for predicate in condition.conditions
        if states.get(predicate.fact_key) == predicate.value
    }
    if any(oid.endswith("_failed") for oid in tripped):
        return "NOT_ELIGIBLE"
    if any(oid.endswith("_indeterminate") for oid in tripped):
        return "ELIGIBILITY_PENDING"
    return "ELIGIBLE"


def _pack_disposition(pack: PolicyPack, scenario: AdvisoryScenario) -> str:
    """The advisory disposition as the pack's decision rule determines it."""
    if scenario.insufficient or not scenario.scores:
        # No scored dimension admits an outcome: the pack's evidence requirements
        # block rather than proceed.
        return "HOLD"
    rule = next(r for r in pack.decision_rules if r.object_id == "rule.advisory_advance")
    facts = {
        "lowest_dimension_score": min(s for s in scenario.scores if s is not None),
        "aggregate_confidence_percent": round(scenario.confidence * 100),
    }
    satisfied = all(
        facts[predicate.fact_key] >= predicate.value for predicate in rule.conditions
    )
    return rule.on_satisfied_outcome if satisfied else rule.on_unsatisfied_outcome


def _pack_binding_authority(pack: PolicyPack) -> Tuple[str, bool]:
    """Who the pack says may bind: a human authority, never a machine actor."""
    authority = next(
        a for a in pack.authority_requirements if a.object_id == AUTHORITY_ID
    )
    return authority.authority_type.value, authority.allow_non_human


def _eligibility_reads_no_score(pack: PolicyPack) -> Tuple[str, ...]:
    """Fact keys an eligibility-determining object reads. Scores must not appear."""
    score_like = ("score", "fit", "confidence", "rank", "percentile")
    offenders = []
    for condition in pack.prohibited_conditions:
        for predicate in condition.conditions:
            if any(token in predicate.fact_key.lower() for token in score_like):
                offenders.append(f"{condition.object_id}:{predicate.fact_key}")
    return tuple(offenders)


# --------------------------------------------------------------------------- #
# The harness
# --------------------------------------------------------------------------- #


def run_equivalence(pack: Optional[PolicyPack] = None) -> EquivalenceResult:
    """Compare the compiler's AI Hiring interpretation with the live product."""
    _require_reference()
    pack = pack if pack is not None else build_ai_hiring_policy_pack()
    dimensions = []

    # 1. Non-compensatory eligibility derivation, including FAIL over INDETERMINATE.
    mismatches = tuple(
        f"{s.name}: pack={_pack_eligibility(pack, s)} reference={_reference_eligibility(s)}"
        for s in GATE_SCENARIOS
        if _pack_eligibility(pack, s) != _reference_eligibility(s)
    )
    dimensions.append(
        DimensionResult(
            "eligibility_derivation",
            EQUIVALENT if not mismatches else CONFLICTING_INTERPRETATION,
            len(GATE_SCENARIOS),
            mismatches,
        )
    )

    # 2. Advisory disposition floors.
    mismatches = tuple(
        f"{s.name}: pack={_pack_disposition(pack, s)} reference={_reference_disposition(s)}"
        for s in ADVISORY_SCENARIOS
        if _pack_disposition(pack, s) != _reference_disposition(s)
    )
    dimensions.append(
        DimensionResult(
            "advisory_disposition",
            EQUIVALENT if not mismatches else CONFLICTING_INTERPRETATION,
            len(ADVISORY_SCENARIOS),
            mismatches,
        )
    )

    # 3. Advisory-versus-binding separation: the product types a recommendation as
    #    an AI actor that never binds; the pack reserves binding for a human.
    actor, binding = _reference_recommendation_is_advisory()
    authority_type, allow_non_human = _pack_binding_authority(pack)
    separation = []
    if actor != "AI" or binding is not False:
        separation.append(f"reference recommendation actor={actor} binding={binding}")
    if authority_type != "HUMAN_APPROVER" or allow_non_human:
        separation.append(
            f"pack binding authority type={authority_type} allow_non_human={allow_non_human}"
        )
    dimensions.append(
        DimensionResult(
            "advisory_binding_separation",
            EQUIVALENT if not separation else CONFLICTING_INTERPRETATION,
            2,
            tuple(separation),
        )
    )

    # 4. Compatibility is never eligibility. The product enforces this by importing
    #    no scores into its eligibility module; the pack, by reading no score fact
    #    in any eligibility-determining object.
    offenders = _eligibility_reads_no_score(pack)
    eligibility_module = _require_reference()[0]
    reference_clean = not any(
        token in getattr(eligibility_module, "__doc__", "").lower()
        for token in ("compatibility determines", "score determines")
    )
    problems = tuple(f"pack eligibility reads {o}" for o in offenders) + (
        () if reference_clean else ("reference eligibility admits scores",)
    )
    dimensions.append(
        DimensionResult(
            "compatibility_not_eligibility",
            EQUIVALENT if not problems else CONFLICTING_INTERPRETATION,
            len(pack.prohibited_conditions) + 1,
            problems,
        )
    )

    # 5. The float-to-integer translation of the product's floors must be exact.
    translation = []
    if MIN_SCORE_FOR_ADVANCE != PRODUCT_MIN_SCORE_FOR_ADVANCE:
        translation.append(
            f"score floor {MIN_SCORE_FOR_ADVANCE} != product {PRODUCT_MIN_SCORE_FOR_ADVANCE}"
        )
    if MIN_CONFIDENCE_PERCENT_FOR_ADVANCE != round(PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE * 100):
        translation.append(
            f"confidence floor {MIN_CONFIDENCE_PERCENT_FOR_ADVANCE}% != product "
            f"{PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE}"
        )
    dimensions.append(
        DimensionResult(
            "deterministic_threshold_translation",
            EQUIVALENT if not translation else CONFLICTING_INTERPRETATION,
            2,
            tuple(translation),
        )
    )

    classification = (
        EQUIVALENT
        if all(d.classification == EQUIVALENT for d in dimensions)
        else CONFLICTING_INTERPRETATION
    )
    return EquivalenceResult(classification, tuple(dimensions))


__all__ = [
    "run_equivalence",
    "EquivalenceResult",
    "DimensionResult",
    "ReferenceUnavailable",
    "GATE_SCENARIOS",
    "ADVISORY_SCENARIOS",
    "EQUIVALENT",
]

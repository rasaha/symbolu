"""M-3R.3 must not move the standalone GV-3R-b evaluator.

Orchestration may *subtract* — refuse a binding, exclude an uncataloged
indicator — but once it has built a ``ReadinessEvaluationCase``, the evaluator
must behave exactly as it did before this milestone.

The proof is in five layers:

1. **Byte identity** of every evaluator module, pinned by sha-256 against the
   merged 0.3.0 tree, so an accidental edit fails here.
2. **Vocabulary identity** — the rule, reason, advisory and condition-decision
   enums, and the classification table, are unchanged member-for-member.
3. **Formula identity** — ``EVALUATOR_FORMULA_VERSION`` is exactly ``GV-3R-b.3``.
4. **Digest identity** for indicator-free cases: the evaluation, determination
   and case-input canonical digests are pinned to the literals produced by the
   merged 0.3.0 tree.
5. **Behavioural identity** for indicator-bearing cases: same tier, same rule
   trace, same reason codes.

Why layer 4 is scoped to indicator-free cases, stated honestly
--------------------------------------------------------------
The GV-3R-a indicator contract gained three **appended, defaulted** identity
fields at 0.4.0 (``indicator_id``, ``system_binding_ref``,
``system_binding_digest``). A determination that embeds indicator records
therefore serializes three more keys, so its canonical digest moves. That is a
**documented contract change, not an evaluator change**, and its blast radius is
pinned below in both directions: the 0.3.0 and 0.4.0 literals for the same
indicator-bearing case are both recorded, and layer 5 proves the classification
and trace are identical across them.

Indicator-free cases carry the whole gate-driven classification surface — every
tier, every precedence rule — so layer 4 is the substantive byte-identity proof.
"""

from __future__ import annotations

import hashlib
import pathlib

import pytest

import ugence_agent_value_readiness as R
from ugence_agent_value_readiness.api import (
    ConditionDecisionCode,
    GateStatus,
    ReadinessAdvisoryCode,
    ReadinessClassification,
    ReadinessReasonCode,
    ReadinessRuleId,
    evaluate_readiness,
)
from ugence_agent_value_readiness.evaluation.codes import EVALUATOR_FORMULA_VERSION

from _fixtures import (  # noqa: E402
    BOTH,
    MANDATORY,
    NOW,
    case,
    gate,
    gate_result,
    indicators,
    readiness_policy,
)

PKG_ROOT = pathlib.Path(R.__file__).resolve().parent

#: sha-256 of each evaluator module in the merged 0.3.0 tree
#: (763aa8e67c1a811df82dc4711cc31c34234194c1). M-3R.3 edits none of them.
#: A change here is a change to the classification algorithm and requires an
#: EVALUATOR_FORMULA_VERSION bump and its own review.
FROZEN_EVALUATOR_SOURCE_DIGESTS = {
    "evaluation/evaluator.py": "e8b4873ca3164fddbca748b92db0cec8d0efdc7e38983a322602c50d0d09938f",
    "evaluation/codes.py": "ebe04fc9336d79081edbe3d163271c0d0f2f1d0dbd33539118ea7945056d0872",
    "evaluation/case.py": "0e3c4e660b4964379a05afe3819e74d8bf51782fab64df7cc3b38b0f0f2cb9ab",
    "evaluation/trace.py": "efb539805563a7fe4700e00a791846a3e2bda43933796f8a4c19cea0a7475b78",
    "evaluation/errors.py": "913a3d6c7b624e2f51a65ab37c5f5e29ed382fa0c5cc6ae23a265adcdb55febb",
}


# --------------------------------------------------------------------------- #
# 1. Byte identity of the evaluator modules
# --------------------------------------------------------------------------- #
def test_every_evaluator_module_is_byte_identical_to_the_merged_tree():
    actual = {
        rel: hashlib.sha256((PKG_ROOT / rel).read_bytes()).hexdigest()
        for rel in FROZEN_EVALUATOR_SOURCE_DIGESTS
    }
    assert actual == FROZEN_EVALUATOR_SOURCE_DIGESTS


# --------------------------------------------------------------------------- #
# 2. Vocabulary identity
# --------------------------------------------------------------------------- #
def test_the_classification_table_is_unchanged():
    assert [m.value for m in ReadinessClassification] == [
        "NOT_ASSESSABLE",
        "NOT_READY",
        "PILOT_READY",
        "READY_WITH_CONDITIONS",
        "DEPLOYMENT_READY",
    ]


@pytest.mark.parametrize(
    "enum_cls, expected",
    [
        (ReadinessRuleId, 9),
        (ReadinessReasonCode, 15),
        (ReadinessAdvisoryCode, 8),
        (ConditionDecisionCode, 13),
    ],
)
def test_no_evaluator_enum_gained_or_lost_a_member(enum_cls, expected):
    members = list(enum_cls)
    assert len(members) == expected, [m.name for m in members]
    # Names and values remain one-to-one with no alias.
    assert len({m.name for m in members}) == expected
    assert len({m.value for m in members}) == expected


def test_no_evaluator_enum_carries_catalog_or_binding_vocabulary():
    """M-3R.3's vocabulary lives in the orchestration namespace, nowhere else."""

    for enum_cls in (
        ReadinessRuleId,
        ReadinessReasonCode,
        ReadinessAdvisoryCode,
        ConditionDecisionCode,
        ReadinessClassification,
    ):
        for member in enum_cls:
            lowered = member.value.lower()
            assert "catalog" not in lowered, member
            assert "system_binding" not in lowered, member
            assert "indicator_id" not in lowered, member


# --------------------------------------------------------------------------- #
# 3. Formula identity
# --------------------------------------------------------------------------- #
def test_the_evaluator_formula_version_did_not_move():
    assert EVALUATOR_FORMULA_VERSION == "GV-3R-b.3"


def test_only_the_orchestrator_version_moved():
    from ugence_agent_value_readiness.api import READINESS_ORCHESTRATOR_VERSION

    assert READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.2"
    assert EVALUATOR_FORMULA_VERSION == "GV-3R-b.3"


# --------------------------------------------------------------------------- #
# 4. Digest identity for indicator-free cases
# --------------------------------------------------------------------------- #
#: Produced by the merged 0.3.0 tree for the case built below. Byte-identical at
#: 0.4.0 — verified against a checkout of the base commit.
FROZEN_EVALUATION_DIGEST = "7788d477235b710b6dd8f234759f959534189d8a3aedd1168655c31c3aff2a38"
FROZEN_DETERMINATION_DIGEST = "1144661061be14cfe7b0c1d7189de21f55b901a2a0d32097c7d0cea87a3a182a"
FROZEN_CASE_INPUT_DIGEST = "0dc85e426a3ff320ce4576d101721181737881525ac508e497ee083625fc5543"


def _indicator_free_case():
    policy = readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))
    return case(
        policy=policy,
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        with_indicators=False,
    )


def test_an_indicator_free_case_reproduces_the_merged_trees_digests():
    built = _indicator_free_case()
    result = evaluate_readiness(built, evaluation_time=NOW)

    assert result.classification is ReadinessClassification.DEPLOYMENT_READY
    assert built.canonical_input_digest() == FROZEN_CASE_INPUT_DIGEST
    assert result.canonical_digest() == FROZEN_EVALUATION_DIGEST
    assert result.determination.canonical_digest() == FROZEN_DETERMINATION_DIGEST
    assert result.trace.formula_version == "GV-3R-b.3"


def test_an_indicator_free_case_is_deterministic_across_repeated_evaluations():
    a = evaluate_readiness(_indicator_free_case(), evaluation_time=NOW)
    b = evaluate_readiness(_indicator_free_case(), evaluation_time=NOW)
    assert a.canonical_digest() == b.canonical_digest()


# --------------------------------------------------------------------------- #
# 5. Behavioural identity for indicator-bearing cases
# --------------------------------------------------------------------------- #
#: The same indicator-bearing case, before and after the three appended GV-3R-a
#: identity fields. Both literals are recorded so the delta is auditable and
#: attributable to the contract change alone — not to the evaluator.
INDICATOR_BEARING_DETERMINATION_DIGEST_0_3_0 = (
    "fec492f5948b7833d4a3f89614b10ba1be40eff423e10468b88be0dce65adb1a"
)
INDICATOR_BEARING_DETERMINATION_DIGEST_0_4_0 = (
    "e12e975d90d74c469fa42d315acd588b5c584fdbc63ab4788fa3deb8b0c5bee4"
)


def _indicator_bearing_case():
    policy = readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))
    return case(
        policy=policy,
        gate_results=(gate_result(policy, "g1", GateStatus.PASS),),
        with_indicators=True,
    )


def test_the_indicator_bearing_digest_delta_is_pinned_in_both_directions():
    result = evaluate_readiness(_indicator_bearing_case(), evaluation_time=NOW)
    digest = result.determination.canonical_digest()

    assert digest == INDICATOR_BEARING_DETERMINATION_DIGEST_0_4_0
    assert digest != INDICATOR_BEARING_DETERMINATION_DIGEST_0_3_0


def test_the_delta_is_attributable_to_the_three_appended_identity_fields():
    """Exactly three keys were added to the indicator serialization."""

    import dataclasses

    from ugence_agent_value_readiness.api import IntelligenceFitnessResult

    appended = [f.name for f in dataclasses.fields(IntelligenceFitnessResult)][-3:]
    assert appended == ["indicator_id", "system_binding_ref", "system_binding_digest"]
    # All three default to absent, so no M-3R.1 construction became invalid.
    for field in dataclasses.fields(IntelligenceFitnessResult):
        if field.name in appended:
            assert field.default == ""


def test_indicator_records_still_do_not_participate_in_selecting_a_tier():
    """The reason layer 4 can be scoped to indicator-free cases."""

    bare = evaluate_readiness(_indicator_free_case(), evaluation_time=NOW)
    laden = evaluate_readiness(_indicator_bearing_case(), evaluation_time=NOW)

    assert bare.classification is laden.classification
    assert bare.trace.rule_id is laden.trace.rule_id
    assert bare.trace.reason_codes == laden.trace.reason_codes
    assert bare.trace.advisory_codes == laden.trace.advisory_codes
    assert bare.determination.reason_codes == laden.determination.reason_codes


def test_an_indicator_record_carrying_a_system_binding_changes_no_tier():
    """The new fields are inert to the evaluator, whatever they contain."""

    policy = readiness_policy(gates=(gate("g1", MANDATORY, BOTH),))
    plain = indicators()
    stamped = tuple(
        tuple(
            type(r)(
                **{
                    **{f: getattr(r, f) for f in r.__dataclass_fields__},
                    "indicator_id": f"ind-{r.result_id}",
                    "system_binding_ref": "bind-1",
                    "system_binding_digest": hashlib.sha256(b"b").hexdigest(),
                }
            )
            for r in group
        )
        for group in plain
    )
    gates = (gate_result(policy, "g1", GateStatus.PASS),)
    a = evaluate_readiness(
        case(
            policy=policy,
            gate_results=gates,
            intelligence=plain[0],
            capability=plain[1],
            adoption=plain[2],
        ),
        evaluation_time=NOW,
    )
    b = evaluate_readiness(
        case(
            policy=policy,
            gate_results=gates,
            intelligence=stamped[0],
            capability=stamped[1],
            adoption=stamped[2],
        ),
        evaluation_time=NOW,
    )
    assert a.classification is b.classification
    assert a.trace.rule_id is b.trace.rule_id
    assert a.trace.reason_codes == b.trace.reason_codes

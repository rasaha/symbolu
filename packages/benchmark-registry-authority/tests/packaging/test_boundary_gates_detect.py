"""The boundary gates, attacked. A gate that cannot fail proves nothing.

BR-2B's central property — *no callable consumes a transition plan, and no
planner returns a lifecycle payload* — held at the commit the closure audit
examined. The gates asserting it did not: they matched the literal substring
``"BenchmarkTransitionPlan"`` and skipped parameters whose annotation was
``None``, so a plan-consuming, event-returning exported callable could have been
added and every one of them would still have passed.

Each property below plants exactly that callable and requires the checking logic
to report it. The variants are synthetic and live only inside these tests: the
package under audit is never weakened to prove a gate works.
"""

from __future__ import annotations

import typing

from _boundary import (
    resolved_parameter_types,
    resolved_return_types,
    types_in_annotation,
    unannotated_parameters,
)
from ugence_benchmark_registry_authority import api

PLAN = api.BenchmarkTransitionPlan
REFUSAL = api.BenchmarkTransitionRefusal
EVENT = api.BenchmarkRegistrationEventPayload

#: An alias. Spells the plan type without spelling its name.
PlanAlias = PLAN

#: A union alias. Spells it again, one level deeper.
MaybePlan = typing.Optional[PLAN]

#: A widened planning outcome — what a regression would look like.
WidenedOutcome = typing.Union[PLAN, REFUSAL, EVENT]


def test_happy_the_real_planning_functions_pass_every_boundary_check():
    """The gates are strict, and the shipped surface satisfies them anyway."""

    for name in ("plan_transition", "plan_submission_outcome"):
        func = getattr(api, name)
        for types in resolved_parameter_types(func).values():
            assert PLAN not in types, name
        assert unannotated_parameters(func) == [], name
        assert resolved_return_types(func) == {PLAN, REFUSAL}, name


# --------------------------------------------------------------------------- #
# 1 · an aliased plan parameter
# --------------------------------------------------------------------------- #
def test_an_aliased_plan_parameter_is_detected():
    """``PlanAlias`` contains no substring the old gate was looking for."""

    def applies_a_plan(plan: PlanAlias) -> None: ...

    assert "BenchmarkTransitionPlan" not in "PlanAlias"
    assert PLAN in resolved_parameter_types(applies_a_plan)["plan"]


def test_a_plan_nested_in_optional_is_detected():
    def applies_a_plan(plan: MaybePlan) -> None: ...

    assert PLAN in resolved_parameter_types(applies_a_plan)["plan"]


def test_a_plan_nested_in_a_container_is_detected():
    def applies_many(plans: typing.Sequence[PlanAlias]) -> None: ...

    assert PLAN in resolved_parameter_types(applies_many)["plans"]


def test_a_pep563_string_annotation_is_resolved_not_read():
    """Every module here uses ``from __future__ import annotations``.

    So the raw annotation is a *string*. Reading it is how the return-type gate
    came to inspect one opaque name instead of a Union's members.
    """

    namespace = {"PlanAlias": PlanAlias}
    exec(  # noqa: S102 - a synthetic variant, defined and discarded here
        "from __future__ import annotations\n"
        "def applies(plan: PlanAlias) -> None: ...\n",
        namespace,
    )
    applies = namespace["applies"]
    assert isinstance(applies.__annotations__["plan"], str)
    assert PLAN in resolved_parameter_types(applies)["plan"]


# --------------------------------------------------------------------------- #
# 2 · an unannotated plan parameter
# --------------------------------------------------------------------------- #
def test_an_unannotated_plan_parameter_is_reported_not_skipped():
    def applies_a_plan(plan) -> None: ...

    assert unannotated_parameters(applies_a_plan) == ["plan"]
    assert resolved_parameter_types(applies_a_plan)["plan"] == set()


def test_self_and_cls_remain_exempt():
    class Holder:
        def method(self, plan: PlanAlias) -> None: ...

        @classmethod
        def factory(cls, plan: PlanAlias) -> None: ...

    assert unannotated_parameters(Holder.method) == []
    assert unannotated_parameters(Holder.factory) == []
    assert PLAN in resolved_parameter_types(Holder.method)["plan"]


# --------------------------------------------------------------------------- #
# 3 · a widened return union
# --------------------------------------------------------------------------- #
def test_a_widened_return_union_exposes_the_lifecycle_payload():
    def plan_and_register(snapshot: object) -> WidenedOutcome: ...

    returned = resolved_return_types(plan_and_register)
    assert EVENT in returned
    assert not returned <= {PLAN, REFUSAL}


def test_the_shipped_alias_is_exactly_two_members():
    assert set(typing.get_args(api.BenchmarkPlanningOutcome)) == {PLAN, REFUSAL}


def test_widening_the_alias_is_visible_through_the_alias_name_alone():
    """The regression the string-reading gate could not see.

    Both annotations render as one opaque name, and the names even differ only
    in a way no substring rule would flag. Resolution is what separates them.
    """

    def honest(x: object) -> api.BenchmarkPlanningOutcome: ...

    def widened(x: object) -> WidenedOutcome: ...

    assert resolved_return_types(honest) == {PLAN, REFUSAL}
    assert EVENT in resolved_return_types(widened)


# --------------------------------------------------------------------------- #
# 4 · a private plan-consuming helper
# --------------------------------------------------------------------------- #
def test_a_private_plan_consuming_helper_is_detected():
    """Privacy is not exemption. ``pkg.__all__`` would never have shown this."""

    def _commit(plan: PlanAlias, *, force: bool = False) -> None: ...

    assert PLAN in resolved_parameter_types(_commit)["plan"]


def test_a_plan_hidden_in_a_keyword_only_parameter_is_detected():
    def _commit(*, plan: MaybePlan = None) -> None: ...

    assert PLAN in resolved_parameter_types(_commit)["plan"]


def test_types_in_annotation_walks_to_leaves_without_raising():
    """Non-class leaves are dropped rather than crashing the scan."""

    assert types_in_annotation(None) == set()
    assert types_in_annotation(typing.Optional[int]) >= {int}
    assert PLAN in types_in_annotation(typing.Dict[str, typing.List[PlanAlias]])

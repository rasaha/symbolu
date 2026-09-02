"""Test fixtures for slice 2: the research rule set and representative profiles.

``rules.research.v0`` is a TEST FIXTURE ONLY (spec §9). It transcribes the
experimental selector's signal-to-method mapping as ten SUPPORT rules. That
transcription is research provenance for where each rule came from; it is not
evidence that the routing is correct.
"""

from __future__ import annotations

from typing import Optional, Tuple

import matrix_fixtures as fx
from ugence_reasoning_method_advisor.api import (
    ADVISORY_REQUEST_SCHEMA_VERSION,
    RULE_SET_SCHEMA_VERSION,
    Predicate,
    PredicateKind,
    ReasoningMethodAdvisoryRequest,
    Rule,
    RuleKind,
    RuleSet,
)
from ugence_reasoning_method_governance.api import (
    PROFILE_SCHEMA_VERSION,
    ConsequenceClass,
    ImplementationStatus,
    ReasoningMethodCatalog,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
)

# Transcription of WorkflowSelector.SIGNAL_MAP (agentic/agentic_framework/reasoning_workflows.py:1177-1188).
SIGNAL_MAP_TRANSCRIPTION = {
    "comparison_request": "map_reduce",
    "causal_reasoning": "linear_chain",
    "ambiguity_detected": "tree_of_thought",
    "creative_synthesis": "iterative_refinement",
    "conditional_logic": "debate",
    "temporal_reasoning": "linear_chain",
    "abstract_concept": "tree_of_thought",
    "meta_reasoning": "linear_chain",
    "multi_part_question": "map_reduce",
    "domain_expertise": "linear_chain",
}
PROVENANCE_REF = "agentic/agentic_framework/reasoning_workflows.py:1177-1188"
RATIONALE = "transcribed from the experimental WorkflowSelector mapping; provenance only"


def admissibility() -> Predicate:
    return Predicate(PredicateKind.IMPLEMENTATION_STATUS_IN, (ImplementationStatus.EXECUTABLE_TESTED.value,))


def signal_rule(token: str, method_id: Optional[str] = None, version: str = "0", suffix: str = "", method_ids: Optional[Tuple[str, ...]] = None) -> Rule:
    return Rule(
        rule_id=f"research.signal.{token}{suffix}",
        rule_version=version,
        kind=RuleKind.SUPPORT,
        predicate=Predicate(PredicateKind.STRUCTURAL_TOKEN_PRESENT, (token,)),
        method_ids=method_ids or (method_id or SIGNAL_MAP_TRANSCRIPTION[token],),
        rationale_ref=PROVENANCE_REF,
        rationale_statement=RATIONALE,
    )


def research_rules_v0(extra: Tuple[Rule, ...] = (), version: str = "0", replace: Tuple[Rule, ...] = ()) -> RuleSet:
    replaced = {r.rule_id for r in replace}
    rules = tuple(signal_rule(t) for t in SIGNAL_MAP_TRANSCRIPTION if f"research.signal.{t}" not in replaced)
    rules = tuple(sorted(rules + replace + extra, key=lambda r: r.rule_id))
    return RuleSet(RULE_SET_SCHEMA_VERSION, "rules.research", version, admissibility(), rules, PROVENANCE_REF, "fixture:test", fx.NOW)


def exclude_rule(rule_id: str, method_id: str, consequence: ConsequenceClass) -> Rule:
    return Rule(rule_id, "0", RuleKind.EXCLUDE, Predicate(PredicateKind.CONSEQUENCE_CLASS_IN, (consequence.value,)), (method_id,), "fixture:test:exclude", "excluded for this consequence class by test fixture")


def profile(tokens: Tuple[str, ...], consequence: ConsequenceClass = ConsequenceClass.RECOVERABLE, reversibility: TaskReversibility = TaskReversibility.OUTCOME_REVERSIBLE) -> TaskProfile:
    return TaskProfile(PROFILE_SCHEMA_VERSION, "profile.test", "domain:support", "outcome:resolve", consequence, reversibility, (), (), tokens, "population:all")


def governed_class(tokens: Tuple[str, ...], consequence: ConsequenceClass = ConsequenceClass.RECOVERABLE) -> TaskClassIdentity:
    from ugence_reasoning_method_governance.api import TASK_CLASS_SCHEMA_VERSION

    return TaskClassIdentity(
        TASK_CLASS_SCHEMA_VERSION, "class.test", "domain:support", "outcome:resolve", consequence, TaskReversibility.OUTCOME_COMPENSATABLE,
        (), (), tokens, "population:all", "benchmarks:test", fx.HEX_B,
        fx.c8_policy(rule=fx.c7_rule_hc()) if consequence in (ConsequenceClass.MATERIAL, ConsequenceClass.SEVERE) else fx.c8_policy(),
    )


def request(tokens: Tuple[str, ...], *, governed: bool = True, catalog: Optional[ReasoningMethodCatalog] = None, rule_set: Optional[RuleSet] = None, consequence: ConsequenceClass = ConsequenceClass.RECOVERABLE, reversibility: TaskReversibility = TaskReversibility.OUTCOME_REVERSIBLE, request_id: str = "req.test") -> ReasoningMethodAdvisoryRequest:
    return ReasoningMethodAdvisoryRequest(
        ADVISORY_REQUEST_SCHEMA_VERSION, request_id, profile(tokens, consequence, reversibility),
        governed_class(tokens, consequence) if governed else None,
        catalog or fx.c4_catalog(), rule_set or research_rules_v0(), "requester:test",
    )

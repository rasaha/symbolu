"""Deterministic assurance generation (Stage 4).

From the approved policy objects, generate structured test *specifications* (never
arbitrary Python) covering every required category: positive, negative,
missing-evidence, authority-conflict, segregation-of-duties, exception,
override-valid, override-invalid, legitimate-counterexample, replay,
action-constraint, unknown-state, timeout, and indeterminate.

Each generated :class:`TestScenario` carries a source object set, initial facts,
actor identities, evidence, a requested action, and an :class:`ExpectedOutcome`
(terminal state + reason codes + audit events). The output is deterministic:
test ids are content-addressed from the source objects and category.
"""

from __future__ import annotations

from typing import List

from ..models.assurance import (
    AssuranceManifest,
    ExpectedOutcome,
    ReplayCase,
    TestCategory,
    TestScenario,
)
from ..models.policy_pack import PolicyPack
from ..serialization import hashing
from ..validation.coverage import build_coverage_matrix


#: Map declarative outcome labels to synthesis terminal-state labels.
_OUTCOME_TERMINAL = {
    "ADVANCE": "ADVANCE_AUTHORIZED",
    "HOLD": "ESCALATED",
    "ESCALATE": "ESCALATED",
    "REJECT": "DENIED",
    "DENY": "DENIED",
}


def _terminal_for(outcome_label: str) -> str:
    return _OUTCOME_TERMINAL.get(outcome_label, outcome_label)


def _test_id(category: TestCategory, source_ids) -> str:
    key = hashing.digest({"category": category.value, "sources": sorted(source_ids)})
    return f"test_{category.value.lower()}_{key.split(':', 1)[1][:12]}"


def _scenario(
    category: TestCategory,
    name: str,
    source_ids,
    expected: ExpectedOutcome,
    *,
    facts=None,
    actors=None,
    evidence=None,
    requested_action="",
) -> TestScenario:
    return TestScenario(
        object_id=_test_id(category, source_ids),
        name=name,
        category=category,
        source_object_ids=tuple(source_ids),
        initial_facts=dict(facts or {}),
        actor_identities=dict(actors or {}),
        evidence=dict(evidence or {}),
        requested_action=requested_action,
        expected_outcome=expected,
    )


class AssuranceGenerator:
    """Deterministically generates an assurance suite for an approved pack."""

    def generate(self, pack: PolicyPack) -> AssuranceManifest:
        scenarios: List[TestScenario] = []

        # POSITIVE — a compliant case reaches the approved outcome. Covers every
        # decision rule and authority requirement (the happy path exercises them).
        happy_sources = tuple(
            sorted(
                [r.object_id for r in pack.decision_rules if r.enabled]
                + [a.object_id for a in pack.authority_requirements if a.enabled]
            )
        )
        if happy_sources:
            scenarios.append(
                _scenario(
                    TestCategory.POSITIVE,
                    "compliant request reaches approved outcome",
                    happy_sources,
                    ExpectedOutcome(
                        terminal_state="ADVANCE_AUTHORIZED",
                        reason_codes=("NOT_APPLICABLE",),
                        audit_events=("DECISION_CREATED",),
                        authorization_outcome="AUTHORIZED",
                    ),
                    requested_action="advance",
                )
            )

        # NEGATIVE + PROHIBITED — each prohibited condition blocks fail-closed.
        for cond in pack.prohibited_conditions:
            if not cond.enabled:
                continue
            terminal = "ESCALATED" if cond.behavior.value == "ESCALATE" else "BLOCKED"
            scenarios.append(
                _scenario(
                    TestCategory.NEGATIVE,
                    f"prohibited condition blocks: {cond.name}",
                    (cond.object_id,),
                    ExpectedOutcome(
                        terminal_state=terminal,
                        reason_codes=(cond.reason_code,),
                        audit_events=("POLICY_DENIED",),
                    ),
                )
            )

        # MISSING_EVIDENCE — absence of each required-evidence field blocks/escalates.
        for ev in pack.required_evidence:
            if not ev.enabled:
                continue
            terminal = "ESCALATED" if ev.on_missing.value == "ESCALATE" else "BLOCKED"
            scenarios.append(
                _scenario(
                    TestCategory.MISSING_EVIDENCE,
                    f"missing evidence blocks: {ev.name}",
                    (ev.object_id,),
                    ExpectedOutcome(
                        terminal_state=terminal,
                        reason_codes=("MISSING_REQUIRED_EVIDENCE",),
                        audit_events=("POLICY_DENIED",),
                    ),
                    facts={ev.fact_key: None},
                )
            )

        # AUTHORITY_CONFLICT — an approver lacking authority is rejected.
        for auth in pack.authority_requirements:
            if not auth.enabled:
                continue
            scenarios.append(
                _scenario(
                    TestCategory.AUTHORITY_CONFLICT,
                    f"insufficient authority rejected: {auth.name}",
                    (auth.object_id,),
                    ExpectedOutcome(
                        terminal_state="DENIED",
                        reason_codes=("DENIED",),
                        audit_events=("POLICY_DENIED",),
                    ),
                    actors={"approver": "unauthorized_actor"},
                )
            )

        # SEGREGATION_OF_DUTIES — same identity in two segregated roles is rejected.
        for path in pack.approval_paths:
            if not path.enabled or not path.segregation_pairs:
                continue
            scenarios.append(
                _scenario(
                    TestCategory.SEGREGATION_OF_DUTIES,
                    f"segregation-of-duties violation rejected: {path.name}",
                    (path.object_id,),
                    ExpectedOutcome(
                        terminal_state="DENIED",
                        reason_codes=("DENIED",),
                        audit_events=("POLICY_DENIED",),
                    ),
                    actors={"requester": "same_person", "approver": "same_person"},
                )
            )

        # EXCEPTION — each exception triggers its behavior and only its case.
        for exc in pack.exception_rules:
            if not exc.enabled:
                continue
            scenarios.append(
                _scenario(
                    TestCategory.EXCEPTION,
                    f"exception triggers required behavior: {exc.name}",
                    (exc.object_id, exc.decision_rule_id),
                    ExpectedOutcome(
                        terminal_state="ESCALATED",
                        reason_codes=(exc.exception_outcome,),
                        audit_events=("WORKFLOW_TRANSITION",),
                    ),
                )
            )

        # OVERRIDE_VALID / OVERRIDE_INVALID.
        for ovr in pack.override_rules:
            if not ovr.enabled:
                continue
            scenarios.append(
                _scenario(
                    TestCategory.OVERRIDE_VALID,
                    f"valid override admitted and recorded: {ovr.name}",
                    (ovr.object_id, ovr.decision_rule_id),
                    ExpectedOutcome(
                        terminal_state="ADVANCE_AUTHORIZED",
                        reason_codes=("NOT_APPLICABLE",),
                        audit_events=("DECISION_CREATED",),
                    ),
                    facts={"override_justified": True, "override_expired": False},
                )
            )
            scenarios.append(
                _scenario(
                    TestCategory.OVERRIDE_INVALID,
                    f"unjustified/expired override rejected: {ovr.name}",
                    (ovr.object_id, ovr.decision_rule_id),
                    ExpectedOutcome(
                        terminal_state="DENIED",
                        reason_codes=("DENIED",),
                        audit_events=("POLICY_DENIED",),
                    ),
                    facts={"override_justified": False, "override_expired": True},
                )
            )

        # LEGITIMATE_COUNTEREXAMPLE — benign lookalike must be allowed.
        for ce in pack.legitimate_counterexamples:
            if not ce.enabled:
                continue
            scenarios.append(
                _scenario(
                    TestCategory.LEGITIMATE_COUNTEREXAMPLE,
                    f"benign lookalike allowed: {ce.name}",
                    (ce.object_id, ce.resembles_object_id),
                    ExpectedOutcome(
                        terminal_state=_terminal_for(ce.must_allow_outcome),
                        reason_codes=("NOT_APPLICABLE",),
                        audit_events=("DECISION_CREATED",),
                    ),
                )
            )

        # ACTION_CONSTRAINT + INDETERMINATE — in-range allowed / out-of-range denied.
        for constraint in pack.action_constraints:
            if not constraint.enabled:
                continue
            scenarios.append(
                _scenario(
                    TestCategory.ACTION_CONSTRAINT,
                    f"out-of-bound action denied: {constraint.name}",
                    (constraint.object_id,),
                    ExpectedOutcome(
                        terminal_state="DENIED",
                        reason_codes=(constraint.violation_reason_code,),
                        audit_events=("POLICY_DENIED",),
                        authorization_outcome="DENIED",
                    ),
                    requested_action=constraint.action_type,
                )
            )
            scenarios.append(
                _scenario(
                    TestCategory.INDETERMINATE,
                    f"indeterminate authorization holds: {constraint.name}",
                    (constraint.object_id,),
                    ExpectedOutcome(
                        terminal_state="INDETERMINATE",
                        reason_codes=("INDETERMINATE",),
                        audit_events=("WORKFLOW_TRANSITION",),
                        authorization_outcome="INDETERMINATE",
                    ),
                    requested_action=constraint.action_type,
                )
            )

        # UNKNOWN_STATE + TIMEOUT — external-system uncertainty never becomes success.
        pack_scope = (pack.pack_id,)
        scenarios.append(
            _scenario(
                TestCategory.UNKNOWN_STATE,
                "unknown external outcome does not become success",
                pack_scope,
                ExpectedOutcome(
                    terminal_state="INDETERMINATE",
                    reason_codes=("UNKNOWN",),
                    audit_events=("WORKFLOW_TRANSITION",),
                ),
            )
        )
        scenarios.append(
            _scenario(
                TestCategory.TIMEOUT,
                "timed-out external outcome does not become success",
                pack_scope,
                ExpectedOutcome(
                    terminal_state="INDETERMINATE",
                    reason_codes=("TIMED_OUT",),
                    audit_events=("WORKFLOW_TRANSITION",),
                ),
            )
        )

        # REPLAY — authored replay cases plus a synthetic happy-path replay.
        replays: List[ReplayCase] = list(pack.replay_cases)
        if happy_sources:
            replays.append(
                ReplayCase(
                    object_id=_test_id(TestCategory.REPLAY, happy_sources),
                    name="captured compliant decision reproduces on re-run",
                    source_object_ids=happy_sources,
                    captured_facts={"replayed": True},
                    expected_outcome=ExpectedOutcome(
                        terminal_state="ADVANCE_AUTHORIZED",
                        reason_codes=("NOT_APPLICABLE",),
                        audit_events=("DECISION_CREATED",),
                    ),
                )
            )

        # Merge any pack-authored scenarios, then dedupe and order deterministically.
        scenarios.extend(pack.test_scenarios)
        scenarios = _dedupe_scenarios(scenarios)
        replays = _dedupe_replays(replays)

        manifest = AssuranceManifest(
            policy_pack_id=pack.pack_id,
            policy_pack_version=pack.version,
            scenarios=tuple(scenarios),
            replay_cases=tuple(replays),
        )
        matrix = build_coverage_matrix(pack, manifest)
        return manifest.model_copy(update={"coverage_matrix": matrix})


def _dedupe_scenarios(scenarios):
    seen = {}
    for s in scenarios:
        seen.setdefault(s.object_id, s)
    return sorted(seen.values(), key=lambda s: (s.category.value, s.object_id))


def _dedupe_replays(replays):
    seen = {}
    for r in replays:
        seen.setdefault(r.object_id, r)
    return sorted(seen.values(), key=lambda r: r.object_id)

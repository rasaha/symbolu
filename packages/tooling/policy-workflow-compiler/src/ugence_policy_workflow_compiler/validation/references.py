"""Referential and structural validation.

Checks that make a pack internally consistent: unique ids, resolvable references,
authority resolution, approval-path integrity, segregation-of-duties sanity,
known capability identifiers, and present expected outcomes. Every finding is a
structured :class:`ValidationDiagnostic`.
"""

from __future__ import annotations

from typing import List

from ..compiler.capability_registry import CapabilityRegistry, DEFAULT_REGISTRY
from ..models.common import CapabilityId
from ..models.policy_pack import PolicyPack
from .errors import Severity, ValidationDiagnostic


def _diag(code, severity, message, object_id="", related=(), remediation="") -> ValidationDiagnostic:
    return ValidationDiagnostic(
        code=code,
        severity=severity,
        object_id=object_id,
        message=message,
        related_object_ids=tuple(related),
        suggested_remediation=remediation,
    )


def check_duplicate_ids(pack: PolicyPack) -> List[ValidationDiagnostic]:
    seen = {}
    out: List[ValidationDiagnostic] = []
    for obj in pack.all_objects():
        if obj.object_id in seen:
            out.append(
                _diag(
                    "DUPLICATE_OBJECT_ID",
                    Severity.ERROR,
                    f"object id '{obj.object_id}' is used more than once",
                    object_id=obj.object_id,
                    related=(seen[obj.object_id],),
                    remediation="assign a unique object_id to every object",
                )
            )
        else:
            seen[obj.object_id] = obj.object_id
    return out


def check_dangling_references(pack: PolicyPack) -> List[ValidationDiagnostic]:
    index = pack.object_index()
    out: List[ValidationDiagnostic] = []
    for obj in pack.all_objects():
        for ref in obj.related_object_ids:
            if ref not in index:
                out.append(
                    _diag(
                        "DANGLING_REFERENCE",
                        Severity.ERROR,
                        f"object '{obj.object_id}' references unknown object '{ref}'",
                        object_id=obj.object_id,
                        related=(ref,),
                        remediation="add the missing object or remove the reference",
                    )
                )
    return out


def _require(index, ref, obj_id, code, message, out, *, missing_ok=False):
    if not ref:
        if not missing_ok:
            out.append(
                _diag(code, Severity.ERROR, message, object_id=obj_id,
                      remediation="add the missing reference")
            )
        return
    if ref not in index:
        out.append(
            _diag(code, Severity.ERROR, f"{message} (unresolved '{ref}')",
                  object_id=obj_id, related=(ref,),
                  remediation="reference an existing object")
        )


def check_authority_resolution(pack: PolicyPack) -> List[ValidationDiagnostic]:
    index = pack.object_index()
    auth_ids = {a.object_id for a in pack.authority_requirements}
    out: List[ValidationDiagnostic] = []

    for rule in pack.decision_rules:
        ref = rule.authority_requirement_id
        if ref and ref not in auth_ids:
            out.append(
                _diag(
                    "UNRESOLVED_AUTHORITY_REFERENCE",
                    Severity.ERROR,
                    f"decision rule '{rule.object_id}' names authority '{ref}' "
                    "which is not an AuthorityRequirement",
                    object_id=rule.object_id,
                    related=(ref,),
                    remediation="point authority_requirement_id at an AuthorityRequirement",
                )
            )

    for constraint in pack.action_constraints:
        ref = constraint.authority_requirement_id
        if not ref:
            out.append(
                _diag(
                    "ACTION_CONSTRAINT_WITHOUT_AUTHORITY",
                    Severity.ERROR,
                    f"action constraint '{constraint.object_id}' has no applicable authority",
                    object_id=constraint.object_id,
                    remediation="set authority_requirement_id to a governing AuthorityRequirement",
                )
            )
        elif ref not in auth_ids:
            out.append(
                _diag(
                    "UNRESOLVED_AUTHORITY_REFERENCE",
                    Severity.ERROR,
                    f"action constraint '{constraint.object_id}' names authority '{ref}' "
                    "which is not an AuthorityRequirement",
                    object_id=constraint.object_id,
                    related=(ref,),
                    remediation="reference a valid AuthorityRequirement",
                )
            )

    for ovr in pack.override_rules:
        ref = ovr.authority_requirement_id
        if ref and ref not in auth_ids:
            out.append(
                _diag(
                    "UNRESOLVED_AUTHORITY_REFERENCE",
                    Severity.ERROR,
                    f"override '{ovr.object_id}' names authority '{ref}' which is not "
                    "an AuthorityRequirement",
                    object_id=ovr.object_id,
                    related=(ref,),
                    remediation="reference a valid AuthorityRequirement",
                )
            )
    return out


def check_exception_override_targets(pack: PolicyPack) -> List[ValidationDiagnostic]:
    rule_ids = {r.object_id for r in pack.decision_rules}
    out: List[ValidationDiagnostic] = []
    for exc in pack.exception_rules:
        if exc.decision_rule_id not in rule_ids:
            out.append(
                _diag(
                    "EXCEPTION_WITHOUT_DECISION_RULE",
                    Severity.ERROR,
                    f"exception '{exc.object_id}' references no known decision rule",
                    object_id=exc.object_id,
                    related=(exc.decision_rule_id,),
                    remediation="point decision_rule_id at an existing DecisionRule",
                )
            )
    for ovr in pack.override_rules:
        if ovr.decision_rule_id not in rule_ids:
            out.append(
                _diag(
                    "OVERRIDE_WITHOUT_DECISION_RULE",
                    Severity.ERROR,
                    f"override '{ovr.object_id}' references no known decision rule",
                    object_id=ovr.object_id,
                    related=(ovr.decision_rule_id,),
                    remediation="point decision_rule_id at an existing DecisionRule",
                )
            )
    return out


def check_approval_paths(pack: PolicyPack) -> List[ValidationDiagnostic]:
    step_index = {s.object_id: s for s in pack.approval_steps}
    out: List[ValidationDiagnostic] = []
    for path in pack.approval_paths:
        if not path.step_ids:
            out.append(
                _diag(
                    "APPROVAL_PATH_MISSING_STEPS",
                    Severity.ERROR,
                    f"approval path '{path.object_id}' has no steps",
                    object_id=path.object_id,
                    remediation="add at least one ApprovalStep and list it in step_ids",
                )
            )
            continue
        orders = []
        labels = []
        for sid in path.step_ids:
            step = step_index.get(sid)
            if step is None:
                out.append(
                    _diag(
                        "APPROVAL_PATH_MISSING_STEPS",
                        Severity.ERROR,
                        f"approval path '{path.object_id}' references unknown step '{sid}'",
                        object_id=path.object_id,
                        related=(sid,),
                        remediation="add the ApprovalStep or remove the reference",
                    )
                )
                continue
            orders.append(step.order)
            labels.append(step.role_label)
        if len(set(orders)) != len(orders):
            out.append(
                _diag(
                    "IMPOSSIBLE_APPROVAL_ORDERING",
                    Severity.ERROR,
                    f"approval path '{path.object_id}' has duplicate step orders {orders}",
                    object_id=path.object_id,
                    remediation="give each ApprovalStep a distinct order",
                )
            )
        # Segregation-of-duties sanity: a pair naming the same role label is a
        # contradiction (one identity cannot be segregated from itself).
        for a, b in path.segregation_pairs:
            if a == b:
                out.append(
                    _diag(
                        "SEGREGATION_OF_DUTIES_CONTRADICTION",
                        Severity.ERROR,
                        f"approval path '{path.object_id}' segregates role '{a}' from itself",
                        object_id=path.object_id,
                        remediation="segregate two distinct roles/steps",
                    )
                )
    return out


def check_capability_ids(
    pack: PolicyPack, registry: CapabilityRegistry = DEFAULT_REGISTRY
) -> List[ValidationDiagnostic]:
    """Every object's owning capability must be a known registry entry."""
    out: List[ValidationDiagnostic] = []
    for obj in pack.all_objects():
        cap = getattr(obj, "owning_capability", None)
        if cap is None:
            continue
        if not isinstance(cap, CapabilityId) or not registry.has(cap):
            out.append(
                _diag(
                    "UNKNOWN_CAPABILITY",
                    Severity.ERROR,
                    f"object '{obj.object_id}' names unknown capability '{cap}'",
                    object_id=obj.object_id,
                    remediation="use a CapabilityId present in the capability registry",
                )
            )
    return out


def check_expected_outcomes(pack: PolicyPack) -> List[ValidationDiagnostic]:
    """Authored scenarios/replays must carry a non-empty expected outcome."""
    out: List[ValidationDiagnostic] = []
    for scenario in pack.test_scenarios:
        if not scenario.expected_outcome.terminal_state:
            out.append(
                _diag(
                    "MISSING_EXPECTED_OUTCOME",
                    Severity.ERROR,
                    f"test scenario '{scenario.object_id}' has no expected terminal state",
                    object_id=scenario.object_id,
                    remediation="set expected_outcome.terminal_state",
                )
            )
    for replay in pack.replay_cases:
        if not replay.expected_outcome.terminal_state:
            out.append(
                _diag(
                    "MISSING_EXPECTED_OUTCOME",
                    Severity.ERROR,
                    f"replay case '{replay.object_id}' has no expected terminal state",
                    object_id=replay.object_id,
                    remediation="set expected_outcome.terminal_state",
                )
            )
    return out


def check_all(
    pack: PolicyPack, registry: CapabilityRegistry = DEFAULT_REGISTRY
) -> List[ValidationDiagnostic]:
    out: List[ValidationDiagnostic] = []
    out.extend(check_duplicate_ids(pack))
    out.extend(check_dangling_references(pack))
    out.extend(check_authority_resolution(pack))
    out.extend(check_exception_override_targets(pack))
    out.extend(check_approval_paths(pack))
    out.extend(check_capability_ids(pack, registry))
    out.extend(check_expected_outcomes(pack))
    return out

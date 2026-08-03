"""Object-level structural diff between two policy packs.

Exact structured comparison — no natural-language semantic equivalence. Classifies
each change as object added/removed/changed, and for changed objects narrows to
reference / provenance / authority / action-constraint / expected-outcome /
test-coverage / capability-requirement changes.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Tuple

from ..models.common import CompilerModel, ObjectType, PolicyObject
from ..models.policy_pack import PolicyPack
from ..serialization import canonical_json


class ChangeType(str, Enum):
    OBJECT_ADDED = "OBJECT_ADDED"
    OBJECT_REMOVED = "OBJECT_REMOVED"
    OBJECT_CHANGED = "OBJECT_CHANGED"
    REFERENCE_CHANGED = "REFERENCE_CHANGED"
    PROVENANCE_CHANGED = "PROVENANCE_CHANGED"
    AUTHORITY_CHANGED = "AUTHORITY_CHANGED"
    ACTION_CONSTRAINT_CHANGED = "ACTION_CONSTRAINT_CHANGED"
    EXPECTED_OUTCOME_CHANGED = "EXPECTED_OUTCOME_CHANGED"
    TEST_COVERAGE_CHANGED = "TEST_COVERAGE_CHANGED"
    CAPABILITY_REQUIREMENT_CHANGED = "CAPABILITY_REQUIREMENT_CHANGED"


class ObjectChange(CompilerModel):
    """A single classified change to one object."""

    object_id: str
    object_type: str
    change_types: Tuple[str, ...]
    detail: str = ""


class ImpactSummary(CompilerModel):
    """The downstream impact of a set of changes."""

    workflow_nodes_affected: Tuple[str, ...] = ()
    assurance_tests_affected: Tuple[str, ...] = ()
    approval_re_review_required: bool = False
    connector_mappings_affected: Tuple[str, ...] = ()
    authority_scope_affected: Tuple[str, ...] = ()


class PolicyPackDiff(CompilerModel):
    """The full structural diff of two packs plus an impact summary."""

    old_pack_id: str
    new_pack_id: str
    added: Tuple[ObjectChange, ...] = ()
    removed: Tuple[ObjectChange, ...] = ()
    changed: Tuple[ObjectChange, ...] = ()
    impact: ImpactSummary = ImpactSummary()

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def _classify_change(old: PolicyObject, new: PolicyObject) -> Tuple[str, ...]:
    types: List[str] = [ChangeType.OBJECT_CHANGED.value]
    old_d = old.model_dump(mode="python")
    new_d = new.model_dump(mode="python")

    if old_d.get("related_object_ids") != new_d.get("related_object_ids"):
        types.append(ChangeType.REFERENCE_CHANGED.value)
    if old.provenance_refs != new.provenance_refs:
        types.append(ChangeType.PROVENANCE_CHANGED.value)

    for key in ("authority_requirement_id", "authority_type", "required_role", "allow_non_human"):
        if old_d.get(key) != new_d.get(key):
            types.append(ChangeType.AUTHORITY_CHANGED.value)
            break

    if old.object_type is ObjectType.ACTION_CONSTRAINT:
        for key in ("kind", "min_value", "max_value", "members", "action_type", "parameter"):
            if old_d.get(key) != new_d.get(key):
                types.append(ChangeType.ACTION_CONSTRAINT_CHANGED.value)
                break

    if old.object_type in (ObjectType.TEST_SCENARIO, ObjectType.REPLAY_CASE):
        if old_d.get("expected_outcome") != new_d.get("expected_outcome"):
            types.append(ChangeType.EXPECTED_OUTCOME_CHANGED.value)
        if old_d.get("source_object_ids") != new_d.get("source_object_ids"):
            types.append(ChangeType.TEST_COVERAGE_CHANGED.value)

    if old_d.get("owning_capability") != new_d.get("owning_capability"):
        types.append(ChangeType.CAPABILITY_REQUIREMENT_CHANGED.value)

    # Deterministic, de-duplicated order.
    seen = []
    for t in types:
        if t not in seen:
            seen.append(t)
    return tuple(seen)


def _index(pack: PolicyPack) -> Dict[str, PolicyObject]:
    return {o.object_id: o for o in pack.all_objects()}


def diff_policy_packs(old: PolicyPack, new: PolicyPack) -> PolicyPackDiff:
    """Compute the object-level structural diff of two packs."""
    old_index = _index(old)
    new_index = _index(new)

    added = tuple(
        ObjectChange(
            object_id=oid,
            object_type=new_index[oid].object_type.value,
            change_types=(ChangeType.OBJECT_ADDED.value,),
        )
        for oid in sorted(set(new_index) - set(old_index))
    )
    removed = tuple(
        ObjectChange(
            object_id=oid,
            object_type=old_index[oid].object_type.value,
            change_types=(ChangeType.OBJECT_REMOVED.value,),
        )
        for oid in sorted(set(old_index) - set(new_index))
    )
    changed_list: List[ObjectChange] = []
    for oid in sorted(set(old_index) & set(new_index)):
        o, n = old_index[oid], new_index[oid]
        if canonical_json.dumps(o) != canonical_json.dumps(n):
            changed_list.append(
                ObjectChange(
                    object_id=oid,
                    object_type=n.object_type.value,
                    change_types=_classify_change(o, n),
                )
            )
    changed = tuple(changed_list)

    impact = _impact(added, removed, changed, old_index, new_index)
    return PolicyPackDiff(
        old_pack_id=old.pack_id,
        new_pack_id=new.pack_id,
        added=added,
        removed=removed,
        changed=changed,
        impact=impact,
    )


def _impact(added, removed, changed, old_index, new_index) -> ImpactSummary:
    from .change_impact import compute_impact

    return compute_impact(added, removed, changed, old_index, new_index)

"""Deterministic derivation of a review requirement from a structural diff.

Routing is **read** from the pack, never invented. The triggering set is exactly
``APPROVAL_SENSITIVE_OBJECT_TYPES`` — the same table that already drives
``approval_re_review_required`` — and the required steps are the pack's own declared
``ApprovalStep`` objects in their declared order. Where the pack declares no path
covering an approval-sensitive change, the requirement carries
``NO_APPROVAL_PATH_FOR_CHANGE`` and refuses; a reviewer is never defaulted (P3A-1).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..approval.records import compute_pack_digest
from ..diff.change_impact import APPROVAL_SENSITIVE_OBJECT_TYPES
from ..diff.structural_diff import PolicyPackDiff, diff_policy_packs
from ..models.authority import ApprovalPath, ApprovalStep
from ..models.common import ObjectType
from ..models.policy_pack import PolicyPack
from ..serialization import hashing
from .models import ReviewCode, ReviewRequirement, ReviewStepRequirement


def _sensitive_changes(diff: PolicyPackDiff) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Triggering object ids and change types, both sorted and de-duplicated."""
    ids: List[str] = []
    kinds: List[str] = []
    for change in list(diff.added) + list(diff.removed) + list(diff.changed):
        try:
            otype = ObjectType(change.object_type)
        except ValueError:  # pragma: no cover - defensive
            continue
        if otype not in APPROVAL_SENSITIVE_OBJECT_TYPES:
            continue
        ids.append(change.object_id)
        kinds.extend(change.change_types)
    return tuple(sorted(set(ids))), tuple(sorted(set(kinds)))


def _covering_path(
    pack: PolicyPack, triggering_object_ids: Tuple[str, ...]
) -> Optional[ApprovalPath]:
    """The declared approval path covering these changes, or ``None``.

    Three deterministic rules, in order. None of them invents a route:

    1. A changed object that *is* an approval path is covered by itself.
    2. Otherwise a path covers a change when the path explicitly references the
       changed object through ``related_object_ids``, or the object references the
       path. References are explicit in this object model — there are no implicit
       ones — so this is a lookup, not an inference.
    3. Otherwise, when the pack declares exactly one approval path, that is the only
       declared route and it covers.

    When several paths are declared and none references the change, there is no
    determinate route: the caller gets ``NO_APPROVAL_PATH_FOR_CHANGE`` rather than an
    arbitrarily chosen reviewer.
    """
    paths = {p.object_id: p for p in pack.approval_paths}
    if not paths:
        return None

    for oid in triggering_object_ids:
        if oid in paths:
            return paths[oid]

    index = {o.object_id: o for o in pack.all_objects()}
    for path_id in sorted(paths):
        path = paths[path_id]
        for oid in triggering_object_ids:
            obj = index.get(oid)
            if oid in path.related_object_ids or (
                obj is not None and path_id in obj.related_object_ids
            ):
                return path

    if len(paths) == 1:
        return next(iter(paths.values()))
    return None


def _required_steps(
    pack: PolicyPack, path: ApprovalPath
) -> Tuple[ReviewStepRequirement, ...]:
    """The path's declared steps, ordered by declared ``order`` then step id."""
    steps: Dict[str, ApprovalStep] = {s.object_id: s for s in pack.approval_steps}
    selected = [steps[sid] for sid in path.step_ids if sid in steps]
    selected.sort(key=lambda s: (s.order, s.object_id))
    return tuple(
        ReviewStepRequirement(
            step_id=s.object_id,
            order=s.order,
            authority_requirement_id=s.authority_requirement_id,
            role_label=s.role_label,
            optional=s.optional,
        )
        for s in selected
    )


def _requirement_id(pack_id: str, old_digest: str, new_digest: str, path_id: str) -> str:
    """Content-addressed and deterministic: identical inputs, identical id."""
    frame = hashing.digest(
        {
            "policy_pack_id": pack_id,
            "old_pack_digest": old_digest,
            "new_pack_digest": new_digest,
            "required_approval_path_id": path_id,
        }
    )
    return f"review:{pack_id}:{frame.split(':', 1)[1][:32]}"


def derive_review_requirement(
    old_pack: PolicyPack, new_pack: PolicyPack
) -> ReviewRequirement:
    """Derive what the change from ``old_pack`` to ``new_pack`` obliges.

    Deterministic and provenance-backed: identical packs yield an identical
    requirement, including its id. The compiler decides nothing here — it reports
    what the pack's own declared routing requires.
    """
    diff = diff_policy_packs(old_pack, new_pack)
    old_digest = compute_pack_digest(old_pack)
    new_digest = compute_pack_digest(new_pack)
    review_required = diff.impact.approval_re_review_required
    triggering_ids, triggering_kinds = _sensitive_changes(diff)

    path = _covering_path(new_pack, triggering_ids) if review_required else None
    codes: Tuple[str, ...] = ()
    if review_required and path is None:
        codes = (ReviewCode.NO_APPROVAL_PATH_FOR_CHANGE.value,)

    return ReviewRequirement(
        requirement_id=_requirement_id(
            new_pack.pack_id, old_digest, new_digest, path.object_id if path else ""
        ),
        policy_pack_id=new_pack.pack_id,
        old_pack_digest=old_digest,
        new_pack_digest=new_digest,
        review_required=review_required,
        triggering_object_ids=triggering_ids,
        triggering_change_types=triggering_kinds,
        required_approval_path_id=path.object_id if path else "",
        required_steps=_required_steps(new_pack, path) if path else (),
        segregation_pairs=tuple(path.segregation_pairs) if path else (),
        unresolved_codes=codes,
    )


__all__ = ["derive_review_requirement"]

"""D-4 owner-ratified canonical identifiers for the Cloud Scaling risk boundary.

Phase 4 ADR D-4 recorded these identifiers as *proposed, to be ratified in review*, and
Phase 4B deliberately froze **none** of them into Risk Authority — the seam, the
successor resolver port and the neutral subject context are entirely domain-neutral, and
RA imports no Cloud Scaling type. Ratification therefore lands here, in the Cloud Scaling
adapter that owns the domain vocabulary, and nowhere else.

The ratified identifiers (ADR Amendment 4):

============================  ==========================================
``requested_purpose``         ``cloud_scaling.capacity_action``
``requested_domain``          ``cloud_scaling``
``subject_type``              ``cloud_scaling.capacity_subject``
``action_type`` ∈             ``no_change`` / ``scale_up`` /
                              ``scale_down`` / ``coordinated``
============================  ==========================================

``subject_type`` is the one identifier ratified **differently from the ADR's proposal**,
which suggested reusing ``cloud_scaling.capacity_action`` for both the purpose and the
subject type. It names *what is being evaluated* (a capacity subject), not *why* — and
collapsing the two would have made the routing purpose and the subject identity
indistinguishable in an audit record. Since D-4 was explicitly unratified and Phase 4B
froze none of it, this is a ratification, not a contract change: no frozen schema,
digest or Risk Authority behavior moves. Risk Authority's own v2 conformance fixtures
continue to use their illustrative values and are untouched.

The action-type set is **not** an adapter invention and carries no translation layer: it
is asserted at import time to be exactly the controller's canonical
:class:`~ugence_cloud_scaling_controller.planning.candidates.ActionKind` value set, so a
controller-side addition or rename fails this package closed at import rather than
silently projecting an unmapped action.
"""

from __future__ import annotations

from typing import Final

from ugence_cloud_scaling_controller.planning.candidates import ActionKind

__all__ = [
    "PURPOSE_CAPACITY_ACTION",
    "DOMAIN_CLOUD_SCALING",
    "SUBJECT_TYPE_CAPACITY_SUBJECT",
    "CANONICAL_ACTION_TYPES",
    "canonical_action_type",
]

#: ``requested_purpose`` on the outer v2 request, and the sole member of the minimal
#: ``requested_scope`` (never overloaded with topology or capacity dimensions).
PURPOSE_CAPACITY_ACTION: Final[str] = "cloud_scaling.capacity_action"

#: ``requested_domain`` on the outer v2 request.
DOMAIN_CLOUD_SCALING: Final[str] = "cloud_scaling"

#: ``subject_type`` on the outer v2 request and inside the derived ``SubjectBinding``.
SUBJECT_TYPE_CAPACITY_SUBJECT: Final[str] = "cloud_scaling.capacity_subject"

#: The controller's exact canonical ``ActionKind`` values. No aliases, no translation.
CANONICAL_ACTION_TYPES: Final[frozenset[str]] = frozenset(
    {"no_change", "scale_up", "scale_down", "coordinated"}
)

# Fail closed at import if the controller's canonical enum ever drifts from the ratified
# set. Projecting an unmapped or renamed action kind would put a value into the Risk
# Authority digest chain that D-4 never ratified.
_CONTROLLER_ACTION_TYPES = frozenset(kind.value for kind in ActionKind)
if _CONTROLLER_ACTION_TYPES != CANONICAL_ACTION_TYPES:  # pragma: no cover - drift guard
    raise ImportError(
        "ActionKind drift: the controller's canonical action values "
        f"{sorted(_CONTROLLER_ACTION_TYPES)} are not the D-4 ratified set "
        f"{sorted(CANONICAL_ACTION_TYPES)}; Phase 4C fails closed rather than "
        "projecting an unratified action type"
    )


def canonical_action_type(action_kind: ActionKind) -> str:
    """Return the controller's canonical action-type string for ``action_kind``.

    This is a pass-through of ``ActionKind.value`` guarded by the ratified set — it is
    deliberately **not** a mapping table, because a mapping table is where an alias or a
    silent translation would eventually be introduced.
    """

    if not isinstance(action_kind, ActionKind):
        raise TypeError("action_kind must be a controller ActionKind")
    value = action_kind.value
    if value not in CANONICAL_ACTION_TYPES:  # pragma: no cover - guarded at import
        raise ValueError(f"unratified action type: {value!r}")
    return value

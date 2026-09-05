"""Ugence Cloud Scaling Action Admission — Phase 5C.

**An authorization is admission, not execution.** This package implements Risk Authority's
``ActionGatePort`` for capacity actions and composes it into the ``ActionAdmissionSeam``
(Risk Authority 0.8.0), per ADR 5C decisions D-2 and D-4:

* :func:`capacity_action_to_canonical` — the fixed D-2 mapping: ``actor = envelope.subject``,
  ``model = envelope.model_id``, ``action_type = target_scope.action_type``,
  ``target_id = target_scope.digest()``, ``purpose = cloud_scaling.capacity_action``, and
  no data classes, destination or money;
* :class:`CapacityActionGate` — rules on the presented action against the envelope the
  kernel already verified: the target-scope and candidate bindings re-derived and compared,
  the action type canonical and equal to the scope's, actor and model equal to the
  envelope's, the magnitude ceilings, the required conditions; ``AUTHORIZED`` or ``DENIED``
  only;
* :class:`CloudScalingActionAdmission` — the composition root with fail-closed production
  and reference factories; ``admit`` builds one gate and one seam per act.

What it does **not** do: read a clock; verify a signature, window, revocation or epoch
(D-4 keeps those in the kernel); accept a caller-supplied instant, action, binding or
decision; hold a key; broker a credential (5X); reserve or dispatch execution (5D). Every
outcome reports ``executable`` as a permanently-``False`` property.
"""

from __future__ import annotations

from .composition import (
    CapacityAdmissionOutcome,
    CapacityAdmissionRequest,
    CloudScalingActionAdmission,
)
from .errors import (
    ActionAdmissionConfigurationError,
    ActionAdmissionContractError,
    ActionAdmissionExactTypeError,
    CloudScalingActionAdmissionError,
)
from .gate import CapacityActionGate
from .identifiers import (
    ADMISSION_PROFILE,
    ADMISSION_PROFILE_VERSION,
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_TARGET_SCOPE,
    CANONICAL_ACTION_TYPES,
    PURPOSE_CAPACITY_ACTION,
    REQUIRED_ENVELOPE_BINDINGS,
)
from .mapping import capacity_action_to_canonical, capacity_bounds_violations
from .version import __version__

__all__ = [
    "__version__",
    # --- the composition root and its request/outcome ---
    "CloudScalingActionAdmission",
    "CapacityAdmissionRequest",
    "CapacityAdmissionOutcome",
    # --- the gate the seam calls, and the fixed mapping ---
    "CapacityActionGate",
    "capacity_action_to_canonical",
    "capacity_bounds_violations",
    # --- ratified identifiers ---
    "ADMISSION_PROFILE",
    "ADMISSION_PROFILE_VERSION",
    "REQUIRED_ENVELOPE_BINDINGS",
    "BINDING_KIND_AUTHORIZATION_CANDIDATE",
    "BINDING_KIND_TARGET_SCOPE",
    "CANONICAL_ACTION_TYPES",
    "PURPOSE_CAPACITY_ACTION",
    # --- typed errors ---
    "CloudScalingActionAdmissionError",
    "ActionAdmissionConfigurationError",
    "ActionAdmissionContractError",
    "ActionAdmissionExactTypeError",
]

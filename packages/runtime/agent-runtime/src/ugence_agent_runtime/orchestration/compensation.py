"""H22-D — bounded compensation coordination.

Compensation here is **not** "undo the provider action" — H22-D cannot reverse an arbitrary
external side effect, and it never claims to. Compensation means: *record the intent to schedule
a separately-defined, explicitly-governed workflow that mitigates or reverses an earlier effect*,
exactly once, with provenance back to the workflow it compensates. That compensation workflow is
an **ordinary** workflow — when the application schedules it, it flows through the unchanged
H22-A → TransitionProposal → **fresh governance** → exact-action → provider chain like any other.
There is no bypass and no trust granted merely because it is a correction.

What H22-D does here:

* let the application declare a :class:`CompensationSpec` (which compensation workflow definition
  compensates which origin workflow, and on what trigger) — H22-D never synthesizes prompts,
  models, tools, refund amounts, or rollback payloads;
* register that intent **idempotently**, keyed by a deterministic identity, so a repeated failure
  observation never produces a duplicate compensation registration;
* carry origin lineage (origin workflow / task / trigger / reason) on the registration;
* keep the registrations as durable orchestration state so recovery never re-registers one.

What H22-D does NOT do: call a compensation provider (never — that is an ordinary scheduled
quantum below H22), fabricate that the original effect occurred, or claim the external
compensation is exactly-once. Automatic triggering is deliberately conservative (Section 36):
only an observed workflow/portfolio failure or an explicit operator request, never speculative
per-error compensation, because effect certainty belongs to a later Runtime Assurance phase that
is out of scope here.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple


class CompensationTrigger(str, Enum):
    """The bounded set of reasons a compensation intent may be registered.

    Deliberately conservative: no speculative automatic compensation for every error."""

    #: A specific origin workflow reached terminal FAILED.
    ON_WORKFLOW_FAILURE = "ON_WORKFLOW_FAILURE"
    #: The whole portfolio was driven to terminal FAILED (FAIL_PORTFOLIO).
    ON_PORTFOLIO_FAILURE = "ON_PORTFOLIO_FAILURE"
    #: An operator/application explicitly asked to compensate an origin workflow.
    EXPLICIT_OPERATOR_REQUEST = "EXPLICIT_OPERATOR_REQUEST"


def _compensation_key(origin_instance_id: str, compensation_workflow_id: str, trigger: str) -> str:
    """The deterministic identity of a compensation *intent*.

    One intent = (which origin workflow, which compensation workflow definition, which trigger).
    Repeated observations of the same failure therefore collapse to a single registration."""
    return f"{origin_instance_id}::{compensation_workflow_id}::{trigger}"


@dataclass(frozen=True)
class CompensationSpec:
    """An application-declared compensation intent (externally defined; H22-D fabricates nothing).

    ``origin_instance_id`` is the workflow whose effect may need mitigating;
    ``compensation_workflow_id`` is the ``WorkflowDefinition.workflow_id`` of the *separately
    defined* workflow the application will schedule to compensate it; ``trigger`` is the bounded
    reason; ``origin_task_id`` and ``reason`` are optional provenance. H22-D stores this
    relationship — it never authors the compensation workflow's content."""

    origin_instance_id: str
    compensation_workflow_id: str
    trigger: CompensationTrigger
    origin_task_id: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.origin_instance_id or not isinstance(self.origin_instance_id, str):
            raise ValueError("CompensationSpec.origin_instance_id required")
        if not self.compensation_workflow_id or not isinstance(self.compensation_workflow_id, str):
            raise ValueError("CompensationSpec.compensation_workflow_id required")
        if not isinstance(self.trigger, CompensationTrigger):
            raise ValueError("CompensationSpec.trigger must be a CompensationTrigger")

    @property
    def key(self) -> str:
        return _compensation_key(
            self.origin_instance_id, self.compensation_workflow_id, self.trigger.value
        )


@dataclass(frozen=True)
class CompensationRegistration:
    """The immutable record of one registered compensation intent, with origin lineage.

    ``compensation_key`` is the deterministic idempotency identity. ``lineage`` records the
    causal reference back to the origin workflow/task and the trigger/reason, so the eventual
    compensation workflow's provenance is inspectable without altering Canonical Execution
    State."""

    compensation_key: str
    origin_instance_id: str
    compensation_workflow_id: str
    trigger: str
    origin_task_id: Optional[str] = None
    reason: Optional[str] = None

    @property
    def lineage(self) -> Dict[str, Optional[str]]:
        return {
            "compensates_instance_id": self.origin_instance_id,
            "origin_task_id": self.origin_task_id,
            "trigger": self.trigger,
            "reason": self.reason,
        }

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "compensation_key": self.compensation_key,
            "origin_instance_id": self.origin_instance_id,
            "compensation_workflow_id": self.compensation_workflow_id,
            "trigger": self.trigger,
            "origin_task_id": self.origin_task_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, object]) -> "CompensationRegistration":
        return cls(
            compensation_key=str(d["compensation_key"]),
            origin_instance_id=str(d["origin_instance_id"]),
            compensation_workflow_id=str(d["compensation_workflow_id"]),
            trigger=str(d["trigger"]),
            origin_task_id=d.get("origin_task_id"),  # type: ignore[arg-type]
            reason=d.get("reason"),  # type: ignore[arg-type]
        )


class CompensationRegistry:
    """An idempotent, durable registry of compensation intents for one portfolio.

    Registration is keyed by the deterministic compensation identity, so registering the same
    intent again — a second failure observation, or a recovery replay — is a no-op that returns
    the existing registration. It performs **no execution**: scheduling the compensation workflow
    (prepare → register → ordinary H22-A/B/D quantum → fresh governance → provider) is the
    application's responsibility."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Insertion-ordered for deterministic enumeration.
        self._registrations: Dict[str, CompensationRegistration] = {}

    def register(self, spec: CompensationSpec) -> Tuple[CompensationRegistration, bool]:
        """Register a compensation intent idempotently.

        Returns ``(registration, created)`` — ``created`` is ``True`` only the first time this
        intent's key is seen; a repeat returns the existing registration unchanged and
        ``created=False`` (so a compensation intent is registered **exactly once**)."""
        with self._lock:
            existing = self._registrations.get(spec.key)
            if existing is not None:
                return existing, False
            reg = CompensationRegistration(
                compensation_key=spec.key,
                origin_instance_id=spec.origin_instance_id,
                compensation_workflow_id=spec.compensation_workflow_id,
                trigger=spec.trigger.value,
                origin_task_id=spec.origin_task_id,
                reason=spec.reason,
            )
            self._registrations[spec.key] = reg
            return reg, True

    def is_registered(self, compensation_key: str) -> bool:
        with self._lock:
            return compensation_key in self._registrations

    def registrations(self) -> Tuple[CompensationRegistration, ...]:
        """All registrations, in deterministic (compensation-key sorted) order."""
        with self._lock:
            return tuple(self._registrations[k] for k in sorted(self._registrations))

    def registry_state(self) -> List[Dict[str, object]]:
        """The durable slice for a portfolio checkpoint (sorted for a stable digest)."""
        return [r.to_dict() for r in self.registrations()]

    @classmethod
    def restore(cls, state: object) -> "CompensationRegistry":
        """Rebuild from durable state (a list of registration dicts). Idempotent keys mean a
        recovered registry never double-registers an already-recorded compensation."""
        registry = cls()
        if not state:
            return registry
        with registry._lock:
            for d in state:  # type: ignore[assignment]
                reg = CompensationRegistration.from_dict(d)
                registry._registrations[reg.compensation_key] = reg
        return registry

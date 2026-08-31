"""Neutral Agent Runtime event → :class:`TrajectoryObservation` adapter (spec §17, §22).

RA-7 observes the Agent Runtime through its **existing neutral event seam** — the
optional ``event_sink`` callable that receives a ``RuntimeEvent`` (``.seq`` /
``.type`` / ``.detail``). This adapter converts such an event, plus the authority
**binding context** the caller already holds (which tenant / workflow instance /
envelope / policy the observed run operates under), into a fully-bound
observation.

Critically, this module imports **nothing** from the Agent Runtime: it accepts a
duck-typed event (any object exposing ``seq``, ``type``, and ``detail`` /
``to_dict``). This preserves the ratified boundary — ``agent-runtime`` never
imports Risk Authority, and RA-7 depends only on a *stable data shape*, not on the
runtime package (invariant N8/I11). The runtime event carries only coordination
facts; the authority bindings come from the caller's context, never invented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from .contracts import (
    RUNTIME_ASSURANCE_SCHEMA_VERSION,
    TrajectoryObservation,
    TrajectoryPolicyRef,
)

__all__ = [
    "RuntimeBindingContext",
    "RuntimeEventAdapter",
]


@dataclass(frozen=True)
class RuntimeBindingContext:
    """The authority domain an observed runtime run belongs to.

    Supplied by whoever wires the observer to a specific workflow instance's event
    stream (they already know the envelope under which it runs). The adapter binds
    every produced observation to this domain — it never guesses tenant / envelope
    from event contents.
    """

    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    source: str
    source_version: str
    policy_ref: Optional[TrajectoryPolicyRef] = None


def _event_fields(event: Any) -> tuple[Optional[int], str, Mapping[str, Any]]:
    """Extract ``(seq, type, detail)`` from a duck-typed runtime event."""

    seq = getattr(event, "seq", None)
    etype = getattr(event, "type", None)
    detail = getattr(event, "detail", None)
    if detail is None and hasattr(event, "to_dict"):
        try:
            d = event.to_dict()
            if isinstance(d, Mapping):
                seq = d.get("seq", seq)
                etype = d.get("type", etype)
                detail = d.get("detail", {})
        except Exception:  # noqa: BLE001 - a broken event is simply non-mappable
            detail = None
    if not isinstance(detail, Mapping):
        detail = {}
    if isinstance(seq, bool) or not isinstance(seq, int):
        seq = None
    return seq, (etype if isinstance(etype, str) else ""), detail


class RuntimeEventAdapter:
    """Maps neutral runtime events to bound observations for a single trajectory.

    Stateless apart from the injected binding context and a clock. ``event_id`` is
    derived deterministically from the workflow instance and the event ``seq`` so a
    replayed event dedupes idempotently at the observer (invariant I8). The caller
    supplies ``observed_at`` (or a clock) — the adapter uses no wall clock of its
    own, keeping conversion deterministic.
    """

    def __init__(self, context: RuntimeBindingContext) -> None:
        self._ctx = context

    def to_observation(
        self,
        event: Any,
        *,
        observed_at: datetime,
        action_id: str = "",
        extra_detail: Optional[Mapping[str, Any]] = None,
    ) -> Optional[TrajectoryObservation]:
        """Convert one runtime event to an observation, or ``None`` if unusable.

        A ``None`` return (event with no usable type/seq) is *not* an escalation —
        an unmappable event simply produces no observation.
        """

        seq, etype, detail = _event_fields(event)
        if not etype or seq is None:
            return None
        merged: dict[str, Any] = dict(detail)
        if extra_detail:
            merged.update(extra_detail)
        # Prefer an action/task id carried in the event detail when the caller did
        # not pass one explicitly.
        resolved_action = action_id or _detail_str(detail, "task_id") or _detail_str(
            detail, "action_id"
        )
        ctx = self._ctx
        return TrajectoryObservation(
            schema_version=RUNTIME_ASSURANCE_SCHEMA_VERSION,
            event_id=f"{ctx.workflow_instance_id}:{seq}",
            tenant_id=ctx.tenant_id,
            workflow_instance_id=ctx.workflow_instance_id,
            envelope_id=ctx.envelope_id,
            runtime_event_type=etype,
            observed_at=observed_at,
            source=ctx.source,
            source_version=ctx.source_version,
            action_id=resolved_action,
            sequence_number=seq,
            policy_ref=ctx.policy_ref,
            detail=merged,
        )


def _detail_str(detail: Mapping[str, Any], key: str) -> str:
    val = detail.get(key)
    return val if isinstance(val, str) else ""

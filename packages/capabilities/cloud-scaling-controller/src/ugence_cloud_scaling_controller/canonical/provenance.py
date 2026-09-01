"""First-class, provider-neutral provenance for canonical capacity observations.

Every canonical state records *where its observations came from* and *when*. Provenance
is **evidence, not authority**: the controller never interprets ``source_type`` or
``provider`` as decision logic. The provider label exists so a later reader can trace an
observation to its origin, not so the decision kernel can branch on it.

**The scope of that rule, ratified 2026-09-01** (guard-coverage context; recorded in
ADR_CLOUD_SCALING_CANONICAL_CAPACITY_INTELLIGENCE_PHASE1 §"Ratification: the scope of
provider neutrality"). The prohibition binds the *projection* and the *decision kernel*:
neither may branch on ``provider``, and the projection carries no ``provider == "..."``
test. It does not bind presentation. Code that renders an already-made decision for a
human — a console link, a report, an operator summary — may read ``provider`` to choose
how to display it, because such code cannot change what was decided.

That distinction is enforced structurally, not by convention:
:class:`~..contracts.ScalingObservation`, the decision kernel's sole input, carries
neither a subject nor a provenance record, so no provider value is reachable from the
kernel at all. A reader who finds a ``provider`` branch inside the projection or the
kernel has found a defect regardless of this paragraph.

Two time concepts are kept distinct and must never be conflated:

* ``observed_at`` — when the underlying measurement was taken (caller/source supplied).
* ``collected_at`` — when this provenance/evidence record was produced (optional).

Provenance may apply to a whole :class:`~...state.CanonicalCapacityState` (state-level
default) or to individual measurements (measurement-level overrides keyed by signal
name). When different measurements originate from different sources/windows, the
measurement-level map makes that explicit rather than implying one global record covers
everything. Missing provenance is represented explicitly by
:data:`ObservationSourceType.UNKNOWN`, never silently invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ProvenanceError(ValueError):
    """Raised when a provenance record is malformed or contradictory (fail closed)."""


class ObservationSourceType(str, Enum):
    """Provider-neutral kind of observation source.

    Listing a value here does NOT imply a provider-specific collector ships in this
    package. Phase 1 implements only low-risk sources (fixture / trace replay / an
    adaptation of the existing read-only Prometheus adapter); native cloud collectors
    are future work.
    """

    PROMETHEUS = "prometheus"
    CLOUDWATCH = "cloudwatch"
    AZURE_MONITOR = "azure_monitor"
    GCP_MONITORING = "gcp_monitoring"
    KUBERNETES = "kubernetes"
    FIXTURE = "fixture"
    TRACE_REPLAY = "trace_replay"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


def _require_datetime(name: str, value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise ProvenanceError(f"{name} must be a datetime, got {type(value).__name__}")
    return value


@dataclass(frozen=True)
class ObservationProvenance:
    """Immutable provenance record for an observation (or a single measurement).

    Fields:
        source_type: Provider-neutral source kind (``UNKNOWN`` = provenance missing).
        source_id: Opaque identifier of the concrete source (e.g. a scrape target).
        provider: Provider label (``aws``/``gcp``/``self-hosted``/…). Never a
            *decision* input: the projection and the decision kernel must not branch
            on it, and structurally cannot — ``ScalingObservation`` carries no
            provenance. Presentation code rendering an already-made decision may read
            it (ratified 2026-09-01; see this module's docstring).
        observed_at: When the measurement was taken (required; caller/source supplied).
        collected_at: When this record was produced (optional; distinct from observed).
        metric_window_seconds: Aggregation window of the measurement, if applicable.
    """

    source_type: ObservationSourceType
    observed_at: datetime
    source_id: Optional[str] = None
    provider: Optional[str] = None
    collected_at: Optional[datetime] = None
    metric_window_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_type, ObservationSourceType):
            raise ProvenanceError(f"source_type must be an ObservationSourceType")
        _require_datetime("observed_at", self.observed_at)
        if self.collected_at is not None:
            _require_datetime("collected_at", self.collected_at)
        for name in ("source_id", "provider"):
            v = getattr(self, name)
            if v is not None and not isinstance(v, str):
                raise ProvenanceError(f"{name} must be a string if provided")
        if self.metric_window_seconds is not None:
            if isinstance(self.metric_window_seconds, bool) or not isinstance(
                self.metric_window_seconds, (int, float)
            ):
                raise ProvenanceError("metric_window_seconds must be a real number")
            if self.metric_window_seconds < 0:
                raise ProvenanceError("metric_window_seconds must be >= 0")

    @property
    def is_missing(self) -> bool:
        """True when this record explicitly represents absent provenance."""
        return self.source_type is ObservationSourceType.UNKNOWN

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "provider": self.provider,
            "observed_at": self.observed_at,
            "collected_at": self.collected_at,
            "metric_window_seconds": self.metric_window_seconds,
        }

    @classmethod
    def missing(cls, observed_at: datetime) -> "ObservationProvenance":
        """Explicit 'provenance unknown' record bound to an observation time."""
        return cls(source_type=ObservationSourceType.UNKNOWN, observed_at=observed_at)


__all__ = ["ProvenanceError", "ObservationSourceType", "ObservationProvenance"]

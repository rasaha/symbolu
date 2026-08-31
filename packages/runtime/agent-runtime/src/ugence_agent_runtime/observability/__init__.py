"""Neutral runtime observability (events, tracing, metrics)."""
from __future__ import annotations

from ..models.events import EVENT_TYPES, RuntimeEvent
from .attempts import (
    PROVIDER_USAGE_METADATA_KEY,
    AttemptContext,
    AttemptObservationErrorReporter,
    AttemptObservationFailure,
    AttemptObserver,
    ObservationFailureKind,
    ProviderAttempt,
    ProviderAttemptStatus,
    RecordingAttemptObserver,
    RecordingObservationErrorReporter,
    classify_observation_failure,
)
from .metrics import event_counts
from .tracing import EventSink, RunTrace, format_trace

__all__ = [
    "RuntimeEvent",
    "EVENT_TYPES",
    "RunTrace",
    "EventSink",
    "format_trace",
    "event_counts",
    # attempt telemetry (CM-TA1)
    "ProviderAttempt",
    "ProviderAttemptStatus",
    "AttemptContext",
    "AttemptObserver",
    "RecordingAttemptObserver",
    "PROVIDER_USAGE_METADATA_KEY",
    # attempt-observation failure surfacing (CM-TA1 F2 / N2)
    "AttemptObservationFailure",
    "AttemptObservationErrorReporter",
    "RecordingObservationErrorReporter",
    "ObservationFailureKind",
    "classify_observation_failure",
]

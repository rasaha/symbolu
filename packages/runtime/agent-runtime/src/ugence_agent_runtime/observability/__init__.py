"""Neutral runtime observability (events, tracing, metrics)."""
from __future__ import annotations

from ..models.events import EVENT_TYPES, RuntimeEvent
from .attempts import (
    PROVIDER_USAGE_METADATA_KEY,
    AttemptContext,
    AttemptObserver,
    ProviderAttempt,
    ProviderAttemptStatus,
    RecordingAttemptObserver,
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
]

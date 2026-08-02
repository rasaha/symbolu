"""Neutral provider/tool execution boundary.

A provider executes a runtime-requested operation *after* all required runtime and
external governance checks have completed. The runtime treats the provider as
opaque: it hands over a neutral invocation and consumes a neutral result. The
runtime embeds no vendor-specific behavior (no OpenAI, Anthropic, GitHub, cloud, or
database specifics) — those belong in concrete provider implementations that live
in separate packages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolInvocation:
    """A neutral request to execute one operation via a provider."""

    provider_id: str
    operation: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """A neutral provider execution result.

    ``ok`` distinguishes an expected failure from success; ``failure_category`` is a
    neutral classification string the runtime folds into its own taxonomy. ``output``
    is opaque to the runtime and is never reinterpreted.
    """

    provider_id: str
    operation: str
    ok: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    failure_category: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """The neutral contract a concrete provider satisfies."""

    provider_id: str
    version: str

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        ...

"""Conformance-kit fixture protocol and lifecycle-outcome capture.

A consuming domain adapts itself to the reusable conformance kit by providing a
:class:`DomainConformanceFixture`: how to build its platform, how to run one full
governance lifecycle on it, and which platform attributes should be kernel
services/repositories. The kit then runs a domain-agnostic battery of checks
against the captured :class:`LifecycleOutcome`.

The same kit validates every consuming domain without modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from ..audit import AuditEvent
from ..base import DomainModel


@dataclass(frozen=True)
class LifecycleOutcome:
    """The result of running one full governance lifecycle on a domain platform.

    * ``audit_events`` — every event written during the run (kernel governance
      events);
    * ``reconciliation_status`` — the terminal reconciliation status value;
    * ``records`` — the kernel governance records produced (decision, action
      request, execution/reconciliation records) for serialization/hash checks;
    * ``audit_repository`` — the sink the run wrote to (so checks can re-read).
    """

    audit_events: tuple[AuditEvent, ...]
    reconciliation_status: str
    records: tuple[DomainModel, ...] = ()
    audit_repository: Any = None


@runtime_checkable
class DomainConformanceFixture(Protocol):
    """What a domain must provide for the conformance kit to validate it."""

    #: Human-readable domain name (e.g. the domain's package label).
    name: str

    def build_platform(self) -> Any:
        """Construct and return a fully-wired domain platform."""

    def run_lifecycle(self, platform: Any) -> LifecycleOutcome:
        """Drive one complete governance lifecycle and capture the outcome."""

    def expected_service_types(self) -> Mapping[str, type]:
        """Platform attribute name → the kernel service class it must be."""

    def expected_repository_types(self) -> Mapping[str, type]:
        """Platform attribute name → the kernel repository class it must be."""


@dataclass
class SimpleFixture:
    """A convenience concrete fixture built from callables and type maps."""

    name: str
    _build: Any
    _run: Any
    _service_types: Mapping[str, type] = field(default_factory=dict)
    _repo_types: Mapping[str, type] = field(default_factory=dict)

    def build_platform(self) -> Any:
        return self._build()

    def run_lifecycle(self, platform: Any) -> LifecycleOutcome:
        return self._run(platform)

    def expected_service_types(self) -> Mapping[str, type]:
        return self._service_types

    def expected_repository_types(self) -> Mapping[str, type]:
        return self._repo_types

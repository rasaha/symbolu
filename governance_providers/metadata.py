"""Provider metadata and descriptors (immutable).

Describes *what a provider is* so the registry can register, discover, and
version-check it, and the resolver can select it — independent of any concrete
implementation. The three provider kinds are peers and are **not**
interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .lifecycle import ProviderLifecycleState


class ProviderKind(str, Enum):
    """A governance capability family. Peers — never conflated.

    * ``ASSERTION_GOVERNANCE`` — evaluate an assertion against evidence
      (future: TAP); integrates into assessment/recommendation.
    * ``ACTION_GOVERNANCE`` — authorize a prepared action (future: ActionGate);
      adapts onto ``ActionControlPlanePort``.
    * ``EXTERNAL_EXECUTION`` — dispatch to / observe an external system; adapts
      onto ``ExternalExecutionPort``. Distinct from assertion governance.
    """

    ASSERTION_GOVERNANCE = "ASSERTION_GOVERNANCE"
    ACTION_GOVERNANCE = "ACTION_GOVERNANCE"
    EXTERNAL_EXECUTION = "EXTERNAL_EXECUTION"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities. ``features`` are free-form tags a resolver matches."""

    kind: ProviderKind
    features: frozenset[str] = frozenset()
    deterministic: bool = False

    def supports_feature(self, feature: str) -> bool:
        return feature in self.features


@dataclass(frozen=True)
class ProviderCompatibility:
    """Versioning surface used for compatibility validation at registration."""

    contract_version: str
    #: kernel versions this provider's adapter is built against (majors as strings)
    compatible_kernel_majors: frozenset[str] = frozenset({"1"})
    config_schema_version: str = "1"


@dataclass(frozen=True)
class ProviderHealth:
    state: ProviderLifecycleState
    healthy: bool
    detail: str = ""


@dataclass(frozen=True)
class ProviderDescriptor:
    """Everything the registry needs to register, describe, and build a provider."""

    provider_id: str
    kind: ProviderKind
    implementation_version: str
    compatibility: ProviderCompatibility
    capabilities: ProviderCapabilities
    #: zero-arg callable returning a provider instance (registry owns instantiation)
    factory: Callable[[], object]
    vendor: str = ""
    default: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def contract_version(self) -> str:
        return self.compatibility.contract_version

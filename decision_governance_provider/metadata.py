"""Provider metadata & capabilities (application layer).

Describes *what a provider is* — independent of any concrete implementation — so
the registry can register, discover, and version-check providers, and the
resolver can select them by kind or capability. None of these reference a
specific provider (no TAP, no ActionGate); they are the neutral description model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProviderKind(str, Enum):
    """The governance capability a provider supplies.

    Each kind is adapted onto exactly one kernel port (see the adapters package):

    * ``ASSERTION``      → ``LinkedRecordPort`` (resolve a finalized upstream record)
    * ``AUTHORIZATION``  → ``ActionControlPlanePort`` (authorize a prepared action)
    * ``EXECUTION``      → ``ExternalExecutionPort`` (dispatch to / observe a system)
    """

    ASSERTION = "ASSERTION"
    AUTHORIZATION = "AUTHORIZATION"
    EXECUTION = "EXECUTION"


@dataclass(frozen=True)
class ProviderCapabilities:
    """The declared capabilities of a provider.

    ``features`` are free-form capability tags a resolver can match on (e.g.
    ``"constraints"``, ``"callbacks"``). ``supported_action_types`` empty means
    "all". ``deterministic`` marks providers safe for reproducible tests.
    """

    kind: ProviderKind
    features: frozenset[str] = frozenset()
    supported_action_types: frozenset[str] = frozenset()
    deterministic: bool = False

    def supports_feature(self, feature: str) -> bool:
        return feature in self.features

    def supports_action_type(self, action_type: str) -> bool:
        return not self.supported_action_types or action_type in self.supported_action_types


@dataclass(frozen=True)
class ProviderMetadata:
    """Identity and versioning of a provider."""

    name: str
    version: str
    kind: ProviderKind
    #: The kernel version whose ports this provider is built against (e.g. "1.0.0").
    kernel_port_version: str
    description: str = ""
    vendor: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)

"""Provider Framework version & kernel compatibility.

The Provider Framework is an **application-layer** component that sits above the
Decision Governance kernel (``decision_governance``) and lets applications consume
external governance capabilities (assertion, authorization, execution providers)
without importing any specific implementation.

It is versioned independently of the kernel. It declares which kernel major
version it targets; a provider registered against an incompatible kernel major is
rejected.
"""

from __future__ import annotations

__version__ = "0.1.0"

VERSION = __version__
VERSION_INFO: tuple[int, int, int] = tuple(int(p) for p in __version__.split("."))  # type: ignore[assignment]

#: The kernel major version this framework (and the providers it manages) targets.
TARGET_KERNEL_MAJOR = 1


def kernel_major(version: str) -> int:
    """The major component of a semantic version string."""
    return int(version.split(".")[0])


def is_kernel_compatible(provider_kernel_version: str) -> bool:
    """A provider is compatible when it targets the same kernel major version."""
    return kernel_major(provider_kernel_version) == TARGET_KERNEL_MAJOR

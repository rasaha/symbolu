"""Governance Provider Framework — version & kernel compatibility.

An **application-layer** framework, above the Decision Governance kernel, that
lets applications plug in specialized governance capabilities as interchangeable
peer providers. It is versioned independently of the kernel and declares which
kernel major version its adapters target.

The framework hosts three *distinct, non-interchangeable* provider families:

* **Assertion governance** (future: TAP) — evaluate whether an assertion is
  supported by evidence; integrates into the assessment/recommendation workflow.
* **Action governance** (future: ActionGate) — authorize a prepared action;
  adapts onto the kernel ``ActionControlPlanePort``.
* **External execution** — dispatch to and observe an external system; adapts
  onto the kernel ``ExternalExecutionPort``.

Assertion governance is **not** external execution and is never routed through
the execution port.
"""

from __future__ import annotations

__version__ = "0.1.0"

VERSION = __version__
VERSION_INFO: tuple[int, int, int] = tuple(int(p) for p in __version__.split("."))  # type: ignore[assignment]

#: The provider-contract version this framework publishes.
CONTRACT_VERSION = "1.0.0"

#: The kernel major version this framework's adapters target.
TARGET_KERNEL_MAJOR = 1


def major_of(version: str) -> int:
    return int(version.split(".")[0])


def is_kernel_compatible(kernel_version: str) -> bool:
    """A provider's declared kernel target is compatible on matching major."""
    return major_of(kernel_version) == TARGET_KERNEL_MAJOR


def is_contract_compatible(contract_version: str) -> bool:
    """A provider's contract version is compatible on matching major."""
    return major_of(contract_version) == major_of(CONTRACT_VERSION)

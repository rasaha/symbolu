"""Typed errors: configuration and contract faults, never verdicts."""

from __future__ import annotations

__all__ = [
    "CloudScalingBoundedExecutionError",
    "BoundedExecutionConfigurationError",
    "BoundedExecutionContractError",
    "BoundedExecutionExactTypeError",
    "BarePolicyRollbackRefused",
]


class CloudScalingBoundedExecutionError(Exception):
    """Base class for every error this package raises."""


class BoundedExecutionConfigurationError(CloudScalingBoundedExecutionError):
    """The seam was built over something it may not stand on."""


class BoundedExecutionContractError(CloudScalingBoundedExecutionError):
    """An input violated the contract in a way no outcome can express."""


class BoundedExecutionExactTypeError(BoundedExecutionContractError):
    """An input was not the exact type the boundary admits; subclasses are refused."""


class BarePolicyRollbackRefused(CloudScalingBoundedExecutionError):
    """A rollback was requested on a bare policy; rollback is a second bounded action (D-4)."""

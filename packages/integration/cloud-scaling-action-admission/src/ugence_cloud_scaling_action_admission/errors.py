"""Typed errors: programming and configuration faults, never verdicts.

A denied action is an answer and travels as an ``ActionAuthorization`` with
``decision = DENIED``. These exceptions are raised only where continuing would mean
composing the wrong thing.
"""

from __future__ import annotations

__all__ = [
    "CloudScalingActionAdmissionError",
    "ActionAdmissionConfigurationError",
    "ActionAdmissionContractError",
    "ActionAdmissionExactTypeError",
]


class CloudScalingActionAdmissionError(Exception):
    """Base class for every error this package raises."""


class ActionAdmissionConfigurationError(CloudScalingActionAdmissionError):
    """The composition root was built over something it may not stand on."""


class ActionAdmissionContractError(CloudScalingActionAdmissionError):
    """An input violated the contract in a way no verdict can express."""


class ActionAdmissionExactTypeError(ActionAdmissionContractError):
    """An input was not the exact type the boundary admits; subclasses are refused."""

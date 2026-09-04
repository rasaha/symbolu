"""Typed errors: configuration and contract faults, never verdicts."""

from __future__ import annotations

__all__ = [
    "CloudScalingCredentialBrokerError",
    "CredentialBrokerConfigurationError",
    "CredentialBrokerContractError",
    "CredentialBrokerExactTypeError",
    "CredentialRequestRefused",
]


class CloudScalingCredentialBrokerError(Exception):
    """Base class for every error this package raises."""


class CredentialBrokerConfigurationError(CloudScalingCredentialBrokerError):
    """The composition root was built over something it may not stand on."""


class CredentialBrokerContractError(CloudScalingCredentialBrokerError):
    """An input violated the contract in a way no outcome can express."""


class CredentialBrokerExactTypeError(CredentialBrokerContractError):
    """An input was not the exact type the boundary admits; subclasses are refused."""


class CredentialRequestRefused(CloudScalingCredentialBrokerError):
    """The minter refused to mint a request; carries the typed refusal for the seam."""

    def __init__(self, refusal: object, detail: str) -> None:
        super().__init__(detail)
        self.refusal = refusal
        self.detail = detail

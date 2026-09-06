"""Typed errors. A contract refuses its input by raising one of these at
construction; the verification seam never raises them past itself — it returns
a typed refusal instead (see :mod:`.verification`)."""

from __future__ import annotations

__all__ = [
    "EffectAttestationError",
    "EffectAttestationContractError",
    "EffectAttestationSigningBoundaryError",
    "EffectAttestationConfigurationError",
]


class EffectAttestationError(Exception):
    """Base of every error this package raises."""


class EffectAttestationContractError(EffectAttestationError, ValueError):
    """A contract refused its input: wrong exact type, malformed field, or a
    representation this package will not repair."""


class EffectAttestationSigningBoundaryError(EffectAttestationContractError):
    """A signer was asked to sign for coordinates it does not hold, or a
    reference signer was requested where production was declared."""


class EffectAttestationConfigurationError(EffectAttestationError):
    """A verifier was composed with a missing, reference-grade or otherwise
    inadmissible collaborator under the declared posture."""

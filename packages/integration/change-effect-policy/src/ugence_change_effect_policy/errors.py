"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class ChangeEffectPolicyError(Exception):
    """Base class for every error this package raises."""


class ChangeEffectPolicyFieldError(ChangeEffectPolicyError, ValueError):
    """A caller supplied a structurally invalid or mismatched field."""


class DelegationEntryRefused(ChangeEffectPolicyError, ValueError):
    """A delegation entry was offered. Stage 1 ships none, active or otherwise.

    The owner's ruling of 2026-09-13: the initial table is **empty**, not populated
    with inactive entries. D1, D3, D4 and D5 and their parameters, predicates and
    anticipated structures are outside Stage 1 and require separate review and
    activation. There is deliberately no entry type in this package to offer.
    """


class MappingCoordinateRefused(ChangeEffectPolicyError, ValueError):
    """A mapping coordinate was a sentinel, a placeholder or a fabrication.

    A coordinate that names nothing real is worse than an absent one: absence is
    visible and blocks an operative lifecycle state, while a placeholder would look
    like a governed reference and would pass every check that only tests presence.
    """


class OperativeWithoutMappingRefused(ChangeEffectPolicyError, ValueError):
    """An artifact without a valid mapping coordinate cannot become operative.

    Ruling 6. It supports no COMPLETED closure either, because the closure's bundle
    is derived by a mapping this artifact does not name.
    """

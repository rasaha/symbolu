"""Typed construction errors for the strategy-permission policy family.

Every failure is fail-closed: no ``StrategyPermissionPolicy`` is produced. A
malformed artifact never reaches the authority, and one that somehow does is
refused again by the adapter.

`[R]` **None of these names, and no message any of them carries, emits a denial,
an abstention, a reserved authority term, a terminal outcome or a candidate
disposition.** They name construction and identity facts only. Which component
maps a structural permission failure to an operational outcome is deliberately
unruled (`S2B-D5=A`), and nothing here maps one.
"""

from __future__ import annotations

__all__ = [
    "StrategyPermissionPolicyError",
    "StrategyPermissionFieldError",
    "StrategyPermissionOrderingError",
    "StrategyPermissionDuplicateError",
]


class StrategyPermissionPolicyError(Exception):
    """Root of this family's error taxonomy."""


class StrategyPermissionFieldError(StrategyPermissionPolicyError):
    """A field is absent, of the wrong exact type, or outside its admitted domain."""


class StrategyPermissionOrderingError(StrategyPermissionPolicyError):
    """A declared ordering is violated: the permitted set, or the effective interval."""


class StrategyPermissionDuplicateError(StrategyPermissionPolicyError):
    """The permitted set names one strategy twice, so its membership is ambiguous."""

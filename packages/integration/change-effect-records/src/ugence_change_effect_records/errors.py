"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class ChangeEffectRecordsError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(ChangeEffectRecordsError, ValueError):
    """A caller supplied structurally invalid or mismatched input.

    A blank reference, a wrong type, a naive datetime, a digest that is not a full
    lowercase SHA-256, a chosen rather than derived identifier, or a payload the
    canonical-bytes profile refuses.
    """


class CanonicalFormRefused(ContractViolation):
    """A payload violates the canonical-bytes profile of rule section 6a.

    A null, a JSON boolean, a float, an out-of-range integer or an unencodable type.
    The refusal carries the profile's own code so a caller can distinguish them.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail

"""Canonicalization error taxonomy.

The minimum error surface the JCS + Action-Profile canonicalizer needs, extracted
verbatim (names, categories, ``path`` attribute) from the CER V0.3 clean-room
taxonomy so that consumers observe identical failure classes after extraction.

Each error carries a stable ``category`` string: the portable comparison key used
by differential-conformance runners, which compare *error classes* across
implementations without depending on either implementation's exception types.

These are canonicalization faults only. This package raises no policy, authority,
authorization, clearance or decision error, and defines no such vocabulary.
"""
from __future__ import annotations


class JcsError(Exception):
    """Base class. ``category`` is the portable comparison key."""
    category = "error"

    def __init__(self, message: str, *, path: str = ""):
        super().__init__(message)
        self.path = path


class BareNumberError(JcsError):
    category = "E_BARE_NUMBER"


class NonFiniteNumberError(JcsError):
    category = "E_NAN_INF"


class NonNFCError(JcsError):
    category = "E_NON_NFC"


class UnsupportedTypeError(JcsError):
    category = "E_UNSUPPORTED_TYPE"


class DuplicateSetElementError(JcsError):
    category = "E_DUPLICATE_SET_ELEMENT"


__all__ = [
    "JcsError",
    "BareNumberError",
    "NonFiniteNumberError",
    "NonNFCError",
    "UnsupportedTypeError",
    "DuplicateSetElementError",
]

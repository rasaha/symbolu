"""ugence-jcs — RFC 8785 (JCS) + Action-Profile canonicalization.

An independently installable, standard-library-only, authority-neutral leaf
distribution. It produces canonical bytes for an already-parsed JSON value and
nothing else: no digesting scheme, no envelope schema, no profile registry, no
policy, and no authority vocabulary.

Extracted from ``cer_v0_3/cleanroom/canon.py`` with its byte stream preserved
exactly; the CER V0.3 clean-room package now consumes this distribution, and the
frozen CER V0.2 identity digests remain reproducible through it.

Public surface:
    canonical_string(value, set_paths=..., nfc_paths=...) -> str
    canonical_bytes(value, set_paths=..., nfc_paths=...)  -> bytes
    canonical_sha256_hex(value, set_paths=..., nfc_paths=...) -> str
    JcsError and its canonicalization subclasses
"""
from __future__ import annotations

from .canon import canonical_bytes, canonical_sha256_hex, canonical_string
from .errors import (
    BareNumberError,
    DuplicateSetElementError,
    JcsError,
    NonFiniteNumberError,
    NonNFCError,
    UnsupportedTypeError,
)
from .version import __version__

__all__ = [
    "canonical_string",
    "canonical_bytes",
    "canonical_sha256_hex",
    "JcsError",
    "BareNumberError",
    "NonFiniteNumberError",
    "NonNFCError",
    "UnsupportedTypeError",
    "DuplicateSetElementError",
    "__version__",
]

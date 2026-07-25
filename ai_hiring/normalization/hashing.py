"""Deterministic content hashing.

Two hashes are maintained per evidence version:

* ``raw_hash`` — SHA-256 over the exact raw submission bytes. Identical raw
  content always yields the same ``raw_hash`` (used for duplicate detection).
* ``normalized_hash`` — SHA-256 over the normalized text. Two submissions that
  differ only in whitespace/encoding transport artifacts converge to the same
  ``normalized_hash`` while keeping distinct ``raw_hash`` values.
"""

from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_hash(content: bytes) -> str:
    """Hash the exact raw bytes of a submission."""
    return sha256_hex(content)


def normalized_hash(normalized_text: str) -> str:
    """Hash the normalized text (UTF-8)."""
    return sha256_hex(normalized_text.encode("utf-8"))


def chunk_hash(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))

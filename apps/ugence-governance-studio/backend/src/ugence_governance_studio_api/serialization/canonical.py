"""Canonical JSON serialization for API presentation only (§19).

This module NEVER re-canonicalizes AWC objects in a way that changes their
meaning or fingerprints. It only mirrors the exact ``model_dump(mode="json")``
projection the AWC fixture generator uses, and provides a byte-stable
``sort_keys`` encoding for export bundles and digesting. AWC result fields are
passed through intact; result fingerprints are computed by AWC, never here.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Convert an AWC model (or list/tuple of models) into plain JSON types.

    Mirrors ``generate_fixtures._to_jsonable`` so serialized artifacts match the
    frozen expected outputs byte-for-byte.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def canonical_bytes(obj: Any) -> bytes:
    """Byte-stable canonical encoding (sorted keys, 2-space indent, trailing
    newline) — identical to the fixture generator's ``_canonical_bytes``."""
    text = json.dumps(to_jsonable(obj), sort_keys=True, indent=2, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def canonical_digest(obj: Any) -> str:
    """sha256 of the canonical encoding, prefixed to match AWC digest style."""
    return "sha256:" + hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

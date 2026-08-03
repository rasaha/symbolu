"""Deterministic fingerprints and content-addressing helpers.

Every canonical object carries a content fingerprint over its own fields; every
eligibility result and adaptation carries a fingerprint over its logical content.
All fingerprints are ``sha256:<hex>`` over canonical JSON (see :mod:`canonical`),
so they are byte-stable across processes and Python builds. Fingerprinting adds
no behaviour — it hashes an already-produced record.
"""
from __future__ import annotations

from typing import Mapping

from .canonical import AwcModel, digest, to_canonical_obj


def fingerprint(payload: Mapping[str, object]) -> str:
    """Stable ``sha256:<hex>`` over the canonical JSON of ``payload``.

    Accepts any JSON-native mapping (e.g. a result's ``to_dict()``). Adds no new
    behaviour — it hashes an already-produced record for audit and replay.
    """
    return digest(payload)


def stamp_fingerprint(model: AwcModel, field: str) -> AwcModel:
    """Return a copy of ``model`` with ``field`` set to the content digest of the
    object computed **excluding** ``field`` itself.

    Deterministic: the excluded field's prior value never affects the digest, so
    stamping is idempotent and independent of any placeholder value.
    """
    data = to_canonical_obj(model)
    if not isinstance(data, dict):  # pragma: no cover - defensive
        raise TypeError("stamp_fingerprint requires a model serializing to an object")
    data.pop(field, None)
    return model.model_copy(update={field: digest(data)})


__all__ = ["fingerprint", "stamp_fingerprint"]

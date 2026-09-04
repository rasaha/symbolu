"""Record and artifact codecs for the durable registry (ADR §15.7).

The core stores three record shapes and one opaque policy artifact per issuance.
Records are family-agnostic and are encoded and decoded **here**; the artifact
is family-owned, so the core only defines the :class:`PolicyArtifactCodec` port
and the adapter layer supplies the implementation. Encoding reuses the package's
one canonical encoder, so the stored form of an artifact is byte-for-byte the
structure its body digest was computed over.

:func:`decode_dataclass` is a generic, annotation-driven decoder for frozen
dataclasses built from ``str``, ``int``, ``bool``, aware ``datetime``, ``Enum``,
``Optional``, ``tuple[...]`` and nested dataclasses — exactly the vocabulary the
canonical encoder accepts. It is deliberately strict: an unexpected key, a
missing required field, or a value of the wrong shape is a
:class:`PolicyRegistryStorageError`, never a best-effort guess. Rehydrating a
record runs the target dataclass's own ``__post_init__`` validation, so a stored
value the contracts would refuse at construction is refused on read.
"""

from __future__ import annotations

import base64
import dataclasses
import typing
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from .adapters import PolicyCoordinate
from .canonical import _TIMESTAMP_FMT, to_canonical_obj
from .errors import PolicyAuthorityError, PolicyRegistryStorageError
from .records import (
    IssuedPolicyRecord,
    PolicyRevocationRecord,
    PolicySupersessionRecord,
)
from .statuses import PolicyRevocationReasonCode

__all__ = [
    "PolicyArtifactCodec",
    "decode_dataclass",
    "parse_canonical_datetime",
    "encode_issued_record",
    "decode_issued_record",
    "encode_revocation_record",
    "decode_revocation_record",
    "encode_supersession_record",
    "decode_supersession_record",
]


@runtime_checkable
class PolicyArtifactCodec(Protocol):
    """Family-owned (de)serialization of the opaque ``IssuedPolicyRecord.policy``."""

    def encode(self, policy: object) -> Any:
        """The canonical structure of ``policy`` (what its digest was computed over)."""
        ...

    def decode(self, *, adapter_id: str, policy_type: str, canonical: Any) -> object:
        """Rebuild the exact runtime artifact, or raise a ``PolicyAuthorityError``."""
        ...


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def parse_canonical_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise PolicyRegistryStorageError(f"{path}: expected a canonical timestamp string")
    try:
        return datetime.strptime(value, _TIMESTAMP_FMT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PolicyRegistryStorageError(f"{path}: malformed canonical timestamp") from exc


def _decode_bytes(value: object, path: str) -> bytes:
    if not isinstance(value, str):
        raise PolicyRegistryStorageError(f"{path}: expected base64url text")
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise PolicyRegistryStorageError(f"{path}: malformed base64url") from exc


def _decode_value(value: Any, hint: Any, path: str) -> Any:
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)

    if hint is Any:
        return value
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if value is None and len(non_none) < len(args):
            return None
        if len(non_none) == 1:
            return _decode_value(value, non_none[0], path)
        raise PolicyRegistryStorageError(f"{path}: unsupported union annotation")
    if origin in (tuple, list):
        if not isinstance(value, list):
            raise PolicyRegistryStorageError(f"{path}: expected a list")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_value(v, args[0], f"{path}[{i}]") for i, v in enumerate(value))
        if args and len(args) == len(value):
            return tuple(_decode_value(v, a, f"{path}[{i}]") for i, (v, a) in enumerate(zip(value, args)))
        return tuple(value)
    if isinstance(hint, type):
        if issubclass(hint, bool):
            if not isinstance(value, bool):
                raise PolicyRegistryStorageError(f"{path}: expected a bool")
            return value
        if issubclass(hint, Enum):
            try:
                return hint(value)
            except ValueError as exc:
                raise PolicyRegistryStorageError(f"{path}: {value!r} is not a {hint.__name__}") from exc
        if issubclass(hint, datetime):
            return parse_canonical_datetime(value, path)
        if hint is bytes:
            return _decode_bytes(value, path)
        if hint is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise PolicyRegistryStorageError(f"{path}: expected an int")
            return value
        if hint is str:
            if not isinstance(value, str):
                raise PolicyRegistryStorageError(f"{path}: expected a string")
            return value
        if dataclasses.is_dataclass(hint):
            return decode_dataclass(hint, value, path=path)
    raise PolicyRegistryStorageError(f"{path}: annotation {hint!r} is not decodable")


def decode_dataclass(cls: type, value: Any, *, path: str = "$") -> Any:
    """Rebuild ``cls`` from its canonical structure, strictly."""

    if not (isinstance(cls, type) and dataclasses.is_dataclass(cls)):
        raise PolicyRegistryStorageError(f"{path}: {cls!r} is not a dataclass")
    if not isinstance(value, dict):
        raise PolicyRegistryStorageError(f"{path}: expected an object for {cls.__name__}")
    hints = typing.get_type_hints(cls)
    known = {f.name: f for f in dataclasses.fields(cls) if f.init}
    unexpected = set(value) - set(known)
    if unexpected:
        raise PolicyRegistryStorageError(
            f"{path}: unexpected fields for {cls.__name__}: {sorted(unexpected)}")
    kwargs: dict[str, Any] = {}
    for name, f in known.items():
        if name not in value:
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                raise PolicyRegistryStorageError(f"{path}.{name}: required field missing")
            continue
        kwargs[name] = _decode_value(value[name], hints.get(name, Any), f"{path}.{name}")
    try:
        return cls(**kwargs)
    except PolicyRegistryStorageError:
        raise
    except Exception as exc:  # the target's own validation refused the stored value
        raise PolicyRegistryStorageError(f"{path}: {cls.__name__} refused stored value: {exc}") from exc


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
def encode_issued_record(record: IssuedPolicyRecord, codec: PolicyArtifactCodec) -> dict:
    encoded = to_canonical_obj(
        {f.name: getattr(record, f.name) for f in dataclasses.fields(record) if f.name != "policy"}
    )
    encoded["policy"] = codec.encode(record.policy)
    return encoded


def decode_issued_record(value: Any, codec: PolicyArtifactCodec, *, path: str = "$") -> IssuedPolicyRecord:
    if not isinstance(value, dict):
        raise PolicyRegistryStorageError(f"{path}: expected an issuance object")
    body = dict(value)
    canonical_policy = body.pop("policy", None)
    if canonical_policy is None:
        raise PolicyRegistryStorageError(f"{path}.policy: missing stored artifact")
    try:
        policy = codec.decode(adapter_id=body.get("adapter_id", ""),
                              policy_type=body.get("policy_type", ""), canonical=canonical_policy)
    except PolicyRegistryStorageError:
        raise
    except PolicyAuthorityError as exc:
        raise PolicyRegistryStorageError(
            f"{path}.policy: configured codec cannot rehydrate the stored artifact: {exc}") from exc
    hints = typing.get_type_hints(IssuedPolicyRecord)
    kwargs = {}
    for f in dataclasses.fields(IssuedPolicyRecord):
        if f.name == "policy":
            continue
        if f.name not in body:
            raise PolicyRegistryStorageError(f"{path}.{f.name}: required field missing")
        kwargs[f.name] = _decode_value(body[f.name], hints[f.name], f"{path}.{f.name}")
    return IssuedPolicyRecord(policy=policy, **kwargs)


def encode_revocation_record(record: PolicyRevocationRecord) -> dict:
    return to_canonical_obj(record)


def decode_revocation_record(value: Any, *, path: str = "$") -> PolicyRevocationRecord:
    record = decode_dataclass(PolicyRevocationRecord, value, path=path)
    if not isinstance(record.reason_code, PolicyRevocationReasonCode):
        raise PolicyRegistryStorageError(f"{path}.reason_code: not a revocation reason")
    return record


def encode_supersession_record(record: PolicySupersessionRecord) -> dict:
    return to_canonical_obj(record)


def decode_supersession_record(value: Any, *, path: str = "$") -> PolicySupersessionRecord:
    return decode_dataclass(PolicySupersessionRecord, value, path=path)


def coordinate_key(coordinate: PolicyCoordinate) -> str:
    """Deterministic storage key for one exact coordinate."""

    from .canonical import canonical_dumps

    return canonical_dumps(coordinate)


def identity_slot_key(coordinate: PolicyCoordinate) -> str:
    from .canonical import canonical_dumps

    return canonical_dumps(list(coordinate.identity_slot))


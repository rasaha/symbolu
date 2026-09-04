"""Strict, annotation-driven codec for the durable store (ADR durable persistence, D-2).

Encoding is the package's one canonical encoder, :func:`to_canonical_obj`, so the stored
form of a record is byte-for-byte the structure its digests were computed over. Decoding
is the inverse, driven by the target dataclass's own annotations: ``str``, ``int``,
``bool``, aware ``datetime``, ``bytes``, ``Enum``, ``Optional``, ``tuple[...]``,
``Mapping[str, str]`` and nested dataclasses — exactly the vocabulary the encoder emits.
It is deliberately strict: an unexpected key, a missing required field or a value of the
wrong shape is a :class:`PersistenceStorageError`, never a best-effort guess, and
rehydrating a record runs the target's own ``__post_init__`` so a stored value the domain
would refuse at construction is refused on read.

The shape mirrors Policy Authority's ``core/codec.py`` and imports nothing from it: Risk
Authority is a leaf and stays one.

Two records need more than the generic decoder. The envelope's signature is a
non-canonical field, so it is stored **beside** the canonical body and re-attached on
read. A case is a mutable aggregate, so it is stored as its
:class:`~risk_authority.domain.risk_case.RiskCaseSnapshot` and rebuilt through
:meth:`RiskDecisionCase.from_snapshot`, which replays and chain-checks its events.
"""

from __future__ import annotations

import base64
import collections.abc
import dataclasses
import typing
from dataclasses import replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..crypto.canonical import _TIMESTAMP_FMT, to_canonical_obj
from ..domain.envelope import RiskAuthorizationEnvelope
from ..domain.errors import RiskAuthorityError
from ..domain.risk_case import RiskCaseSnapshot, RiskDecisionCase
from .errors import PersistenceStorageError

__all__ = [
    "decode_dataclass",
    "parse_canonical_datetime",
    "encode_record",
    "decode_record",
    "encode_envelope",
    "decode_envelope",
    "encode_case",
    "decode_case",
]


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #
def parse_canonical_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise PersistenceStorageError(f"{path}: expected a canonical timestamp string")
    try:
        return datetime.strptime(value, _TIMESTAMP_FMT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PersistenceStorageError(f"{path}: malformed canonical timestamp") from exc


def _decode_bytes(value: object, path: str) -> bytes:
    if not isinstance(value, str):
        raise PersistenceStorageError(f"{path}: expected base64url text")
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise PersistenceStorageError(f"{path}: malformed base64url") from exc


def _encode_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


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
        raise PersistenceStorageError(f"{path}: unsupported union annotation")
    if origin in (tuple, list):
        if not isinstance(value, list):
            raise PersistenceStorageError(f"{path}: expected a list")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_value(v, args[0], f"{path}[{i}]") for i, v in enumerate(value))
        if args and len(args) == len(value):
            return tuple(
                _decode_value(v, a, f"{path}[{i}]") for i, (v, a) in enumerate(zip(value, args))
            )
        return tuple(value)
    if origin in (dict, collections.abc.Mapping):
        if not isinstance(value, dict):
            raise PersistenceStorageError(f"{path}: expected an object")
        key_hint, value_hint = args if len(args) == 2 else (str, Any)
        return {
            _decode_value(k, key_hint, f"{path}.<key>"): _decode_value(v, value_hint, f"{path}.{k}")
            for k, v in value.items()
        }
    if isinstance(hint, type):
        if issubclass(hint, bool):
            if not isinstance(value, bool):
                raise PersistenceStorageError(f"{path}: expected a bool")
            return value
        if issubclass(hint, Enum):
            try:
                return hint(value)
            except ValueError as exc:
                raise PersistenceStorageError(f"{path}: {value!r} is not a {hint.__name__}") from exc
        if issubclass(hint, datetime):
            return parse_canonical_datetime(value, path)
        if hint is bytes:
            return _decode_bytes(value, path)
        if hint is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise PersistenceStorageError(f"{path}: expected an int")
            return value
        if hint is str:
            if not isinstance(value, str):
                raise PersistenceStorageError(f"{path}: expected a string")
            return value
        if dataclasses.is_dataclass(hint):
            return decode_dataclass(hint, value, path=path)
    raise PersistenceStorageError(f"{path}: annotation {hint!r} is not decodable")


def decode_dataclass(cls: type, value: Any, *, path: str = "$") -> Any:
    """Rebuild ``cls`` from its canonical structure, strictly."""

    if not (isinstance(cls, type) and dataclasses.is_dataclass(cls)):
        raise PersistenceStorageError(f"{path}: {cls!r} is not a dataclass")
    if not isinstance(value, dict):
        raise PersistenceStorageError(f"{path}: expected an object for {cls.__name__}")
    hints = typing.get_type_hints(cls)
    known = {f.name: f for f in dataclasses.fields(cls) if f.init}
    unexpected = set(value) - set(known)
    if unexpected:
        raise PersistenceStorageError(
            f"{path}: unexpected fields for {cls.__name__}: {sorted(unexpected)}"
        )
    kwargs: dict[str, Any] = {}
    for name, f in known.items():
        if name not in value:
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                raise PersistenceStorageError(f"{path}.{name}: required field missing")
            continue
        kwargs[name] = _decode_value(value[name], hints.get(name, Any), f"{path}.{name}")
    try:
        return cls(**kwargs)
    except PersistenceStorageError:
        raise
    except Exception as exc:  # the target's own validation refused the stored value
        raise PersistenceStorageError(
            f"{path}: {cls.__name__} refused stored value: {exc}"
        ) from exc


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
def encode_record(value: Any) -> Any:
    """The canonical structure of any domain record (what its digest covers)."""

    try:
        return to_canonical_obj(value)
    except TypeError as exc:
        raise PersistenceStorageError(f"record is not canonicalizable: {exc}") from exc


def decode_record(cls: type, value: Any) -> Any:
    return decode_dataclass(cls, value, path=f"${cls.__name__}")


def encode_envelope(envelope: RiskAuthorizationEnvelope) -> dict:
    """Canonical body beside the signature the body excludes (D-2)."""

    if not isinstance(envelope, RiskAuthorizationEnvelope):
        raise PersistenceStorageError("encode_envelope requires a RiskAuthorizationEnvelope")
    return {
        "envelope": to_canonical_obj(envelope),
        "signature": _encode_bytes(bytes(envelope.signature)),
    }


def decode_envelope(value: Any) -> RiskAuthorizationEnvelope:
    if not isinstance(value, dict) or set(value) != {"envelope", "signature"}:
        raise PersistenceStorageError("$envelope: expected {envelope, signature}")
    body = decode_dataclass(RiskAuthorizationEnvelope, value["envelope"], path="$envelope")
    return replace(body, signature=_decode_bytes(value["signature"], "$envelope.signature"))


def encode_case(case: RiskDecisionCase) -> Any:
    if not isinstance(case, RiskDecisionCase):
        raise PersistenceStorageError("encode_case requires a RiskDecisionCase")
    return to_canonical_obj(case.snapshot())


def decode_case(value: Any) -> RiskDecisionCase:
    snapshot = decode_dataclass(RiskCaseSnapshot, value, path="$case")
    try:
        return RiskDecisionCase.from_snapshot(snapshot)
    except RiskAuthorityError as exc:
        raise PersistenceStorageError(f"$case: {exc}") from exc

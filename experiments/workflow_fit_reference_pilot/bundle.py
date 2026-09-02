"""Deterministic artifact bundle for the reference pilot: a fixed layout, JSON artifacts in
the contracts' canonical payload shape, a type-hint-driven rebuild of every contract object
from its artifact, and an index whose digest covers the complete artifact set.

The index is workspace tooling (a map of relative path -> sha256 plus its JCS digest). It is
not a ratified contract, carries no schema version and confers no evidence status. Raw
provider requests and responses never enter a bundle: capture records carry digests only."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import typing
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple, Type, TypeVar

from ugence_jcs import canonical_sha256_hex
from ugence_workflow_fit_pilot._canon import payload

T = TypeVar("T")
INDEX_FILE = "index.json"


class BundleError(ValueError):
    """The bundle is not a complete, unmodified artifact set. Verification fails closed."""


# --------------------------------------------------------------------------- JSON I/O

def dumps(obj: Any) -> str:
    """Canonical payload shape (ints and bools as strings, datetimes RFC 3339 UTC, enums by
    value) rendered with sorted keys so a rewrite of equal content is byte-identical."""
    return json.dumps(payload(obj), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _no_duplicate_keys(pairs):
    d: Dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise BundleError(f"duplicate key {k!r} in a bundle document")
        d[k] = v
    return d


def loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_no_duplicate_keys)


def write_artifact(root: Path, rel: str, obj: Any) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")


def read_artifact(root: Path, rel: str) -> Any:
    path = root / rel
    if not path.is_file():
        raise BundleError(f"artifact {rel} is absent")
    return loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- rebuild

def _unwrap_optional(tp):
    origin = typing.get_origin(tp)
    if origin is typing.Union:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1 and len(typing.get_args(tp)) == 2:
            return args[0], True
    return tp, False


def rebuild(tp: Any, data: Any, *, where: str = "$") -> Any:
    """Rebuild a contract value of type ``tp`` from its canonical payload. Every field must
    be present; unknown fields are refused; nothing is defaulted, so a dataclass with default
    fields is rebuilt only from a payload that carries them. Self-digest fields are passed
    through, so each contract's own constructor re-verifies its digest."""
    tp, optional = _unwrap_optional(tp)
    if data is None:
        if optional:
            return None
        raise BundleError(f"{where}: null where {tp} is required")
    origin = typing.get_origin(tp)
    if origin in (tuple, typing.Tuple) or tp is tuple:
        if not isinstance(data, list):
            raise BundleError(f"{where}: expected a JSON array")
        args = typing.get_args(tp)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(rebuild(args[0], v, where=f"{where}[{i}]") for i, v in enumerate(data))
        if len(args) != len(data):
            raise BundleError(f"{where}: expected {len(args)} items")
        return tuple(rebuild(a, v, where=f"{where}[{i}]") for i, (a, v) in enumerate(zip(args, data)))
    if isinstance(tp, type) and issubclass(tp, Enum):
        if not isinstance(data, str):
            raise BundleError(f"{where}: enum value must be a string")
        try:
            return tp(data)
        except ValueError:
            raise BundleError(f"{where}: {data!r} is not a {tp.__name__} member") from None
    if tp is bool:
        if data not in ("true", "false"):
            raise BundleError(f"{where}: boolean must be the canonical 'true'/'false' string")
        return data == "true"
    if tp is int:
        if not isinstance(data, str) or not data.lstrip("-").isdigit():
            raise BundleError(f"{where}: integer must be a canonical decimal string")
        return int(data)
    if tp is Decimal:
        if not isinstance(data, str):
            raise BundleError(f"{where}: decimal must be a string")
        return Decimal(data)
    if tp is datetime:
        if not isinstance(data, str) or not data.endswith("Z"):
            raise BundleError(f"{where}: instant must be an RFC 3339 UTC string")
        try:
            return datetime.fromisoformat(data.replace("Z", "+00:00"))
        except ValueError:
            raise BundleError(f"{where}: malformed instant") from None
    if tp is str:
        if not isinstance(data, str):
            raise BundleError(f"{where}: expected a string")
        return data
    if dataclasses.is_dataclass(tp):
        if not isinstance(data, Mapping):
            raise BundleError(f"{where}: expected a JSON object for {tp.__name__}")
        hints = typing.get_type_hints(tp)
        fields = [f for f in dataclasses.fields(tp) if f.init]
        names = {f.name for f in fields}
        missing, unknown = sorted(names - set(data)), sorted(set(data) - names)
        if missing or unknown:
            raise BundleError(f"{where}: {tp.__name__} fields missing {missing or '-'}; unknown {unknown or '-'}")
        kwargs = {f.name: rebuild(hints[f.name], data[f.name], where=f"{where}.{f.name}") for f in fields}
        return tp(**kwargs)
    raise BundleError(f"{where}: unsupported contract type {tp!r}")


def rebuild_artifact(root: Path, rel: str, tp: Type[T]) -> T:
    return rebuild(tp, read_artifact(root, rel), where=rel)


# --------------------------------------------------------------------------- index

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk(root: Path) -> Tuple[str, ...]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            out.append(rel)
    return tuple(sorted(out))


def index_digest(artifacts: Mapping[str, str]) -> str:
    return canonical_sha256_hex({k: artifacts[k] for k in sorted(artifacts)})


def write_index(root: Path) -> Dict[str, Any]:
    """Digest every file currently in the bundle (the index itself excluded) and write the index last."""
    files = [f for f in _walk(root) if f != INDEX_FILE]
    artifacts = {rel: sha256_file(root / rel) for rel in files}
    index = {"artifacts": artifacts, "index_digest": index_digest(artifacts)}
    (root / INDEX_FILE).write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def verify_index(root: Path, expected_layout: Tuple[str, ...]) -> Dict[str, str]:
    """Fail closed on any omitted, substituted, duplicated or unexpected artifact.

    - omitted: an indexed or layout-required file is absent;
    - substituted: a file's sha256 differs from its indexed digest;
    - duplicated: an index key repeats (refused at parse) or two files share a layout slot;
    - unexpected: a file on disk is not in the index, or an indexed file is outside the layout."""
    if not root.is_dir():
        raise BundleError(f"bundle directory {root} does not exist")
    path = root / INDEX_FILE
    if not path.is_file():
        raise BundleError("index.json is absent")
    index = loads(path.read_text(encoding="utf-8"))
    if not isinstance(index, Mapping) or set(index) != {"artifacts", "index_digest"} or not isinstance(index["artifacts"], Mapping):
        raise BundleError("index.json is not {artifacts, index_digest}")
    artifacts: Dict[str, str] = dict(index["artifacts"])
    if index["index_digest"] != index_digest(artifacts):
        raise BundleError("index_digest does not cover the indexed artifact set")
    on_disk = set(_walk(root)) - {INDEX_FILE}
    indexed = set(artifacts)
    layout = set(expected_layout)
    if on_disk - indexed:
        raise BundleError(f"unexpected artifacts not covered by the index: {sorted(on_disk - indexed)}")
    if indexed - on_disk:
        raise BundleError(f"indexed artifacts omitted from the bundle: {sorted(indexed - on_disk)}")
    if indexed - layout:
        raise BundleError(f"indexed artifacts outside the deterministic layout: {sorted(indexed - layout)}")
    if layout - indexed:
        raise BundleError(f"layout artifacts omitted from the index: {sorted(layout - indexed)}")
    for rel, digest in sorted(artifacts.items()):
        if not isinstance(digest, str) or sha256_file(root / rel) != digest:
            raise BundleError(f"artifact {rel} was substituted: sha256 differs from the index")
    return artifacts


__all__ = ["BundleError", "INDEX_FILE", "dumps", "loads", "write_artifact", "read_artifact", "rebuild", "rebuild_artifact", "sha256_file", "index_digest", "write_index", "verify_index"]

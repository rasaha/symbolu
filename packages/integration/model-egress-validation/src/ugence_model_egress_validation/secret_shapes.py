"""Secret-shape scanning (LP-7 ruling 11): findings name a path, never a value.

The shapes are the unit's :data:`CREDENTIAL_SHAPE_PREFIXES` plus any string the caller
registers as a *known marker* (a fixture secret the harness leased, so its appearance
anywhere in a report is a leak by construction). The scan walks nested mappings,
sequences and strings; a finding carries the JSON-pointer-like path and the shape name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Sequence, Tuple

from ugence_model_egress_unit import CREDENTIAL_SHAPE_PREFIXES, looks_like_a_credential

__all__ = ["Finding", "scan", "assert_clean"]


@dataclass(frozen=True)
class Finding:
    path: str
    shape: str  # the prefix family, or "known-marker"

    def __str__(self) -> str:
        return f"{self.path}: {self.shape}"


def _shape_of(value: str, markers: Sequence[str]) -> str:
    for marker in markers:
        if marker and marker in value:
            return "known-marker"
    if looks_like_a_credential(value):
        present = [prefix for prefix in CREDENTIAL_SHAPE_PREFIXES if prefix in value]
        return max(present, key=len) if present else "credential-shape"
    return ""


def scan(obj: Any, *, known_markers: Iterable[str] = (), path: str = "$") -> List[Finding]:
    """Every credential-shaped string under ``obj``, by path. Values are never returned."""

    markers = tuple(known_markers)
    found: List[Finding] = []
    if isinstance(obj, str):
        shape = _shape_of(obj, markers)
        if shape:
            found.append(Finding(path, shape))
    elif isinstance(obj, Mapping):
        for key, value in obj.items():
            key_shape = _shape_of(str(key), markers)
            if key_shape:
                found.append(Finding(f"{path}.<key>", key_shape))
            found.extend(scan(value, known_markers=markers, path=f"{path}.{key}"))
    elif isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            found.extend(scan(value, known_markers=markers, path=f"{path}[{index}]"))
    return found


def assert_clean(obj: Any, *, known_markers: Iterable[str] = (), what: str = "object") -> None:
    findings = scan(obj, known_markers=known_markers)
    if findings:
        raise ValueError(f"{what} carries a credential shape at: " + "; ".join(str(f) for f in findings))

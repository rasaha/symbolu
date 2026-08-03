"""Complexity limits for structured content (JSON / CSV).

All checks fail closed with :class:`StructuredLimitError`; nothing partially
accepted. Duplicate-key behavior for JSON is deterministic and documented:
Python's ``json`` keeps the last value for a duplicated key, and this module
additionally *detects* duplicates via an object hook and rejects them so an
attacker cannot smuggle a shadowed field past quarantine.
"""

from __future__ import annotations

import csv
import io
import json

from ..errors import ContentExtractionError, StructuredLimitError
from .limits import DEFAULT_LIMITS, EvidenceLimits


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise StructuredLimitError(f"duplicate JSON key detected: {key!r}")
        seen.add(key)
    return dict(pairs)


def parse_json_bounded(raw: bytes, limits: EvidenceLimits = DEFAULT_LIMITS) -> object:
    """Parse JSON with byte + structural limits and duplicate-key rejection."""
    if len(raw) > limits.max_json_bytes:
        raise StructuredLimitError(
            f"JSON of {len(raw)} bytes exceeds max_json_bytes={limits.max_json_bytes}"
        )
    try:
        obj = json.loads(raw.decode("utf-8", errors="replace"),
                         object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ContentExtractionError(f"invalid JSON submission: {exc}") from exc
    _check_json_structure(obj, limits)
    return obj


def _check_json_structure(obj: object, limits: EvidenceLimits) -> None:
    scalars = 0
    fields = 0

    def walk(node: object, depth: int) -> None:
        nonlocal scalars, fields
        if depth > limits.max_json_depth:
            raise StructuredLimitError(
                f"JSON nesting depth exceeds max_json_depth={limits.max_json_depth}"
            )
        if isinstance(node, dict):
            fields += len(node)
            if fields > limits.max_json_fields:
                raise StructuredLimitError(
                    f"JSON field count exceeds max_json_fields={limits.max_json_fields}"
                )
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, list):
            if len(node) > limits.max_json_array_length:
                raise StructuredLimitError(
                    f"JSON array length exceeds max_json_array_length="
                    f"{limits.max_json_array_length}"
                )
            for v in node:
                walk(v, depth + 1)
        else:
            scalars += 1
            if scalars > limits.max_json_total_scalars:
                raise StructuredLimitError("JSON scalar count exceeds max_json_total_scalars")
            if isinstance(node, str) and len(node) > limits.max_json_string_length:
                raise StructuredLimitError("JSON string exceeds max_json_string_length")

    walk(obj, 0)


def check_csv_bounded(raw: bytes, limits: EvidenceLimits = DEFAULT_LIMITS) -> None:
    """Validate CSV byte + shape limits deterministically before extraction."""
    if len(raw) > limits.max_csv_bytes:
        raise StructuredLimitError(
            f"CSV of {len(raw)} bytes exceeds max_csv_bytes={limits.max_csv_bytes}"
        )
    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    total_cells = 0
    rows = 0
    try:
        for i, row in enumerate(reader):
            if i == 0:
                header_len = sum(len(c) for c in row)
                if len(row) > limits.max_csv_columns:
                    raise StructuredLimitError(
                        f"CSV column count exceeds max_csv_columns={limits.max_csv_columns}"
                    )
                if header_len > limits.max_csv_header_length:
                    raise StructuredLimitError("CSV header exceeds max_csv_header_length")
            rows += 1
            if rows > limits.max_csv_rows:
                raise StructuredLimitError(
                    f"CSV row count exceeds max_csv_rows={limits.max_csv_rows}"
                )
            for cell in row:
                if len(cell) > limits.max_csv_cell_length:
                    raise StructuredLimitError("CSV cell exceeds max_csv_cell_length")
            total_cells += len(row)
            if total_cells > limits.max_csv_total_cells:
                raise StructuredLimitError("CSV total cells exceeds max_csv_total_cells")
    except csv.Error as exc:
        raise ContentExtractionError(f"invalid CSV submission: {exc}") from exc

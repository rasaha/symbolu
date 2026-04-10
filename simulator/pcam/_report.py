"""
Internal reporting helpers for PCAM benchmark scripts.

This module is private (leading underscore) — it is NOT exported from
``simulator/pcam/__init__.py`` and does NOT broaden the Phase 1 public
API surface. It exists so that the three Phase 3 benchmark scripts
(``pcam_trace_replay``, ``pcam_compare_baselines``, ``pcam_vllm_demo``)
can share a small, dependency-free set of formatting primitives
without each script re-implementing the same 30 lines.

The helpers are intentionally minimal:

- ``section_header(title)``       one-line banner
- ``format_table(rows, headers)`` compact left-aligned ASCII table
- ``emit_json(data, path)``       json.dumps to a file, defaulting
                                  non-JSON-native types to str

No framework, no dependency, no exporter. If a Phase 4 benchmark
grows real reporting needs (Prometheus, CSV roll-ups, HTML
dashboards, etc.), build them elsewhere — do not extend this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Union

__all__ = ["section_header", "format_table", "emit_json"]


def section_header(title: str) -> str:
    """Return a one-line banner suitable for stdout section breaks."""
    bar = "=" * max(3, len(title) + 4)
    return f"\n{bar}\n  {title}\n{bar}"


def format_table(
    rows: Sequence[Sequence[Any]],
    headers: Sequence[str],
) -> str:
    """
    Compact left-aligned ASCII table with a separator row under the
    header. Columns are sized to the widest cell in each column,
    counting the header.

    Intended for small result tables (tens of rows). Not optimized
    for wide or long output.
    """
    if not headers:
        raise ValueError("format_table: headers must be non-empty")

    rows_str: List[List[str]] = [[str(c) for c in row] for row in rows]
    widths = [
        max(
            len(str(h)),
            max((len(r[i]) for r in rows_str if i < len(r)), default=0),
        )
        for i, h in enumerate(headers)
    ]

    lines = [
        "  ".join(str(h).ljust(w) for h, w in zip(headers, widths)),
        "  ".join("-" * w for w in widths),
    ]
    for row in rows_str:
        # Pad a short row with empty cells so we don't index-error.
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append(
            "  ".join(c.ljust(w) for c, w in zip(padded, widths))
        )
    return "\n".join(lines)


def emit_json(data: Dict[str, Any], path: Union[str, Path]) -> None:
    """
    Write ``data`` as pretty-printed JSON to ``path``. Non-native
    types (enums, dataclasses, sets) fall back to ``str`` so the
    writer never raises on a serialization surprise.

    Creates parent directories as needed.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True, default=str))

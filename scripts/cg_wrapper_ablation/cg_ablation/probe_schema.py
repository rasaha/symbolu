"""Schema + loader for the Bhava/ontology supervised probe (generation-quality track).

Input JSONL rows:
    {"id","prompt","expected","label",0/1,"label_type":"correctness","metadata":{}}

This module is the lane guard: it accepts ONLY generation-quality label types and rejects any
governance/trust label so that track cannot leak into this one. Pure Python — no torch/numpy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

# Generation-quality labels — the ONLY ones allowed here.
ALLOWED_LABEL_TYPES = frozenset({
    "correctness",
    "format_validity",
    "constraint_satisfaction",
    "groundedness",
    "reasoning_correctness",
})

# Trust/governance labels — explicitly rejected (belong to the Trust Observable Architecture).
OUT_OF_SCOPE_LABEL_TYPES = frozenset({
    "tool_safety", "unsafe_action_risk", "governance", "power_seeking",
    "policy_violation", "trust_score", "risk", "safety",
})


class ProbeSchemaError(ValueError):
    """Raised when a probe-data row violates the schema or uses an out-of-scope label."""


def validate_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one row; return it normalized. Raises ProbeSchemaError on violation."""
    if not isinstance(row, dict):
        raise ProbeSchemaError(f"row must be an object, got {type(row).__name__}")
    for key in ("id", "label", "label_type"):
        if key not in row:
            raise ProbeSchemaError(f"row missing required key {key!r}: {row.get('id', '?')}")
    lt = row["label_type"]
    if lt in OUT_OF_SCOPE_LABEL_TYPES:
        raise ProbeSchemaError(
            f"label_type {lt!r} is OUT OF SCOPE (Trust/governance track). "
            f"Allowed (generation-quality): {sorted(ALLOWED_LABEL_TYPES)}")
    if lt not in ALLOWED_LABEL_TYPES:
        raise ProbeSchemaError(
            f"unknown label_type {lt!r}; allowed: {sorted(ALLOWED_LABEL_TYPES)}")
    label = row["label"]
    if label not in (0, 1, True, False):
        raise ProbeSchemaError(f"label must be binary 0/1 (got {label!r}) for id={row['id']}")
    row = dict(row)
    row["label"] = int(bool(label))
    row.setdefault("prompt", "")
    row.setdefault("expected", "")
    row.setdefault("metadata", {})
    return row


def load_probe_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    """Load + validate a probe JSONL file. Raises on the first bad row."""
    rows: List[Dict[str, Any]] = []
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProbeSchemaError(f"{p.name}:{i}: invalid JSON ({exc})") from exc
            try:
                rows.append(validate_row(obj))
            except ProbeSchemaError as exc:
                raise ProbeSchemaError(f"{p.name}:{i}: {exc}") from exc
    return rows


def group_by_label_type(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["label_type"], []).append(r)
    return out

"""Structural limits on a caller-supplied workflow document (BW-2, BW-3).

The three workflow routes (validate, adapt, compare-adaptations) accept a workflow
document in the request body. The body-size middleware bounds the bytes; nothing
bounded the structure, so a document inside the byte cap could still carry thousands
of nodes or pathological nesting into the adapter. These limits are checked before
any adapter runs, and a breach is a typed 422 ``workflow_too_complex`` naming the
measure, the observed value and the limit. They are contract-neutral: no route,
schema or status code is added to the frozen ``governance_studio.api.v1`` document.

The figures are the owner's (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §22, BW-2), and the
front end applies the same figures before it sends anything, so a document refused
here was already refused there; this is the authoritative check, that one is the
courtesy. Nothing here parses, executes or stores the document.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from .errors import ApiException

__all__ = [
    "MAX_DOCUMENT_BYTES",
    "MAX_DEPTH",
    "MAX_NODES",
    "MAX_EDGES",
    "MAX_ELEMENTS",
    "LIMITS",
    "measure_document",
    "enforce_workflow_limits",
]

#: Compact-encoded UTF-8 size of one document (BW-2: 1 MiB).
MAX_DOCUMENT_BYTES = 1024 * 1024
#: Nesting depth, counting the top-level container as 1 (BW-2: 32).
MAX_DEPTH = 32
#: Longest list held under a key named ``nodes`` anywhere in the document (BW-2: 200).
MAX_NODES = 200
#: Longest list held under a key named ``edges`` anywhere in the document (BW-2: 400).
MAX_EDGES = 400
#: Every container and leaf counted once; bounds the walk itself.
MAX_ELEMENTS = 50_000

LIMITS: Dict[str, int] = {
    "document_bytes": MAX_DOCUMENT_BYTES,
    "depth": MAX_DEPTH,
    "nodes": MAX_NODES,
    "edges": MAX_EDGES,
    "elements": MAX_ELEMENTS,
}


def measure_document(document: Any) -> Dict[str, int]:
    """Depth, element count and the longest ``nodes`` / ``edges`` lists, in one
    iterative walk (no recursion, so a deep document cannot exhaust the stack)."""
    depth = 0
    elements = 0
    nodes = 0
    edges = 0
    stack = [(document, 1, None)]
    while stack:
        value, level, key = stack.pop()
        elements += 1
        if elements > MAX_ELEMENTS:
            break
        if level > depth:
            depth = level
        if isinstance(value, Mapping):
            for k, v in value.items():
                stack.append((v, level + 1, k))
        elif isinstance(value, (list, tuple)):
            if key == "nodes" and len(value) > nodes:
                nodes = len(value)
            if key == "edges" and len(value) > edges:
                edges = len(value)
            for v in value:
                stack.append((v, level + 1, None))
    return {"depth": depth, "elements": elements, "nodes": nodes, "edges": edges}


def enforce_workflow_limits(document: Any, field_path: str = "workflow") -> Dict[str, int]:
    """Refuse a document over any limit with a typed 422; return its measures."""
    measures = measure_document(document)
    for measure in ("elements", "depth", "nodes", "edges"):
        if measures[measure] > LIMITS[measure]:
            _refuse(field_path, measure, measures[measure])
    size = len(json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    measures["document_bytes"] = size
    if size > MAX_DOCUMENT_BYTES:
        _refuse(field_path, "document_bytes", size)
    return measures


def _refuse(field_path: str, measure: str, observed: int) -> None:
    raise ApiException(
        422, "workflow_too_complex",
        f"{field_path}: {measure} {observed} exceeds the limit {LIMITS[measure]}",
        field_path=field_path,
        safe_details={"measure": measure, "observed": observed, "limit": LIMITS[measure],
                      "limits": dict(LIMITS)},
    )

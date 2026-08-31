"""Frozen deterministic serializer for the unseen-identifier diagnostic.

Implements exactly the merged protocol-lock templates (Decision 2). Byte-identical under repeated
generation; fixed field names, capitalization, whitespace, newline layout, fact ordering, answer
prefix, distractor syntax, evidence syntax. No optional formatting, no serializer search, no
candidate-index representation.
"""
from __future__ import annotations

from .tasks import Example

_ANSWER_PREFIX = "ANSWER ="


def serialize(example: Example) -> str:
    """Return the exact model-visible prompt text ending at the answer prefix."""
    lines: list[str] = [f"TASK = {example.task_name}"]
    if example.split == "C1":
        lines.append(f"TARGET = {example.target_id}")
    elif example.split == "C3":
        lines.append(f"QUERY_RELATION = {example.query_source} -> {example.query_target}")
        lines.append("FACTS:")
        for (src, tgt), ev in zip(example.pairs, example.pair_evidence):
            lines.append(f"{src} -> {tgt} | EVIDENCE = {ev}")
    else:  # C2/C4/C5/C6/C7 relation lookup, C8 missing-key
        lines.append(f"QUERY_SOURCE = {example.query_source}")
        lines.append("FACTS:")
        for src, tgt in example.pairs:
            lines.append(f"{src} -> {tgt}")
    lines.append(_ANSWER_PREFIX)
    rendered = "\n".join(lines) + "\n"
    rendered.encode("ascii")  # frozen ASCII invariant (raises on any non-ASCII)
    return rendered

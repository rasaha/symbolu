"""
explanation.py — real-model explanation of an already-computed typed result (§5 role B).

The model NEVER computes or overrides the outcome here. It receives the typed finding, its cited
evidence, and the source, and produces a natural-language explanation. We then extract the evidence
ids the explanation cites so the faithfulness evaluator can check attribution against the source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..event_schema import EventRecord, STATUSES
from ..datasets import CLASS_NAMES
from .prompts import build_explanation_prompt


def build_typed_result(outcome: int, cited_ids: List[int], records: List[EventRecord],
                       task_family: str) -> Dict:
    """Serialize the deterministic typed finding + its evidence into the explainer's input payload.

    Qualifiers are lifted from the cited exact records so the evaluator can check that the model
    preserved them."""
    by_id = {r.evidence_id: r for r in records}
    quals: List[str] = []
    numbers: List[int] = []
    for eid in cited_ids:
        r = by_id.get(eid)
        if r is None:
            continue
        quals.append(f"status:{STATUSES[r.status] if 0 <= r.status < len(STATUSES) else r.status}")
        quals.append(f"version:v{r.version}")
        quals.append(f"authority:{round(r.authority, 2)}")
        # every number traceable to a cited exact field is "supported" (value, version, authority*10)
        numbers.extend([r.normalized_value, r.version, int(round(r.authority * 10))])
    return {
        "task_family": task_family,
        "outcome": outcome,
        "outcome_label": CLASS_NAMES[outcome] if 0 <= outcome < len(CLASS_NAMES) else str(outcome),
        "cited_evidence_ids": [f"EV-{e}" for e in cited_ids],
        "cited_evidence_ids_int": cited_ids,
        "qualifiers": sorted(set(quals)),
        "supported_numbers": sorted(set(numbers)),
    }


@dataclass
class ExplanationResult:
    text: str
    cited_ids: List[int]
    typed_result: Dict
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


_CITE_RE = re.compile(r"\[EV-(\d+)\]")


def parse_cited_ids(text: str) -> List[int]:
    return [int(m) for m in _CITE_RE.findall(text)]


def explain(backend, outcome: int, cited_ids: List[int], records: List[EventRecord],
            task_family: str, docs: Dict[int, str]) -> ExplanationResult:
    typed = build_typed_result(outcome, cited_ids, records, task_family)
    system, user = build_explanation_prompt(typed, docs)
    gen = backend.generate(system, user)
    return ExplanationResult(
        text=gen.text, cited_ids=parse_cited_ids(gen.text), typed_result=typed,
        prompt_tokens=gen.prompt_tokens, completion_tokens=gen.completion_tokens,
        latency_ms=gen.latency_ms)

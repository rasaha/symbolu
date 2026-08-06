"""One strict output parser and evaluator shared by both arms."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .schema import CanonicalEpisode, StructuredOutput

_REQUIRED_FIELDS = (
    "status",
    "selected_entity_id",
    "selected_relation_type",
    "relation_supported",
    "evidence_refs",
    "tenant_id",
    "reason_code",
)


class OutputParseError(ValueError):
    pass


def _object_pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OutputParseError(f"duplicate output field: {key}")
        result[key] = value
    return result


def parse_output(text: str) -> StructuredOutput:
    try:
        payload = json.loads(text, object_pairs_hook=_object_pairs_no_duplicates)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputParseError("output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise OutputParseError("output must be a JSON object")
    if tuple(payload.keys()) != _REQUIRED_FIELDS:
        raise OutputParseError(
            f"output fields/order must be exactly {_REQUIRED_FIELDS}, got {tuple(payload.keys())}"
        )
    if payload["selected_entity_id"] is not None and not isinstance(
        payload["selected_entity_id"], str
    ):
        raise OutputParseError("selected_entity_id must be string or null")
    if payload["selected_relation_type"] is not None and not isinstance(
        payload["selected_relation_type"], str
    ):
        raise OutputParseError("selected_relation_type must be string or null")
    if payload["relation_supported"] is not None and not isinstance(
        payload["relation_supported"], bool
    ):
        raise OutputParseError("relation_supported must be boolean or null")
    if not isinstance(payload["evidence_refs"], list) or not all(
        isinstance(item, str) for item in payload["evidence_refs"]
    ):
        raise OutputParseError("evidence_refs must be an array of strings")
    for key in ("status", "tenant_id", "reason_code"):
        if not isinstance(payload[key], str):
            raise OutputParseError(f"{key} must be a string")
    try:
        return StructuredOutput(
            status=payload["status"],
            selected_entity_id=payload["selected_entity_id"],
            selected_relation_type=payload["selected_relation_type"],
            relation_supported=payload["relation_supported"],
            evidence_refs=tuple(payload["evidence_refs"]),
            tenant_id=payload["tenant_id"],
            reason_code=payload["reason_code"],
        )
    except ValueError as exc:
        raise OutputParseError(str(exc)) from exc


@dataclass(frozen=True)
class ExampleScore:
    exact_output: bool
    entity_correct: bool
    relation_correct: bool
    relation_support_correct: bool
    status_correct: bool
    abstention_correct: bool
    evidence_precision: float
    evidence_recall: float
    tenant_correct: bool
    unauthorized_cross_tenant_inclusion: bool
    unsupported_evidence_refs: tuple[str, ...]


def _precision_recall(predicted: Iterable[str], expected: Iterable[str]) -> tuple[float, float]:
    pred = set(predicted)
    gold = set(expected)
    if not pred:
        precision = 1.0 if not gold else 0.0
    else:
        precision = len(pred & gold) / len(pred)
    if not gold:
        recall = 1.0
    else:
        recall = len(pred & gold) / len(gold)
    return precision, recall


def score_output(
    episode: CanonicalEpisode, prediction: StructuredOutput, gold: StructuredOutput | None = None
) -> ExampleScore:
    gold = gold or episode.authoritative_output
    precision, recall = _precision_recall(prediction.evidence_refs, gold.evidence_refs)
    entity_index = {item.entity_id: item for item in episode.entities}
    selected = entity_index.get(prediction.selected_entity_id or "")
    unauthorized = selected is not None and selected.tenant_id != episode.tenant_id
    unsupported = tuple(sorted(set(prediction.evidence_refs) - set(gold.evidence_refs)))
    return ExampleScore(
        exact_output=prediction == gold,
        entity_correct=prediction.selected_entity_id == gold.selected_entity_id,
        relation_correct=prediction.selected_relation_type == gold.selected_relation_type,
        relation_support_correct=prediction.relation_supported == gold.relation_supported,
        status_correct=prediction.status == gold.status,
        abstention_correct=(prediction.status == "INSUFFICIENT_EVIDENCE")
        == (gold.status == "INSUFFICIENT_EVIDENCE"),
        evidence_precision=precision,
        evidence_recall=recall,
        tenant_correct=prediction.tenant_id == gold.tenant_id,
        unauthorized_cross_tenant_inclusion=unauthorized,
        unsupported_evidence_refs=unsupported,
    )


@dataclass(frozen=True)
class AggregateMetrics:
    count: int
    exact_accuracy: float
    entity_accuracy: float
    relation_accuracy: float
    relation_support_accuracy: float
    abstention_accuracy: float
    evidence_precision: float
    evidence_recall: float
    tenant_accuracy: float
    unauthorized_cross_tenant_inclusions: int
    unsupported_evidence_emissions: int


def aggregate_scores(scores: Iterable[ExampleScore]) -> AggregateMetrics:
    items = tuple(scores)
    if not items:
        raise ValueError("cannot aggregate zero scores")
    n = len(items)
    mean = lambda values: sum(values) / n
    return AggregateMetrics(
        count=n,
        exact_accuracy=mean(int(item.exact_output) for item in items),
        entity_accuracy=mean(int(item.entity_correct) for item in items),
        relation_accuracy=mean(int(item.relation_correct) for item in items),
        relation_support_accuracy=mean(int(item.relation_support_correct) for item in items),
        abstention_accuracy=mean(int(item.abstention_correct) for item in items),
        evidence_precision=mean(item.evidence_precision for item in items),
        evidence_recall=mean(item.evidence_recall for item in items),
        tenant_accuracy=mean(int(item.tenant_correct) for item in items),
        unauthorized_cross_tenant_inclusions=sum(
            int(item.unauthorized_cross_tenant_inclusion) for item in items
        ),
        unsupported_evidence_emissions=sum(len(item.unsupported_evidence_refs) for item in items),
    )

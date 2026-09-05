"""Programmatic reference evaluator for SYNTHETIC structured-answer cases only.

Scoring rule (the whole rule, digested into scoring_instruction_digest): the final response's
last line beginning with ``ANSWER:`` is taken, whitespace-normalized and lower-cased, and
compared for exact equality with the expected answer treated the same way; a match scores
``1`` and anything else scores ``0``. Expected answers live outside every workflow-visible
input. The evaluator declares its independence as DECLARED_UNVERIFIED like every 4A evaluator;
this rule says nothing about reasoning quality beyond exact structured agreement."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Mapping

from ugence_workflow_fit_pilot._canon import digest_of

SCORING_RULE_TEXT = (
    "reference-evaluator.v0: take the last line of the final response that starts with 'ANSWER:'; "
    "strip the prefix; collapse whitespace; lower-case; compare for exact equality with the expected answer "
    "normalized the same way; score 1 on equality, 0 otherwise; no partial credit; no semantic judgment."
)


def scoring_instruction_digest(benchmark_manifest_digest: str, sufficiency_rule_id: str, sufficiency_rule_version: str) -> str:
    return digest_of({"rule": SCORING_RULE_TEXT, "benchmark_manifest_digest": benchmark_manifest_digest, "sufficiency_rule": f"{sufficiency_rule_id}@{sufficiency_rule_version}"})


def normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def extract_answer(response: str) -> str:
    lines = [ln for ln in response.splitlines() if ln.strip().upper().startswith("ANSWER:")]
    return normalize(lines[-1].strip()[len("ANSWER:"):]) if lines else ""


class ReferenceEvaluator:
    """QualityScorerPort. Keyed by case digest; expected answers are supplied at construction
    from the separate expected document, never from the case inputs."""

    def __init__(self, expected_by_case_digest: Mapping[str, str]) -> None:
        self._expected: Dict[str, str] = {k: normalize(v) for k, v in expected_by_case_digest.items()}

    def score(self, case_digest: str, response: str) -> Decimal:
        expected = self._expected[case_digest]
        return Decimal("1") if extract_answer(response) == expected else Decimal("0")


__all__ = ["SCORING_RULE_TEXT", "scoring_instruction_digest", "normalize", "extract_answer", "ReferenceEvaluator"]

"""
explanation.py — real-model explanation + RM1 faithfulness evaluator (RM1 §13).

The token model turns an already-decided typed result into prose; it does not re-decide. The
faithfulness of that prose is judged by a DETERMINISTIC evaluator against gold annotations and the
cited exact records — the model is never the sole judge of its own explanation. Because the
repository ships no callable TAP API for free-text enterprise explanations, this evaluator is
explicitly labelled `RM1_FAITHFULNESS_EVALUATOR`, NOT "TAP".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..event_schema import EventRecord, ACTIVE
from ..datasets import CLASS_NAMES, ABSTAIN, CONFLICT, YES, NO
from .prompts import build_explanation_prompt

EVALUATOR_NAME = "RM1_FAITHFULNESS_EVALUATOR"


def build_typed_findings(task_family: str, answer: int, used_ids: List[int],
                         admitted: List[EventRecord]) -> Dict:
    return {
        "task_family": task_family,
        "decision": CLASS_NAMES[answer],
        "abstained": answer == ABSTAIN,
        "material_conflict": answer == CONFLICT,
        "boolean_outcome": {YES: True, NO: False}.get(answer, None),
        "evidence_ids": list(used_ids),
    }


def cited_records(used_ids: List[int], admitted: List[EventRecord]) -> List[Dict]:
    by = {r.evidence_id: r for r in admitted}
    out = []
    for i in used_ids:
        r = by.get(i)
        if r is None:
            continue
        out.append({"evidence_id": r.evidence_id, "subject_id": r.subject_id,
                    "relation_type": r.relation_type, "object_id_or_value": r.object_id_or_value,
                    "normalized_value": r.normalized_value, "version": r.version,
                    "status": r.status, "authority": r.authority,
                    "source_span": r.source_span, "provenance_hash": r.provenance_hash})
    return out


def generate_explanation(backend, typed_findings: Dict, cited: List[Dict],
                         max_new_tokens: int = 160) -> Dict:
    prompt = build_explanation_prompt(typed_findings, cited)
    gen = backend.generate(prompt, max_new_tokens=max_new_tokens)
    return {"text": gen.text, "n_input_tokens": gen.n_input_tokens,
            "n_output_tokens": gen.n_output_tokens}


# ------------------------------------------------------------------ faithfulness evaluation
_EV_RE = re.compile(r"EV[- ]?(\d+)", re.IGNORECASE)
_NUM_RE = re.compile(r"(?<![A-Za-z])(\d+)(?![A-Za-z])")
_NEG_QUALIFIERS = ("no ", "not ", "without", "missing", "absent", "never", "n't")


@dataclass
class FaithfulnessResult:
    evaluator: str = EVALUATOR_NAME
    supported_claim_precision: float = 1.0
    unsupported_claim_recall: float = 1.0     # recall of DETECTING an injected unsupported claim
    qualifier_preservation: float = 1.0
    evidence_attribution_exact_match: float = 1.0
    flags: List[str] = field(default_factory=list)
    blocked: bool = False                     # corrupt provenance / missing span → must block


def evaluate_faithfulness(text: str, typed_findings: Dict, cited: List[Dict],
                          expect_unsupported: bool = False,
                          expect_missing_qualifier: bool = False) -> FaithfulnessResult:
    """Deterministic faithfulness check. `expect_*` are set by the causal controls to verify the
    evaluator actually DETECTS an injected fault (recall)."""
    res = FaithfulnessResult()
    cited_ids = {c["evidence_id"] for c in cited}
    cited_values = set()
    for c in cited:
        cited_values.update({c["normalized_value"], c["object_id_or_value"], c["version"],
                             c["evidence_id"]})
    # 0) hard blocks: corrupt provenance or missing source span among cited records
    for c in cited:
        if not c.get("source_span"):
            res.blocked = True
            res.flags.append("missing_source_span")
        # provenance corruption is detected upstream; a blank/`CORRUPT` hash blocks here too
        if not c.get("provenance_hash") or c["provenance_hash"] == "CORRUPT":
            res.blocked = True
            res.flags.append("corrupt_provenance")

    # 1) evidence-id attribution: every EV id mentioned must be in the cited set
    mentioned = [int(m) for m in _EV_RE.findall(text)]
    if mentioned:
        good = sum(1 for m in mentioned if m in cited_ids)
        res.evidence_attribution_exact_match = good / len(mentioned)
        if good < len(mentioned):
            res.flags.append("fabricated_evidence_id")

    # 2) numeric support: every standalone number must match a cited value or an EV id
    ev_nums = set(mentioned)
    numbers = [int(n) for n in _NUM_RE.findall(text)]
    unsupported = [n for n in numbers if n not in cited_values and n not in ev_nums]
    total_claims = max(1, len(numbers) + len(mentioned))
    supported = total_claims - len(unsupported) - sum(1 for m in mentioned if m not in cited_ids)
    res.supported_claim_precision = max(0.0, supported / total_claims)
    detected_unsupported = bool(unsupported) or ("fabricated_evidence_id" in res.flags)
    if detected_unsupported:
        res.flags.append("unsupported_claim")

    # 3) qualifier preservation: negative outcomes must carry a negation qualifier
    needs_negation = (typed_findings.get("boolean_outcome") is False
                      or typed_findings.get("abstained")
                      or bool(typed_findings.get("material_conflict")))
    if needs_negation:
        has_neg = any(q in text.lower() for q in _NEG_QUALIFIERS)
        res.qualifier_preservation = 1.0 if has_neg else 0.0
        if not has_neg:
            res.flags.append("missing_qualifier")

    # 4) control-recall bookkeeping: did we detect the injected fault?
    if expect_unsupported:
        res.unsupported_claim_recall = 1.0 if detected_unsupported else 0.0
    if expect_missing_qualifier:
        res.qualifier_preservation = res.qualifier_preservation  # already 0 if detected
        res.unsupported_claim_recall = res.unsupported_claim_recall
    return res

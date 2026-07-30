"""
clarification.py — bounded, append-only, replayable ClarificationRequest contract (RM1 §7).

When required evidence is missing or a span is ambiguous, the event/validation layer may ask the
token model exactly one clarification by default. The contract:

    * hard attempt limit (default 1);
    * append-only log of every request and response (replayable);
    * NO silent widening of the permitted document / source-span scope;
    * each response is re-validated INDEPENDENTLY against the source — never against the hypothesis
      that triggered the clarification;
    * after the limit → QUARANTINE or HUMAN_REVIEW_REQUIRED.

This prevents interpretation shopping and any indirect learned influence over authoritative
admission. The token model proposes; it never mutates authoritative evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional


@dataclass
class ClarificationResponse:
    attempt: int
    raw_generation: str
    interpretation: Optional[Dict]
    validation_outcome: str          # VALIDATED | REJECTED | QUARANTINED
    validation_detail: str = ""
    at: str = ""


@dataclass
class ClarificationRequest:
    request_id: str
    triggering_evidence_ids: List[int]
    unresolved_question: str
    permitted_document_ids: List[str]
    permitted_source_spans: List[str]
    max_attempts: int
    requesting_component: str
    created_at: str = "t0"
    responses: List[ClarificationResponse] = field(default_factory=list)
    final_outcome: str = "OPEN"      # OPEN | VALIDATED | QUARANTINE | HUMAN_REVIEW_REQUIRED

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


def run_clarification(req: ClarificationRequest, ask: Callable[[str], str],
                      validate: Callable[[Dict], Dict], parse: Callable[[str], Optional[Dict]],
                      question_prompt: str, clock: Callable[[], str] = lambda: "t") -> ClarificationRequest:
    """Drive a bounded clarification loop.

    ask(prompt)->raw generation ; parse(raw)->interpretation dict or None ;
    validate(interpretation)->{"outcome":..., "detail":...} validated against the SOURCE.
    Scope is fixed to req.permitted_* and never widened here.
    """
    attempt = 0
    while attempt < req.max_attempts:
        attempt += 1
        raw = ask(question_prompt)
        interp = parse(raw)
        if interp is None:
            req.responses.append(ClarificationResponse(attempt, raw, None, "REJECTED",
                                                       "unparseable", clock()))
            continue
        # independent validation against source (validate must not see the triggering hypothesis)
        v = validate(interp)
        req.responses.append(ClarificationResponse(attempt, raw, interp, v["outcome"],
                                                   v.get("detail", ""), clock()))
        if v["outcome"] == "VALIDATED":
            req.final_outcome = "VALIDATED"
            return req
    req.final_outcome = "HUMAN_REVIEW_REQUIRED" if req.responses else "QUARANTINE"
    return req

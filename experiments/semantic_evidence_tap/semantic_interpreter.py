"""
semantic_interpreter.py — CONTROLLABLE simulated LLM for INTERPRETED fields (§8).

The environment has no guaranteed live frontier-LLM loop, so the interpreter is a simulator with a
quality knob `q` (probability of a correct semantic reading) and a hallucination rate `h`
(probability of asserting a fact with no supporting span). This lets us inject exactly the §12
failure modes and measure whether the governance layers (validator, TAP) catch them, AS A FUNCTION
of interpreter quality — more informative than one model's point accuracy.

Every interpreted record is emitted with interpretation_status INFERRED/AMBIGUOUS (never EXACT) and
the interpretation contract (proposition, span, confidence, alternatives, supporting/conflicting
evidence). The interpreter MAY propose records; it may NOT declare outcomes/authority (enforced by
never emitting outcome/authority fields).
"""
from __future__ import annotations

import torch
from typing import List, Dict

from .document_schema import Document, Workflow
from .evidence_schema import EvidenceRecord, INFERRED, AMBIGUOUS, EXACT, EXTRACT_LLM, EXTRACT_ORACLE

INTERPRETED = ("approval_granted", "clauses_conflict", "exception_applies")


def _rng(seed):
    return torch.Generator().manual_seed(seed)


def _p(g):
    return float(torch.rand(1, generator=g).item())


def interpret_document(doc: Document, q: float, h: float, g, oracle=False) -> List[EvidenceRecord]:
    """Return interpreted-field records. Reads only doc.body + doc.truth spans (truth used only to
    know the correct answer the simulated model is trying to produce)."""
    recs = []
    for fact in doc.truth:
        if fact.field not in INTERPRETED:
            continue
        span_ok = fact.span in doc.body
        if oracle:
            pred = fact.value; status = INFERRED; conf = 0.99; span = fact.span
        else:
            correct = _p(g) < q
            pred = fact.value if correct else (not fact.value)
            # calibrated: correct → high confidence (admitted); wrong → low confidence (reviewed).
            status = AMBIGUOUS if fact.interpretation_status == AMBIGUOUS or _p(g) < 0.10 else INFERRED
            conf = (0.97 if correct else 0.55) - (0.2 if status == AMBIGUOUS else 0.0)
            span = fact.span
            if _p(g) < h:                      # miscalibrated hallucination: confident + fabricated span
                span = "[[no-such-span]]"; conf = 0.9; pred = not fact.value
        recs.append(EvidenceRecord(
            f"{doc.doc_id}-I-{fact.field}", doc.tenant_id, doc.doc_id, span, doc.subject_id,
            fact.field, pred, pred, 1, "active", 0, 10**9, None,
            EXTRACT_ORACLE if oracle else EXTRACT_LLM, conf, status, field_name=fact.field))
    return recs


def interpret_workflow(wf: Workflow, q=0.85, h=0.05, seed=0, oracle=False) -> List[EvidenceRecord]:
    g = _rng(seed)
    out = []
    for d in wf.documents:
        out += interpret_document(d, q, h, g, oracle=oracle)
    return out

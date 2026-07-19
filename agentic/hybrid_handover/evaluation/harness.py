#!/usr/bin/env python3
"""
Evaluation harness — runs a case through the complete enterprise flow under a
named configuration and produces a fully-measured ``CaseResult``.

Configurations:
  * "gates_only" — the frozen pipeline's gates (grounding + packet-vs-full
    faithfulness) only. Represents the architecture AS FROZEN.
  * "augmented"  — frozen gates PLUS the independent validators. Represents the
    architecture WITH the proposed independent validation added.

Running both lets the report answer the stated question directly: are the frozen
gates sufficient, and does independent validation actually reduce unsafe
handovers?
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic.hybrid_handover.faithfulness import ground_spans, packet_only_reresolve
from agentic.hybrid_handover.pipeline import decide_escalation
from agentic.hybrid_handover.schema import Corpus, Document, EvidencePacket

from .cases import EvalCase
from .injectors import Injector
from .metrics import (
    precedence_recall,
    recall,
    unsupported_claims,
)
from .protocols import ExtractorProtocol
from .validators import CoverageValidator, ValidationOutcome

CONFIGS = ("gates_only", "augmented")


class CaseResult(BaseModel):
    case_id: str
    failure_mode: str
    config: str
    injector: str = "none"

    system_decision: str  # SERVE_IN_HOUSE | ESCALATE | REFUSE
    expected_routing: str
    routing_correct: bool

    decisive: tuple[int, int]
    defeater: tuple[int, int]
    definition: tuple[int, int]
    precedence: tuple[int, int]

    decisive_missing: bool
    accepted: bool
    unsafe_handover: bool

    packet_sufficient: bool
    unsupported: tuple[int, int]
    coverage_ok: bool
    should_refuse: bool
    refused: bool

    grounding_ok: bool
    faithfulness_ok: bool
    validator_findings: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    is_synthetic: bool = True


def _packet_as_corpus(packet: EvidencePacket) -> Corpus:
    docs: dict[str, Document] = {}
    order = 0
    for s in packet.evidence:
        if s.doc_id not in docs:
            docs[s.doc_id] = Document(doc_id=s.doc_id, citation=s.citation, order=order, text="")
            order += 1
        docs[s.doc_id].text = (docs[s.doc_id].text + " " + s.quote).strip()
    return Corpus(documents=list(docs.values()))


def evaluate_case(
    case: EvalCase,
    extractor: ExtractorProtocol,
    validators,
    config: str,
    injector: Injector | None = None,
    injected: bool = False,
) -> CaseResult:
    corpus = case.corpus
    if injector is not None and injector.kind == "corpus":
        corpus = injector.apply_corpus(corpus)

    packet = extractor.extract(case.question, corpus)
    if injector is not None and injector.kind == "packet":
        packet = injector.apply_packet(packet)

    # --- frozen gates ------------------------------------------------------
    grounding_ok = ground_spans(packet, corpus).ok
    faithfulness_ok = packet_only_reresolve(packet, extractor).ok

    blocked_by: list[str] = []
    findings: list[str] = []
    if not grounding_ok:
        blocked_by.append("grounding")
    if not faithfulness_ok:
        blocked_by.append("faithfulness")

    # --- independent validators (augmented only) ---------------------------
    coverage_ok = CoverageValidator().validate(case, packet, corpus).passed  # always measured
    if config == "augmented":
        for v in validators:
            outcome: ValidationOutcome = v.validate(case, packet, corpus)
            if not outcome.passed:
                findings.extend(f"{outcome.name}: {f}" for f in outcome.findings)
                if outcome.blocks_handover:
                    blocked_by.append(outcome.name)

    refused = bool(blocked_by)
    system_decision = "REFUSE" if refused else decide_escalation(packet, "interpretation")
    accepted = system_decision in ("ESCALATE", "SERVE_IN_HOUSE")

    # --- completeness metrics ---------------------------------------------
    dec = recall(packet, case.required_decisive)
    dfe = recall(packet, case.required_defeaters)
    dfn = recall(packet, case.required_definitions)
    prc = precedence_recall(packet, case.required_precedence)

    def incomplete(frac):
        return frac[1] > 0 and frac[0] < frac[1]

    decisive_missing = (
        incomplete(dec) or incomplete(dfe) or incomplete(dfn) or incomplete(prc)
        or not coverage_ok
    )
    unsafe = decisive_missing and accepted

    # --- packet sufficiency (downstream reasoner on packet only) ----------
    packet_answer = extractor.resolve(case.question, _packet_as_corpus(packet))
    packet_sufficient = packet_answer.key() == case.expected_answer.key()

    unsupported = unsupported_claims(packet)

    if injected:
        # A fault injector's job is to remove decisive evidence. If it actually
        # did (decisive_missing), the enterprise-safe outcome is REFUSE. If the
        # injector was a no-op on this case (nothing decisive to remove), the
        # packet is still complete and escalating is correct — do not penalise.
        effective_expected = "REFUSE" if decisive_missing else "ESCALATE"
        should_refuse = decisive_missing
    else:
        effective_expected = case.expected_routing
        should_refuse = case.expected_routing == "REFUSE"
    routing_correct = system_decision == effective_expected

    return CaseResult(
        case_id=case.case_id, failure_mode=case.failure_mode, config=config,
        injector=injector.name if injector else "none",
        system_decision=system_decision, expected_routing=effective_expected,
        routing_correct=routing_correct,
        decisive=dec, defeater=dfe, definition=dfn, precedence=prc,
        decisive_missing=decisive_missing, accepted=accepted, unsafe_handover=unsafe,
        packet_sufficient=packet_sufficient, unsupported=unsupported,
        coverage_ok=coverage_ok, should_refuse=should_refuse, refused=refused,
        grounding_ok=grounding_ok, faithfulness_ok=faithfulness_ok,
        validator_findings=findings, blocked_by=blocked_by,
        is_synthetic=case.is_synthetic,
    )

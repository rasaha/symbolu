#!/usr/bin/env python3
"""
Pipeline bridge — reports the EXISTING SEEB pipeline metrics per resolver,
unchanged and not redefined.

A resolver + evidence mode is wrapped as an ExtractorProtocol adapter: the
resolver's typed graph becomes the packet's `conflicts_resolved`, its derived
answer becomes `resolved_answer`, and the mode's spans become the evidence. The
packet is then scored by SEEB's own `evaluate_case` + aggregator — SEEB is not
modified.

Caveat: SEEB routing/abstention is validator-driven and frozen. A resolver's
`abstain` decision is a component-level signal (measured by the resolution-layer
metrics); it does not itself drive SEEB routing here. So the pipeline metrics
mainly reflect improvements that flow through `conflicts_resolved` (precedence)
and `resolved_answer` (sufficiency).
"""

from __future__ import annotations

from agentic.hybrid_handover.evaluation.corpus import CONTROL_CASE_IDS, all_cases
from agentic.hybrid_handover.evaluation.harness import evaluate_case
from agentic.hybrid_handover.evaluation.injectors import ALL_INJECTORS
from agentic.hybrid_handover.evaluation.report import aggregate
from agentic.hybrid_handover.evaluation.validators import DEFAULT_VALIDATORS
from agentic.hybrid_handover.schema import (
    ConflictResolution,
    Coverage,
    EvidencePacket,
    ResolvedAnswer,
)

from .modes import MODES


class _ResolverAdapter:
    """Wraps (resolver, evidence-mode) as an ExtractorProtocol for SEEB."""

    def __init__(self, resolver, mode_fn):
        self._resolver = resolver
        self._mode = mode_fn

    def _evidence_for(self, corpus):
        # reconstruct a throwaway case-like holder for the mode functions
        class _C:
            pass
        c = _C(); c.corpus = corpus; c.question = self._q
        return self._mode(c)

    def extract(self, question, corpus) -> EvidencePacket:
        self._q = question
        evidence = self._evidence_for(corpus)
        res = self._resolver.resolve(question, evidence)
        conflicts = []
        for e in res.graph.edges:
            if e.type in ("supersedes", "overrides", "governs_over"):
                conflicts.append(ConflictResolution(
                    clause="termination_for_convenience",
                    superseded=e.dst, superseded_by=e.src, rule=e.type))
        answer = ResolvedAnswer(
            termination_for_convenience=res.tfc,
            notice_days=res.notice_days, penalty=res.penalty,
            governing_citations=res.governance.governing)
        cov = Coverage(docs_scanned=len(corpus.documents),
                       tokens_ingested=corpus.total_tokens(),
                       spans_returned=len(evidence))
        return EvidencePacket(question=question, evidence=evidence,
                              conflicts_resolved=conflicts, resolved_answer=answer,
                              coverage=cov)

    def resolve(self, question, corpus) -> ResolvedAnswer:
        self._q = question
        res = self._resolver.resolve(question, self._evidence_for(corpus))
        return ResolvedAnswer(termination_for_convenience=res.tfc,
                              notice_days=res.notice_days, penalty=res.penalty,
                              governing_citations=res.governance.governing)


def pipeline_metrics(resolver, mode_name="B_bm25") -> dict:
    adapter = _ResolverAdapter(resolver, MODES[mode_name])
    cases = all_cases()
    controls = [c for c in cases if c.case_id in CONTROL_CASE_IDS]
    results = []
    for case in cases:
        results.append(evaluate_case(case, adapter, DEFAULT_VALIDATORS, "augmented"))
    for case in controls:
        for inj in ALL_INJECTORS:
            results.append(evaluate_case(case, adapter, DEFAULT_VALIDATORS, "augmented",
                                         injector=inj, injected=True))
    agg = aggregate(results)

    def pct(fr):
        return None if fr.value is None else round(fr.value * 100, 1)
    return {
        "unsafe_handover_rate": pct(agg.unsafe_handover),
        "fail_closed_rate": pct(agg.fail_closed),
        "packet_sufficiency": pct(agg.packet_sufficiency),
        "routing_accuracy": pct(agg.routing_accuracy),
        "unsupported_claim_rate": pct(agg.unsupported_claim),
        "precedence_recall": pct(agg.precedence_recall),
    }

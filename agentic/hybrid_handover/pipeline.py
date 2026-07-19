#!/usr/bin/env python3
"""
Two-tier handover pipeline.

Part 1 (in-house, O(n), on-prem)   ->  gates  ->  Part 2 (frontier API, redacted)

Flow:
  1. Part 1: in-house tier distills the corpus into an EvidencePacket.
  2. Gate A — grounding: every span must quote its source verbatim.
  3. Gate B — faithfulness: the packet, re-resolved alone, must reproduce the
     full-corpus verdict (the "did we drop the needle?" check).
  4. Escalation decision: serve in-house, or escalate to the frontier.
  5. Redact: swap real values for placeholders; keep the map in-house.
  6. Gate C — no-leak: hard stop if any secret survived redaction.
  7. Part 2: frontier reasons over the redacted packet.
  8. Re-hydrate the frontier answer in-house; emit an audit record.

Any gate failure raises ``HandoverRefused`` — a cheap wrong answer is worse than
an expensive right one, so the pipeline refuses rather than degrade silently.
"""

from __future__ import annotations

import json

from .faithfulness import ground_spans, packet_only_reresolve
from .frontier import FrontierModel
from .inhouse import InHouseExtractor
from .redaction import assert_no_leak, redact, rehydrate
from .schema import (
    Corpus,
    EvidencePacket,
    HandoverAudit,
    HandoverResult,
)


class HandoverRefused(RuntimeError):
    """A gate blocked the handover. Carries the failed gate name and detail."""

    def __init__(self, gate: str, detail: str):
        self.gate = gate
        self.detail = detail
        super().__init__(f"[{gate}] {detail}")


def _est_tokens(obj) -> int:
    return len(json.dumps(obj, default=str)) // 4


def decide_escalation(
    packet: EvidencePacket, task_type: str, min_confidence: float = 0.9
) -> str:
    """SERVE_IN_HOUSE for pure lookup with confident, complete spans; ESCALATE
    when the task needs generation/interpretation the O(n) tier can't do."""
    if not packet.evidence:
        return "REFUSE"
    weakest = min(s.confidence for s in packet.evidence)
    if task_type == "lookup" and weakest >= min_confidence:
        return "SERVE_IN_HOUSE"
    return "ESCALATE"


def run_handover(
    question: str,
    corpus: Corpus,
    secrets: dict[str, str],
    extractor: InHouseExtractor,
    frontier: FrontierModel,
    task_type: str = "interpretation",
) -> HandoverResult:
    # --- Part 1: in-house distillation -------------------------------------
    packet = extractor.extract(question, corpus)

    # --- Gate A: grounding -------------------------------------------------
    grounding = ground_spans(packet, corpus)
    if not grounding.ok:
        raise HandoverRefused("grounding", f"ungrounded spans: {grounding.ungrounded}")

    # --- Gate B: packet-only faithfulness ----------------------------------
    faith = packet_only_reresolve(packet, extractor)
    if not faith.ok:
        raise HandoverRefused(
            "faithfulness",
            f"packet re-resolves to {faith.packet_only.key()} "
            f"but full corpus gave {faith.full.key()} — distillation lost the answer",
        )

    # --- Escalation decision ----------------------------------------------
    decision = decide_escalation(packet, task_type)
    corpus_tokens = packet.coverage.tokens_ingested

    if decision == "REFUSE":
        raise HandoverRefused("escalation", "no evidence to act on")

    if decision == "SERVE_IN_HOUSE":
        ra = packet.resolved_answer
        answer = (
            f"[in-house] Termination for convenience: "
            f"{ra.termination_for_convenience}; notice {ra.notice_days} days; "
            f"penalty {ra.penalty}; per {', '.join(ra.governing_citations)}."
        )
        audit = HandoverAudit(
            escalated=False,
            corpus_tokens=corpus_tokens,
            egress_tokens_est=0,
            reduction_ratio=float("inf"),
            grounded_spans=len(packet.evidence),
            masked_placeholders=[],
            leak_check="pass",
            decision=decision,
        )
        return HandoverResult(final_answer=answer, audit=audit, packet=packet)

    # --- Redact for egress -------------------------------------------------
    redacted, rmap = redact(packet, secrets)
    egress_blob = redacted.model_dump_json()

    # --- Gate C: no-leak (hard stop) --------------------------------------
    assert_no_leak(egress_blob, secrets.keys())  # raises LeakError if any survived

    egress_tokens = _est_tokens(redacted.model_dump())

    # --- Part 2: frontier reasoning over redacted packet -------------------
    memo_redacted = frontier.reason(redacted)

    # --- Re-hydrate in-house ----------------------------------------------
    final = rehydrate(memo_redacted, rmap)

    audit = HandoverAudit(
        escalated=True,
        corpus_tokens=corpus_tokens,
        egress_tokens_est=egress_tokens,
        reduction_ratio=round(corpus_tokens / max(egress_tokens, 1), 1),
        grounded_spans=len(packet.evidence),
        masked_placeholders=sorted(rmap.mapping.keys()),
        leak_check="pass",
        decision=decision,
    )
    return HandoverResult(final_answer=final, audit=audit, packet=packet)

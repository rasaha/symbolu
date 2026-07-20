# Hybrid-LLM Enterprise Handover

A runnable scaffold for the **two-tier deployment** of the Hybrid LLM: an
in-house O(n) tier that distills a confidential long-context corpus on-prem, and
a frontier quadratic-model API that reasons over a small, redacted evidence
packet. The point of this package is to make the **handover** concrete — it is
the piece every "in-house tier + API" pitch hand-waves.

```
Part 1 (in-house, O(n), on-prem)  ──►  gates  ──►  Part 2 (frontier API, redacted)
   distill + reconcile                 grounding      reason / draft
   250K tokens, nothing egresses       faithfulness   ~a few hundred tokens
                                       no-leak         placeholders only
```

## The scenario (fixture)

Vendor contract renewal. The MSA prohibits termination for convenience;
**Amendment 4, ~200K tokens later, silently overrides it**; Amendment 6 sets the
penalty. The correct verdict requires reconciling a clause near the start with
one near the end — the long-range recall the O(n) tier exists to perform.

## The handover contract (the developed piece)

1. **Evidence packet** (`schema.py`) — verbatim spans + provenance
   (`char_span`), recorded supersessions, and a structured `ResolvedAnswer`.
   Only a **redacted** copy ever egresses; the redaction map stays in-house.
2. **Grounding gate** (`faithfulness.ground_spans`) — every span must re-slice to
   its quote in the source. Ungrounded → refuse.
3. **Faithfulness gate** (`faithfulness.packet_only_reresolve`) — re-resolve using
   *only* the packet; it must reproduce the full-corpus verdict. This is the
   "did we drop the needle?" check, and it needs no oracle. Divergence → refuse.
4. **Redaction gate** (`redaction.py`) — real values → placeholders before egress;
   `assert_no_leak` is a hard stop if any secret survived; `rehydrate` restores
   values in-house on the returned answer.
5. **Escalation decision** (`pipeline.decide_escalation`) — serve confident
   lookups in-house; escalate interpretation/generation to the frontier.

## Run it

```bash
python -m agentic.hybrid_handover.demo      # end-to-end walkthrough
python -m pytest tests/test_hybrid_handover.py -q
```

Demo output: 205K tokens ingested in-house → ~480 tokens egressed (**~427×
reduction**), secrets masked, and a needle-drop is refused by the faithfulness
gate.

## Status — honest

- The in-house tier here is a **deterministic rules-based stand-in** that
  implements the same `extract` / `resolve` interface a
  `HybridPhaseTransformer`-backed extractor would. Swapping in the neural model
  changes nothing downstream — the gates, redaction, and frontier wiring are
  identical.
- The frontier tier is a **template mock**; the real deployment swaps
  `MockFrontierModel` for an Anthropic/OpenAI client with the same contract.
- What is **not yet measured**: extraction faithfulness on *real* long documents.
  Today only a 240K-param synthetic needle result exists. Until that gate is
  validated on real corpora, the two-tier story is a design, not a capability —
  this scaffold is what that validation would run against.

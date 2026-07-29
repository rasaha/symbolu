# Hybrid Token + Event Dual-Attention — bounded validation

**Decisive question.** Can Mistral retain its token-level language capability while a *separate,
bounded, provenance-preserving event-attention path* improves enterprise relational reasoning — and
is that gain large enough to justify **integrating** the two paths rather than keeping the event
reasoner external?

This is the bounded validation phase for the proposed dual-attention Hybrid LLM:

```
raw enterprise text
  → Mistral token-level processing        (token attention — language)
  → proposed normalized EvidenceRecords
  → normalization + provenance validation  (deterministic gate)
  → P5 binding slots                        (bounded exact working memory)
  → full event-to-event softmax over K governed records   (event attention — evidence)
  → typed findings + deterministic outcome
  → Mistral explanation → TAP
```

It is the direct successor to `experiments/enterprise_slots_quadratic` (which established that full
slot-to-slot attention **S5** beats query-to-slot-only **S6**); here we wrap that event operator in
the Mistral token path and test the **dual-attention** architecture across arms H0–H8.

## Two attention domains (never merged)

| domain | operates over | softmax axis | role |
|---|---|---|---|
| **token attention** | text tokens | token positions | language understanding / generation (Mistral-native) |
| **event attention** | K validated `EvidenceRecords` (K∈{4,8,16}) | **event slots** | conflicts, support, exceptions, version, chains |

Thousands of tokens and a handful of evidence events are **never** concatenated into one
undifferentiated matrix; event attention never replaces token attention.

## Sandbox honesty boundary

This environment has **no GPU and no `torch`/`numpy`/`transformers`**. Two consequences, both handled
explicitly rather than by fabricating numbers:

1. The whole pipeline is implemented on a **~350-line pure-stdlib reverse-mode autograd**
   (`autograd.py`, gradient-checked in the test suite). The decisive object under test — the bounded
   K≤16 event operator — is tiny, so it trains and evaluates for real on CPU.
2. The token path (`mistral_adapter.py`) is a **small local causal-transformer stand-in for
   Mistral**, used *identically across every arm*. Absolute perplexity is not Mistral's; **cross-arm
   comparisons are valid** because every arm sees the same token model. Every result in
   `results/HYBRID_TOKEN_EVENT_ATTENTION_RESULTS.json` is a real CPU run.

## Arms (§6)

`H0` vanilla token · `H1` token+retrieved text · `H2` events+mean-pool · `H3` events+**full event
self-attention** · `H4` deterministic event reasoning · `H5` oracle events+attention · `H6` predicted
events+attention · `H7` integrated adapter (frozen base) · `H8` H7+LoRA.

`H2` and `H3` share **identical encoder + head init** — the only difference is a **gated-residual**
slot-to-slot interaction (gate init 0 → H3 starts byte-identical to H2 and can only *add* the
interaction), so `H3 − H2` isolates the causal value of event-to-event interaction.

## Layout

```
event_schema.py               EventRecord (all §3 fields) + provenance hash + Slot
normalization_bridge.py       deterministic validate → authorize → P5-admit ≤K  (integrity gate)
event_encoder.py              typed exact fields → learned E ∈ R^(K×d)
event_attention.py            bounded full event self-attention (K×K softmax over slots) + mean-pool
mistral_adapter.py            local Mistral stand-in: causal token attn + LM head + task head + LoRA
token_event_bridge.py         token↔event cross-attention adapters (Level B)
deterministic_event_reasoner.py   frozen rule-based outcome mapper (H4)
model_arms.py                 arms H0–H8
datasets.py                   procurement/approval corpus, 10 task families, oracle+predicted+text
train.py                      staged protocol (§9 Stage 1–5)
evaluate.py                   §11 metrics, §13 capacity, §15 acceptance
causal_controls.py            §12 interventions
run.py                        orchestrator → results JSON
tests/test_hybrid.py          autograd gradcheck, softmax-axis, integrity invariants
```

## Reproduce

```bash
PYTHONPATH=<repo> python -m experiments.hybrid_token_event_attention.run          # full (~12 min CPU)
PYTHONPATH=<repo> python -m experiments.hybrid_token_event_attention.run --quick  # fast smoke
PYTHONPATH=<repo> python -m unittest experiments.hybrid_token_event_attention.tests.test_hybrid
```

Frozen components (Phase research, evidence ledger, deterministic joins, P5 policy, deterministic
field computation, outcome mapper, TAP, Decision Governance, ActionGate) are **consumed, never
modified**. **No Phase in any arm.** FSCS is out of scope for this experiment (§14).

See `HYBRID_TOKEN_EVENT_ATTENTION_REPORT.md` for the full findings and verdict.

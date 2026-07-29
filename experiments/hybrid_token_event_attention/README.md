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

---

# Recommended Architecture — Post-Experiment Reviewer Notes

> **Status: post-hoc architecture recommendation, NOT part of the pre-registered study.**
> Nothing in this section modifies the pre-registered acceptance criteria, the raw results, the
> verdicts, or the experimental conclusions above. These are design recommendations *derived from*
> the canonical results in `HYBRID_TOKEN_EVENT_ATTENTION_RESULTS.json` and are explicitly separated
> from what the controlled run validated. Where a recommendation was not tested, it is labelled
> as such.

## 1. Router-gated event attention

The recommended runtime architecture is revised so that **event attention is not permanently
inline**. Event attention becomes one branch of a contract-aware router, not the default reasoning
mechanism:

```
Validated EvidenceRecords
    ↓
Contract-aware reasoning router
    ├── deterministic-only path for exact threshold, version, date,
    │   access, authority, schema and calculation contracts
    ├── deterministic + bounded event-attention path for conflict,
    │   exception, support/opposition, chain and multi-record contracts
    └── quarantine / bounded clarification / human-review path when
        required evidence is missing or ambiguous
```

Grounding in the canonical results:

- The **governed event substrate was strongly supported** (H3 − H0 = +0.633; H3 − H1 = +0.377).
- **Event attention produced causal but task-specific value** (mean-pool ablation cost −0.083
  relational accuracy — a real causal contribution — but concentrated on relational families).
- **H3 − H2 was +0.046 relational and +0.017 overall.**
- The relational gain **remained below the pre-registered +0.05 bar.**
- Therefore event attention is an **optional relational operator, not the default reasoning
  mechanism** for every contract; exact-lookup contracts should take the deterministic-only path
  and pay neither the K² attention cost nor its training variance.
- The **routing policy itself was not validated in this experiment** and is a recommended
  next-stage design.

## 2. Promote event construction and validation to a first-class subsystem

The token→event stage should be expanded from a single arrow into a first-class subsystem:

- candidate extraction;
- schema validation;
- source-span verification;
- entity and subject resolution;
- active-version resolution;
- authority and access validation;
- confidence calibration;
- duplicate and contradiction checks;
- `VALIDATED`, `QUARANTINED`, `REJECTED`, `SUPERSEDED` and `AUTHORITATIVE` states;
- bounded human review for low-confidence or materially ambiguous records.

Grounding in the final metrics:

- **event extraction exact match = 0.909**
- **required-event survival (K=8, predicted) = 0.773**
- **oracle-versus-predicted gap (H5 − H6) = 0.087**
- **conditional accuracy given required events survived = 0.823 ≫ 0.757 unconditional**

Together these show that the **dominant current bottleneck is event construction and selection,
not reasoning over correct evidence**: when the required evidence survives, the reasoner is strong
(0.823); most of the lost accuracy is evidence that was never extracted, mis-normalized, or evicted.

**ROADMAP (not validated):** multi-pass extraction, consensus/ensemble extraction, and human
adjudication are recommended directions but were **not** implemented or measured in this study.
Only the single-pass extraction + deterministic validation gate reported above is VALIDATED.

## 3. Govern the event-to-token clarification loop

The event→token clarification capability must be constrained by a bounded `ClarificationRequest`
contract:

```json
{
  "request_id": "CLR-0007",
  "triggering_evidence_ids": ["EV-1042", "EV-1047"],
  "unresolved_question": "Does 'approved' refer to the current request or the prior contract?",
  "permitted_scope": {"document_ids": ["POLICY-2026-03"], "source_spans": ["p3:120-240"]},
  "max_attempts": 2,
  "requesting_component": "event_reasoner",
  "created_at": "2026-07-29T00:00:00Z",
  "responses": [{"attempt": 1, "interpretation": "...", "provenance_hash": "...", "at": "..."}]
}
```

Required controls:

- a **hard attempt limit**;
- **append-only logging** of every request and response;
- **no silent widening** of the permitted document / source-span scope;
- **independent schema, provenance, authority and access validation** of each response;
- validation **against the source, not against the hypothesis** that caused the clarification;
- **quarantine or human review** once the attempt limit is reached;
- **deterministic replay** of the full clarification history.

Rationale: these controls prevent **interpretation shopping** (re-asking until some interpretation
passes) and block **indirect learned influence** by the token model over authoritative evidence
admission — the token model proposes; it never mutates authoritative evidence.

**This control is an architectural recommendation and was not experimentally validated.**

## 4. Revalidate TAP after any model-weight change

Any adapter, LoRA, or base-weight modification must trigger a **full TAP re-validation**, not merely
a language-quality check:

- supported-claim precision;
- unsupported-claim recall;
- authority-exceedance recall;
- qualifier preservation;
- evidence-ID attribution;
- corrupt-provenance rejection;
- irrelevant-document invariance;
- missing-source-span blocking;
- evaluation on **predicted** events, not only oracle events.

**Perplexity preservation alone must not be treated as proof of explanation faithfulness.**

**Reconciliation against the canonical results.** The integrated LoRA arm (H8) in the canonical
`HYBRID_TOKEN_EVENT_ATTENTION_RESULTS.json` scored macro-all **0.950** (H8 − H7 = **+0.070**,
H7 − H3 = **+0.040**) with a language-preservation figure of **−23.79 %** perplexity change relative
to the frozen base reference — i.e. **no** language regression (perplexity slightly improved), so the
≤ 1 % regression bar is met. An earlier value of **+6.95 %** regression appeared in an intermediate
development log during this work; it came from a **superseded development run** (fewer epochs /
smaller data / single seed) and is **not** the canonical result. The canonical final-run numbers
above supersede it. Regardless of sign, note that these figures were measured on **oracle** events
and reflect language quality only — under recommendation 4 they do not by themselves license
adopting LoRA, which requires the TAP re-validation on predicted events described here.

## Recommended runtime architecture (post-hoc)

```
Raw enterprise sources
    ↓
Frozen token-language model
    ↓
Provisional EvidenceRecords
    ↓
First-class extraction, normalization and provenance-validation subsystem
    ↓
Authoritative evidence ledger
    ↓
P5 smallest-sufficient-set selection
    ↓
Contract-aware reasoning router
    ├── deterministic computation
    ├── deterministic computation + bounded event attention where validated
    └── quarantine / bounded clarification / human review
    ↓
Typed evidence-linked findings
    ↓
Frozen token-language explanation
    ↓
TAP
    ↓
Decision Governance
    ↓
ActionGate
```

## Evidence taxonomy

| claim | category | basis |
|---|---|---|
| Governed event path >> token-only / retrieval (H3−H0 +0.633, H3−H1 +0.377) | **SUPPORTED BY THIS CONTROLLED RUN** | canonical arms table |
| Frozen base preserves language exactly (H7 0.0%); full fine-tune destroys it (H0 +5661%) | **SUPPORTED BY THIS CONTROLLED RUN** | §10 language preservation |
| Exact-record + embedding; evidence-ID preservation 1.00; unauthorized 0.00; corrupt-ID invalidation 1.00 | **SUPPORTED BY THIS CONTROLLED RUN** | §6 integrity + §12 controls |
| Deterministic reasoning sufficient on fully-specified domain (H4 oracle 1.00) | **SUPPORTED BY THIS CONTROLLED RUN** | canonical arms table |
| Event-to-event attention causal but task-specific (ablation −0.083; H3−H2 +0.017 macro) | **SUPPORTED BY THIS CONTROLLED RUN** | §2, §3, §7 |
| Extraction / selection is the dominant bottleneck (survival 0.773; H5−H6 0.087; cond 0.823≫0.757) | **SUPPORTED BY THIS CONTROLLED RUN** | §6 |
| Contract-aware router gating event attention on/off per contract | **ARCHITECTURE RECOMMENDATION** | recommendation 1 (untested) |
| First-class construction subsystem with VALIDATED/QUARANTINED/REJECTED/SUPERSEDED/AUTHORITATIVE states | **ARCHITECTURE RECOMMENDATION** | recommendation 2 (states untested) |
| Bounded, append-only, replayable ClarificationRequest contract | **ARCHITECTURE RECOMMENDATION** | recommendation 3 (untested) |
| Mandatory TAP re-validation after any weight change | **ARCHITECTURE RECOMMENDATION** | recommendation 4 (untested) |
| Multi-pass extraction, consensus extraction, human adjudication | **ARCHITECTURE RECOMMENDATION** (ROADMAP) | recommendation 2 (not implemented) |
| Absolute accuracy / perplexity / LoRA value at real scale (Mistral, real corpora) | **REQUIRES REAL-MODEL VALIDATION** | token path is a local stand-in |
| H7/H8 integration value on predicted (not oracle) events at scale | **REQUIRES REAL-MODEL VALIDATION** | H7/H8 measured on oracle events |
| End-to-end value, latency, and governance behaviour on live tenant data | **REQUIRES ENTERPRISE SHADOW PILOT** | out of scope for a controlled run |
| Router policy, clarification-loop, and human-review efficacy in production | **REQUIRES ENTERPRISE SHADOW PILOT** | recommendations 1–3 in operation |

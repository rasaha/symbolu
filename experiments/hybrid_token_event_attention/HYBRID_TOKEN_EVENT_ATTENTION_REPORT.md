# Hybrid Token + Event Dual-Attention — validation report

Bounded validation of the proposed dual-attention Hybrid LLM: a Mistral-compatible **token-language
path** plus a separate, governed, provenance-preserving **event-reasoning path** over K validated
`EvidenceRecords`. The question is not whether to replace Mistral's token attention — it is whether
a *separate* bounded event-to-event attention path adds **measurable, causal** value, and whether
that value justifies **integrating** the two paths rather than keeping the event reasoner external.

> **Reproducibility & honesty boundary.** No GPU / `torch` / `numpy` / `transformers` exist in this
> sandbox. The pipeline runs on a ~350-line pure-stdlib reverse-mode autograd (`autograd.py`,
> gradient-checked). The token path is an explicit **local Mistral stand-in** used *identically*
> across all arms — absolute perplexity is not Mistral's, but every cross-arm comparison is valid.
> All numbers below are a **real CPU run** (2 seeds, `n_train=800`, `n_heldout=300` unseen
> entities/templates/wording; runtime ≈ 884 s) recorded in
> `results/HYBRID_TOKEN_EVENT_ATTENTION_RESULTS.json`. Frozen components (Phase, evidence ledger,
> deterministic joins, P5 policy, deterministic field/outcome mappers, TAP, Decision Governance,
> ActionGate) were consumed, never modified. **No Phase in any arm. FSCS excluded (§14).**

## 1. Arm results (held-out macro accuracy)

| arm | description | event source | macro-all | macro-relational |
|---|---|---|---:|---:|
| **H0** | vanilla token model over raw text | — | 0.207 | 0.292 |
| **H1** | token + retrieved text packet | — | 0.463 | 0.342 |
| **H2** | events + mean pooling | oracle | 0.823 | 0.646 |
| **H3** | events + **full event self-attention** | oracle | **0.840** | **0.692** |
| **H4** | deterministic event reasoning | oracle | **1.000** | 1.000 |
| **H4** | deterministic event reasoning | predicted | 0.777 | 0.825 |
| **H5** | oracle events + full attention | oracle | 0.840 | 0.692 |
| **H6** | predicted events + full attention | predicted | 0.753 | 0.633 |
| **H7** | integrated adapter (frozen base) | oracle | 0.880 | 0.783 |
| **H8** | H7 + limited LoRA | oracle | 0.950 | 0.908 |

## 2. Required comparisons (§7)

| comparison | meaning | value |
|---|---|---:|
| **H3 − H2** (relational) | value of event-to-event interaction over pooling | **+0.046** |
| H3 − H2 (all) | " (all families) | +0.017 |
| **H3 − H4** (oracle) | learned attention beyond deterministic rules | **−0.160** |
| H3 − H4 (predicted) | " under realistic extraction | −0.023 |
| **H5 − H6** | loss from event extraction/normalization | **+0.087** |
| **H3 − H1** | governed events vs ordinary retrieved text | **+0.377** |
| H3 − H0 | governed events vs vanilla token | +0.633 |
| **H7 − H3** | integrated adapter vs external reasoner | **+0.040** |
| **H8 − H7** | value of adapting Mistral weights (LoRA) | **+0.070** |

**The decisive positive result is the event path itself.** A governed, normalized event path
(H3) beats vanilla token processing by **+0.63** and retrieval-augmented text by **+0.38**. This is
where the enterprise value lives, and it is large and unambiguous.

**Event-to-event interaction over pooling is real but marginal at the macro level** (+0.017 all,
+0.046 relational — just under the +0.05 bar). Its causal reality is confirmed by the ablation
below, not by the headline macro.

**Deterministic reasoning is sufficient on this fully-specified domain** — H4 is exact on oracle
(1.000) and even edges H3/H6 on predicted (0.777 vs 0.753). Learned event attention does **not**
exceed complete deterministic rules here; its niche is robustness where rules are incomplete.

## 3. Causal controls (§12) — H3 on predicted events

| intervention | metric | result | expected | verdict |
|---|---|---:|---|---|
| replace event attention with mean pooling | relational acc | 0.658 → 0.575 (**−0.083**) | relational must degrade | ✅ interaction is causal |
| shuffle event **order** | all acc | 0.757 → 0.757 (**0.000**) | no change on set-like tasks | ✅ no positional artefact |
| remove one **required** event | all acc | 0.757 → 0.460 (**−0.297**) | must reduce | ✅ material |
| remove **irrelevant** events | all acc | 0.757 → 0.630 (−0.127) | little/positive | ⚠️ mild sensitivity to slot composition |
| inject exact **duplicates** | all acc | 0.757 → 0.770 (+0.013) | robust | ✅ robust |
| **corrupt evidence IDs** | authoritative-output invalidation | **1.000** | must invalidate | ✅ |
| inject **unauthorized** cross-tenant | admitted-unauthorized rate | **0.000** | never admitted | ✅ |

The mean-pool ablation is the key scientific result on the interaction axis: **removing event-to-event
interaction costs 0.083 relational accuracy**, so the interaction *does* carry causal weight on
relational tasks even though a separately-trained pooling arm nearly matches H3 on the macro. Order
invariance holds (set-like reasoning, as intended). Required-event removal is materially damaging;
irrelevant-event removal shows a mild negative (the gated-pool context is somewhat sensitive to slot
composition — a known limitation of pooled readouts, not a provenance issue).

## 4. Token-language preservation (§10)

| model | perplexity | Δ vs base reference |
|---|---:|---:|
| base reference (LM-pretrained) | 44.55 | — |
| **H7** (frozen base + event adapter) | 44.55 | **0.0 %** |
| **H8** (frozen base + LoRA) | 33.96 | **−23.8 %** (improved, no regression) |
| **H0** (full task fine-tune of the token model) | 2566.87 | **+5661 %** (catastrophic) |

This is one of the strongest findings: **freezing the base preserves language exactly (H7: 0 %)**,
LoRA caused **no** language regression (it slightly improved perplexity on this corpus), and
**full fine-tuning of the token path to do the task destroys language modelling** (+5661 %). The
lesson is decisive — do not fine-tune the token path to reason over evidence; keep the event path
**external or as a frozen-base adapter**.

## 5. Event capacity study (§13) — H3 on predicted events

| K | required survival | final acc | acc \| required survived | attention ops (K²) | event-state bytes |
|---:|---:|---:|---:|---:|---:|
| 4 | 0.747 | 0.730 | 0.804 | 16 | 576 |
| **8** | 0.773 | **0.757** | **0.823** | 64 | 1152 |
| 16 | 0.773 | 0.757 | 0.823 | 256 | 2304 |

**K=8 is the smallest sufficient capacity for full enterprise outcomes.** K=4 reaches within 0.03 of
it at **¼ the attention cost and ½ the event-state bytes** — the right choice for tight contracts.
**K=16 adds nothing** (identical to K=8: the extra slots admit no additional required evidence and
only inflate cost). Select the smallest sufficient K per contract.

## 6. Integrity, extraction, and bottleneck (§11)

- **Evidence-ID preservation = 1.00**, **unauthorized-event inclusion = 0.00**, corrupt-ID
  invalidation = 1.00 — every event-level result is traceable to an exact evidence ID (Q3 ✅).
- Extraction: exact-match 0.909, entity-linking 0.957, schema-validity 1.00, source-span 1.00.
- Required-event survival (K=8, predicted) = 0.773; **conditional accuracy given required events
  survived = 0.823** ≫ unconditional 0.757.
- Conflict F1: H3 0.832 > H2 0.766 (H4 exact 1.0). Abstention precision/recall = 1.0/1.0 (H3 oracle).
- Event-attribution exact-match (top-attended slot ∈ required set) = 0.561 — the *attention-argmax*
  attribution is weak, but **ledger traceability is a structural guarantee (1.00)**, independent of
  where soft attention mass lands.

The gap between conditional (0.823) and unconditional (0.757) accuracy, the H5−H6 construction gap
(0.087), and required-survival (0.773) all point to the **same bottleneck: event extraction and
selection**, not event reasoning, not the token↔event bridge, not language generation.

## 7. Acceptance scorecard (§15) — thresholds fixed before the run

| criterion | target | value | met |
|---|---|---:|:--:|
| H3 − H2 relational | ≥ 0.05 | 0.046 | ❌ (narrow) |
| H3 − H1 conflict/multi-event | ≥ 0.08 | 0.200 | ✅ |
| event-attribution exact-match | ≥ 0.95 | 0.561 | ❌ |
| evidence-ID preservation | = 1.00 | 1.000 | ✅ |
| unauthorized-event inclusion | = 0.00 | 0.000 | ✅ |
| held-out degradation | ≤ 0.05 | 0.087¹ | ❌¹ |
| token-language regression (H8) | ≤ 1 % | −23.8 % | ✅ |
| event-path ablation removes relational gain | — | −0.083 | ✅ |
| required-event removal ⇒ material decrease | ≥ 0.05 | 0.297 | ✅ |
| H6 within 0.10 of H5 (or extraction identified) | ≤ 0.10 | 0.087 | ✅ |
| H7 beats/matches H3 | ≥ −0.01 | +0.040 | ✅ |

¹ The 0.087 figure is the **oracle→predicted construction gap**, not a memorization gap: *every*
accuracy reported here is already on the unseen held-out split. It is flagged, honestly, as the
extraction bottleneck (§6), not a generalization failure — consistent with the H5−H6 gap.

**Verdict on strict validation of the interaction axis:** two thresholds (H3−H2 ≥ 0.05;
attribution ≥ 0.95) are **not** met. Per the pre-registered rule we do **not** lower them. The
architecture is therefore **not** validated as a universal interaction win; it is validated as a
**governed event path with task-specific interaction value and complete provenance** (below).

## 8. Interpretation (§16)

- **H3 > H2 but H3 ≈/≤ H4 ⇒ deterministic reasoning is sufficient** on this closed domain; retain
  event attention only for the families where it demonstrably helps (authoritative-source, conflict
  F1, supporting/opposing), per the ablation.
- **H5 ≳ H6 with the gap in extraction ⇒ event construction is the primary bottleneck.**
- **H7 ≈ H3 (+0.04) ⇒ prefer the external governed reasoner** for modularity and auditability; the
  integrated adapter's gain is modest.
- **H8 > H7 (+0.07) with no language harm ⇒ LoRA adds enterprise value without regressing language
  or provenance** in this bounded test — but on **oracle** events and by touching base weights;
  its value should be re-confirmed on predicted events before production, and it does not change the
  event path's structural provenance (still 1.00).
- **Value is mode-specific, not universal superiority:** the event path's decisive win is over
  token-only/retrieval baselines; the event-to-event interaction is a smaller, task-specific effect.

---

## Final verdict (§17)

```
Mistral token path:
  preserved  (frozen base = 0.0% perplexity regression; H7 identical to base.
              WARNING: full fine-tuning of the token path to do the task — H0 —
              degrades language catastrophically, +5661% perplexity. Do not fine-tune
              the base to reason over evidence.)

Event construction:
  bottleneck  (extraction exact-match 0.909, required-event survival 0.773,
               H5-H6 construction gap 0.087; conditional accuracy 0.823 >> 0.757
               unconditional — the dominant realistic limiter is extraction/selection.)

Event-to-event attention:
  task-specific  (causal: mean-pool ablation costs -0.083 relational accuracy;
                  but macro gain over pooling is marginal (+0.017 all, +0.046 relational,
                  below the 0.05 bar), and complete deterministic rules match or beat it.)

Event attention versus pooling:
  +0.017 macro-all  (+0.046 relational; causal contribution -0.083 when removed)

Event attention versus deterministic reasoning:
  -0.160 on oracle  (-0.023 on predicted) — deterministic reasoning is sufficient on this
  fully-specified domain; learned attention's niche is robustness where rules are incomplete.

Oracle-event gap:
  0.087  (H5 0.840 - H6 0.753)

Best architecture:
  H8 (0.950) > H7 (0.880) > H3 (0.840) on this bounded oracle-event test.
  For production, the EXTERNAL governed reasoner (H3-class, 0.840) is recommended for
  auditability, modularity, and perfect language preservation; H7/H8 gains are modest
  and were measured on oracle events.

Best integration mode:
  external (recommended for modularity/auditability/language preservation)
  / adapter H7 (+0.04, frozen base, 0% language regression)
  / LoRA H8 (+0.07, no measured language harm, but touches base weights — re-verify on
    predicted events before adopting)

Best event capacity:
  K=8 for full enterprise outcomes; K=4 for tight contracts (within 0.03 at 1/4 attention
  cost and 1/2 event-state bytes); K=16 adds nothing (noise/cost ceiling).

Token-language regression:
  0.0%  (H7, frozen base)   |   H8 LoRA: -23.8% (improved, no regression)
  |   H0 full fine-tune: +5661% (catastrophic — cautionary, not adopted)

Evidence-ID preservation:
  1.00

Unauthorized-event inclusion:
  0.00

Primary remaining bottleneck:
  event extraction / event selection
  (not event reasoning, not the token-event bridge, not language generation)

Authorized architecture:
  Mistral token attention
  → governed event construction
  → normalization validation
  → P5 binding slots
  → bounded full event-to-event attention where useful (relational / conflict families; K=8, or K=4
    for tight contracts)
  → deterministic typed findings and outcome
  → Mistral explanation
  → TAP
  → Decision Governance
  → ActionGate
```

**Answer to the decisive question.** Yes — Mistral's token-language capability is fully retained
while a separate, bounded, provenance-preserving event path (evidence-ID preservation 1.00,
unauthorized inclusion 0.00) improves enterprise relational reasoning **decisively over token-only
and retrieval baselines (+0.38 to +0.63)**. But the *incremental* value of full event-to-event
attention over simple pooling is **task-specific and small** (+0.017 macro; causal −0.083 on
relational when ablated), and complete deterministic rules already suffice on a fully-specified
domain. Integrating the two paths (H7/H8) yields only a modest additional gain on oracle events and
its main risk — language degradation — is entirely avoided by freezing the base. **Recommendation:
ship the external governed event reasoner with deterministic outcome mapping and event attention on
the relational/conflict families; treat the integrated adapter and LoRA as optional accelerators to
be re-validated on predicted events, never as a reason to fine-tune the token path.**

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

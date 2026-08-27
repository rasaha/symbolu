# Preregistration — Phase restricted to true HRR binding

**Status:** **PREREGISTRATION ONLY — NOT AUTHORIZED FOR IMPLEMENTATION OR EXECUTION.**
**Date:** 2026-08-27
**Track:** Hybrid LLM neural-memory research. Corresponds to the thesis §11 future-research
menu, every item of which is explicitly unauthorized; inclusion there does not authorize
execution, and neither does this document.
**Sources read:** `symbolu/lightweight_phase/reference_equations.md` (frozen canonical
equations) · `experiments/phase_lc/REPORT.md` and `experiments/phase_lc/models.py` (the
executed falsification and the arms it actually ran).

> This document creates no code, runs nothing, and changes no verdict. It exists so that if
> the variant is ever authorized, its gates were fixed **before** any result was seen.

---

## 1. The question, stated so it can fail

Holographic Reduced Representations bind with unit-modulus phasors and unbind by conjugate
multiplication. Phase, as shipped and as falsified, is *shaped* like HRR but violates three of
its preconditions. The question is narrow:

> Does restoring HRR's algebraic preconditions — unit-modulus keys, exact conjugate unbind, no
> decay, and a count-based rather than learned normalizer — move Phase from chance-level
> retrieval to measurable retrieval, under the same matched conditions that falsified it?

**A negative answer is the expected outcome and is a publishable result**, because it would
close the "Phase was never given a fair HRR formulation" objection permanently.

## 2. The delta is smaller than it looks — stated up front

The naive framing of this variant is "remove the amplitude head and the detached normalizer."
Reading the arm that was actually falsified shows that is **not** the delta.

| Ingredient | Canonical (`reference_equations.md`) | Falsified arm (`phase_lc/models.py:129` `PhaseAttn`) | HRR variant |
|---|---|---|---|
| Key/query modulus | learned, `σ(W·x)` (§2, §4) | learned, `sigmoid(Wq_amp)` / `sigmoid(Wk_amp)` (`:152`, `:154`) | **fixed at 1** |
| Detached denominator `Z_t` | present, `stopgrad` (§5) | **already absent** — `out = (q * state).real` (`:177`) | absent |
| Decay `γ` | optional, `γ=1` recovers core (§3) | learned, clamped `[0.90, 0.9995]` (`:143`) | **fixed at 1** |
| Readout | `Re(q ⊙ S)` | `Re(q ⊙ S)` | `Re(conj(k_q) ⊙ S) / N_t` |
| Phase spread | unconstrained | unconstrained | controlled (arm H2) |

So relative to the arm that was falsified, removing the detached normalizer is **not a change
at all** — that arm never had one. The real deltas are unit modulus, `γ = 1`, the count
normalizer, and phase spread. That is a modest change to an arm that scored at chance
(needle 0.01 at every distance, chance ≈ 0.02), which sets a **low prior on success**. This is
recorded here so a later positive cannot be presented as vindication of a larger idea, and a
later negative cannot be dismissed as "they tested the wrong thing".

Note also that `Re(q ⊙ S)` with `q = polar(a_q, +φ_q)` and `k = polar(a_k, −φ_k)` is *already*
conjugate multiplication; it becomes exact HRR unbinding only once the moduli are 1. The
"explicit conjugate unbind" is therefore a consequence of unit modulus, not an independent
change — except that the query must emit a *key-shaped* phasor (§3, arm H1).

## 3. Arm ladder

Five arms on the **identical skeleton** used by `phase_lc` §3: token + absolute-position
embedding, pre-norm blocks, GELU FFN, tied LM head, differing **only** in the token mixer.

| Arm | Status | Mixer |
|---|---|---|
| **Q** | existing | full causal softmax — the capability ceiling (needle 0.53–0.59, follow-rate 0.63) |
| **R** | existing | gated real diagonal linear recurrence — **the decisive control**; it already beat Phase 2.1× on perplexity and tied it (both at chance) on retrieval |
| **P** | existing | Phase as falsified, reproduced unchanged as the reference point |
| **H1** | new | HRR-strict: `\|k\| = \|q\| = 1`, `γ = 1`, readout `Re(conj(k_q) ⊙ S) / N_t`, query emits a key-shaped phasor through the same projection family as the key |
| **H2** | new | HRR-codebook: H1 with a **fixed random unit-modulus key per vocabulary id**, not derived from content |

**H2 is not an optimization of H1 — it is the diagnostic that separates two different
failures.** HRR's retrieval bound assumes near-orthogonal (i.i.d. uniform-phase) keys. Learned,
content-derived keys have no such guarantee. If H1 fails and H2 succeeds, the finding is
"the HRR algebra works here, but learned content keys destroy the orthogonality it needs" —
a precise, narrow result. If **both** fail, the mechanism is dead at this scale and the
question is closed rather than deferred.

## 4. Parameter matching

Parameters matched to **±0.1%** of ~2.0M via FFN-width auto-tune, as in `phase_lc` §5 (which
achieved ~0.03%).

**Disclosed asymmetry:** H1 and H2 delete `Wq_amp` and `Wk_amp`, i.e. `2 · d²` per layer =
`2 · 128² · 4 layers` = **131,072 parameters**, about 6.5% of the budget. The FFN absorbs
them, so the HRR arms carry *more* FFN capacity and *less* mixer capacity than P. This shifts
capacity in H's favour on language modelling and away from the mixer being tested; it must be
stated in any result, and it is a reason a PPL improvement alone cannot count as success (§6).

## 5. Seeds and protocol

- **Development seeds:** 0, 1, 2 — for wiring, numerical checks and diagnostics only. No
  verdict may be drawn from them.
- **Primary verdict:** **5 fresh holdout seeds, 10–14**, declared before execution, following
  the five-seed holdout discipline established for the slot work. Development-seed rescue is
  never generalization.
- Identical tokenizer, corpus, data-order RNG per seed, optimizer, schedule, precision and
  step budget across all five arms — the `phase_lc` §3 configuration verbatim: d=128, 4 heads,
  4 layers, train ctx 256, AdamW lr 3e-3 OneCycle, wd 0.01, grad-clip 1.0, batch 16, fp32.
- Tasks reused **frozen and unmodified** from `experiments/phase_lc/tasks.py`: needle by
  distance, entity–attribute binding by entity count, 2-hop multihop, supersession, source,
  length generalization (train 256 → eval 256/512/1024) and the distant-evidence follow-rate
  probe. Answer-token supervision applied identically to every arm.

**Step budget.** `phase_lc` §15 identified undertraining as the central unresolved caveat —
softmax retrieval was bimodal across seeds and zero Phase seeds crossed the threshold. This
preregistration therefore adopts §17's step budget: **4k–8k needle-heavy steps**, not the
2k used in the original run. Running the HRR arms at 2k would reproduce the ambiguity rather
than resolve it.

## 6. Numeric gates

The repository already fixed the bar for moving Phase off "falsified at tested scale"
(`phase_lc` §17). **This preregistration inherits it rather than inventing a softer one**, since
a Phase variant judged by an easier gate than Phase itself would be worthless:

> **G1 (inherited).** Mean needle accuracy **≥ 0.50 at d ≥ 96 in ≥ 3 of 5 seeds**, while
> staying **within 1.3× of softmax (Q) perplexity**.

Additional gates, all of which must hold for the arm to be carried forward:

- **G2 — beats the decisive control.** `needle@d96(H) ≥ needle@d96(R) + 0.10`. R tying H is
  the criterion that retired P (`phase_lc` §13); it applies unchanged here.
- **G3 — causal.** Replacing the conjugate key with a random unit phasor at readout must
  remove **≥ 50%** of H's gain over R. A null ablation is a null result, exactly as in §12.
- **G4 — capacity scaling.** Accuracy must degrade *gracefully* with the number of bound
  items, consistent with HRR's crosstalk growth, and must remain above chance at the largest
  tested load. Collapse to chance at small N falsifies the binding claim even if a single-item
  needle passes.
- **G5 — no language catastrophe.** `ppl(H) ≤ 1.5 × ppl(R)`. R is the cheapest arm and was
  2.1× better than P; an HRR arm that retrieves but cannot model language is not a successor.

A **PPL improvement alone never passes**, for the §4 reason: the HRR arms carry extra FFN
capacity by construction.

## 7. Falsification — retire the variant if any holds

- **G1 fails**, i.e. fewer than 3 of 5 holdout seeds reach 0.50 needle at d ≥ 96.
- **R ties or beats H on retrieval.** The same criterion that retired Phase.
- **G3 null ablation**: removing the conjugate unbind changes nothing, because there was
  nothing to remove.
- **Both H1 and H2 fail.** This is the decisive close: the fixed-codebook arm is the most
  favourable formulation the algebra allows, so its failure means the mechanism does not work
  at this scale — not that it was formulated unfairly.
- H1 passes only with the fixed codebook (H2) and not with learned keys → the variant is
  **not** carried forward as a language-model mixer; the result is recorded narrowly as
  "HRR algebra viable, learned phase keys not", and any successor needs its own
  preregistration.

Retirement is recorded with the same weight as a pass. No re-run with adjusted gates, seeds or
step budgets to recover a failure; a changed design is a new preregistration.

## 8. Verdicts this does not disturb

Explicitly unaffected, whatever the outcome:

- `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` — this is Phase, not BindingSlots.
- `E1_TEMPORAL_TRANSFER_PARTIAL` and the closed C1 / frozen-readout tracks.
- `KDA_VALIDATION_BLOCKED` — nothing here unblocks KDA.
- The **falsification of Phase** in `phase_lc` §16. A success here would establish a *different
  mixer*; it would not rehabilitate the arm that was falsified, and the "Phase adds no
  retrieval / is ablation-neutral" findings stand as results about that arm.
- The C4 micro-scale fluency finding (window+Phase 73 vs window-only 118 PPL) — untouched and
  not evidence for this variant.
- The Cloud Scaling third-baseline evaluation. That is **clock-anchored harmonic regression
  over timestamps** with no learned phase and no neural component; it shares vocabulary with
  this document and nothing else. Neither outcome bears on the other.
- Deterministic retrieval over the relational database remains the operational foundation
  regardless of the result.

## 9. Execution constraint

`torch` is **not installed in the current environment** (verified), so execution here is
`RESOURCE_BLOCKED` — the same status the vNext lab recorded for its neural reproduction. The
step budget in §5 is 2–4× the original run, on five arms and five seeds; a realistic compute
estimate is a precondition of authorization, not an afterthought.

## 10. Owner decisions

1. **Authorize execution at all.** The thesis lists every future-research item as
   unauthorized. This document supplies the preregistration; it does not supply the
   authorization.
2. **Compute.** Whether the 4k–8k-step budget across 5 arms × 5 seeds is funded, and on what
   hardware, given `torch` is absent here and the original study was CPU-bound.
3. **H2's status.** Whether the fixed-codebook arm is diagnostic-only, or an eligible
   successor in its own right if it passes while H1 fails.
4. **Task suite.** Reuse the frozen `phase_lc` tasks verbatim, or add a purpose-built synthetic
   binding task with controlled item counts for G4.
5. **Sufficiency of a synthetic positive.** Whether a synthetic-only success may proceed at
   all, given the C8 → C9 history: a frozen-Phase distant-recall gain of +0.741 on a synthetic
   cue task collapsed to chance and ablation-neutrality under natural language.

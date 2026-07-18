# B1.12 — Order-Hypothesis Review (was order ever a prediction of the theory?)

Docs-only conceptual review. Modifies no preregistration or experimental artifact. Determines, from repository
evidence, whether B1.12 was misframed by testing an **order** prediction that the stated AND-composition theory
never makes. `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Refines (does not overturn) the
Development Reset (`2442604`).

**Conclusion: `B1_12_SHOULD_BE_RESCOPED`** — the order-vs-scramble premise is not a prediction of the endorsed
theory (`ORDER_HYPOTHESIS_NOT_FOUND` within it); the theory-aligned question is **mapping-set specificity**
(membership, no order), which is **complementary** to — not a merge of — the Varṇa–Affliction Resolution Test.

---

## 0. Repository evidence base (frozen)

- **T-AFFLICTION** = `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1.md` — the source of B1.12's binding-gloss content.
  **R5 (AND-composition, line 57):** `A(w) = a₁ ∧ a₂ ∧ … ∧ aₙ`. **R6 (no progression, line 60):** "No claim
  that one varṇa transforms/balances/removes another, or that **order is causal**." Its scoring is **absolute
  and explicitly non-comparative (line 112):** *"its **own** frozen affliction packet — **not** vs another word,
  a control, the sample average, or a ranking."* Disclosed limitation (lines 97–99): the Stage-C adjudication is
  **nonblind** → Barnum-fit risk.
- **T-OPERATOR** = `SYMBOL_U_THEORY_V1_FREEZE.md` — a *different* theory: `ρ(σ₁…σₙ) = M_{σₙ}∘⋯∘M_{σ₁}(s₀)`,
  "**order-sensitivity (non-commutativity) is the distinctive structural commitment**"; falsifier: "order-effects
  ≈ 0 → non-commutativity [falsified]." Observable = a **latent reading state**, not judge-based referent/
  affliction matching; does not use the affliction glosses.
- **B1.12 artifacts** — base prereg (`2c613f4`) frames it as an **order** study (lines 46–48 "order carries
  word-specific information"; 64–65 H2-primary; 114–115 arms A true-order / B order-scramble; 291 `Δ_order`;
  315 `ORDER_SIGNAL_SUPPORTED`); V1.1 (`6f197fd`) G0 metrics are order-sensitive (edit distance, self-order,
  ordered n-grams, endpoints); V1.2 (`7935f48`) is an order-distinctness correction.

The user's stated position in this task **is** T-AFFLICTION: "pronunciation determines which varṇas belong…
combine simultaneously… no temporal progression, no causal chain… simply the conjunction (AND-composition)…
once membership is fixed, I make no claim that scrambling changes the combined meaning."

## 1. Did B1.12 introduce an order hypothesis the theory never claimed?

**Yes.** "True pronunciation order should outperform a scrambled order" is:
- **not explicitly stated** by T-AFFLICTION — R5/R6 make no order claim;
- **not implied** by it — it is **contradicted** by R6 ("order not causal") and by the commutativity of ∧;
- **merely assumed by B1.12's design** — introduced in the base prereg's framing (the "why a new number"
  rationale and H2-primary/`Δ_order`), whose only frozen provenance is the **separate T-OPERATOR** theory
  (non-commutativity) that the user now disavows.

So the order hypothesis entered through **experiment design importing a claim from a different (now-disavowed)
theory**, not from the endorsed AND-composition theory. Relative to the endorsed theory:
**`ORDER_HYPOTHESIS_NOT_FOUND`.**

## 2. Under pure AND-composition, is scrambling an irrelevant manipulation?

**Yes — theoretically inert.** `∧` is commutative and associative, so `A ∧ B ∧ C ≡ C ∧ A ∧ B`. Arm A (true
order) and Arm B (scramble) encode the **identical conjunction** → the theory predicts **identical** combined
meaning. Therefore:
- the order-vs-scramble contrast carries **zero theoretical signal** — A and B are the *same stimulus* under the
  theory;
- any measured A≠B difference could reflect only an **evaluator reading artifact** (order used as a cue) or
  **leakage**, never the theory;
- a **null** (A≈B) is exactly the theory's **prediction**, so it **cannot falsify** the mappings — the
  experiment cannot fail informatively.
An order-vs-scramble experiment thus **cannot meaningfully test** an AND-composition theory.

## 3. The theory-aligned question: mapping-set specificity

The variable the theory actually endows with meaning is **membership** (which varṇas belong, via pronunciation),
combined conjunctively. The aligned question is: **"Does a word's own frozen mapping set explain the target
better than appropriate control mapping sets?"** — varying membership, **not** order. Control alignment:

| control | varies membership? | theory-aligned? | note |
|---|---|---|---|
| another word's mapping set | yes | ✔ | valid only if **low varṇa overlap** (else near-identical set) |
| matched random mapping sets | yes | ✔ | the key Barnum/specificity control |
| equal-size decoy mapping sets | yes | ✔ | controls set size |
| generic negative-affliction packet | yes | ✔ | **critical** — all binding glosses are negative, so a generic-negativity control is essential |
| no packet | (floor) | ✔ | baseline |
| ~~order-scramble~~ | **no** | **✗** | same membership → theoretically inert (this is why B1.12's Arm B is invalid *as a theory control*) |

All membership-varying controls are aligned; the order-scramble control is **not**. **Crucial scope caveat:** the
matched *target* must be the affliction **resolution/embodiment profile** (the theory-valid semantic relation),
**not** ordinary-referent identification — the descriptor-example review (`6b8e561`) already showed the binding
glosses do not identify ordinary referents.

## 4. Every B1.12 decision that assumed order mattered (provenance)

| design decision | why it assumed order mattered | source |
|---|---|---|
| "why a new number" / H2 = "order carries word-specific info" (base §0.1, §4) | to distinguish B1.12 from B1.10's bag | **design** (borrowed T-OPERATOR non-commutativity) |
| Arms A (true order) vs B (order-scramble); primary `Δ_order = Acc(A)−Acc(B)` | order treated as the hypothesis-carrying variable | **design** |
| V1.1 G0 metrics: normalized **edit distance**, **self-order** `o(x)`, **ordered** bi/tri-grams, endpoint caps | select words by order-distinctness | **design** |
| V1.2 `d_ord\|inv` order-distinctness correction | fix the order metric | **design** |
| G0 audit selection = max–min pairwise **edit distance** | pick the most order-distinct six | **design** |
| every G1 instrument (opaque, semantic v1/v1.2) | make order **recoverable** by an evaluator | **design** |

**Every** order assumption traces to **experiment design**, none to the AND-composition theory.

## 5. Should B1.12 be rescoped to mapping-set specificity? (question, not redesign)

**Advantages:** theory-aligned (membership + AND-composition, no order); **falsifiable** (a word's own set should
fit its resolution profile better than random/decoy sets *iff* the mappings carry specific information);
**addresses the affliction test's disclosed Barnum limitation** (lines 97–99) with the comparative control that
test explicitly omits (line 112); **removes the inert order confound** entirely.

**Disadvantages / risks:** the valid target is the **resolution/embodiment** profile → it operates in the
affliction **content domain** (all-negative binding glosses; the same nonblind-adjudication and
generic-negativity risks); requires **low-overlap** word sets (distinct-inventory words are inventory-separable);
and it must be scoped so as **not** to duplicate or merge with the affliction test.

**Net:** mapping-set specificity is a **better framing** than order — it tests the theory's actual variable and
can fail informatively — provided it targets the resolution profile and is kept methodologically distinct from
the affliction test.

## 6. Relationship to the Varṇa–Affliction Resolution Test

**Complementary (overlapping in content, distinct in method) — not identical, not independent, not to be
merged.**
- The affliction test is **absolute and non-comparative** by explicit design (line 112: own packet only, *not*
  vs another word/control/average/ranking); its disclosed weakness is Barnum-fit under nonblind adjudication.
- Mapping-set specificity is **comparative** (own set vs random/decoy/generic/no-packet). It is exactly the
  control the affliction test omits, and it directly targets that test's Barnum limitation.
- They share content (binding packets) and the resolution target, so they are **not independent**; they differ
  in design (comparative vs absolute), so they are **not identical**. → **complementary.** If B1.12 is rescoped,
  it must be a **separate preregistration** with its own words, comparative scoring, and conclusions — **no
  import/merge** of the affliction test's words, scoring, or verdicts in either direction.

## 7. Conclusion

**`B1_12_SHOULD_BE_RESCOPED`.** The order-vs-scramble premise tests a prediction the endorsed AND-composition
theory never makes (and actively disclaims via R6); under commutative conjunction, scrambling is an inert
manipulation and a null is the theory's own prediction, so the order experiment cannot inform the theory. The
theory-aligned reframe is **mapping-set specificity** — does a word's own membership-fixed mapping set fit its
resolution/embodiment profile better than membership-varying controls — which is **complementary** to the
Varṇa–Affliction Resolution Test (it supplies the comparative control that test deliberately omits) and must be
pursued, if at all, as a separate, non-merged preregistration. This **refines** the reset (`2442604`): B1.12
should stop being an *order* experiment, but a *specificity* reframe gives it a potential theory-aligned role
that the reset's "no independent role" finding under-weighted, because the affliction test is explicitly
non-comparative.

**This review recommends the scientific question change; it does not redesign or implement anything.**

## Guardrails
Docs-only review; no preregistration or experimental artifact modified; selected six, G0, pool, parser, lexicon,
scoring, the Varṇa–Affliction Resolution Test, B1.10, and B1.11 all unchanged; no judges, run, or freeze.
Structure, not validated meaning.

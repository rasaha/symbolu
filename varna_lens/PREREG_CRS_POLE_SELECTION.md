# PREREG — CRS pole selection (A baseline · B first target · C gated future)

> **Status:** pre-registered, not yet run. **Date:** 2026-06-25.
> **Scope:** specification only — **no code is implemented by this document.** Defines how (and whether) a
> CRS signal may touch varṇa pole selection without reintroducing circularity. Results, when run, go in a
> separate `RESULTS_CRS_POLE_SELECTION.md`.
> **Terminology guard:** the **CRS** here (C = ontological/acoustic constraint, R = structural realization,
> S = semantic/contextual coherence) is **not** the project's prior **C×R×S truth engine** that the lens is
> firewalled *from*. Different objects; the firewall against semantics→acoustics feedback still applies (§4).

## 0. Decision encoded by this prereg

- **A — strict structure-first decoding — is the PERMANENT BASELINE.** Always computed, always reported; the
  falsifiable floor every other design must beat. Never retired.
- **B — CRS-weighted interpretation — is the FIRST implementation target.** Non-circular by construction
  (it never flips poles). This is what gets built and tested first.
- **C — CRS-guided pole selection — is NOT implemented now.** It is a future, gated experiment, admissible
  only after B passes, and only **constrained to genuine structural/pronunciation ambiguity** — never as an
  override of an unambiguous pole.

## 1. Problem statement

Whole-word semantic labels must **not** choose varṇa poles. "kill is bad/binding → force its varṇas into
binding poles" is **circular**: the reading merely echoes the label and carries no information beyond it.
The danger generalizes to any S that is a proxy for the target (dictionary valence, the word's gloss, the
eval labels). The scientific question: **can a semantic/contextual coherence signal S add legitimate value
to the reading without ever authoring the pole it is later judged against?** This prereg admits S only in
roles where the answer is provably yes, and pre-registers the controls that detect circularity.

## 2. Architecture

```
            phoneme structure
                  │
                  ▼
   (R) structural pole decoding         ← deterministic vowel-attachment rule = DESIGN A (baseline floor)
                  │
                  ▼
        candidate readings              ← from genuine structural/segmentation ambiguity only
                  │
                  ▼
   (C×R×S) weighting / confidence        ← DESIGN B: ranks readings, sets confidence; NEVER flips a pole
                  │
                  ▼
     ranked reading + calibrated confidence (+ always: the Design-A baseline reading)
```

**Safe-locus principle (binding):** S may disambiguate *which sound is realized* (the input to R) and may
*rank* fully-decoded readings (after R). S may **never** sit between R and the pole to override an
unambiguous structural decision. *S before R, or S after R — never inside R.*

## 3. CRS scoring formula

For a candidate reading `z` of word `w` in context `ctx`:

> **score(z | w, ctx) = α · log C(z) + β · log R(z | structure) + γ · log S(z, ctx)**

- **C(z)** — ontological/acoustic prior over pole configurations from the fixed varṇa system (no target access).
- **R(z | structure)** — structural likelihood = the vowel-attachment rule re-expressed as a per-position
  pole probability; **≈ 1 on unambiguous positions** (this near-degeneracy *is* the structural veto that
  forbids overriding fixed poles).
- **S(z, ctx)** — context-coherence model `p(z coherent | ctx)`, computed under the §4 firewall.
- **α, β, γ** — weights **pre-registered or fit on a separate dev split**, never on the eval set. The
  posterior over readings is `softmax(score)`; report the argmax **and** the full distribution.

Design B uses this score **only to rank readings and set confidence**. No term in the score is permitted to
change a pole that R fixes unambiguously (guaranteed by R ≈ 1 there + the §9 hard constraints).

## 4. Firewall (binding — prevents semantic leakage)

S's input schema **structurally cannot contain**, and S **may not consult**:

- the word's **dictionary gloss / definition**,
- any **known valence** of the word (good/bad/sattvic/tamasic),
- the **target explanation / reference reading**,
- the **evaluation labels** (human ratings, downstream targets).

S receives **only** the independent context `ctx`. Enforcement is threefold: (i) interface — S's input type
literally excludes the forbidden fields; (ii) **provenance logging** — every pole/reading decision records
its `(log C, log R, log S)` contributions and asserts no target access; (iii) the **pseudoword arm** (§7),
where no dictionary valence exists to leak. This is the same firewall principle that keeps the lens out of
truth-scoring: semantics may not feed back to author the acoustic reading.

## 5. Ablations

Run the full factor lattice to attribute any signal and expose circular paths:

`C` · `R` · `S` · `CR` · `RS` · `CS` · `CRS`

Each ablation uses identical candidates, judges, splits, and capacity. R-only (≡ Design A) is the reference.

## 6. Controls (matched capacity, pre-registered)

- **R-only baseline** (Design A) — the floor.
- **shuffled-S** — S's mapping permuted; the decisive circularity control.
- **shuffled-C** — C's ontology permuted (relabeling-invariance control).
- **random CRS** — random scores at matched dimensionality.

Operational definition of non-circularity, fixed in advance: **CRS must beat shuffled-S on held-out data.**
If CRS ≈ shuffled-S, S's contribution is inert or circular.

## 7. Tests

Blind, source-masked, fixed rubric, ≥5 seeds, bootstrap 95% CIs, `MIN_EFFECT` pre-registered per test.

1. **Held-out human coherence ratings** — CRS-weighted ranking vs R-only on unseen items.
2. **Pseudowords (the linchpin)** — pronounceable nonwords in context; **no dictionary valence exists to
   leak**, so any S-coherence gain here is the strongest evidence of non-circular signal.
3. **Unseen real words** — generalization beyond any tuning set (no lexicon memorization).
4. **Ambiguous / heteronym contexts** — does S pick the contextually-correct **pronunciation** (the
   legitimate, S-before-R disambiguation), e.g. *lead*, *bow*, *wind*?

Plus a redundancy probe: compare CRS poles/rankings to a **dictionary-valence predictor**; CRS must **add
beyond it** and **not merely reproduce it** (reproducing it ⇒ circular/redundant).

## 8. Decision rules (pre-registered)

- **R1 — keep structure-first only.** If CRS does **not** beat **R-only** → no value; ship Design A alone.
- **R2 — inert or circular.** If CRS beats **R-only** but **not shuffled-S** → S carries no legitimate
  signal (inert or leaked). Reject CRS; keep Design A.
- **R3 — B is valid.** If CRS improves coherence on **pseudowords AND unseen real words** (over R-only and
  over shuffled-S, beyond the dictionary-valence predictor) → **Design B is validated** and may be shipped
  as a ranking/confidence layer over the Design-A baseline.
- **R4 — gate to constrained-C.** **Only if B passes (R3)** may **constrained-C** be *considered* — and only
  in the ambiguity-restricted form (§9), under its own future prereg, with its own controls. B passing does
  **not** authorize pole overriding.

No post-hoc rescue; a fired rule is reported as-is. Null/negative results are first-class.

## 9. Permissions and hard constraints on S

**CRS MAY:**
- **rank** interpretations (order candidate readings),
- **adjust confidence** (posterior / entropy / abstention),
- **resolve genuine structural ambiguity** (choose among valid segmentations/pronunciations — S before R).

**CRS MAY NOT:**
- **override an unambiguous pole.** Where R fixes a pole (R ≈ 1), no C/S term may change it. This is enforced
  by the structural veto in the formula (§3) and is non-negotiable; violating it reintroduces circularity
  and breaches the firewall (§4).

## 10. What this document does and does not do

- It **specifies**; it implements **no code** (per instruction). Design A already exists; B is the first
  build target once authorized; C remains unbuilt and gated.
- It does **not** claim CRS works — that is what the tests decide.
- It does **not** weaken any prior empirical/falsification result; the NO_SIGNAL findings stand and are
  untouched.
- It does **not** authorize semantic labels to choose poles; the firewall and §9 forbid it.

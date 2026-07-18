# Milestone A — Candidate-F Specification (true L2 formation)

**Status:** Specification memo (docs-only). Attempts to specify candidate L2 formation functions `F`. Not a
run, not a dataset, not code.
**Governed by:** `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`, `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`,
`B1_4_LAYER_INTEGRATION_AUDIT.md`.
**No meaning validated. No dataset built. Nothing run or scored. B1.4 remains decoder-level only until F is
specified.**
**Track B remains blocked. Structure, not validated meaning.**

Grounding (read-only): `symbolu_neural/structural_v1/operators.py`, `.../features.py` (Stage A; **not
modified**).

---

## 1. Purpose

This memo attempts to **specify candidate L2 formation functions `F`** — a real `z = F(M_{σ_1}, …, M_{σ_n},
s_0) ∈ S` — that could replace B1.4's attribute-table placeholder with a genuine, operator-derived latent. It
**validates no meaning** and authorizes no run. Its single deliverable is an admissibility decision on whether
`F` can be specified at all without collapsing back to (a) a static varṇa→attribute lookup or (b) pure
phonology.

---

## 2. Problem statement

The B1.4 layer-integration audit found `L2_PLACEHOLDER_ATTRIBUTE_TABLE`: B1.4 runs as `varṇa split →
attribute-table lookup → KCPR pole → profile → generator → judge` and has **no** `F`. The missing component is
exactly `z = F(M_σ…, s_0)`. Until `F` exists and is admissible, full L1→L2→L3 validation is blocked
(`B1_4_L2_MISSING_BLOCKS_FULL_VALIDATION`).

**Structural fact that shapes everything below.** In Stage A, `M_σ = expm(Σ_j f_{σ,j} G_j)` is an **orthogonal
4×4 operator**, and the parameters `f_{σ,j}` are **standard articulatory/phonological features** (place,
manner, voicing, sonority), which the source explicitly marks *provisional and not meaning-carrying*.
Consequences that constrain any `F`:

- Because the operators are orthogonal, the state **norm is conserved** — `‖t_i‖ = ‖s_0‖` for all `i`. So
  norm-based latent features are **degenerate (constant)** and carry no information. Only *directional /
  rotational* structure is informative.
- Because the operators are parameterized **only** by phonological features, any operator-derived `F` is, at
  most, a **nonlinear, order-sensitive function of phonological features**. `F` is therefore *gloss-independent
  by construction* — but its **semantic ceiling is whatever structured phonology can explain**, and the
  phonological baseline is the decisive control.

---

## 3. Requirements for `F`

`F` must be:

- **operator-derived** — a function of the frozen L1 operators `M_{σ_i}` / their composition, not a table
  beside them;
- **gloss-independent** — no dictionary/vṛtti/sphere/polarity meaning as input;
- **non-additive** — not a sum/average of per-varṇa values;
- **order-sensitive** — permuting the varṇas must change `z` (operator non-commutativity must matter);
- **baseline-testable** — yields a `z` a probe can score against the full baseline suite;
- **not equivalent to varṇa-identity lookup** — must not be reconstructible as a fixed per-varṇa table;
- **not a decoder output** — `F` produces the latent, it does not read out a semantic label.

---

## 4. Inputs allowed

`F` may consume only:

- the **frozen L1 operator sequence** `M_{σ_1}, …, M_{σ_n}` (equivalently the feature vectors `f_{σ,j}` that
  define them, via `operators.py`);
- the **initial state** `s_0` (a fixed, pre-registered 4-vector);
- **structural features derived from operator composition** (the trajectory `t_0…t_n`, the composed operator,
  commutators, rotation geometry);
- **phonological/acoustic features** — permitted **only** as explicit **baselines or auxiliary controls**,
  never as the privileged semantic content of `F`.

---

## 5. Inputs forbidden

`F` may **never** consume:

- varṇa **glosses**;
- **dictionary meanings**;
- **vṛtti** meanings;
- **four-sphere** meanings;
- **polarity** meanings;
- **bridge-pool** paraphrases;
- the **target word meaning**; or
- **hand-authored attribute labels** used *as* `F` (that is the placeholder table, not a formation function).

---

## 6. Candidate F-1 — operator composition state

**Definition.** The composed endpoint (or the composed operator itself):

```
z = M_{σ_n} · … · M_{σ_1} · s_0            (state form, z ∈ S^3 ⊂ ℝ^4)
    or   Z = M_{σ_n} · … · M_{σ_1} ∈ O(4)  (operator form, order-sensitive)
```

**Assessment.**
- *Non-additive?* **Yes** — matrix composition, not summation.
- *Order-sensitive?* **Yes** — the coupling generators `G_C, G_D` do not commute, so reordering varṇas changes
  the product. (The `(G_A, G_B)` pair commutes, so purely-`AB` substrings are order-blind; overall it is
  order-sensitive.)
- *Not a lookup?* **Yes** — depends on the whole sequence.
- *Risk:* norm-conservation makes the **state-form** `z` a point on a fixed sphere; only its **direction**
  matters. More seriously, it **risks being merely structural with no semantic target** — a rotation endpoint
  of phonological features. Admissible **as a formation**, but the collapse-to-phonology test (§13) is decisive.

---

## 7. Candidate F-2 — trajectory features

**Definition.** `z` from the sequence of intermediate states `t_0, t_1, …, t_n` (with `t_i = M_{σ_i} t_{i−1}`).

Because norms are conserved, admissible features are **directional / geometric**, e.g.: successive **angles**
between states, the **cumulative rotation angle**, the **rotation planes/bivectors** traversed, path
**curvature** and **torsion** on the sphere, **stability/return** (proximity of `t_n` to `t_0`), and
**divergence** between nearby initial states (sensitivity). Norm, energy, and any magnitude feature are
**excluded as degenerate** (constant under orthogonal operators).

**Assessment.**
- *Non-additive / order-sensitive?* **Yes** — geometry of the ordered path.
- *Not a lookup?* **Yes.**
- *Admissibility:* **admissible as a formation**, with the same phonological-ceiling caveat; the features are
  richer than F-1's endpoint and may separate order effects better, but they remain functions of phonological
  parameters.

---

## 8. Candidate F-3 — operator interaction features

**Definition.** `z` from **non-commutativity** among the operators: pairwise **commutators**
`[M_{σ_i}, M_{σ_j}] = M_{σ_i}M_{σ_j} − M_{σ_j}M_{σ_i}`, higher-order interaction/associator terms, and
summaries of how much the realized order departs from an order-blind product.

**Assessment.**
- *Captures structure beyond bag/sequence baselines?* **Potentially yes** — commutator content is **exactly**
  what a bag-of-varṇas baseline cannot see and what a naive sequence baseline only partly sees; this is the
  candidate most likely to *demonstrate* genuine composition beyond ablation controls.
- *Non-additive / order-sensitive / not lookup?* **Yes** on all three.
- *Admissibility:* **admissible as a formation**, and the **most defensible** on the "beyond bag/sequence"
  requirement. Still phonology-parameterized (collapse test applies), but its whole value is the part of the
  signal the additive/bag baselines *cannot* reproduce, so it is the cleanest test of "does composition
  matter."

---

## 9. Candidate F-4 — learned probe over frozen operators

**Definition.** A **bounded learned** `F` — a small model trained to map allowed structural inputs (F-1/F-2/F-3
features) to the latent — trained **only** on structural inputs.

**Strict limits.**
- **No gloss input** — training features are structural only; no dictionary/vṛtti/sphere/polarity/target
  meaning.
- **No dictionary labels as training leakage** — dictionary/attribute labels may appear **only** as the
  downstream target `Y` in a properly split, held-out evaluation, never as `F`'s training input.
- **Strong baselines required** — the learned `F` must beat every baseline in §13; a learned map trivially
  overfits and can manufacture apparent signal.
- **Overfitting risk is high** — requires held-out splits, capacity caps, and a phonology-only learned control
  (same architecture, phonological features only) to prove `F` adds nothing beyond phonology.

**Assessment.** *Admissible only under these guards*; without them it is the **easiest** candidate to fool
yourself with. Lowest priority; specify last, if at all.

---

## 10. Candidate F-5 — reject static lookup

**Static varṇa→attribute lookup is NOT `F`.** A fixed per-varṇa table (the current B1.4 attribute table) is
additive-ish, order-blind, and reconstructible by identity — it fails the operator-derived, non-additive, and
not-a-lookup requirements. It may serve as an **L3 decoder input** or a **hypothesis table**, but it is **not**
an L2 formation function and cannot be relabeled as one. This candidate is listed only to **exclude** it
explicitly.

---

## 11. Candidate codomain `S`

Possible latent spaces for `z` (no semantic labels assigned yet):

- **Vector space** — `ℝ^4` (state form), restricted to the sphere `S^3` by norm conservation.
- **Low-dimensional manifold** — the orthogonal group `O(4)`/`SO(4)` (operator form), or its Lie-algebra
  (bivector) coordinates.
- **Signed structural feature space** — a fixed-length vector of directional/geometric features (F-2) and
  interaction summaries (F-3).
- **Trajectory-feature space** — the ordered geometry of `t_0…t_n`.

`S` is a structural space only. **No dimension of `S` is given a meaning at this stage.**

---

## 12. How `F` connects to decoder `D`

`F` and `D` are **separate**. `F` produces the structural latent `z ∈ S`. A decoder `D` may **later** map `z`
to attribute profiles (`y = D(z)`), and multiple decoders (KCPR/DBP/polarity) may share the same `z`. But:

- **`F` cannot itself be a semantic gloss table** — if the "formation" already contains the attribute labels,
  there is no `F`, only a decoder wearing L2's name.
- A decoder's success is a statement about `D` over `z`, and only becomes an L2 claim if `z` itself
  (via `F`) beats the baselines. `D` never rescues an inadmissible `F`.

---

## 13. Baselines for `F`

Any `F` claim must beat **all** of:

- **bag of varṇas** (order destroyed) — kills F-1/F-2 if order adds nothing;
- **shuffled order** — same varṇas, permuted;
- **random relabeling of operators** — operators reassigned to varṇas at random;
- **phonological similarity** — **the decisive control**, since the operators *are* phonological; `F` must beat
  a phonology-only predictor or it has shown nothing semantic;
- **length / frequency**;
- **simple identity lookup** — the static table (F-5); `F` must beat the very placeholder it replaces;
- **sentiment / lexicon** baselines at the decoder/probe stage.

The **phonological baseline is dispositive**: because `M_σ` is phonology-parameterized, any effect `F` shares
with the phonological baseline is **not** evidence of a semantic latent.

---

## 14. Admissibility decision

**`F_ADMISSIBLE_FOR_PRE_REG`** — *conditioned on the phonological baseline as the primary gate.*

Rationale, held honestly:

- **A real `F` can be specified.** F-1 (composition state), F-2 (trajectory geometry), and F-3 (interaction /
  commutator features) are genuine operator-derived, non-additive, order-sensitive latents — **not** static
  lookups (F-5 rejected) and **not** gloss-fed (no forbidden input). So the specification question — *can `F`
  be written without falling back to lookup?* — is answered **yes**. That is the memo's charge, and it
  succeeds.
- **But the semantic ceiling is phonology.** Since the operators are parameterized solely by phonological
  features, an admissible `F` is at most structured phonology. The dominant predicted risk is
  **`F_COLLAPSES_TO_PHONOLOGY`**, and the prior is negative (sound-over-meaning; B1.1
  `RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈ real 0.967). Admissibility for pre-registration is **not** a
  prediction of success.
- Therefore `F` is admissible **only** to enter a pre-registration whose **primary control is the phonological
  baseline** and whose **primary structural endpoint is F-3** (the beyond-bag/sequence commutator content). If,
  at test, `F` cannot beat the phonological baseline, the correct terminal is `F_COLLAPSES_TO_PHONOLOGY` → `⊥`
  for full-layer semantic validation.

(Other labels considered and **not** selected now: `F_STATIC_LOOKUP_REJECTED` applies to F-5 only, not the
memo; `F_INSUFFICIENTLY_SPECIFIED` is false — F-1/2/3 are specified; `F_CIRCULAR_RETURN_BOTTOM` is false — no
gloss input; `F_COLLAPSES_TO_PHONOLOGY` and `MILESTONE_A_F_INCONCLUSIVE` remain the likely **outcomes at test**,
which is a matter for the run, not the specification.)

---

## 15. Recommended next step

Because at least one `F` candidate (F-3, with F-1/F-2 as secondary) is admissible for pre-registration,
recommend drafting a **pre-registration for a true B1.4b L1→L2→L3 study**, with these non-negotiables:

1. **Primary control = phonological baseline**; a phonology-only predictor (and, for F-4, a phonology-only
   learned control) must be beaten or the result is `⊥`.
2. **Primary structural endpoint = F-3** commutator/interaction content (the part bag/sequence baselines cannot
   reproduce).
3. **`Y` and the E/decoder split** resolved per the B1.4 design and candidate-E audit **before** any run.
4. **Held-out evaluation and no gloss leakage** into `F` (critical for F-4).

If, on specification review or at test, **no `F` beats the phonological (and bag/sequence) baselines**, then
**full-layer validation returns `⊥`** and B1.4 remains decoder-level only. No rescue; prior negatives stand.

---

## 16. Boundary statement

> Candidate-F specification completed. No meaning validated. No dataset built. Nothing run or scored. B1.4
> remains decoder-level only until F is specified. Track B remains blocked. Structure, not validated meaning.

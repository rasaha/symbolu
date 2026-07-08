# Pre-Registration — B1.4b True L1→L2→L3 Validation (F-3 operator-interaction latent)

**Status:** Pre-registration (docs-only). Fixes the design **before** any data is seen. Not a run, not a
dataset, not code.
**Governed by:** `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`, `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`,
`MILESTONE_A_CANDIDATE_F_SPEC.md`, `B1_4_LAYER_INTEGRATION_AUDIT.md`.
**No meaning validated. No dataset built. Nothing run or scored. Track B remains blocked.**
**Structure, not validated meaning.**

Grounding (read-only): `symbolu_neural/structural_v1/operators.py`, `.../features.py` — **not modified**.

---

## 1. Purpose

This pre-registers a **true L1→L2→L3 validation study (B1.4b)** in which L2 is an actual operator-derived latent
— candidate **F-3 operator-interaction / commutator features** — **not** a static varṇa→attribute lookup. The
pre-registration fixes hypothesis, latent, decoder, target, probe, baselines, primary endpoint, failure
conditions, and terminal labels in advance, so the eventual result cannot be reshaped after the fact. It
**validates no meaning** and authorizes no run.

---

## 2. Starting state

- **B1.4a exists but lacks L2.** The decoder-level design (`B1_4_WORD_BLIND_ATTRIBUTE_VALIDATION_DESIGN.md`) is
  a real word-blind attribute-profile study, but the B1.4 layer audit found it `L2_PLACEHOLDER_ATTRIBUTE_TABLE`
  / `B1_4_DECODER_LEVEL_ONLY`: no `F`.
- **Candidate-F spec admits F-3 for pre-reg.** `MILESTONE_A_CANDIDATE_F_SPEC.md` → `F_ADMISSIBLE_FOR_PRE_REG`,
  with F-3 (interaction/commutator content) the most defensible candidate and the phonological baseline the
  decisive control.
- **Prior remains negative.** Sound-over-meaning sensitivity; B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈
  real ~0.967; O1.5 construct-gate failure; corpus norms near-null. The expected outcome of B1.4b is
  `F_COLLAPSES_TO_PHONOLOGY → ⊥`. This pre-registration is written to be able to detect signal **if** it
  exists, not to manufacture it.

---

## 3. Core hypothesis

**H1 (directional, pre-registered):** operator-interaction / commutator features derived from the frozen L1
operators contain **order-dependent compositional structure** that predicts an independently measured
attribute/propensity profile `Y` **beyond** the phonological baseline and beyond bag/shuffle/random baselines.

**H0 (null, expected default):** F-3 features predict `Y` **no better than** the phonological baseline and the
bag/shuffle/random baselines — i.e. any apparent signal is structured phonology or order-blind content.

The burden is entirely on F-3 to beat **every** baseline in §9; H0 is retained otherwise.

---

## 4. L1 definition (frozen)

L1 is the Stage A operator layer, used **exactly as frozen**:

```
M_σ = expm( Σ_j f_{σ,j} · G_j ),   j ∈ {A,B,C,D},   M_σ ∈ O(4)
```

- `f_{σ,j}` are **phonological/articulatory** coordinates (place_frontness, manner_openness, voicing,
  sonority_height), normalized to [−1,1]. They are **not semantic** and are marked provisional in the source.
- `G_A..G_D` are fixed skew-symmetric generators; `(G_A,G_B)` commute, `G_C/G_D` do not (non-abelian → order
  can matter).
- `M_σ` is **orthogonal** (norm-preserving), so state norm is conserved.

**Stage A / `symbolu_neural/structural_v1` remain untouched.** B1.4b consumes the operators read-only; it does
not fit, tune, or modify them.

---

## 5. L2 definition — F-3 (operator-interaction latent)

`z = F₃(M_{σ_1}, …, M_{σ_n}, s_0) ∈ S` is a fixed-length vector of **structural interaction features** over the
ordered operator sequence. Pre-registered feature families:

- **Pairwise commutators** `[M_i, M_j] = M_i M_j − M_j M_i` — summarized (e.g. Frobenius norm, principal
  rotation angle of the commutator) over adjacent and, optionally, all pairs.
- **Non-commutativity measures** — magnitude of departure between the realized ordered product
  `M_{σ_n}…M_{σ_1}` and an order-blind reference (e.g. the symmetrized/averaged product), quantifying how much
  order changed the result.
- **Ordered-product interaction terms** — associator-style triples and higher-order interaction summaries that
  a bag or a single-pass sequence baseline cannot reproduce.
- **Trajectory curvature / directional change** *(optional secondary)* — angular change / turning of the state
  path `t_0…t_n`, included only as directional geometry.

**Excluded by construction:** **norm / magnitude / energy** features — degenerate (constant) under orthogonal
operators; admitted only if a specific feature is proven non-degenerate and justified in writing before use.

The F-3 feature list, its summarization, and `s_0` are **frozen in this pre-registration** before any data.

---

## 6. L3 decoder

`D` is a **separate** mapping from the structural latent `z` to either (a) predicted attribute-profile values
or (b) a word-blind generated passage. `D` is chosen/fit **only** on allowed structural inputs and a held-out
split (no gloss input; §7/§11). **`D` is not proof:** a decoder producing plausible output over `z` is not
evidence — only the probe `P` beating the baseline suite `B` is. `D` never rescues F-3; if `z` does not beat
baselines, no decoder can make it signal.

---

## 7. Target `Y`

`Y` is an **independently measured attribute/propensity profile** of each target concept — **not** its
dictionary definition. Pre-registered candidate sources (exactly one, or a pre-declared combination, fixed
before any run):

- **blind human attribute ratings** (raters blind to varṇas, to F-3, and to the hypothesis);
- **independent feature-production / semantic-feature norms** (published, collected without reference to
  Symbol-U);
- **behavioral association judgments** (task-derived attribute measures).

**No dictionary/gloss target leakage:** `Y` must not be the word's definition, nor built from the varṇa table,
nor produced by a model shown the varṇa mapping. If no admissible `Y` can be specified, the study **stops**
(§16; label `Y_NOT_INDEPENDENT`).

---

## 8. Probe `P`

`P` (the test, **separate from `D`**) is one of, fixed here before any run:

- **P-predict:** predict `Y` from F-3 features on a **held-out split** (correlation / rank metrics), compared
  against every baseline in §9; **or**
- **P-generate:** produce **word-blind** outputs via `D(F₃)` and have an **independent, blinded judge** rate
  fit to the target concept / to `Y`, forced-choice against control-arm outputs.

Constraints: the probe is **not** the decoder; the judge (P-generate) is a **different model** from the
generator and is blind to arm identity, varṇa sequence, source, and key; the generator is **blind to the
target word** (any leak → `WORD_LEAKAGE_INVALID`).

---

## 9. Baseline suite `B`

F-3 must be tested against **all** of:

- **plain phonological features** (`f_{σ,j}` used directly) — the phonology-only predictor;
- **phonological similarity** (sound-similar, meaning-unrelated neighbors);
- **bag of varṇas** (order destroyed);
- **shuffled order** (same varṇas, permuted);
- **random / relabel operators** (operators reassigned to varṇas at random);
- **length / frequency**;
- **sentiment / lexicon**;
- **semantic-only baseline** where applicable (concept meaning, no varṇa);
- **chance / null**.

Beating some but not all is **not** signal.

---

## 10. Primary endpoint

**F-3 must beat (a) the phonological baselines AND (b) the random/relabel and shuffle baselines**, on the
pre-registered metric, by the pre-registered margin, with multiple-comparison correction across the baseline
family.

- The **phonological baseline is primary** because the L1 operators are phonology-parameterized: any effect
  F-3 shares with phonology is **not** semantic signal.
- The **order baselines (shuffle / random-relabel)** are co-primary because F-3's entire claim is
  *order-dependent composition*; if shuffle/random match F-3, the interaction content is inert.

Both (a) and (b) must pass for `L1_L2_L3_ATTRIBUTE_SIGNAL`. Failing either → the corresponding failure label
(§11–§12).

---

## 11. Failure conditions (return `⊥`)

Return `⊥` (via the matching terminal label) if any hold:

- F-3 **does not beat phonology** (`F_COLLAPSES_TO_PHONOLOGY`);
- F-3 **does not beat bag/shuffle/random** baselines (`BAG_OR_SHUFFLE_EXPLAINS` / `RANDOM_RELABEL_EXPLAINS`);
- **`Y` is not independently measured** (`Y_NOT_INDEPENDENT`);
- the **decoder leaks dictionary/gloss meaning** (`DECODER_LEAKAGE_INVALID`);
- the **generator sees the target word** (`WORD_LEAKAGE_INVALID`);
- the result relies on **plausibility or post-hoc interpretation** (no clean baseline-beating endpoint →
  `NULL_RETURN_BOTTOM` / `INCONCLUSIVE`).

`⊥` is the correct, expected output in these cases — not a prompt to re-tune. No rescue.

---

## 12. Allowed terminal labels

- **`L1_L2_L3_ATTRIBUTE_SIGNAL`** — F-3 beat phonology **and** order baselines **and** all others on the
  pre-registered endpoint.
- **`F_COLLAPSES_TO_PHONOLOGY`** — phonological baseline matches/exceeds F-3.
- **`BAG_OR_SHUFFLE_EXPLAINS`** — order-blind/shuffled baseline matches F-3.
- **`RANDOM_RELABEL_EXPLAINS`** — random operator relabeling matches F-3.
- **`SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS`** — semantic-only / sentiment baseline accounts for the result.
- **`Y_NOT_INDEPENDENT`** — no gloss-independent `Y` could be secured.
- **`DECODER_LEAKAGE_INVALID`** — gloss/meaning leaked into `D`.
- **`WORD_LEAKAGE_INVALID`** — target-revealing token reached the generator.
- **`NULL_RETURN_BOTTOM`** — clean run, no signal.
- **`INCONCLUSIVE`** — the study could not resolve the question.

Only `L1_L2_L3_ATTRIBUTE_SIGNAL` is positive, and it requires beating **all** baselines. **No
ONTOLOGICAL_SIGNAL. No Sanskrit privilege.**

---

## 13. Pilot stages

1. **Synthetic harness first** — validate F-3 computation, blinding, leak scans, and the baseline pipeline on
   synthetic (non-real) items. No evidence value.
2. **Small smoke (plumbing only)** — a handful of items to confirm end-to-end word-blind operation and that
   baselines compute. **No evidence claim from smoke.**
3. **Powered pilot only after `P` / `Y` / `B` are frozen** — sized to the pre-registered primary endpoint;
   sample size fixed in the pre-registration amendment before any powered run.
4. **No terminal label from synthetic or smoke** — only the frozen, powered run may emit a §12 label.

---

## 14. Relation to prior studies

- **B1.3 v3 remains parked** (pre-rulebook exploratory; not modified).
- **B1.4a remains decoder-level** (`B1_4_DECODER_LEVEL_ONLY`; not modified by this pre-registration).
- **B1.4b is fresh** — a new versioned study; it does not consume or relabel B1.4a/B1.3 artifacts.
- **Prior negatives remain unchanged** — Tracks C/D/E/F/G (incl. `RANDOM_POLARITY_EXPLAINS`,
  `CORRECTNESS_DEGRADED`), B1.1 (`RANDOM_OR_SCRAMBLED_MATCHES`), O1.5, corpus norms.

---

## 15. No-rescue rule

B1.4b **cannot** reinterpret Tracks **C/D/E/F/G**, **B1.1**, **B1.3**, or **B1.4a** as positive. A B1.4b result
stands only for B1.4b. No framing, latent, or decoder introduced here may relabel any prior null/negative as a
signal. If B1.4b itself returns `⊥` (the expected outcome), that is recorded as-is and does not diminish or
"explain away" the prior negatives — it joins them.

---

## 16. Next-step gate

After this pre-registration, the next step is **implementation planning only if `Y` can be independently
specified** (an admissible, gloss-independent target secured per §7). Concretely, before any harness:

1. Secure and freeze `Y` (source, collection protocol, blinding) — **if impossible, STOP** (`Y_NOT_INDEPENDENT`).
2. Freeze `P`, the F-3 feature list, the baseline suite, the metric, the margin, and the sample size (a
   pre-registration amendment).
3. Only then, and only under explicit operator authorization, begin the synthetic harness (§13).

No implementation, dataset, or run is authorized by this document.

---

## 17. Boundary statement

> B1.4b pre-registration completed for true L1→L2→L3 operator-interaction validation. No meaning validated. No
> dataset built. Nothing run or scored. Track B remains blocked. Structure, not validated meaning.

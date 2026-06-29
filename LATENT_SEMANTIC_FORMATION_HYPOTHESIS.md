# LATENT_SEMANTIC_FORMATION_HYPOTHESIS

> **STATUS — CANDIDATE HYPOTHESIS (Layer 2).**
> **Not validated · Not implemented · Does not modify Stage A · Does not validate Sanskrit
> privilege · Does not validate operator semantics · Does not validate dictionary prediction.**
> **The structural layer is frozen; the semantics in this document remain hypothetical.**
> Companions (unchanged): `SYMBOL_U_THEORY_V1_FREEZE.md`,
> `SYMBOL_U_IMPLEMENTABLE_ARCHITECTURE_V1.md`, `symbolu_neural/structural_v1/`.

## 0. Scope and what this document is *not*

This is a Layer-2 research hypothesis about *how* a semantic representation might emerge
from the already-frozen structural operator layer. It makes **no empirical claim**. It does
not assert that varṇas carry meaning, that the latent state predicts dictionary meaning, or
that any decoder is correct. Every formula below is either a **definitional placeholder** or a
**hypothesis requiring empirical validation**, explicitly marked as such.

## 1. Three-layer architecture

| layer | name | status | content |
|---|---|---|---|
| **L1** | Structural Operator Layer | **FROZEN** | operator algebra; ordered composition; Stage A benchmark; *structural validation only; no semantic claims* |
| **L2** | Latent Semantic Formation | **CANDIDATE (this doc)** | how a latent semantic representation `z` might form from L1; *no decoding assumptions* |
| **L3** | Semantic Decoders | **FUTURE** | DBP, transformation-chain, polarity, or any decoder `D` mapping `z` to an observable; replaceable without touching L2 |
| **V** | Validation layer | **METHOD (this doc)** | probe `P`, baseline set `B`, and failure state `⊥` used to *test* whether `z` carries recoverable information; an evaluation instrument, **not** part of semantic formation |

L1 is untouched. L2 sits *above* L1 and *below* L3. DBP lives in **L3**, not L2: it is **one
possible readout of `z`**, not the semantic theory. The **Validation layer (V)** is orthogonal:
it does not produce meaning, it only measures whether `z` contains semantic information, and its
results never alter L1/L2/L3 definitions (see §3.5).

## 2. Fundamental hypothesis (stated precisely)

> Each varṇa is hypothesized to carry an intrinsic acoustic-root semantic essence. When
> varṇas participate in an ordered operator sequence, these essences **interact through
> operator composition**. The essences are **not destroyed**; they become **latent,
> distributed** across a whole-word semantic state. Observable lexical meaning is **one
> projection** of that latent state — not an additive composition of varṇa meanings, and not
> the latent state itself.

```
varṇa acoustic-root semantic essences
        ↓  (ordered operator interaction — L1)
latent semantic representation  z ∈ S    (L2)
        ↓  (decoder D — L3)                 ↘  (probe P, baselines B — Validation layer)
observable lexical meaning  y ∈ Y           P(z) vs B   →  signal? else ⊥
```

The distinctive commitment versus a bag/sum model is that meaning is a projection of a
**non-additive, order-dependent** latent state, and that varṇa essence information is
**hypothesized to remain recoverable** from `z` (not lost).

## 3. Mathematical formulation

### 3.1 Structural substrate (L1, frozen — restated, not redefined)
Ordered varṇa sequence `σ₁,…,σₙ`; per-unit operators `M_{σ_i}` (Stage A form, provisional);
initial state `s₀`; structural evolution
```
t_0 = s₀ ,   t_i = M_{σ_i} t_{i−1} ,   so   t_n = M_{σ_n} ⋯ M_{σ_1} s₀ .
```
This is exactly the frozen monoid action / VSO reading. **No semantics are attached to it.**

### 3.2 Latent semantic representation (L2)
Define the latent semantic state as
```
z = F(M_{σ_1},…,M_{σ_n}, s₀)
```
where:
- `F` denotes a **constrained candidate family** of order-dependent latent-state formation
  functions. The document does **not** choose a final member of that family, but **any future
  `F` must be gloss-independent, non-additive, operator-derived, and testable** against bag,
  relabel, and phonological-similarity baselines.
- `z` is the **latent semantic state**;
- `z` **is not** dictionary meaning.

**Why bound `F` to a family rather than fix a member (deliberately).** Committing now to a
single `F` (trajectory endpoint vs. equilibrium field vs. transition operators) would
(i) smuggle in an untested modeling choice as if it were theory, (ii) entangle L2 with a
particular L3 decoder, and (iii) pre-empt the model-selection question that data — not prose —
must settle. Bounding `F` to a family with explicit admissibility constraints
(**gloss-independent, non-additive, operator-derived, baseline-testable**) keeps L2 as a
*structural commitment* — `z` is some order-dependent, non-additive functional of the operators
— while leaving the *specific functional* an empirical choice. The binding constraint L2
imposes is **non-additivity**: an admissible `F` is hypothesized **not** to reduce to
`Σ_i g(σ_i)` (the bag); a member that did would falsify L2's distinctive claim.

### 3.3 Observable meaning (L3)
Dictionary meaning is a **decoded projection**:
```
y = D(z)
```
where `D` is a semantic decoder; **DBP is one candidate `D`**, and others (transformation-chain,
polarity) may exist or replace it **without changing `F` or `z`**.

**Why this decomposition is cleaner than embedding DBP in formation.** Making DBP primitive
fused the *formation* of the representation with one *readout* of it, which (a) created
circularity (roles were assigned and then used to define the composition that produced them),
(b) made every DBP failure look like a failure of the whole theory, and (c) prevented testing
"is there latent semantic structure at all?" independently of "is DBP the right readout?".
Factoring `y = D(F(·))` separates a representation question (L2: does `z` carry recoverable
semantic information?) from a readout question (L3: which `D` exposes it?). The two can then be
falsified independently.

### 3.4 Information-theoretic statement of the hypothesis
Let `E = (e_{σ_1},…,e_{σ_n})` denote the (hypothesized, unvalidated) varṇa essences.

- **Retention hypothesis (the core L2 claim):**
  ```
  I(z ; E) > 0
  ```
  the latent state retains **recoverable** information about the individual varṇa essences.
  This is the *falsifiable* form of "latent and distributed, not lost": if `I(z;E)=0` the
  hypothesis is false.

- **Projection/compression hypothesis (the L2→L3 step):**
  ```
  I(y ; E)  <  I(z ; E)
  ```
  the observable meaning exposes **less** essence information than the latent state — decoding
  is a lossy projection. This is the intended ordering, and it is the precise, non-mystical
  restatement of "essences become latent and no longer separately visible."

- **Why this is the correct formulation (and a caution).** `I(z;E)>0` makes "recoverable"
  measurable (decode `E` from `z` above chance). `I(y;E)<I(z;E)` makes "projection loss"
  measurable (the observable carries strictly less). **Neither is asserted as fact.** Both are
  hypotheses; either can be false. Note also the data-processing inequality: since `y=D(z)`,
  necessarily `I(y;E) ≤ I(z;E)` for *any* `D` — so the inequality `I(y;E)<I(z;E)` is only
  *content-bearing* when it is **strict and `I(z;E)` is itself shown `>0`**; otherwise it is a
  triviality (0 ≤ 0). The substantive, falsifiable claim is therefore the **conjunction**
  `I(z;E) > 0  ∧  I(z;E) > I(y;E)`.

A further, decisive empirical predicate (stated here, tested later): for the retention claim to
be *semantic* rather than *acoustic*, `z` must carry essence/meaning information **beyond
phonological similarity** — i.e., `I(z ; meaning | phonology) > 0`. Without conditioning on
phonology, any positive `I(z;E)` may merely reflect that `z` encodes sound.

### 3.5 Validation layer (probe, baselines, failure state)
The layers above *define* `z`; they do not *test* it. Whether `z` carries recoverable
information is established only through an explicit evaluation layer:

```
spaces        S = latent state space,   Y = observable semantic output space
formation     z = F(M_{σ_1},…,M_{σ_n}, s₀) ∈ S        (L2)
decoding      y = D(z) ∈ Y                              (L3, intended readout)
validation    P(z) = probe output                       (evaluation instrument)
              B    = baseline set
              ⊥    = failure / no-valid-reading state
```

- `P` is a **probe** — an instrument used *only* to test whether `z` contains recoverable
  information (e.g. a linear probe or a mutual-information estimator for `I(z;E)`,
  `I(z;meaning|phonology)`). It is **not** a production decoder.
- `B` is the **baseline set** against which any probe result must be judged: at minimum
  **bag-of-varṇas, relabel/random, phonological similarity, length/frequency, and
  sentiment/lexicon** baselines. A probe "succeeds" only if it exceeds **all** of these,
  *especially phonological similarity*.
- `⊥` is the explicit **failure state**: if `P` (or a decoder `D`) cannot extract information
  above `B`, or if `z` is unstable/undefined, the system **returns `⊥`** rather than forcing a
  semantic reading. `⊥` is first-class and must never be silently overwritten by a label.

### 3.6 Required conceptual distinctions (binding)

1. **Definition vs validation.** `z` can be *defined* without choosing any decoder. But
   whether `z` contains *useful semantic information* can only be *tested* through a probe `P`.
   Consequently every claim of the form "`z` carries semantic information" is meaningful **only
   relative to a stated probe class `P` and baseline set `B`** — there is no decoder-free
   measurement of `z`'s content.
2. **Decoder vs probe.** `D` is an *intended semantic readout* (a candidate product mapping
   `z → y`). `P` is an *evaluation instrument*. They are not interchangeable: **a probe success
   does not validate a production decoder** (probes can extract information a decoder does not
   use), and a decoder failure does not by itself prove `I(z;·)=0`.
3. **Canonical frame vs hypothetical content.** The `L1 → L2 → L3` (+ Validation) **frame is
   canonical** — the standing way to organize semantic work. The **actual semantic content of
   `z` remains hypothetical and unvalidated.** The frame's cleanliness is *not* evidence for
   the content.
4. **Representation-learning analogy (structural only).** This resembles a
   **frozen-backbone + probe / task-head** architecture (L1 frozen, `z` a representation, `D`
   heads, `P` probing). But unlike modern learned-representation systems, **`F` is not yet
   learned from data** and there is no training signal. Therefore the architectural similarity
   is **not evidence of semantic validity** — it borrows the *form* of representation learning
   without its *engine*.
5. **Failure state.** If `P` or `D` cannot extract information above `B`, or if the latent state
   is unstable or undefined, the system must return **`⊥`**, not a forced semantic reading.

## 4. Scientific status (binding, repeated)

- **Candidate hypothesis.** Not a result.
- **Not validated** — no empirical support is claimed; relevant prior evidence (O1.5, S1/S2)
  is largely *against* the recoverable-semantic version.
- **Not implemented.**
- **Does not modify Stage A** — L1 is frozen and untouched.
- **Does not validate Sanskrit / varṇa privilege.**
- **Does not validate operator semantics** — the operators `M_σ` are provisional.
- **Does not validate dictionary prediction.**
- **Structure is frozen; semantics remain hypothetical.**

## 5. Language discipline

- This document does **not** say *meaning is lost*. It says **semantic information becomes
  latent, distributed, and is *hypothesized* to remain recoverable** (`I(z;E)>0`, to be tested).
- This document does **not** say *DBP is the semantic theory*. It says **DBP is one possible
  decoder `D` of the latent semantic state `z`**.

## 6. What would make this testable (pointer, not a plan)

A future Layer-2 test must, at minimum: freeze a varṇa essence table **independently of word
glosses** (anti-circularity); specify one concrete admissible `F`; choose a probe `P`; and
measure `I(z;E)` and `I(z;meaning|phonology)` with `P` against the **baseline set `B`** of §3.5
(**bag-of-varṇas, relabel/random, phonological similarity, length/frequency, sentiment/lexicon**)
— passing only if it exceeds **all** of them, *especially phonological similarity*. If it does
not, the result is **`⊥`**, reported as such, never a forced reading.

On synonyms as a diagnostic: **synonyms may project to similar observable dictionary meanings
while preserving different latent organization.** Therefore synonym similarity is a **useful
diagnostic, but not a sole falsifier** unless the theory claims dictionary meaning is the
*primary* projection of `z`. Treat it as one signal among the baselines above, not as a
stand-alone test. Until such measurements exist, L2 is a hypothesis with a negative prior, not
an open question.

> **Candidate hypothesis. Not validated. Structure frozen; semantics hypothetical.**
> **structure, not validated meaning.**

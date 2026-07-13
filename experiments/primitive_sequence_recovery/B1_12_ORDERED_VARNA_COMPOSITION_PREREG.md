# B1.12 — Ordered Varṇa Composition Word-Specificity Study — PREREGISTRATION (docs-only)

**Docs-only preregistration.** No code, no scaffold, no word selection, no parser run on candidates, no context
authoring, no judge run, no evidence-freeze declaration, no result artifact. Nothing under B1.10 or B1.11 is
changed. New experiment number **B1.12** within the primitive-sequence-recovery program (**not** B2). Resonance /
phonetic-fidelity refinement only — **no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology /
Sanskrit-privilege / individual-varṇa claim.** B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b blocked;
Track B blocked. **Structure, not validated meaning.**

---

## 1. Status

**`READY_FOR_G0_DESIGN_IMPLEMENTATION`** — for the **B1.12 G0 audit only**.

This preregistration fully specifies (a) the primary **structural representation** used for the distinctness
gate, (b) the **B1.12-specific Gate G0** and its mechanical selection rule, metrics, caps-principle, and failure
outcome, and (c) the full downstream design (arms, controls, task, scoring, contrasts, evidence tiers,
falsification). The next authorized step is to **implement and run the B1.12 G0 audit** over a predeclared
candidate pool — a separate, explicitly-approved step. It is **not** ready to run the study.

Two things are explicitly **deferred and gated** (they do **not** block G0, mirroring B1.10's structure where G0
was purely representational and context/judge rendering came at G1):

- **G1 — evaluator-facing rendering decision (deferred).** The choice of the evaluator-facing encoding — see
  §5.5 "Representation decision record" — is a Gate-G1 decision made **after** G0 passes. G0 operates only on
  the opaque ordered-ID sequences (§5) and needs no evaluator rendering.
- **Confirmatory RUN — model availability (blocked in this environment).** A confirmatory run additionally
  requires an available real judge panel (§10, §12). In the current container `torch`, `transformers`, `vllm`,
  and `numpy` are all absent; a confirmatory run is therefore **not runnable here** and is out of scope for this
  docs-only step.

## 2. Relationship to B1.10 and B1.11 (preserved, not rescued)

- **B1.10 remains `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`.** B1.10 tested word-specificity through
  **unordered union-of-facet prose packets** and, per `B1_10_WORD_SPECIFICITY_G0_REPORT.md`, no size-6 subset
  of the candidate pool yielded mutually-distinctive prose packets (only 11 varṇas render a facet; `ra` alone
  appears in 9 of 16 valid words). That result is **not reinterpreted, weakened, or rescued** by B1.12. B1.10's
  native-Sanskrit word-specificity study also returned a robust **null** (`B1_NATIVE_WORD_SPECIFICITY_RESULT.md`);
  that null stands.
- **B1.11 remains its own blind replication study** (`B1_11_BLIND_REPLICATION_PREREG.md`) of the B1.10
  pole-legibility / `context_pole_margin` instrument on new words. B1.12 does not touch, reuse, or re-run it.
- **B1.12 does not rescue or reverse any prior B1 finding.** A positive B1.12 result would support **only**
  ordered-composition identifiability **under the tested instrument** (§14). It would establish nothing
  metaphysical, ontological, or universally semantic.
- **Why a new number (per program criterion — hypothesis + instrument).** B1.10/B1.11 collapse a word's varṇas
  into an **order-free** representation (a bag of facets / two context-invariant packets). B1.12's hypothesis
  (order carries word-specific information) and instrument (an **order-preserving** composition with
  order-removing controls) are **structurally different**, so it takes a new experiment number while remaining
  inside the primitive-sequence-recovery program.

## 3. Core research question (narrow)

> Does the ordered, pronunciation-derived varṇa composition of a Sanskrit word contain **word-specific
> information that is lost** when the same varṇas are collapsed into an **unordered** representation?

The study must isolate a genuine **sequence/order** signal from every non-order explanation: varṇa inventory
alone; sequence length; repeated-varṇa count; first-/last-varṇa cues; lexical/transliteration leakage; generic
spiritual-language effects; prose-length differences; a judge already knowing the word; and arbitrary positional
templates. Each is neutralized by a matched control arm (§5) and/or a leakage control (§6).

## 4. Hypotheses

- **H2-primary.** The correct word is identifiable from its **own true ordered** varṇa composition **more
  accurately** than from matched control compositions (order-scrambled, position-preserving mismatch, unordered
  inventory, structural decoy, no-composition baseline).
- **H2-null.** Ordered composition provides **no reliable advantage** over controls once varṇa inventory,
  sequence length, repetition profile, and positional surface cues are matched. (This is the default; it is
  assumed true until the preregistered order advantage is demonstrated.)
- **H2-failure interpretation.** Any apparent gain that **disappears** under the inventory-preserving
  (Arm D) or order-scrambled (Arm B) control is **not** evidence for composition-specific information — it is an
  inventory/length/leakage artifact and is reported as such.

Scope guard: even a confirmed H2-primary is **identifiability under this instrument only** — no single-varṇa
attribution, no ontology, no Sanskrit-privilege, no generation-utility claim.

## 5. Representations and arms

### 5.1 Provenance of the ordered sequence (frozen, read-only)

The ordered varṇa sequence for a word is obtained by the **frozen native Stage-1 parser**
(`sanskrit_stage1_parser.py`, `SPEC_VERSION = PARSER_SPEC_v1`; `B1_STAGE1_SANSKRIT_PARSER_SPEC.md`), read-only,
which for a Sanskrit word returns an **ordered** `atomic_varnas` list plus `aksharas` (syllable boundaries),
`multiplicity.varna_counts`/`geminations` (repeats), and per-unit provenance (`type`, `origin`, `aspirated`,
`vowel_length`, `inherent`, `source_akshara_index`, `unsupported`/`missing` status). **Order, repeats,
boundaries, and unsupported/missing-unit status are preserved by construction.** No new decomposer is authored.
(The parser is **not** run on any candidate in this task — §16.)

> **Note (why B1.12 escapes B1.10's structural limit).** B1.10's prose packets only exist for the **11** varṇas
> with a facet render, which is what made its G0 not testable. B1.12's **structural** representation and G0
> metrics (§5.2, §7) are defined over the parser's atomic-varṇa **identity sequence** for **every** varṇa it
> emits, independent of any facet render — so the 11-varṇa ceiling does not bind B1.12's gate.

### 5.2 Primary structural representation (identity-masked, order-preserving)

The primary object is a word's **ordered opaque-ID composition**:

- A **frozen opaque-ID bijection** assigns every distinct parser varṇa a stable identity token (e.g. `U01,
  U02, …`) that carries **no** phonetic, orthographic, or semantic hint (it is **not** derived from the varṇa's
  sound or spelling). The bijection is committed with a pinned sha256 before any word is encoded.
- A word's composition = the **ordered list of opaque IDs** for its parser varṇa sequence, **repeats
  preserved**, **akṣara/sequence boundaries marked**, rendered through a **frozen deterministic template**
  (fixed separators, fixed boundary markers, fixed handling of unsupported/missing units).
- The opaque IDs, not IAST/Devanāgarī varṇa symbols, are the primary surface — so the raw sequence **cannot
  spell the Sanskrit word** to a reader (§6).

All arms below are rendered through the **same** frozen template and the **same** opaque-ID space, so arms
differ **only** in the manipulation they encode.

### 5.3 Required arms (conceptual; no data generated)

| arm | name | what it is | what it controls / tests |
|---|---|---|---|
| **A** | True ordered composition | the exact pronunciation-derived ordered varṇa sequence (opaque IDs, repeats, boundaries), frozen template | the hypothesis-carrying stimulus |
| **B** | Order-scrambled control | **same multiset + same length**, order permuted under a **fixed seed** | removes order while holding inventory + length constant → **isolates order** |
| **C** | Position-preserving mismatch | a **different word's** composition, matched as closely as achievable on length, repetition profile, unit-class pattern (consonant/vowel where applicable), and initial/final unit classes | tests whether a same-shape *wrong* word is confusable |
| **D** | Unordered inventory | the same varṇas presented **without order** (deterministic canonical ordering or explicit bag/multiset representation) | isolates whether **order** adds anything beyond **inventory** |
| **E** | Structural decoy | a non-target sequence matched on **superficial structure** (length, repetition, boundary shape) but built from **different varṇas** | catches "matched on surface form, wrong content" |
| **F** | No-composition baseline | only the ordinary task context, **no** varṇa composition information | floor / task-legibility calibration |

Arms B and D are the two decisive order/inventory controls; A>B and A>D are the primary contrasts (§11). No
semantic prose gloss is added to any arm above. A semantic-ordered variant may exist **only** as a separately
labeled **secondary** arm (§5.4); it never replaces the primary structural arms.

### 5.4 Secondary (optional, subordinate) — semantic-ordered arm

If included, a secondary arm may render the frozen `VARNA_PLAIN` facet clauses **in pronunciation order** (order
preserved, repeats preserved) — using the **frozen, read-only** facet map, **never** a newly-authored bridge or
per-word narrative. It is explicitly **subordinate**: it does not define the primary endpoint, it inherits all
leakage controls (§6), and it is reported alongside — never in place of — the structural primary. It exists only
because the frozen facets cover 11 varṇas, so it cannot represent most words and is not a general instrument.

### 5.5 Representation decision record (the one deferred, G1-gated design decision)

There is a genuine, documented tension in the **evaluator-facing** encoding, to be resolved at **Gate G1**
(after G0), **not** here:

- **Pure-opaque horn (leakage-safe, matchability-limited).** Fully opaque IDs cannot be matched to a word by an
  evaluator that lacks a key → a blind LLM would sit at chance for all arms (degenerate).
- **Keyed/semantic-ordered horn (matchable, semantics-exposed).** Providing a decode reference (the frozen
  facet key) restores matchability but reintroduces semantic content and its leakage surface, and only covers
  11 varṇas.

This decision determines the evaluator instrument but **not** G0: the G0 gate (§7) is computed purely on the
opaque ordered-ID **sequences** (edit distance, LCS, positional/bigram/trigram structure), which are defined
regardless of how the stimulus is later shown to an evaluator. G0 is therefore fully specified now; the
evaluator-encoding fork is named here and carried to G1 as an explicit dependency (§12).

## 6. Critical leakage controls (preregistered)

Before any run, mechanically verify (fail-closed) that no arm leaks the answer:

1. **Transliteration overlap** — the evaluator-facing surface contains **no** IAST/Devanāgarī rendering of the
   target word or its varṇa string (opaque IDs enforce this for the primary; the secondary §5.4 is leak-checked
   like B1.10 §4.4).
2. **Exact character/substring overlap** — no candidate label or sequence token shares a distinctive substring
   with the Sanskrit word.
3. **Word-length leakage** — number of units/tokens must not, by itself, single out the target among candidates
   (controls B/C/D/E hold length matched; report residual length spread).
4. **Distinctive first/last-unit leakage** — initial/final opaque IDs must not deterministically identify the
   word within the candidate set (Arm C matches initial/final unit classes; report first/last-ID uniqueness).
5. **Repeated-varṇa pattern leakage** — the repetition profile must not be a unique fingerprint of the target
   among candidates (report repetition-profile collisions).
6. **Deterministic template artifacts** — the frozen template must add no token that correlates with word
   identity (separators/boundary markers are word-independent; verified by construction).
7. **Candidate-answer ordering effects** — candidate order is **randomized per trial under a recorded seed**
   with position counterbalancing; report position-choice balance.
8. **Judge memorization / Sanskrit knowledge** — probe whether an evaluator can name the word from the opaque
   sequence **without** the intended signal (a no-signal / shuffled-key control); pin model + revision so
   memorization is auditable; human raters attest no prior identification.
9. **Context gives it away** — any task context (if used) must **not** make the answer obvious without the
   composition; verified by an **F-arm (no-composition) legibility check** — if F alone is above chance, the
   context leaks and the run is invalid (`CONTROL_LEAKAGE`).

**Identity-masked encoding requirement.** Because a Sanskrit word's varṇa string effectively **is** the word,
raw varṇa symbols must **never** be the primary surface. The frozen opaque-ID bijection (§5.2) is the masking;
its mapping table is **frozen with a pinned hash before encoding** and is not disclosed to evaluators in the
primary structural task.

## 7. B1.12-specific Gate G0 (HARD PRE-IMPLEMENTATION GATE) — ordered-composition distinctness

**G0 does NOT reuse B1.10's prose-facet "unique-discriminating-facet" rule.** B1.12's representation is an
ordered opaque-ID sequence, so distinctness is measured on **sequence structure**, and the gate asks whether a
precommitted candidate set has **enough ordered-composition diversity** for a word to be separable from matched
controls.

**G0.1 Candidate pool.** A predeclared pool of **≥ ~30 real, attested Sanskrit words** (source dictionary +
citation recorded) assembled for **compositional breadth** (varied length, varied inventory, varied repetition
and boundary structure), **never** for whether a word "looks right." (Assembled, not selected, here — §8.)

**G0.2 Per-word + pairwise structural metrics** (computed mechanically over opaque-ID sequences, before any
context or rating), for every candidate and every pair:

- **normalized Levenshtein edit distance** between ordered sequences;
- **longest-common-subsequence (LCS) ratio**;
- **positional overlap** (fraction of positions with identical unit up to the shorter length);
- **multiset (inventory) Jaccard** — the order-free overlap, to separate order-distinctness from inventory
  overlap;
- **repetition-profile similarity** (per-varṇa count vector distance);
- **sequence-length difference**;
- **first-/last-unit overlap** (initial and final identity match rate);
- **count of unique ordered bigrams / trigrams** per word and **shared n-gram overlap** per pair;
- **inventory-controlled order distinctness** — order-based distance **after** conditioning on shared inventory
  (i.e. how much A differs from its own order-scrambled Arm B on the same metrics), so the gate certifies that
  the set has words whose **order** (not just inventory) is separable.

**G0.3 Mechanical selection rule (no semantic cherry-picking).** Fix **k** for a chosen chance baseline (e.g.
k = 6 → forced-choice chance 1/6, run01-comparable). Among pool words passing basic filters (valid parse; no
transliteration/substring leakage; length within a declared band; encodable under the frozen opaque-ID map),
**select the size-k subset that maximizes minimum pairwise ordered-composition distinctness** — concretely,
**maximize the minimum pairwise normalized edit distance** subject to a required **inventory-controlled
order-distinctness floor** (each selected word must be separable from its **own** order-scramble and from every
other selected word's composition by a preregistered margin). Tie-break deterministically: (a) maximize mean
pairwise edit distance, then (b) maximize mean unique-trigram count, then (c) minimize mean multiset-Jaccard,
then (d) alphabetical. **Selection uses structure only — never semantic fit.**

**G0.4 Thresholds — principled, not reverse-engineered.** Discriminability thresholds (minimum pairwise edit
distance; the inventory-controlled order-distinctness floor; maximum tolerated first/last-unit and n-gram
overlap) are set from a **stated discriminability requirement** (a word must be distinguishable from matched
controls above a declared confusability margin), **not** tuned to guarantee a passing subset. They are frozen
before the audit runs.

**G0.5 Freeze order + failure outcome.** The word set is fixed by this rule **before** any context, rendering
decision (§5.5), or rating exists, then frozen with its metric matrices. If **no** size-k subset meets the
thresholds, report **`G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET`** and stop — **do not relax thresholds**, do
not select a best-effort set. **Word set = PENDING (not selected here).**

## 8. Future word-set policy

The eventual word set (fixed by §7's rule, **not** chosen in this task) must:

- contain **real, attested** Sanskrit words (dictionary source + citation recorded per word);
- be **frozen before** any packet/composition generation for the experiment;
- **span multiple semantic categories** (not one field);
- **avoid near-synonyms and obvious morphological families** unless a family is *intentionally* included as a
  controlled contrast (declared as such);
- **avoid words whose transliteration directly exposes** the encoded sequence beyond the opaque-ID masking;
- be **selected by the deterministic §7 rule** from the predeclared pool — no semantic hand-picking.

## 9. Task design

**Primary endpoint (choose one — this preregistration fixes it):** **forced-choice word identification.** For
each target, the evaluator sees the target word's task frame and, as anonymous candidates, the arm compositions
(true-ordered A among matched controls, candidate order randomized per trial), and **chooses the single
composition that belongs to the word**; an optional full **ranking** is recorded as a secondary readout (MRR /
diagonal rank). Chance for k candidates = 1/k.

Equivalent framing permitted at implementation, fixed before run: present one composition and k candidate
**words**, choose the word — provided blinding/leakage controls (§6) hold identically. Exactly **one** primary
endpoint is used; if any generation task is added it is **subordinate** and never replaces identification.

## 10. Judges (do not silently inherit B1.10's policy)

B1.10's official panel (J0 `meta-llama/Llama-3.1-8B-Instruct`, J1 `meta-llama/Meta-Llama-3-8B-Instruct`,
J2 `google/gemma-2-9b-it`, transformers, greedy temp 0) was designed for a **0–6 prose-fit rating**, a different
instrument. B1.12's forced-choice identification over opaque structural sequences is **not the same task**, so
the panel is **re-preregistered for B1.12**, not inherited by default:

- **Panel:** a newly preregistered panel; **reusing** the same three real models is permitted **for
  cross-study comparability** but must be justified against the new task (opaque-ID identification, not prose
  rating) and re-declared, not assumed. **No Claude/Mistral/Qwen judges** carry over as constraints; family
  independence from any author is preserved.
- **Both LLM and later human evaluation** are supported: the identification task is human-runnable, and a human
  panel is the cleanest check on the memorization/Sanskrit-knowledge leakage risk (§6.8).
- **Required for any judged run:** arm blinding; randomized candidate order (seed recorded); exact model id +
  revision recorded; deterministic decoding where feasible (greedy/temp 0); **no mock judges for evidence**
  (a mock/plumbing double is `DIAGNOSTIC_ONLY / NOT_EVIDENCE` only); an **explicit model-availability gate**
  (fail-closed if a required model cannot be loaded — as is the case in the present container); and **raw
  outputs preserved**.

## 11. Scoring and contrasts

Report, per arm × (per judge and pooled):

- **primary accuracy** = top-1 own-composition identification; **chance = 1/k**;
- **per-word accuracy** and **arm-wise accuracy**;
- **sequence-order advantage** and **inventory advantage** (below);
- **confidence intervals** (cluster bootstrap over words/judges);
- **exact or permutation testing** for the primary contrasts (label-permutation over the composition↔word
  assignment);
- **multiple-comparison handling** (pre-declared family of contrasts; Holm or equivalent correction, declared
  before run);
- **judge agreement** (inter-judge concordance on the forced choice);
- **invalid-response handling** (parse-failure → retry ≤ 2 then drop; > 15% missing on a word → that word
  inconclusive; > 15% overall → `RUN_INVALID`);
- **stopping / exclusion rules** fixed before run (no post-hoc word dropping to move the aggregate).

**Primary contrasts (both required for the primary claim):**

```
Δ_order     = Accuracy(A: True Ordered)  − Accuracy(B: Order-Scrambled)
Δ_inventory = Accuracy(A: True Ordered)  − Accuracy(D: Unordered Inventory)
```

The primary claim requires a **positive, preregistered order advantage** — `Δ_order > 0` (and `Δ_inventory > 0`)
with its CI excluding 0 under the permutation test — **not merely above-chance** accuracy on Arm A (which could
be pure inventory or leakage). Arm C (position-preserving mismatch) and Arm E (structural decoy) bound
confusability; Arm F bounds context leakage.

## 12. Evidence tiers

- **Diagnostic smoke run** — plumbing only (encoders, template, candidate assembly, scorer), possibly with a
  mock/plumbing judge; produces **no evidence** and is labeled **`DIAGNOSTIC_ONLY / NOT_EVIDENCE`**, written to
  a separated directory.
- **Exploratory run** — small, real, non-confirmatory; clearly labeled exploratory; does not fix the verdict.
- **Confirmatory run** — the single evidential run; requires **all** of: passed **B1.12 G0**; **frozen word
  set**; **frozen rendering** (§5 template + opaque-ID map, and the §5.5 G1 decision resolved); **frozen
  controls**; **frozen contexts** (if any); a **valid evidence-freeze declaration** (anti-circularity, pinned
  input hashes, panel, seeds); an **available real judge panel**; and **manifest validation**. In the current
  container the model-availability gate **fails** (`torch`/`transformers`/`vllm`/`numpy` absent) → a
  confirmatory run is **not runnable here**.

## 13. Falsification criteria (the study can conclude any of these)

- **`ORDER_SIGNAL_SUPPORTED`** — `Δ_order > 0` and `Δ_inventory > 0`, CIs excluding 0, surviving leakage
  controls and multiple-comparison correction.
- **`INVENTORY_ONLY`** — Arm A above chance but `Δ_order ≈ 0` (A ≈ B): the signal is inventory/length, not
  order.
- **`NO_SEQUENCE_SIGNAL`** — Arm A at chance / no advantage over any control.
- **`CONTROL_LEAKAGE`** — an above-chance effect traced to a leakage channel (incl. F-arm above chance, or the
  no-signal/shuffled-key probe succeeding); the effect is invalid, not a finding.
- **`JUDGE_UNSTABLE`** — inter-judge agreement below a declared floor / results not reproducible across
  seeds/judges.
- **`G0_NOT_TESTABLE`** — (`G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET`) no size-k subset meets the §7
  thresholds.
- **`RUN_INVALID`** — missing-data / manifest / freeze / availability gate failure.

**No isolated favorable words override a null aggregate.** Per-word wins are reported but the verdict is the
aggregate under the preregistered contrasts; cherry-picking words is prohibited (§14).

## 14. Prohibited rescue operations

- Do **not** reinterpret, weaken, or rescue B1.10's `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS` or the native
  null; do not reuse a B1.10 "best-effort" set.
- Do **not** relax B1.10 or B1.12 gates, thresholds, or caps post-hoc; do not tune §7 thresholds to pass.
- Do **not** drop words, arms, or judges after seeing results to move the aggregate.
- Do **not** promote a secondary/generation arm to primary, or swap the endpoint after the run.
- Do **not** read a per-word win as a study-level positive; do **not** infer individual-varṇa meaning (no H1→
  single-varṇa leap), ontology, Sanskrit-privilege, or generation-utility from any B1.12 outcome.
- Do **not** import the Varṇa–Affliction Resolution Test rubric or any of its scoring into B1.12.

## 15. Implementation readiness

- **G0 audit:** **`READY_FOR_G0_DESIGN_IMPLEMENTATION`** — representation (§5.2), metrics (§7.2), mechanical
  rule (§7.3), thresholds-principle (§7.4), freeze order + failure outcome (§7.5) are fully specified; the next
  step is to implement the deterministic B1.12 G0 audit over a predeclared pool.
- **Gate G1 (rendering/contexts):** blocked pending the §5.5 evaluator-encoding decision and (if used) blind
  context authoring — **after** G0.
- **Confirmatory run:** blocked pending G0 pass + G1 resolution + a real, loadable judge panel (unavailable in
  this environment) + evidence-freeze + manifest validation.

## 16. Exact dependencies

- **Frozen, read-only:** `sanskrit_stage1_parser.py` (`PARSER_SPEC_v1`; ordered `atomic_varnas`, `aksharas`,
  `multiplicity`) and `B1_STAGE1_SANSKRIT_PARSER_SPEC.md`; `frozen/varna_native_stage1_merged_v1.json` (varṇa
  inventory / scopes). The secondary arm (§5.4) additionally reads the frozen `VARNA_PLAIN` facet map
  (11-varṇa coverage) read-only.
- **To be created by the G0-implementation step (separate approval):** the frozen **opaque-ID bijection**
  (with pinned hash), the frozen **deterministic render template**, the **predeclared candidate pool** of
  attested Sanskrit words (with dictionary citations), and the deterministic **B1.12 G0 audit** script + tests.
- **Decision to record at G0 time:** confirm the **native Stage-1 parser** (not the English g2p bridge
  `varna_bridge_active`) is the pronunciation-derived source for attested **Sanskrit** words; pin its spec hash.
- **Deferred (G1):** the §5.5 evaluator-facing encoding decision (pure-opaque vs keyed/semantic-ordered) and
  its leakage/matchability resolution.
- **Environment (confirmatory only):** a real judge backend — `transformers` + the panel models (or a human
  panel). Absent in the current container.

## 17. Guardrails

Docs-only preregistration. No word selection, no parser run on candidates, no packet/composition computation, no
context authoring, no code, no scaffold, no judge run, no evidence-freeze declaration, no result artifact;
nothing under B1.10 or B1.11 (or any prior evidence) is modified. Resonance / phonetic-fidelity refinement only.
No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth / Sanskrit-privilege / generation-
utility claim; no individual-varṇa attribution. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked.
Track B blocked. Structure, not validated meaning.**

# B1.1 — Random-Resonance Decomposition: Design Memo (B2 follow-up)

**Status:** `FUTURE_DESIGN_ONLY` — drafted 2026-07-04. **No model run · no generation · no scoring · no
prereg registered · nothing committed until reviewed.** This memo does **not** modify B1, does **not**
change the B1 verdict, does **not** rescue Track B, and makes **no** claim of ontology validation,
Sanskrit privilege, semantic truth, or H2 validation. **Structure, not validated meaning.**

Purpose: design a *decomposition experiment* (B1.1) that explains **why the random-resonance control R
matched A in B1**, using stricter and better-motivated controls — without weakening the science to let A
win. B1.1 is a **new** experiment; it can only ever speak about a **revised** pipeline, never re-label B1.

---

## 1. B1 result recap (fixed, not under revision)

- **B1 verdict remains `RANDOM_OR_SCRAMBLED_MATCHES`.** Unchanged by this memo.
- **The culprit was R (random resonance), not S (scrambled).** A *beat* scrambled; A *tied* random:

  | contrast | win-rate | corrected CI | outcome |
  |---|---|---|---|
  | A_vs_R | **0.5135** | [0.4656, 0.5573] | **FAIL (kill)** |
  | A_vs_S | 0.5615 | [0.5146, 0.6062] | pass |
  | A_vs_D | 0.5542 | [0.5073, 0.6000] | pass |
  | A_vs_C | 0.7562 | [0.7135, 0.7979] | pass |
  | A_vs_X | 0.6271 | [0.5813, 0.6729] | pass |

- **A improved over neutral X on creative/evocative tasks** (T3 metaphor 0.76, T5 tone 0.82, T6 evoke
  0.65) but **never uniquely beat R on any task**. B1 therefore supports **generic resonant/symbolic
  prompting**, not H2-specific utility.
- **Track B remains BLOCKED.** This memo is **design only**.
- Preserved prior (verbatim): Track G `RANDOM_POLARITY_EXPLAINS` (A_vs_R −0.1917, A_vs_X −0.075);
  Track F `CORRECTNESS_DEGRADED`. **Two independent tracks already show random explains A.** B1.1 must be
  able to *kill*, not merely to rescue.

---

## 2. What R is, and why it is the dangerous-but-necessary control

Three conditions share the **same wrapper, length, grammar, and task**; they differ only in **where the
conditioning content comes from**:

| arm | content source | holds constant | breaks |
|---|---|---|---|
| **A** | the real H2/varṇa-derived mapping for *this* word | everything | nothing (this is the claim) |
| **S** | the real ingredients for this word, **order/assignment scrambled** | the *ingredients* | internal *structure/order* |
| **R** | a mapping drawn **at random from the same meaning pool** | *pool + style + fluency* | *word-specific selection* |

**Why R is the decisive control.** A "beats X" only shows that *some* evocative conditioning beats none.
A "beats S" only shows that the *internal arrangement* of the ingredients matters a little. Neither shows
that **the specific, word-derived mapping carries information**. R holds the pool, the style, and the
fluency fixed and randomizes *only the word→mapping link*. If A cannot beat R, then the one thing A adds
over "a fluent evocative phrase from the same vocabulary" — **word-specific selection** — is carrying no
measurable signal. That is exactly the B1 outcome, and it is why R is the control you cannot drop: it is
the only one that isolates the H2 claim from generic evocativeness.

**Why R is dangerous.** R is *easy to make artificially weak* (ugly, off-style, wrong length), and any
such weakening hands A a win it did not earn. B1.1's integrity rules (§10) forbid that: R must be
**fluent, same length, same grammar, same wrapper — wrong only in semantic fit.**

### The seven candidate explanations, mapped to what discriminates them

| # | Hypothesis for why R matched A | Discriminating contrast in B1.1 |
|---|---|---|
| 1 | varṇa meaning pool too semantically overlapping | contrastivity audit (§3) + R_same on revised pool vs B1's R0 |
| 2 | any evocative symbolic prompt helps | R4 generic-poetic, R5 style-only, vs A |
| 3 | random mappings stay emotionally coherent | R_same vs R6 valence-matched-wrong-operation |
| 4 | the wrapper/style does most of the work | R5 style-only, C (surface) vs A |
| 5 | word-specific fit does not matter | **R_deranged (R2)** — real mappings, wrong word |
| 6 | the current R is too easy/generic | R_deranged + R_domain (harder, fairer controls) |
| 7 | H2 truly has no incremental utility beyond random resonance | A fails R_same **and** R_deranged **and** R_domain on a *contrastive* pool → this is the conclusion |

No single arm proves a positive; the **pattern across arms** is the evidence.

---

## 3. Varṇa-gloss contrastivity audit plan

**Question:** are the current varṇa meanings too semantically interchangeable, so that a random pick lands
in the same affective neighborhood as the "correct" pick (making R strong for reasons unrelated to H2)?

**Method (to be run as a read-only script before any B1.1 generation):**
1. Enumerate every consonant's `binding_state`/`liberating_state` (blocked/liberated) glosses from
   `varna_lens/lexicon_authoritative.json`, and every BRIDGE meaning-phrase from
   `varna_lens/layer2_bridge_vocab.json`.
2. Compute, over the pool: (a) **exact duplicate** glosses; (b) **near-duplicate liberated poles**
   (share ≥1 content lemma); (c) **near-duplicate blocked poles**; (d) **broad-valence clusters**
   (embedding cosine ≥ τ, τ pre-registered) collapsing many entries into one affect.
3. Emit a per-collision record and an **embedding-distance histogram**; define a pre-registered
   **contrastivity gate**: median pairwise gloss distance ≥ τ_min and no cluster larger than k.

**Seed findings** (already gathered by the committed read-only inspection in
`B1_LEXICON_CONTRASTIVENESS_DIAGNOSTIC.md`, 4ee85ab — *these are preliminary, to be replaced by the
scripted audit*): 33 of 64 BRIDGE meanings sit in overlapping clusters; collisions are mostly on a
**shared liberated pole**, blocked poles usually differ. Illustrative rows (audit table format):

| varṇa | blocked gloss | liberated gloss | collision type | colliding varṇas | severity | why this could make R strong | rewrite principle |
|---|---|---|---|---|---|---|---|
| Ṅa | Dambha (pretense) | Vinaya (humility) | near-dup liberated | Ja | near | random draw lands on "humility" too | split liberated pole by *operation* |
| Ja | Ahaṁkāra (ego) | Vinaya (humility) | near-dup liberated | Ṅa | near | same as above | ego-deflation ≠ pretense-dropping |
| Ṭha | Anutāpa (remorse) | Ātmaprasāda (self-acceptance) | near-dup (Kṣamā root) | Da | near | "forgiveness" basin | remorse-release ≠ anger-release |
| Da | Krodha (anger) | Dhairya (forbearance) | near-dup (Kṣamā root) | Ṭha | near | same basin | forbearance ≠ self-acceptance |
| Ta | Jāḍya (dullness) | Jāgaraṇa (awakening) | near-dup liberated | Bha | near | "awakening" basin | dullness-lift ≠ stupor-lift |
| Bha | Mūrcchā (stupor) | Jāgaraṇa (awakening) | near-dup liberated | Ta | near | same basin | distinguish onset vs collapse |
| Kha | Cintā (anxiety) | Viśvāsa (trust) | near-dup liberated | Ya | near | "trust" basin | open-under-uncertainty ≠ relational trust |
| Ya | Aviśvāsa (distrust) | Viśvāsa (trust) | near-dup liberated | Kha | near | same basin | relational trust ≠ spatial openness |
| Ḍha | Piśunatā (malice) | Karuṇā (compassion) | **near-dup both poles** | La | **exact/near** | strongest collision | one keeps malice→compassion, one cruelty→compassion; separate by object |
| La | Krūratā (cruelty) | Karuṇā (compassion) | **near-dup both poles** | Ḍha | **exact/near** | strongest collision | as above |
| Ca | Aviveka (non-discernment) | Viveka (discernment) | near-dup liberated | Na | near | "clarity" basin | discernment ≠ delusion-exit |
| Na | Moha (delusion) | Viveka (discernment) | near-dup liberated | Ca | near | same basin | delusion-exit ≠ analytic discernment |
| Ḍa | Lajjā (shame) | Nirbhayatā (fearlessness) | near-dup liberated | Pha | near | "fearlessness" basin | shame-release ≠ fear-release |
| Pha | Bhaya (fear) | Abhaya (fearlessness) | near-dup liberated | Ḍa | near | same basin | fear-release ≠ shame-release |
| Ka | Āśā (hope) | Nirāśā (detachment) | broad-valence cluster | Gha, Dha | broad | large "detachment/renunciation" basin | detach-from-outcome ≠ detach-from-craving |
| Gha | attachment | Anāsakti (non-attachment) | broad-valence cluster | Ka, Dha | broad | same basin | object-release ≠ hope-release |
| Dha | craving | Nivṛtti (cessation) | broad-valence cluster | Ka, Gha | broad | same basin | cessation ≠ non-attachment |

**Flagged clusters to audit exhaustively** (from the request; each collapses many varṇas into one affect
and is a candidate reason R stays strong):
attachment / craving / clinging / greed · detachment / renunciation / non-attachment ·
fear / courage / fearlessness / trust · compassion / friendliness / softening ·
awareness / awakening / clarity / knowledge · ignorance / confusion / escapism / dogma ·
cruelty / hatred / harshness · vanity / hypocrisy / ego-display.

**Output of the audit:** `VARNA_GLOSS_CONTRASTIVITY_AUDIT_PLAN.md` (companion) + a machine-readable
collision report + a pass/fail contrastivity gate that the **revised A pool must clear before B1.1
generation.** Passing the gate is *necessary but not sufficient* — contrastiveness with an arbitrary
word→mapping link still yields A ≈ R (that is the whole point of R_deranged, §5).

---

## 4. Contrastive rewrite principle

**Do not swap synonyms.** A more contrastive pool is not a prettier list of the same affects. Each varṇa
gets **four fields**, and the *contrast boundary* is what forces separability:

- **blocked impulse** — the constrained/afflicted form
- **liberated impulse** — the freed form
- **functional operation** — what the varṇa *does* (a verb, not a mood)
- **contrast boundary** — what this varṇa is **not** (the neighbors it must be told apart from)

Worked design examples (illustrative; not claims, not pipeline output):

```
Kha:
  blocked impulse:      anxiety before open, unstructured space
  liberated impulse:    capacity to remain open under uncertainty
  functional operation: holds an uncertain space open without collapsing it into a decision
  contrast boundary:    NOT confidence, NOT courage, NOT faith, NOT relational trust (that is Ya)

Ka:
  blocked impulse:      grasping for a desired outcome (hope-as-clinging)
  liberated impulse:    release of attachment to outcome while still acting
  functional operation: lets go of the result without letting go of the effort
  contrast boundary:    NOT renunciation of the object (that is Gha), NOT cessation of craving (that is Dha)

Da:
  blocked impulse:      reactive anger at obstruction
  liberated impulse:    forbearance that absorbs provocation without discharge
  functional operation: converts an impulse-to-strike into a held, patient stance
  contrast boundary:    NOT self-acceptance after remorse (that is Ṭha), NOT fearlessness (that is Pha/Ḍa)

La:
  blocked impulse:      cruelty toward a vulnerable other
  liberated impulse:    active compassion toward the one harmed
  functional operation: turns harming-energy toward protection of the weak
  contrast boundary:    NOT malice/slander→compassion (that is Ḍha; La's object is the physically weak)
```

The **contrast-boundary field is the deliverable that a synonym swap cannot fake** — it is what an
embedding-distance gate (§3) can measure and what R_deranged (§5) can stress-test.

---

## 5. R-control redesign

Each variant, with construction rule · what it tests · what an outcome means · fair or too-weak ·
implementation difficulty · co-primary vs exploratory.

**R0_current** — *baseline from B1.*
- **Construct:** random bridge from the **current** (B1) meaning pool.
- **Tests:** reproduces the B1 R for continuity.
- **Outcome:** A≈R0 replicates B1; A≫R0 would flag that *something else* changed between B1 and B1.1.
- **Fair?** Fair as a *reference*, but too generic to be the H2 test (that was the B1 problem).
- **Difficulty:** trivial. **Role:** exploratory (continuity anchor only).

**R1_same_pool_contrastive** — *random from the revised, contrastive pool.*
- **Construct:** random bridge from the **revised** contrastive pool (§3 gate passed).
- **Tests:** hypothesis 1 — does a *contrastive glossary alone* let A separate from random?
- **Outcome:** A≫R1 ⇒ contrastiveness was the missing ingredient; A≈R1 ⇒ contrastiveness is not enough
  (better meanings help A *and* R equally).
- **Fair?** Fair, and the honest risk is real: a better pool makes *both* arms more evocative.
- **Difficulty:** low (reuse pipeline with new pool). **Role:** **co-primary** (this is "R_same").

**R2_deranged_real_A** — *another word's real mapping, never its own.*
- **Construct:** apply a fixed derangement π over words (π(w) ≠ w); word *w* receives the **real A
  mapping of π(w)**. e.g. *mother* gets *sword*'s real mapping; *doctor* gets *river*'s; *king* gets
  *flower*'s. Mapping **quality/fluency held maximal**; only word→mapping **fit** is broken.
- **Tests:** hypothesis 5/7 — does **word-specific fit** matter at all?
- **Outcome:** A≫R_deranged ⇒ word-specific fit carries signal (the first real H2 evidence);
  **A≈R_deranged ⇒ the mapping is interchangeable across words — decisive against H2 word-specific
  utility.**
- **Fair?** The **fairest and strongest** control — it cannot be dismissed as "ugly" because it *is* a
  real, high-quality mapping. **Preferred.**
- **Difficulty:** low (permute an existing column; pin the derangement seed). **Role:** **co-primary
  (highest priority).**

**R3_domain_mismatch** — *fluent, same style, symbolic operations from distant domains.*
- **Construct:** same length/grammar/wrapper; sample operations from **domains deliberately distant** from
  the target. e.g. *mother* — forbidden domains {care, holding, nurture, origin, relation}; allowed R
  domains {cutting, measurement, dominance, abstraction, competition}. Pre-register the
  forbidden/allowed domain lists per word.
- **Tests:** does **semantic fit** matter while style/fluency are held?
- **Outcome:** A≫R_domain ⇒ fit matters even against fluent-but-wrong content; A≈R_domain ⇒ domain-wrong
  content competes ⇒ fit is not the operative variable.
- **Fair?** Fair *if* the domain lists are pre-registered and not gerrymandered; risk of researcher
  degrees-of-freedom in choosing "distant."
- **Difficulty:** medium (needs a principled domain taxonomy). **Role:** **co-primary (secondary).**

**R4_generic_poetic** — *spiritual/poetic filler, no varṇa source.*
- **Construct:** generic evocative chain with no varṇa derivation, e.g. `trust → compassion →
  awareness`.
- **Tests:** hypothesis 2 — does *any* evocative language lift creative generation?
- **Outcome:** A≈R4 ⇒ the lift is generic poeticness, not H2; A≫R4 ⇒ varṇa content adds beyond generic
  poetry.
- **Fair?** Fair as a *lower bound*; slightly favorable to A (no word-fit at all), so a weak bar.
- **Difficulty:** trivial. **Role:** exploratory.

**R5_style_only** — *wrapper + length + grammar, low-semantic placeholders.*
- **Construct:** identical wrapper with abstract placeholders / near-empty semantic content.
- **Tests:** hypothesis 4 — how much is the **prompt wrapper/style** alone worth?
- **Outcome:** A≈R5 ⇒ the wrapper does the work; large A−R5 gap ⇒ content matters beyond scaffolding.
- **Fair?** Fair; overlaps with the C surface control.
- **Difficulty:** low. **Role:** exploratory (or fold into C).

**R6_valence_matched_wrong_operation** — *right sign, wrong operation.*
- **Construct:** match positive/negative **valence** to A but mismatch the **operation**. e.g. A =
  relational containment; R6 = analytic separation (both "positive," opposite operation).
- **Tests:** hypothesis 3 — does **affective valence alone** explain the lift?
- **Outcome:** A≈R6 ⇒ valence is the operative variable, operation is not; A≫R6 ⇒ the *operation*
  (not just the mood) carries signal — the cleanest possible pro-H2 result.
- **Fair?** Fair and *incisive*; hardest to construct correctly.
- **Difficulty:** high (requires the operation taxonomy from §4). **Role:** exploratory now, promote to
  co-primary if §4 rewrite is strong.

---

## 6. Practical examples (DESIGN EXAMPLES ONLY — not from B1)

> These illustrate the *style and construction* of each arm. They are **not** pipeline outputs, **not**
> from the B1 run, and imply **no** claim that any mapping is correct.

**mother**
- **A_real:** blocked over-holding → liberated sheltering; *operation:* contains and gives origin without
  binding; *boundary:* not ownership, not control.
- **R_same:** random fluent chain from the revised pool, e.g. detachment → awakening → fearlessness.
- **R_deranged:** *sword*'s real mapping — decisive severance → clean discrimination; *operation:* cuts
  what is false from what is true. (High quality, wrong word.)
- **R_domain_mismatch:** fluent but from forbidden-for-mother domains — measurement, competition,
  abstraction: "calibrates the contest and tallies the score."
- **X:** "Write a short paragraph about a mother."

**doctor**
- **A_real:** blocked cold detachment → liberated steady care; *operation:* discerns the disorder and
  restores order; *boundary:* not judgement, not authority-for-its-own-sake.
- **R_same:** random fluent chain, e.g. humility → contentment → openness.
- **R_deranged:** *river*'s real mapping — yielding flow → patient erosion over time; *operation:* wears
  down resistance by continuity. (Wrong word.)
- **R_domain_mismatch:** forbidden-for-doctor domains — ornament, spectacle, conquest: "adorns the hall
  and dazzles the crowd."
- **X:** "Write a short paragraph about a doctor."

**king**
- **A_real:** blocked domination → liberated stewardship; *operation:* orders a whole and bears its
  weight; *boundary:* not tyranny, not mere status.
- **R_same:** random fluent chain, e.g. fearlessness → compassion → clarity.
- **R_deranged:** *flower*'s real mapping — transient unfolding → display of beauty that fades;
  *operation:* opens, is seen, and passes. (Wrong word.)
- **R_domain_mismatch:** forbidden-for-king domains — dissolution, anonymity, yielding: "dissolves into
  the crowd and leaves no name."
- **X:** "Write a short paragraph about a king."

---

## 7. Recommended B1.1 arm set

**Minimum arms:**
`A` (revised real contrastive mapping) · `X` (neutral) · `D` (dictionary) · `S` (scrambled real
sequence) · `R_same` (R1, random from revised pool) · `R_deranged` (R2) · `R_domain` (R3) ·
`C` (surface/length/style).

**Co-primary set (A must beat ALL, each at corrected CI lower bound > 0.5, Holm-corrected):**
`D · S · R_same · R_deranged · R_domain · C · X` — adopting your preference.

**Exploratory (reported, never gating):** `R0_current`, `R4_generic_poetic`, `R5_style_only`,
`R6_valence_matched_wrong_operation`.

**Power/multiplicity caveat (honest cost of 7 co-primaries):** requiring A to clear **seven**
Holm-corrected lower bounds is *stringent by design* — good science, but it lowers power. Pre-register a
sample size (words × tasks × models × seeds) sized so each co-primary has adequate power at the smallest
effect worth caring about; otherwise a true small effect could fail on power alone. State the assumed
effect size and the resulting n **before** generation. Do **not** drop co-primaries after seeing data
(§10).

---

## 8. Pass/fail logic

Decision rule per contrast: **A "beats" a control iff the item-clustered, paired-bootstrap, Holm-corrected
CI lower bound > 0.5.** Verdict is a function of the *pattern*:

| Observed pattern | Interpretation / label |
|---|---|
| A beats X only | generic prompting effect (`NO_SIGNAL`-adjacent) |
| A beats X and C but **not R_same** | **generic resonance explains it** (`RANDOM_OR_SCRAMBLED_MATCHES`, as B1) |
| A beats R_same but **not R_deranged** | real-looking symbolic mappings help, **word-specific fit not shown** |
| A beats R_deranged but **not R_domain** | word-specific fit partly matters, **domain-mismatch still competitive** |
| A beats **D/S/R_same/R_deranged/R_domain/C/X** | candidate `LIMITED_GENERATION_UTILITY` **for revised B1.1 only** — still **no ontology, no H2 truth** |
| A fails **D** | `DICTIONARY_DOMINATES` |
| A worse than control on **T4** correctness | `CORRECTNESS_DEGRADED` (or an accuracy caveat qualifying any win) |

**Pre-committed KILL condition (anti-unfalsifiability):** if A fails **R_same or R_deranged** on the
revised contrastive pool, B1.1 is a **negative** and the program records a *third* independent
random-matches result. There is no "the lexicon still wasn't good enough" retry without a **new,
differently-motivated mechanism** (not just another gloss pass). Guard against infinite regress: at some
point "it would work with a better lexicon" **is** the result.

---

## 9. Data-persistence fix (close the B1 gap)

B1 kept only hashes in-repo; raw outputs, packets, and per-item judge responses lived on RunPod and are
now unrecoverable — so "show me an R-beats-A example" is unanswerable from the repo. For B1.1, **require**:
- Commit a **small, leak-scanned, blinded sample of 30–50 packets**, deliberately including:
  - cases where **R beats A**, and cases where **A beats R**;
  - the **judges' stated reasons** if the harness captures them;
  - **no hidden arm/model/seed labels** in the public sample (blinding preserved).
- Store the **full** raw outputs + packets in durable/secure artifact storage (not the ephemeral pod),
  **hash-bound** in the repo (as B1 did) so the public sample and the full set are both verifiable.
- Add a persistence assertion to the packet builder: refuse to finish unless the committed sample exists
  and its hash is recorded.

---

## 10. Experimental-integrity rules

- **New B1.1 only.** It cannot alter B1 or B1's verdict.
- **New pre-registration required before any generation** (arms, seeds, n, effect size, gate τ, judge
  panel, attention rule, bootstrap params, stopping/KILL rule).
- **No post-hoc removal of R variants.** The co-primary set is fixed at prereg.
- **No weakening R to make A win.** Every R must be **fluent, same length, same grammar, same wrapper**,
  and **wrong only in semantic fit** — never ugly or nonsensical.
- Any parse/repair or replacement rule must be **pre-declared** (as the B1 narrow brace-repair was).
- **The revised A pool must pass the §3 contrastivity gate before generation**, and the pool + gate result
  are frozen and hash-bound.
- **Track B remains BLOCKED** unless B1.1 later passes **all** co-primaries under the frozen rule.
- The whole B1.1 runs under the same freeze discipline as B0 (index → hashes → signed record →
  `INVALID_POSTHOC` on any post-freeze edit), and the **lexicon JSONs must be inside the freeze set** this
  time (B1 flagged that they were not).

---

## 11. Recommended output files (design/audit only)

- `B1_1_RANDOM_RESONANCE_DECOMPOSITION_DESIGN.md` — **this memo.**
- `VARNA_GLOSS_CONTRASTIVITY_AUDIT_PLAN.md` — companion audit procedure + gate spec (drafted alongside).

No model run · no generation · no scoring · no B1 artifact modified · **not committed until you approve.**

---

## Final recommendation — priority order for B1.1

1. **Varṇa contrastivity rewrite (§3–§4) — first.** It is the *precondition*: without a contrastive,
   contrast-boundaried A pool, neither A nor any R is interpretable, and R_deranged/R_domain cannot be
   read cleanly. It also directly tests hypothesis 1.
2. **R_deranged control (R2) — the decisive co-primary.** It holds mapping *quality* maximal and breaks
   only word→mapping *fit*, so it isolates the single thing H2 must add. **A vs R_deranged is the crux
   experiment**; its result is the most informative bit in the whole design (word-specific fit exists, or
   H2 has no word-specific utility).
3. **R_domain_mismatch control (R3) — secondary confirmation** of semantic-fit, guarding against "fit
   didn't matter but derangement happened to stay coherent."
4. **Data persistence (§9) — baked in from the start**, non-negotiable, so B1.1 is inspectable regardless
   of outcome.
5. **New pre-registration (§10) — the gate before any generation**, with a pre-committed KILL condition
   so B1.1 can end the line rather than perpetuate it.

**Honest prior:** two independent tracks (Track G, B1) already show random explains A. B1.1 is worth
running **because R_deranged makes the failure conclusive and a success uncheatable** — not because a
positive is expected. If A cannot beat R_deranged on a contrastive pool, that is the answer, and the
program should record it and stop, not re-roll the lexicon.

**Structure, not validated meaning.** Design only; the B1 verdict `RANDOM_OR_SCRAMBLED_MATCHES` stands and
Track B remains BLOCKED.

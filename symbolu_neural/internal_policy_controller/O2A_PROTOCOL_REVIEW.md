# O2A Protocol — Adversarial Peer Review

> **Type:** scientific peer review. **Does not modify** `O2A_OFFLINE_EVALUATION_PROTOCOL.md`
> (the frozen pre-registration) or `ROADMAP_O2A_O2B_SPLIT.md`. This is a separate review
> simulating a hostile ACL/EMNLP/NeurIPS reviewer whose prior is:
> *"This is probably just another handcrafted symbolic semantic lexicon."*
> **Reviewer recommendation on the protocol as written: REJECT (major revision required).**

---

## A. Overall review

The protocol is competent on hygiene (pre-registration, frozen thresholds, a phonetic-
substrate floor, a random-label floor) but **tests an easier surrogate than the stated
hypothesis**. The stated claim is "captures meaning **beyond ordinary linguistic
baselines**"; the protocol operationalizes "separates six author-chosen binary contrasts
better than a **sentiment dictionary**." In 2026 the sentiment dictionary is not the
baseline a reviewer cares about — a pretrained sentence encoder is — and the protocol
makes that encoder *optional*. Therefore a PASS is fully consistent with the reviewer's
null (a hand-built, sentiment-correlated lexicon on self-authored data), and **would not
move their prior.** Three structural problems compound this: separability is tested
instead of representation, stability is gameable by Symbol-U's known near-constancy, and
the data is authored by people who know the ontology. The protocol is salvageable, but
only with the revisions in §D, an O1.5 construct gate (§E), and a V2 (§F).

## B. Major weaknesses

**B1 — The decisive baseline is optional (fatal).** "Ordinary linguistic baselines" means
SBERT/RoBERTa, not VADER. As written, the protocol can return PASS while a stock encoder
beats the reading outright. Beating a lexicon is no evidence of semantics. → **Sentence
embeddings must be REQUIRED and primary (§3, §D).**

**B2 — Separability ≠ a semantic representation.** AUC on six binary contrasts the authors
built to be separable is a low bar; any affect-correlated scalar clears joy/grief. A
meaningful representation must show *graded* structure (similarity ~ human judgments),
*compositional* sensitivity (word order matters), and *relational* behavior (entailment).
None are tested.

**B3 — Stability is gameable by the documented failure mode.** A near-constant function —
exactly what the phonetic substrate produced — passes every stability metric trivially.
Stability is meaningful **only conditional on adequate sensitivity**. The protocol never
couples them, so it can pass stability for the wrong reason.

**B4 — Self-authored datasets leave circularity uncontrolled.** One insider-authored
holdout is not enough; sentence selection can unconsciously track varṇa composition. The
"acoustic essences" are themselves English-meaning annotations, so predicting meaning from
them risks tautology.

**B5 — Contrasts are sentiment-entangled.** joy/grief, calm/urgent, certainty all covary
with sentiment, so they *cannot* demonstrate "beyond sentiment." No sentiment-orthogonal
contrasts are included.

**B6 — No construct-validity prerequisite.** Nothing checks that the reading varies enough
to be testable or that English→varṇa extraction is principled. Risk of building the whole
protocol on a dead-on-arrival near-constant signal.

## C. Minor weaknesses

- **Multiple comparisons:** six contrasts × several metrics × baselines invites
  researcher degrees of freedom; needs correction (Holm/BH) and a pre-committed primary
  metric.
- **Tiny n (20+20):** AUC CIs will be wide; a power analysis and ≥100/pole is advisable.
- **M4 human study underspecified:** rater sourcing, instructions, and the "proxy"
  fallback caps rigor; pre-register the human study or drop the claim.
- **Distance metric unspecified** for M2 (standardization, Euclidean vs cosine) — affects
  the ratio materially.
- **No inter-annotator agreement** required on the labels themselves (dataset validity).

## D. Recommended protocol improvements (for V2)

1. **Require sentence embeddings; reframe as incremental information (see §4 below).**
2. **Add the lexicon-shuffle ablation family (see §5).**
3. **Mandate external datasets (see §6).**
4. **Add sentiment-orthogonal contrasts** (abstract/concrete, intention/observation,
   literal/sarcastic) and a **topic negative control** (matched-sentiment, different
   topic — reading should *not* separate it).
5. **Couple every invariance with a sensitivity test** (word-order scramble must *change*
   the reading); report stability/sensitivity as a ratio, not stability alone.
6. **Add an acoustic-only ablation** (features from sound properties with glosses removed)
   to separate "the sounds carry signal" from "the gloss annotations carry signal."
7. **Add compositionality and graded-similarity tests** (STS correlation; word-order
   sensitivity).
8. **Multiple-comparison correction + power analysis + a single pre-committed primary
   endpoint.**

---

## Section-by-section findings

### 1. Scientific validity
The protocol tests a **surrogate**: "separability beyond sentiment on self-authored data,"
not "meaning beyond modern baselines." A PASS as written is uninformative w.r.t. the
hypothesis. Fixable via B1/B2/B5 + §D.

### 2. Construct validity — **introduce O1.5 (strongly recommended)**
Before O2A, insert **O1.5 — construct validity & dynamic range**, a near-free gate:
- **Dynamic range:** reading-feature variance across a broad corpus must materially exceed
  the phonetic substrate's. *If the reading is near-constant → TERMINATE before O2A.*
- **Extraction sanity:** semantically clear words yield sensible, deterministic chains;
  English→IAST→varṇa is principled, not arbitrary (audit transliteration on a gold list).
- **Confidence validity:** the coherence/confidence values must correlate with something
  (e.g., higher on unambiguous than on garbled inputs), else they are decorative.
- **Category-error check:** state explicitly whether English input through Sanskrit-varṇa
  machinery is theoretically licensed; if it is a category error, O2A on English cannot
  test the theory regardless of outcome.
If O1.5 fails, **stop** — do not build O2A. This is the cheapest possible kill switch.

### 3. Baselines — **sentence embeddings must be REQUIRED**
VADER + length + random + phonetic substrate give a *floor* but no *ceiling*. Without a
strong encoder there is no way to claim "beyond ordinary baselines." Promote SBERT (and a
second encoder, e.g., mean-pooled RoBERTa) to **required primary comparators**; add TF-IDF
+ logistic (controls for word identity) and an NLI model (for entailment invariance).
Demote VADER: beating it proves nothing.

### 4. Orthogonal information — **the right, and fairer, framing**
The reviewer's clarification is correct and scientifically superior. The claim should be:
**"Symbol-U contributes semantic information not already linearly recoverable from
SBERT,"** not "Symbol-U beats SBERT." Rationale:
- A hand-built, untrained representation will almost never *beat* a pretrained encoder on
  raw performance; demanding that sets Symbol-U up to fail for the wrong reason.
- **Incremental information is the stronger and fairer claim.** Operationalize as: (a)
  **complementarity** — fit SBERT→reading regression/CCA; the residual is the part of the
  reading *not* explained by SBERT; (b) the residual must be **predictive** of an external
  human-labeled axis (orthogonal-and-useless is trivial — orthogonal-and-predictive is the
  result); (c) **incremental ΔAUC/ΔR²** of [SBERT + reading] over [SBERT] on external
  tasks, with significance and correction.
- **Caveat:** incremental signal alone does not prove the *ontology* is real (see §8) — a
  useful orthogonal feature could be an arbitrary code. It is necessary, not sufficient.

### 5. Lexicon-shuffle — insufficient as one knob; needs a graded family
A single "shuffle the glosses" is good but conflates several claims. Use a **family of
degrees-of-freedom-matched, consistently-applied** permutations (one fixed permutation per
run, like the v3/v4 relabel), ranked by diagnostic importance:

1. **Shuffle poles (+/−)** — *most decisive, cheapest.* Polarity (binding/liberating) is
   the core semantic claim. If shuffling polarity doesn't hurt, the valence signal is fake.
2. **Shuffle glosses (essence labels)** — tests whether the specific essence *content*
   matters vs. any labeling.
3. **Shuffle varṇa→sound groups** — tests whether the specific phoneme→varṇa assignment
   carries information vs. any grouping of the same alphabet.
4. **Randomize the ontology tree/hierarchy** — only meaningful once the reading *uses*
   hierarchy (O3/O7); low priority for the v1 flat reading.

Pass requires real ≫ each shuffle by a pre-registered margin. If real ≈ shuffle on the
high-rank perturbations → the ontology content is inert regardless of raw AUC.

### 6. External datasets — should be MANDATORY; strongest first
Replace self-authored sets as the *primary* evidence with external, human-labeled, standard
corpora (authors did not choose the items; labels predate Symbol-U):

| Need | Dataset | Why strongest |
|---|---|---|
| **Graded similarity** | **STS-B** | gold standard; tests *graded* structure, not binary — hardest to fake |
| **Continuous emotion** | **EmoBank (VAD)** / Warriner VAD norms | continuous valence/arousal matches Symbol-U's continuous claim; word norms are anti-circular (independent) |
| **Abstraction** | **Brysbaert concreteness norms** | sentiment-orthogonal; lexicon authors didn't consult it |
| **Figurative / irony** | SemEval irony, VU Amsterdam Metaphor | sentiment lexicons fail here — a discriminating test |
| **Uncertainty/factuality** | CommitmentBank, FactBank | tests the pramāṇa/vikalpa claim externally |
| **Contradiction/entailment** | SNLI/MNLI (contradiction subset) | tests relational/compositional behavior |

**Highest evidential value:** STS-B (graded), EmoBank/Warriner (continuous + independent),
Brysbaert (orthogonal), irony (where lexicons break). These four make a PASS hard to
dismiss; the binary hand-authored contrasts become *supplementary*.

### 7. Failure-localization decision tree
```
O2A fails.
│
├─ Does a STRONG ENCODER (SBERT) also fail the same contrast/task?
│     YES → DATASET failure (the contrast isn't separable / labels noisy). Fix data, not Symbol-U.
│     NO  ↓
├─ Does the READING have dynamic range (O1.5 variance check)?
│     NO  → ENGLISH→VARṆA mapping failure (extraction near-constant/arbitrary; signal dies at extraction).
│     YES ↓
├─ Does REAL lexicon beat SHUFFLED lexicon (poles/glosses)?
│     NO  → ONTOLOGY failure (the specific mappings are inert; structure carries no signal).
│     YES ↓
├─ Does a RICHER read-out (alternative aggregation) recover signal the current features missed?
│     YES → READING-CONSTRUCTION failure (chain is fine; the feature aggregation discarded it).
│     NO  ↓
└─ Are thresholds/power/labels sound (IAA, power analysis)?
      NO  → EVALUATION failure (underpowered / mis-thresholded / noisy labels).
      YES → genuine NEGATIVE for the current reading ρ (not the unspecified ρ*).
```
The two pivotal diagnostics: the **strong encoder** (separates dataset failure from
Symbol-U failure) and the **shuffle family** (separates ontology-content failure from
chain/construction failure).

### 8. What a PASS would actually demonstrate (rank separately — do NOT conflate)
- **A. A useful semantic representation:** *Reachable.* A revised-protocol PASS (orthogonal
  info over SBERT, external data, shuffle-robust) supports this. **Confidence highest.**
- **B. Evidence for the Symbol-U ontology:** *Partially reachable.* The **shuffle ablation**
  is the bridge: real ≫ shuffled ⇒ the *specific* mappings matter. But "the ontology works
  as a code" is weaker than "the ontology is the *right/true* structure." **Confidence
  moderate, and only via the ablations.**
- **C. Evidence for Sanskrit-derived semantic structure:** **Essentially unreachable by any
  English-input offline protocol.** Even a perfect PASS cannot show the *Sanskrit/acoustic
  derivation* is responsible — the signal could come from English orthographic/phonotactic
  regularities, or from gloss annotations that are English meanings in disguise.
  Establishing C requires fundamentally different evidence: signal from **acoustic
  properties alone** (gloss-free ablation), **cross-linguistic** replication on actual
  Sanskrit, and ruling out gloss leakage. **Confidence very low; out of scope.**

Ranking: **A ≫ B ≫ C.** The patent's core claim (C) is the *least* supported by O2A even
on success, and the protocol should say so explicitly to avoid overclaiming.

### 9. Remaining risks even if O2A passes
- **Gloss leakage / deep circularity:** the essences are human meaning-annotations; if the
  shuffle doesn't fully sever gloss-vocabulary from target meaning, prediction can remain
  near-tautological. Needs the gloss-free acoustic-only ablation to rule out.
- **The acoustic claim stays untested:** nothing shows *sound* (vs. lexicon annotation)
  carries the signal unless the acoustic-only ablation is run and passes.
- **English category error:** a Sanskrit-varṇa theory tested on English transliteration —
  unresolved by any English protocol.
- **ρ\* still unspecified:** per the project's own boundary doc, a PASS validates the
  *current* reading ρ, not the completed theory.
- **Downstream utility (O2B) remains open:** a meaningful representation need not improve
  LLM answers (the v3/v4 lesson).
- **Researcher degrees of freedom** across many datasets/metrics unless corrected.

---

## Deliverables summary

- **E. Introduce O1.5?** **Yes — mandatory, first.** A near-free construct-validity +
  dynamic-range gate that terminates the program if the reading is near-constant or the
  extraction is arbitrary. It can kill the question for free before O2A is built.
- **F. Should the protocol become V2?** **Yes** — author a *separate* `..._V2.md` (leave V1
  frozen as the historical pre-registration) incorporating: required encoder baselines,
  the incremental-information framing (§4), the shuffle family (§5), mandatory external
  datasets (§6), sensitivity-coupled stability, the acoustic-only ablation, and
  multiple-comparison correction. Gate everything behind O1.5.
- **G. Confidence a PASS on the *revised* protocol convinces a neutral NLP reviewer that
  Symbol-U produces a genuinely meaningful semantic representation (claim A): ~60%.**
  - Current protocol (as frozen): **~12%** — a PASS is consistent with the reviewer's null.
  - Revised V2: **~60%** for claim A; **~35%** for claim B (ontology); **~8%** for claim C
    (Sanskrit-derived). The residual reflects that even a clean, non-redundant,
    non-circular PASS leaves the *acoustic/Sanskrit derivation* and the *completed theory*
    unestablished — which no English-input offline protocol can reach.

**Reviewer's closing note:** the protocol's instinct (offline, pre-registered, adversarial
floors) is right; its **calibration is a decade out of date** (sentiment baseline, binary
separability, insider data). Re-aim it at *incremental information over a strong encoder,
on external human-labeled data, with pole/gloss/acoustic ablations*, gate it behind an
O1.5 dynamic-range check, and a PASS becomes genuinely difficult to dismiss as "just a
lexicon" — for claim A. Claims B and C need their own, harder experiments and should never
be asserted on O2A evidence alone.

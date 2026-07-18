# MILESTONE_A_FOUNDATIONS

> **STATUS — Milestone A provenance analysis. UNRESOLVED.** Documentation only. No code, no
> implementation, no Stage A change, no weakened caveat. This document executes the
> **Foundations** step of `IMPLEMENTATION_ROADMAP.md` up to — and only up to — its **TERMINAL
> gate**: *can a gloss-independent essence table `E` be defined at all?* It reaches a
> **conditional** answer (yes, by exactly one admissible path) and then **stops**, because that
> path has **no committed source yet**. The remaining Foundations deliverables (`Y`, `P`, `B`,
> metrics, pre-registration) are **blocked** until the gate is resolved.
> **Candidate hypothesis · Not validated · Stage A untouched · No Sanskrit privilege ·
> No semantic claims · Glossary-independent inputs required · Preserve ⊥.**
> **structure, not validated meaning.**

## 0. Purpose and scope

`IMPLEMENTATION_ROADMAP.md` Milestone A asks us to freeze everything that defines a *fair*
experiment, with **no implementation**. Its gate is **TERMINAL**:

> if `E` cannot be defined **independently of dictionary meaning**, the program cannot be
> tested non-circularly — **terminate.**

This document does **only** the analysis that gate requires. It does **not** freeze a final
`E`, does **not** name a dataset, and does **not** declare Milestone A complete. It answers a
single question — *is there any admissible provenance for `E`?* — and records the answer as a
**conditional pass with an open dependency**, not a pass.

What this document is **not**: it is not a specification of `Y`, `P`, `B`, the metrics, or the
pre-registration. Those are deliberately deferred (§6): specifying instrumentation for an `E`
whose source is unknown would bake in choices the source has not yet constrained.

## 1. The object under scrutiny

Per `LATENT_SEMANTIC_FORMATION_HYPOTHESIS.md` §3.4 and `VARNA_STATE_OPERATOR_THEORY.md` §4,
`E = (e_{σ_1}, …, e_{σ_n})` is the table of **per-varṇa essences** — the hypothesized intrinsic
content each varṇa is claimed to carry. Every downstream test (`I(z;E)`,
`I(z; meaning | phonology)`) consumes `E` as its *input*. If `E` is contaminated by the very
meanings it will later be tested against, every downstream number is circular and unfalsifiable.

The VSO theory's own observables table (`VARNA_STATE_OPERATOR_THEORY.md` §4) already concedes
the danger: it classifies the theory's internal `φ_binding`/`φ_liberating` coordinates as
**theoretical**, with empirical content *only through a bridge map*, and names treating those
coordinates "as if measured" as **the circularity to avoid.** This document takes that warning
as binding and asks where a *non-theoretical, non-circular* `E` could come from.

## 2. The provenance trilemma

There are exactly three families of source for `E`. They are exhaustive: an essence value
either comes from the word meanings (1), from the physical sound signal (2), or from some
third measurement that is neither (3). We evaluate each against **two** filters that any
admissible `E` must pass:

- **Filter A — anti-circularity (the Milestone A gate):** `E` must be definable **without**
  reading the dictionary glosses / codomain `Y` it will later be used to predict.
- **Filter B — non-collapse (the Milestone B phonology baseline):** `E` must carry information
  **not already captured** by the phonological-similarity baseline; otherwise
  `I(z; meaning | phonology) = 0` by construction and the test returns `⊥` regardless of result.

A source must pass **both**. Filter A is the Milestone A TERMINAL gate; Filter B is what
Milestone B will enforce, but a source that is *guaranteed* to fail B is not worth carrying
forward, so we screen for it now.

| # | Provenance of `E` | Filter A (anti-circular) | Filter B (non-collapse vs phonology) | Verdict |
|---|---|---|---|---|
| 1 | **Gloss-derived** — essences assigned by reading word meanings | **FAIL** — `E` is a function of the glosses it will predict | (moot) | **Ruled out — circular** |
| 2 | **Raw phonetic/acoustic** — place, manner, voicing, sonority, formants | PASS | **FAIL** — `E` *is* the phonology baseline; conditional MI is 0 by construction | **Ruled out — collapses** |
| 3 | **Externally-measured sound-symbolism norms** — human iconicity / pseudoword associations measured on lexically-empty stimuli | PASS (norms read no glosses of the target lexicon) | *Plausibly* PASS — a human perceptual mapping, not a raw acoustic feature vector | **Only admissible candidate** |

### 2.1 Why (1) gloss-derived `E` is ruled out — circular

If the essence `e_σ` is set by inspecting the meanings of words containing `σ` (or by an
author's semantic intuition about those words), then `E` is a function of the glosses, and the
later claim "`E` predicts meaning `Y`" reduces to "meaning predicts meaning." The relabel and
random baselines cannot detect this — the leakage is in the *construction* of `E`, upstream of
any test. This is precisely the failure the VSO §4 table warns against. Filter A fails by
definition. **No experiment built on a gloss-derived `E` can be non-circular.**

### 2.2 Why (2) raw phonetic/acoustic `E` is ruled out — collapses into the phonology baseline

A raw articulatory/acoustic feature table is gloss-independent, so it passes Filter A. But the
baseline suite `B` (`LATENT_SEMANTIC_FORMATION_HYPOTHESIS.md` §3.5) includes a
**phonological-similarity baseline**, and the decisive metric is the *conditional*
`I(z; meaning | phonology)`. If `E` is itself a phonological feature table, then conditioning on
phonology conditions on `E`, and the conditional information is **identically zero by
construction** — not as an empirical finding but as an algebraic fact. The test would return
`⊥` for every possible dataset, making it uninformative. Path (2) therefore cannot *win*; it
can only formally demonstrate that "essence = raw sound" is empty. The standing priors already
point the same way: reading is sound-driven and the signal is lost to a phonology/sentiment
baseline (`O1_5_CONSTRUCT_VALIDITY_REPORT.md`, `O1_5_FAILURE_LOCALIZATION_REPORT.md`,
~12:1 sound-over-meaning sensitivity; synonyms varṇa-disjoint at ~random). **Filter B fails.**

### 2.3 Why (3) sound-symbolism norms is the only admissible candidate

Sound-symbolism / iconicity norms are human judgments collected on **lexically-empty stimuli**
(pseudowords, or cross-linguistic forms with no shared lexicon), measuring associations such as
size, shape (bouba/kiki), magnitude, brightness, or affect from **sound alone**. Two properties
make this the only path through both filters:

- **Passes Filter A:** the norms are measured without reference to the glosses of the target
  lexicon `E` will predict. Provided the norm set is sourced *independently* of `Y` and frozen
  before `Y` is touched (an anti-circularity rule to be specified, §5), there is no gloss
  leakage.
- **Plausibly passes Filter B:** a sound-symbolic association is a **human perceptual mapping**,
  not the raw acoustic feature vector. Sound symbolism is an empirically attested phenomenon
  *distinct* from — though correlated with — raw phonetics; that distinctness is exactly what a
  conditional-on-phonology test can, in principle, detect. "Plausibly," not "certainly": whether
  any residual survives conditioning on phonology is an **empirical** question, and it is the
  question Milestone B exists to answer.

Path (3) is admitted as **the sole candidate**, not as a likely winner. The negative priors
apply to it too: the offline corpus-norm proxy returned R²≈0–2% (`S1_S2_CORPUS_NORM_PRELIMINARY_REPORT.md`).
**The honest pre-registered expectation remains that Milestone B most likely returns `⊥`,**
even under path (3). That is the roadmap working as designed, not a defect.

## 3. What path (3) is **not**

To prevent path (3) from silently readmitting the ruled-out paths:

- It is **not** the theory's authored binding↔liberating essence values. Those are
  gloss-contaminated theoretical coordinates (VSO §4); they may enter only *later*, as a bridge
  *hypothesis* to be tested (Milestone E+), never as the input `E`.
- It is **not** a raw acoustic feature table relabeled as "symbolism." If the proposed `E`
  reduces to phonological features, it is path (2) and is ruled out by §2.2.
- It is **not** norms collected on, or selected using, the target lexicon's meanings. That would
  reintroduce gloss leakage (path 1).

## 4. Milestone A status: UNRESOLVED (conditional pass with open dependency)

The TERMINAL gate asks whether **any** gloss-independent `E` exists. The analysis answers:
**conditionally yes — exactly one admissible provenance (path 3) — but no defensible source for
it has been identified or committed.** Therefore:

- The gate does **not** fire (we do not terminate the program at Milestone A): an admissible
  path exists in principle.
- The gate is **not** passed (we do not declare Foundations complete): an admissible *path* is
  not a defensible *source*.
- **Milestone A is UNRESOLVED, blocked on a single dependency: a concrete, defensible
  externally-measured sound-symbolism source for `E`.**

This is deliberately not forced either way. Declaring a pass now would let an unsourced `E`
leak an undefended modeling choice into every downstream test; firing the gate now would skip
the cheapest decisive empirical test (Milestone B) on the strength of priors B is designed to
adjudicate properly.

## 5. Resolution criteria — what a defensible path-(3) source must satisfy

Milestone A becomes **RESOLVED (pass)** only when a candidate source is proposed *and* meets
**all** of the following, fixed here in advance:

1. **Externally sourced & published.** A norm set produced and published independently of this
   project and of the target lexicon — not authored here.
2. **Gloss-independent by construction.** Collected on lexically-empty stimuli (pseudowords /
   cross-lexicon forms), with no item's value derived from or selected using a target-lexicon
   gloss.
3. **Varṇa-projectable with a stated, pre-registered rule.** A specified, frozen mapping from
   the norm space to per-varṇa values `e_σ`, fixed before `Y` is touched and recorded with a
   `sha256` — the projection rule itself must not consult `Y`.
4. **Non-collapse plausibility argued, not assumed.** An explicit argument (and, at Milestone B,
   a measurement) that the resulting `E` is not a deterministic function of the phonological
   baseline features — i.e., that conditional information is not zero by construction.
5. **Coverage & provenance documented.** Which varṇas are covered, how gaps are handled, inter-
   rater reliability / sample size of the source norms, and the full citation chain.

If **no** source satisfying (1)–(5) can be identified, the dependency cannot be discharged and
the Milestone A gate **fires retroactively → terminate.** Failure to find a defensible source
*is* the TERMINAL-gate failure; it is simply not yet established.

## 6. Deliverables deliberately deferred (and why)

The roadmap's other Foundations deliverables — codomain `Y`, anti-circularity rule set, probe
class `P`, baseline suite `B`, metrics, pre-registration — are **blocked pending §5**. They are
deferred on purpose: each is partly constrained by what path-(3) source is chosen (e.g. the
phonology baseline must be defined so that Filter B is a real test against *that* `E`; `Y` must
be chosen so its anti-circularity separation from the chosen norm set is checkable). Freezing
them against an unknown `E` would either bias the source selection or require redoing them once
the source is known. They will be specified in a follow-up only **after** §5 is discharged, and
will reuse the existing pre-registration conventions (`S1_S2_PSEUDOWORD_PREREGISTRATION.md`) and
the baseline / failure-state definitions already fixed in
`LATENT_SEMANTIC_FORMATION_HYPOTHESIS.md` §3.5.

## 7. Next action

Identify and evaluate candidate externally-measured sound-symbolism norm sets against the §5
criteria. The output of that search is the gate decision: a source that meets §5 → Milestone A
**RESOLVED**, proceed to specify `Y`/`P`/`B`/metrics; no such source → gate **fires** →
terminate. No representation function `F`, no decoder, and no Milestone B instrumentation is
built before §5 is discharged.

---

## Standing constraints (do not weaken)

Candidate hypothesis · Not validated · Milestone A **unresolved** · No `E` committed · No
dataset committed · Stage A untouched · No Sanskrit/varṇa privilege · No semantic claims ·
Inputs glossary-independent · `⊥` preserved · Structure frozen, semantics hypothetical.

> **structure, not validated meaning.**

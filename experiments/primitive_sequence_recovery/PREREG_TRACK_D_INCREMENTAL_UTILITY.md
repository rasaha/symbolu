# Pre-Registration — Track D: Incremental Utility of Varṇa Features (docs only)

**Pre-registration. Nothing implemented, run, or changed.** No code, no experiment, no Stage A
change, no reopening of Track B, no reinterpretation of Track C, no `manifest_v2`, no change to
frozen artifacts. `manifest.json` remains NOT_READY; the runner remains NOT_RUN.

**Framing (read first).** Track D asks an **engineering/utility** question, deliberately weaker
than the ontological one. It is **not** a rescue of Symbol-U, **not** confirmatory evidence of
its truth, and **not** an `ONTOLOGICAL_SIGNAL` test. A positive Track D result supports
**utility in a fixed architecture**, never **truth**. This document fixes the design *before*
any data is touched, so the analysis cannot be steered to a conclusion.

Builds on `varna_lens/PREREG_VARNA_THREE_CHANNEL.md` (incremental-validity framing) and respects
`VERSION1_SCOPE_AND_VERSION2_PROPOSAL.md` (Track D is a **new hypothesis**, not a continuation).

---

## 1. Scientific question

> Does adding a **real varṇa-derived feature channel** improve measurable downstream
> performance **beyond** a context baseline and/or an etymology baseline, in a **fixed**
> architecture — and does that improvement survive controls that rule out "any extra relevant
> text helps"?

The unit of the claim is the **incremental contribution of the varṇa channel**, holding the
architecture, data, and all other channels fixed. The strongest honest form of a positive is:
"the varṇa *assignment* (not merely its English glosses) adds non-redundant value on task T."

## 2. What Track D can and cannot prove

**Can prove (if the controls in §4/§8 pass):**
- the varṇa-derived feature is a **useful feature** in *this* architecture on *this* task;
- it provides an **incremental gain** beyond context and beyond etymology.

**Cannot prove (must never be claimed):**
- that the varṇa ontology is **true** or that varṇa meanings are **intrinsically real**;
- `ONTOLOGICAL_SIGNAL` of any kind;
- that **Track B is unblocked** (it is not; independence is still absent);
- anything that reinterprets or weakens the Track C negative or the Version 1 scope.

Utility ≠ truth. A useful feature can be useful for reasons unrelated to the theory (extra
English semantic text, correlation with etymology, etc.) — §4 exists to separate these.

## 3. Experimental arms

Fixed architecture (§7), fixed data (§5), identical for every arm; only the **input channels**
differ:

| arm | inputs |
|---|---|
| **A** | Context only |
| **B** | Context + Etymology |
| **C** | Context + Varṇa (real assignment) |
| **D** | Context + Etymology + Varṇa (real) |
| **E** | Context + **Scrambled**-Varṇa (same glosses, assignment permuted) |
| **F** | Context + **Equal-length decoy text** (relevance/length-matched, non-varṇa) |
| **G** | Context + Etymology + **Scrambled**-Varṇa |

Arms E, F, G are **controls**, not conditions of interest. The comparisons that matter:
C vs A, C vs E, C vs F, D vs B, D vs G. (Scramble seeds pre-registered in §10.)

## 4. Mandatory controls

1. **Assignment-scramble control (E, G).** Same gloss table, varṇa→gloss assignment permuted.
   If C ≈ E (or D ≈ G), the "improvement" is not the varṇa *system* — it is the glosses as text.
   This is the ablation analogue of the Track C assignment-scramble null.
2. **Equal-information text control (F).** A length- and relevance-matched decoy string (e.g.,
   shuffled dictionary text of equal token budget). If C ≈ F, *any* extra relevant text helps →
   `TEXT_ARTIFACT`.
3. **Incremental-over-etymology control (D vs B).** Varṇa must add value **beyond** etymology
   (with which it partly shares roots). If D ≈ B, varṇa is redundant → `REDUNDANT_WITH_ETYMOLOGY`.
4. **Bare-word / pretrained-knowledge contamination probe.** Measure task performance from the
   **bare word alone** (no channels) under the same model. If the model already solves the task
   from priors, channel gains are attenuated/uninterpretable → probe for `PRETRAINED_KNOWLEDGE_
   ONLY`. Prefer a frozen/deterministic varṇa encoder; if an LLM is used, this probe is required.
5. **Length / token-budget control.** All arms matched on total input token budget (pad/truncate
   per a fixed rule) so gains are not an artifact of longer inputs. F operationalizes this.
6. **Seed / task / report-all guardrail.** Fixed seeds (§10); **all** pre-registered tasks and
   metrics reported (no post-hoc dropping, no metric switching); task selection declared a DOF
   up front (§5).

## 5. Tasks (candidate pool; final selection is a declared DOF)

Candidate downstream tasks (word-meaning-centric, where a varṇa channel could plausibly help):
- definition generation,
- word-sense disambiguation,
- synonym / near-synonym ranking,
- lexical inference (entailment/relatedness between words),
- translation or explanation quality,
- retrieval ranking (word → gloss/definition).

**Task selection is a researcher degree of freedom and is flagged as such.** Rule: the task
set must be **fixed and justified before any run**, chosen for *a priori* plausibility (not
because a pilot showed a gain), and **all chosen tasks reported**. Prefer ≥2 tasks so a
task-scoped result is visible as such. Datasets must be public, fixed-version, and hash-pinned;
any Sanskrit-specific dataset must be checked for overlap with the frozen corpus.

## 6. Metrics (pre-registered candidates)

- **Primary (task-appropriate, pre-committed per task):** accuracy / F1 (classification, WSD,
  inference); MRR / Top-k (ranking, retrieval).
- **Generation tasks:** BLEU/ROUGE **only** as coarse secondary; **human preference only if
  blinded and pre-registered** (raters unaware of arm); never an LLM-as-judge as a primary
  confirmatory metric (contamination/nondeterminism).
- **Secondary only:** embedding similarity (never primary — it is itself a realizer artifact).
- **Report always:** calibration / confidence, and effect size with CI (§10).

One primary metric per task, pre-committed; **no metric switching** after seeing results.

## 7. Model architecture (must be frozen before any train/eval)

The fusion architecture, its hyperparameters, the channel-encoders, and the training/eval
protocol must be **frozen and hashed before touching data**. Implementation is **not chosen
here**; the pre-reg only fixes *what must be frozen*:

- the **channel encoders** (how Context / Etymology / Varṇa become features) — deterministic and
  version-pinned; if an LLM encoder is used, weights + prompts hash-pinned and the §4.4 probe
  mandatory;
- the **fusion mechanism** (one of: frozen-LLM prompt-only; small trainable adapter;
  retrieval-augmented prompt; feature-augmented classifier) — chosen and frozen **once**, applied
  **identically** to every arm;
- **all hyperparameters, seeds, early-stopping, and the train/val/test split** — fixed and
  recorded; the **test set is touched once**, at the end.

A trainable fusion model adds researcher DOF beyond Track B; the freeze-before-data discipline is
what contains it.

## 8. Positive decision label — `INCREMENTAL_UTILITY`

Emitted **only if all** hold (per task, or explicitly task-scoped):
- **C > A** (varṇa beats context-only), and
- **C > E** (varṇa beats scrambled-varṇa), and
- **C > F** (varṇa beats equal-length decoy text), and
- **D > B** (varṇa adds over context+etymology), and
- the effect's **bootstrap CI lower bound > 0** (§10), and
- the effect is **robust across seeds and tasks**, **or** explicitly reported as
  **task-scoped** (positive on task T only, stated as such — not generalized).

Anything less than the full conjunction is **not** `INCREMENTAL_UTILITY`.

## 9. Negative / other labels

- **`NO_UTILITY`** — C ≈ A (varṇa adds nothing over context).
- **`TEXT_ARTIFACT`** — C > A but C ≈ F (any equal-length relevant text helps equally).
- **`REDUNDANT_WITH_ETYMOLOGY`** — C helps alone but D ≈ B (no gain over etymology).
- **`PRETRAINED_KNOWLEDGE_ONLY`** — gains vanish once the bare-word contamination probe is
  accounted for (model already knew the answer).
- **`SCRAMBLE_EQUIVALENT`** — C ≈ E (glosses-as-text, not the varṇa assignment). *(subsumed by
  TEXT_ARTIFACT in spirit but reported distinctly, since E controls the assignment and F controls
  the text.)*
- **`TASK_DEPENDENT`** — positive on some tasks, null/negative on others, with no robust pattern.
- **`INCONCLUSIVE`** — CI includes 0 / underpowered / controls not cleanly separable.

## 10. Statistical plan

- **Held-out test set**, touched exactly once; train/val used for all model selection.
- **Paired comparisons** across arms on identical items (same words/inputs per arm).
- **Bootstrap confidence intervals** (item- and, where applicable, family-aware; ≥2000 resamples)
  on every arm-difference of interest; the **CI lower bound > 0** requirement in §8 is the
  robustness gate — recall the Track C lesson: a scramble-p under 0.05 is *not* enough; the
  resampling CI must clear 0.
- **Multiple seeds** (pre-registered, e.g. 5); report the distribution, not the best seed.
- **Report all tasks and all metrics**; **no post-hoc task dropping**, **no metric switching**,
  no threshold tuning after seeing results.
- **Multiple-comparison control** across arms × tasks × metrics (pre-registered correction).
- **Power caveat:** small corpora / small gains inside wide CIs are the expected failure mode;
  underpowered results are `INCONCLUSIVE`, not "trending positive."

## 11. Relation to previous work

- **Track A** (ontology/framework): complete; reused only as infrastructure, not as evidence.
- **Track B** (ontological, independent concept channel): **BLOCKED** and remains so; Track D
  does **not** reopen it and does **not** rely on independence.
- **Track C** (exploratory English semantic realizer): produced a **non-robust / no-signal**
  result on the consonant-only rendering; Track D does **not** reinterpret or soften this.
- **Version 1 scope:** Track D is a **separate hypothesis** with its **own pre-registration,
  data, and pipeline**; it must not reuse Version 1 conclusions, and its result says nothing
  about the Version 1 negative.
- The varṇa channel here may use the same lossy consonant-only decomposition or a future
  vowel-aware one; either way it is a **feature source**, and Track D claims utility of *that
  feature*, not correctness of the decomposition.

## 12. Risks

- **False positives are easier here than in Track B** — a trainable model + multiple tasks/metrics
  is a large DOF surface. The freeze-before-data + report-all + CI discipline is the only defense.
- **"More text helps" confound** — extra relevant English text can raise metrics regardless of
  varṇa (controls F, E).
- **LLM prior knowledge** — an LLM may solve word-meaning tasks from priors; gains attenuate and
  become uninterpretable (probe §4.4; prefer deterministic encoders).
- **Etymology overlap** — varṇa may be a noisy proxy for etymology (control D vs B).
- **Hyperparameter / architecture fishing** — mitigated only by freezing §7 before data.
- **Task-selection bias** — choosing the task that works is p-hacking (declare + justify + fix
  the task set a priori; report all).
- **Small gain inside a wide CI** — the Track C failure mode; do not over-read.
- **Conclusion creep** — the strongest, most dangerous risk: quietly upgrading "useful feature"
  to "Symbol-U validated." Forbidden (§2).

## 13. Recommendation

**Track D is worth pursuing — but only as an engineering/utility study, explicitly not as
evidence about Symbol-U's truth.** Honest assessment:

- **More practical than Track B:** it avoids the independence blocker outright, because it asks a
  weaker question with controllable confounds rather than an ontological one requiring a
  non-circular concept channel.
- **Lower ontological value:** a positive supports "useful in this architecture," nothing more;
  the shared-source and English-leakage issues cap its interpretive reach.
- **Conditional worth:** valuable **iff** run with the full control battery (E/F, D-vs-B,
  contamination probe), a frozen architecture, pre-registered tasks/metrics/seeds, and CI-based
  robustness. Without those, it is *more* prone to a misleading positive than Track B was — the
  easier a win is to obtain, the stricter the pre-registration must be.
- **Sequencing:** open Track D only **after** Version 1 is frozen/written up, as a clearly
  separate program with this pre-registration governing it. Do not begin implementation until an
  architecture-freeze (§7) is committed.

A positive Track D result would read: *"the varṇa-derived feature carries complementary,
non-redundant information that improves this system on these tasks"* — useful, publishable
engineering, and **still silent on whether varṇas mean anything.**

---

## Report

- **File:** `experiments/primitive_sequence_recovery/PREREG_TRACK_D_INCREMENTAL_UTILITY.md`
- **Docs-only:** yes — no code, schema, ontology, manifest, or experiment.
- **No experiment executed;** manifest still NOT_READY; runner still NOT_RUN; Stage A untouched.

> structure, not validated meaning.

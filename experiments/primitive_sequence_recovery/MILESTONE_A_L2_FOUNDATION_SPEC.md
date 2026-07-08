# Milestone A — L2 Foundation Specification (gloss-independent essence)

**Status:** Foundation design only (docs-only). Not a run, not a dataset, not code.
**Governed by:** `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**It does not validate meaning, does not alter B1.3 v3, and does not unblock Track B.**
**Structure, not validated meaning.**

Related documents:
- `SYMBOL_U_L2_VALIDATION_RULEBOOK.md` (governing framework)
- `B1_3_V3_L2_RULEBOOK_COMPATIBILITY_MEMO.md` (decision: `B1_3_V3_REQUIRES_NEW_VERSION_IF_RULEBOOK_APPLIED`)
- `MILESTONE_A_FOUNDATIONS.md` (prior milestone framing)

---

## 1. Purpose

Milestone A is a **foundation design**, not a run. Its object is to decide, *before any dataset or code
exists*, whether a **gloss-independent essence table `E`** can be defined for Symbol-U's varṇa layer — i.e.
whether there is any non-circular semantic foundation to validate at all.

This document specifies the criteria, gates, codomain, probe, baselines, failure state, candidate sources,
prior, deliverables, and allowed labels for that decision. It produces **no** data, **no** score, and **no**
freeze. It ends in a **terminate-or-proceed recommendation**, nothing more.

---

## 2. Starting decision

Per the compatibility memo, **B1.3 v3-authoritative is parked as a pre-rulebook exploratory line and is not
modified** by Milestone A. Its stimuli, scorer, thresholds, judge config, freeze manifest, and hashes are
untouched. Milestone A starts **fresh** under the L2 rulebook; it neither consumes nor re-labels B1.3 v3
artifacts. If B1.3 v3 is ever run, it is reported on its own pre-rulebook terms, separate from this line.

---

## 3. Core question

> **Can a gloss-independent essence table `E` be defined independently of dictionary meaning?**

`E` assigns each varṇa an "essence." The question is whether that assignment can be sourced and audited
**without** covertly reading the dictionary meanings of the words the varṇa appears in. If every candidate `E`
turns out to be a re-encoding of gloss, there is nothing gloss-independent to test, and the semantic-validation
program terminates (§5). Milestone A answers only this question; it does not test whether `E` *predicts*
anything (that is a later, gated step).

---

## 4. Definition of `E` (admissibility criteria)

An essence table `E` is **admissible for testing** only if it satisfies all of the following:

- **Not copied from dictionary meanings.** `E`'s entries are not derived by reading, paraphrasing, or
  embedding the glosses/definitions of words containing the varṇa.
- **Not word-target fitted.** `E` is not tuned, selected, or back-solved to fit the target words or outcomes of
  any study (including B1.3). No target leakage.
- **Not vṛtti-gloss-only.** `E` is not defined solely from vṛtti (mental-mode) glosses standing in for meaning;
  a gloss by another name is still a gloss.
- **Not decoder output.** `E` is not produced by running a decoder `D` (DBP/polarity/transformation) and
  reading its outputs back as "essence." A decoder read-out is not a foundation (probe ≠ decoder; decoder ≠
  proof).
- **Operator-derived or independently sourced (preferred).** `E` should ideally be a function of the L1
  operators / structural features, **or** sourced from an independent modality (e.g. acoustic/phonological
  measurements) that does not encode meaning.
- **Auditable provenance.** Every entry of `E` has a documented, inspectable source and derivation path, such
  that an auditor can confirm no gloss/target leakage. Provenance that cannot be audited is treated as
  insufficient (label `E_INSUFFICIENT_PROVENANCE`).

An `E` failing any criterion is **not** admissible; it is out of scope for testing, not "weak" evidence.

---

## 5. Terminal kill gate

> **If `E` cannot be defined non-circularly, return `⊥` and stop semantic validation.**

This is a hard stop, enforced before any dataset, probe, or run. If every candidate `E` reduces to
dictionary/gloss meaning, target-fitting, or decoder output — i.e. no admissible `E` survives §4 — Milestone A
emits `E_CIRCULAR_RETURN_BOTTOM` (or `E_INSUFFICIENT_PROVENANCE`) and the semantic-validation program halts.
No cleverer decoder, larger judge panel, or additional arm can rescue a circular `E`. Stopping here is the
correct, expected outcome under the current prior (§11), not a failure of the process.

---

## 6. Codomain `Y`

If (and only if) an admissible `E` survives §4–§5, Milestone A must define the codomain `Y` — the measurable
output space a probe would test `E` against. Candidate `Y` definitions and their risks:

- **Atomic semantic targets** (a small fixed set of essence categories per varṇa).
  *Risk:* the category set itself may be gloss-derived; if categories are named from dictionary senses, `Y`
  re-imports the circularity `E` was required to avoid. `Y` must be operationalized without gloss labels.
- **Polarity / layer targets** (binding vs liberating; kosha layer).
  *Risk:* the standing evidence is that polarity is **not** distinguished blind (scrambled ≈ real at 0.967;
  Track G `RANDOM_POLARITY_EXPLAINS`). A polarity `Y` inherits a very low prior and a known confound; it is
  permitted only with an explicit control for random-polarity explanation.
- **Behavioral probes** (does an `E`-derived representation predict an independent, non-gloss behavioral
  measure — e.g. a perceptual/acoustic judgment).
  *Risk:* behavioral measures can smuggle meaning if annotators know the word; probes must be blind (§7). Also
  risk of low power / noisy human measures.
- **Other measurable outputs** (e.g. structural clustering that must align with an independent, non-gloss
  partition).
  *Risk:* alignment metrics can be gamed by degrees of freedom; requires pre-registration and baselines.

If no `Y` can be operationalized without re-importing gloss or collapsing to a known-null target, emit
`Y_NOT_OPERATIONALIZABLE`.

---

## 7. Probe `P`

A valid probe `P` must:

- **Test `E` against `Y`** — quantify whether the `E`-derived representation predicts/structures `Y` above
  baseline. Producing an output is not enough; `P` must produce a *tested* quantity.
- **Be independent of the decoder `D`** — `P` may not reuse, be tuned by, or be scored by the same mechanism
  that generates semantic read-outs. If `P` cannot be separated from `D`, emit
  `P_B_NOT_SEPARABLE_FROM_DECODER`.
- **Be blind to dictionary/gloss labels** — `P` (and any human annotation feeding it) has no access to word
  meanings, definitions, or vṛtti glosses at test time.
- **Compare against baselines** — `P`'s statistic must be evaluated against the full baseline suite `B` (§8),
  beating **all** of them by a pre-registered margin, or the result is `⊥`.

`P` is a *probe*, not a *decoder*: it validates, it does not generate. This separation is the core rulebook
discipline and is non-negotiable.

---

## 8. Baseline suite `B`

Any claim from `P` must **beat all** of the following:

1. **Random / relabel** — permuted or randomly reassigned varṇa→essence labels.
2. **Bag / sequence ablation** — order-destroyed (bag-of-varṇa) and sequence-shuffled variants.
3. **Phonological similarity** — sound-similar, meaning-unrelated neighbors, to catch sound-driven artifacts
   (material given the sound-over-meaning prior).
4. **Length / frequency** — word-length and corpus-frequency matched controls.
5. **Sentiment / lexicon** — off-the-shelf sentiment/affect-lexicon predictors.
6. **Dictionary / gloss leakage** — a gloss-reading control; if it matches the "signal," the signal is gloss
   leakage, not essence.
7. **Chance / null** — the appropriate chance / null-distribution baseline for the endpoint.

Beating some but not all is a **failure**. Each un-beaten baseline is dispositive against the claim.

---

## 9. Failure state `⊥`

`⊥` ("no validated gloss-independent foundation / no validated signal") is forced by **any** of:

- **No admissible `E`.** Every candidate `E` fails §4 → `E_CIRCULAR_RETURN_BOTTOM` /
  `E_INSUFFICIENT_PROVENANCE` → `⊥` (terminal, §5).
- **`Y` not operationalizable.** No gloss-free, non-null `Y` can be defined → `Y_NOT_OPERATIONALIZABLE` → `⊥`.
- **`P`/`B` not separable from `D`.** The probe cannot be made independent of the decoder →
  `P_B_NOT_SEPARABLE_FROM_DECODER` → `⊥`.
- **Baseline not beaten.** `P` fails to beat **any** baseline in `B` by the pre-registered margin → `⊥`.
- **Gloss-leakage control matches.** The dictionary/gloss-leakage baseline reproduces the effect → the effect
  is leakage, not essence → `⊥`.

`⊥` is a correct, reportable output. It is never a prompt to re-tune `E`, thresholds, or arms until the sign
flips.

---

## 10. Candidate `E` source audit

Possible sources for `E`, each classified by circularity/leakage risk. (This is a design-time risk map, not a
selection — no source is adopted here.)

| Candidate source | Circularity / leakage risk | Notes |
|---|---|---|
| **Authoritative varṇa lexicon** (`varna_lens/lexicon_authoritative_varna.json`) | **High** | Entries are meaning-bearing glosses; using them as essence is gloss-copying. Likely `E_CIRCULAR`. Not editable regardless. |
| **Vṛtti glosses** | **High** | Gloss by another name; §4 excludes vṛtti-gloss-only `E`. |
| **Four-sphere table** | **Medium–High** | Sphere assignments may themselves be meaning-derived; provenance must be audited for gloss/target fitting. |
| **Polarity table** | **High (known-null)** | Binding/liberating carries the random-polarity confound (Track G); low prior, needs explicit control. |
| **Operator-derived structural features** (L1 `M_σ`) | **Low–Medium (preferred)** | Structural, not semantic; risk is that it may carry *no* semantic content at all (could pass §4 but fail to predict any `Y`). Best provenance. |
| **Independent phonological / acoustic features** | **Low (preferred)** | Non-gloss modality; risk is measuring sound, which the prior says dominates — must be tested *against* the phonological baseline, not conflated with it. |
| **Human-blind annotations** | **Medium** | Admissible only if annotators are blind to word identity/meaning; otherwise gloss leaks in. Power/noise risk. |

Preferred admissible directions are **operator-derived** and **independent phonological/acoustic** sources;
gloss/vṛtti/polarity sources are high-risk and most likely trigger the terminal gate.

---

## 11. Expected prior

The prior on Milestone A yielding an admissible, signal-bearing foundation is **negative**, and is **not**
reset by starting this milestone. Reasons on record:

- **O1.5 construct-validity gate failed.**
- **Corpus norms near-null** (S1/S2).
- **Synonym randomization** — near-synonyms share varṇa content at near chance (arbitrariness of the sign).
- **Sound-over-meaning sensitivity** — where sensitivity exists, it tracks sound, not meaning.
- **B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`** — real assignment did not beat random/scrambled; scrambled ≈ real at
  0.967.
- **B1.3 compatibility mismatch** — B1.3 v3 is gloss-dependent, decoder-not-probe, missing the phonological
  baseline (per the compatibility memo).

These make the terminal kill gate (§5) the *expected* outcome, and a `⊥` result fully consistent with the
evidence to date. Milestone A must not be framed as likely to overturn them.

---

## 12. Deliverables

Milestone A produces **only** documents (no data, no code, no run):

1. **`E` admissibility decision** — whether any candidate `E` passes §4, with audited provenance.
2. **`Y` candidate definition** — the operationalized codomain, if `E` survives (else `Y_NOT_OPERATIONALIZABLE`).
3. **`P`/`B` validation design** — the probe and baseline-suite design, decoder-independent and gloss-blind.
4. **Terminate-or-proceed recommendation** — `⊥`/stop, or proceed to a gated B1.4 gloss-independent design.

Nothing in Milestone A freezes evidence, runs a model, scores, or creates a dataset.

---

## 13. Allowed labels

Milestone A may emit exactly these outcome labels:

- **`E_ADMISSIBLE_FOR_B_TEST`** — an admissible, audited `E` exists; may proceed to `P`/`B` design.
- **`E_CIRCULAR_RETURN_BOTTOM`** — `E` reduces to gloss/meaning/target/decoder; terminal `⊥`.
- **`E_INSUFFICIENT_PROVENANCE`** — `E` cannot be audited free of leakage; not admissible.
- **`Y_NOT_OPERATIONALIZABLE`** — no gloss-free, non-null codomain can be defined.
- **`P_B_NOT_SEPARABLE_FROM_DECODER`** — probe cannot be made independent of the decoder.
- **`MILESTONE_A_INCONCLUSIVE`** — the foundation question cannot be resolved at design time.

No other label may be used. **No ONTOLOGICAL_SIGNAL. No Sanskrit privilege.** No positive/validation label
exists at this milestone.

---

## 14. Boundary statement

> Milestone A tests whether a non-circular gloss-independent foundation exists. It does not validate meaning,
> does not alter B1.3 v3, and does not unblock Track B. Structure, not validated meaning.

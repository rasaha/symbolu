# Milestone A — Candidate-E Source Admissibility Audit

**Status:** Source admissibility audit only (docs-only). Not a validation run, not a dataset, not code.
**Governed by:** `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`, `MILESTONE_A_L2_FOUNDATION_SPEC.md`.
**No meaning validated. No dataset built. Nothing run or scored. Track B remains blocked.**
**Structure, not validated meaning.**

Related documents:
- `SYMBOL_U_L2_VALIDATION_RULEBOOK.md` (governing framework)
- `MILESTONE_A_L2_FOUNDATION_SPEC.md` (§4 admissibility criteria, §10 source-risk map, §13 labels)
- `B1_3_V3_L2_RULEBOOK_COMPATIBILITY_MEMO.md` (B1.3 v3 parked as pre-rulebook exploratory)

---

## 1. Purpose

This is a **source admissibility audit** for the gloss-independent essence table `E`. It asks a single
question of each candidate source: *could this source define `E` without covertly reading dictionary/gloss
meaning?* It does **not** test whether any `E` predicts anything — that is Milestone B, and it is reachable
only if an admissible source survives here. No source is adopted, frozen, or run by this document.

---

## 2. Admissibility standard

A candidate source is **admissible** for defining `E` only if **all** hold:

- **Gloss-independent** — the source's entries are not the meanings of the words a varṇa appears in.
- **Not dictionary-derived** — no definition/gloss/translation feeds the essence values.
- **Not word-target fitted** — not tuned, selected, or back-solved against study targets or outcomes
  (including B1.1 / B1.3).
- **Not decoder output** — not produced by running a decoder `D` (DBP / polarity / transformation) and reading
  its outputs back as "essence."
- **Auditable provenance** — every entry has a documented, inspectable derivation an auditor can confirm is
  leakage-free.
- **Definable before observing validation targets** — the source can be fully specified *prior* to seeing `Y`
  or any outcome (no peeking).
- **Baseline-testable** — the resulting `E` yields something a probe can score against the full baseline suite
  `B`.

Failing any one criterion makes the source **inadmissible** — not "weak," out of scope.

---

## 3. Candidate sources

Audited candidates (with the on-disk artifact where one exists):

1. **Authoritative varṇa lexicon** — `varna_lens/lexicon_authoritative_varna.json`
2. **Vṛtti gloss table** — classical acoustic-root/vṛtti meanings (embedded in the lexicons)
3. **Four-sphere table** — `track_e_varna_sphere_lexicon.json` (`TRACK_E_FOUR_SPHERE_REPRESENTATION.md`)
4. **Track G polarity table** — `track_g_polarity_axes.json`, `track_g_polarity_assignments.jsonl`
5. **B1.3 bridge pools** — `b1_3_revised_layer3/b1_3_authoritative_varna_bridge_pool.json`,
   `b1_1_bridge_pool_draft.json`
6. **Operator-derived structural features from L1** — the `M_σ` operators / structural trace (Stage A;
   `symbolu_neural/structural_v1` — read-only, not modified)
7. **Phonological / acoustic features** — articulatory/acoustic descriptors (place, manner, voicing, sonority,
   duration), an independent modality
8. **Human-blind annotations** — ratings by annotators blind to word identity and meaning
9. **External linguistic feature inventories** — e.g. PHOIBLE-style phonological inventories / distinctive
   feature sets (if applicable)

---

## 4. Per-source assessment

Legend — Circularity / Leakage / DoF (researcher degrees of freedom): **Low / Med / High**.

| # | Source | Provenance | Gloss/meaning dependence | Researcher DoF | Circularity risk | Baseline-leakage risk | Definable pre-validation? | Admissibility |
|---|---|---|---|---|---|---|---|---|
| 1 | **Authoritative varṇa lexicon** | Meaning-bearing glosses (`liberating_state`/`binding_state` are semantic descriptions; `_source` is a letters doc) | **Direct** — entries *are* meanings | Med | **High** | **High** (is itself the gloss) | Yes | **INADMISSIBLE** — gloss-copying |
| 2 | **Vṛtti gloss table** | Classical acoustic-root/vṛtti meanings | **Direct** — a gloss by another name | Med | **High** | **High** | Yes | **INADMISSIBLE** — §4 excludes vṛtti-gloss-only `E` |
| 3 | **Four-sphere table** | Self-declared `researcher_interpretive_extraction`, `unvalidated_candidate_representation`; `source_supplies_four_spheres:false`; spheres expanded by researcher from single acoustic-root meanings | **Indirect but real** — spheres derived from the gloss | **High** (interpretive expansion) | **High** | **High** | Partly | **INADMISSIBLE** — gloss-derived + high DoF |
| 4 | **Track G polarity table** | Abstract polarity axes (expansion/contraction, clarity/obscuration…) + per-word assignments | Axes low; **assignments** carry meaning | Med–High | **High (known-null)** | High | Axes yes; assignments no | **INADMISSIBLE** — Track G result is `RANDOM_POLARITY_EXPLAINS`; polarity not distinguished blind |
| 5 | **B1.3 bridge pools** | Built from the authoritative lexicon for B1.3 stimulus construction | **Direct (inherited)** — derived from #1, and target-adjacent | High | **High** | **High** | No — target-fitted for B1.3 | **INADMISSIBLE** — decoder/target-adjacent, gloss-inherited |
| 6 | **Operator-derived structural features (L1)** | Stage A operators `M_σ` / structural trace; structural, not semantic | **None** (structural) | Low–Med | **Low** | Low–Med (may overlap phonology) | Yes | **Admissible on provenance** — but see §5 caveat (may carry no semantic content) |
| 7 | **Phonological / acoustic features** | Independent articulatory/acoustic descriptors | **None** (sound, not meaning) | Low | **Low** | **Med–High vs the phonological baseline** — must be *tested against* it, not conflated | Yes | **Admissible on provenance** — but is a *sound* foundation, and the prior says sound dominates (§5) |
| 8 | **Human-blind annotations** | Ratings with annotators blind to word identity/meaning | None *iff* blinding holds | Med | **Low–Med** | Med (blinding failure re-imports gloss) | Yes | **Conditionally admissible** — only if blinding is auditable; else `E_INSUFFICIENT_PROVENANCE` |
| 9 | **External linguistic feature inventories** | Published distinctive-feature/phonological inventories | None (phonological) | Low | **Low** | Med–High vs phonological baseline | Yes | **Admissible on provenance** — same sound-not-meaning caveat as #7 |

---

## 5. Preferred low-circularity candidates

The lowest-circularity sources are **operator-derived structural features (#6)**, **independent
phonological/acoustic features (#7, #9)**, and **human-blind annotations (#8)**. These can, in principle, be
specified before validation and audited free of gloss leakage.

**Crucial caveat (not a rescue).** Each of these tests something *other than* semantic essence:

- **#6 structural features** test **structure**, which Stage A already establishes at the structural level and
  which carries no demonstrated semantic content. A structural `E` may pass admissibility yet predict no
  semantic `Y` — passing §4 does not imply signal.
- **#7 / #9 phonological features** test **sound**. The standing prior is that sensitivity tracks
  **sound over meaning**; a phonological `E` risks "validating" a sound artifact that the phonological-
  similarity baseline is specifically designed to strip out. Such an `E` must be tested *against* the
  phonological baseline (§B item 3), and any effect it shares with that baseline is **not** semantic essence.
- **#8 human-blind annotations** are admissible only while blinding is provably intact; the moment annotators
  can infer the word or its meaning, the source collapses into gloss (→ `E_INSUFFICIENT_PROVENANCE`).

So the admissible-on-provenance sources are exactly the ones **least likely to encode semantic essence** — a
genuine tension, not a loophole. Admissibility of a source is necessary, not sufficient; predictive signal
against `Y` beating all of `B` is still required, and the prior on that is negative (§11 of the foundation
spec).

---

## 6. Rejected / high-risk candidates

The gloss-derived tables are **inadmissible** for defining `E`:

- **Authoritative lexicon (#1)** — its entries *are* the meanings; using them as essence is direct
  gloss-copying. (Also: not editable, and not to be edited.)
- **Vṛtti table (#2)** — a gloss by another name; §4 explicitly excludes vṛtti-gloss-only `E`.
- **Four-sphere table (#3)** — self-declared researcher-interpretive expansion of the single acoustic-root
  gloss (`source_supplies_four_spheres:false`, `validation_status:unvalidated_candidate_representation`); high
  researcher DoF on top of a gloss base.
- **Polarity table (#4)** — binding/liberating assignments carry the **random-polarity confound**; Track G's
  own result is `RANDOM_POLARITY_EXPLAINS` and scrambled ≈ real at 0.967. A polarity `E` starts from a known
  null and cannot be admitted without begging the question.
- **Bridge pools (#5)** — constructed *from* the authoritative lexicon and *for* B1.x stimulus targets; they
  inherit #1's gloss dependence and add target-adjacency. Using them would reintroduce exactly the
  gloss/decoder circularity the rulebook forbids.

None of these can serve as a gloss-independent foundation. Adopting any would guarantee circularity.

---

## 7. Terminal decision

**`MILESTONE_A_INCONCLUSIVE`.**

Rationale, held honestly in both directions:

- **Not `E_ADMISSIBLE_FOR_B_TEST`:** no source is *both* admissible *and* demonstrated to carry semantic
  essence. The only provenance-admissible sources (#6, #7/#9, #8) plausibly encode **structure or phonology,
  not meaning**, and #8 depends on blinding not yet built or audited.
- **Not `E_CIRCULAR_RETURN_BOTTOM` outright:** it would be overreach to declare the terminal `⊥` while
  provenance-clean, structure/phonology-based candidates remain formally on the table — even though their
  prior for *semantic* signal is negative. Calling them dead now would itself be an unfounded (if negative)
  claim.
- **Not `E_INSUFFICIENT_PROVENANCE` as the headline:** that label fits specific sources (#8 pending blinding
  audit), not the audit as a whole.

The audit therefore resolves to **`MILESTONE_A_INCONCLUSIVE`**: the gloss-derived sources are rejected; the
provenance-clean sources survive admissibility but are unproven for semantics and carry a negative prior. A
narrower follow-up (a pre-registered attempt to define an operator-derived or blind-annotation `E` and audit
its blinding) is required before any `E_ADMISSIBLE_FOR_B_TEST` could be earned — and `E_CIRCULAR_RETURN_BOTTOM`
remains the likely eventual outcome given the standing negatives.

---

## 8. If E is admissible

Should a future follow-up upgrade a source to `E_ADMISSIBLE_FOR_B_TEST`, the **minimal** requirements before
any Milestone B validation run are:

1. **Freeze `E`** — pin the table and its provenance audit under hash; no post-freeze edits.
2. **Define `Y`** — an operationalized, gloss-free, non-null codomain (foundation spec §6).
3. **Define `P`** — a probe independent of any decoder `D`, blind to gloss labels (foundation spec §7).
4. **Define `B`** — the full baseline suite, incl. phonological-similarity and gloss-leakage controls
   (foundation spec §8).
5. **Pre-register metrics and kill thresholds** — the exact statistic, the margin `P` must beat *every*
   baseline by, and the `⊥`-forcing conditions — all fixed before any data is seen.

Only after all five would a Milestone B run be authorized (separately, by explicit operator declaration). This
document authorizes none of it.

---

## 9. If E is not admissible

If the follow-up finds no admissible, non-circular `E` — i.e. every candidate reduces to gloss, target-fit, or
decoder output, or the only clean sources demonstrably encode sound/structure with no semantic signal —
semantic validation **returns `⊥`** and the program **does not proceed to Milestone B**. That is the correct,
expected outcome under the standing negative prior. `⊥` is not a prompt to re-tune `E`, thresholds, or sources
until a sign flips; the no-rescue rule holds. No prior null/negative may be relabeled as positive on the
strength of this audit.

---

## 10. Boundary statement

> Milestone A candidate-E audit completed as source admissibility only. No meaning validated. No dataset built.
> Nothing run or scored. Track B remains blocked. Structure, not validated meaning.

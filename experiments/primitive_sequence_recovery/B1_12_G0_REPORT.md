# B1.12 — Gate G0 (Ordered-Composition Distinctness) — Implementation Report

**Verdict: `BLOCKED_G0_SPEC_UNDERSPECIFIED`.** The audit was **not run**. No candidate pool was parsed, no
opaque-ID map was built, no distinctness metric was computed, no subset was selected. Stopping before the audit
is mandated by the controlling task's Step 1 ("if a materially outcome-sensitive decision remains unresolved,
mark `BLOCKED_G0_SPEC_UNDERSPECIFIED` and stop before running the audit") and by the preregistration's own §7.4
("thresholds … not tuned to guarantee a passing subset … frozen before the audit runs").

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Structure, not validated meaning. No
`GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth / Sanskrit-privilege / individual-varṇa
claim. B1.4b′ remains `NULL_RETURN_BOTTOM`; B1.10 remains `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11
unchanged. Nothing under B1.10/B1.11 or any prior evidence is modified; Gate G1, contexts, judges, and runs
remain untouched.

---

## 1. Controlling preregistration and pins

- **Prereg:** `B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md` (§7 Gate G0).
- **Commit / HEAD:** `2c613f4b35f1e1734f786d0bf1a61f54096f0f70` (the commit that froze B1.12).
- **Parser (would-be provenance):** `sanskrit_stage1_parser.py`, `PARSER_SPEC_v1`, schema 1.1,
  sha256 `d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947`.
- **Merged lexicon:** `frozen/varna_native_stage1_merged_v1.json`,
  sha256 `af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96`.

## 2. Step-1 contract extraction — what §7 froze vs. what it left open

### 2.1 Fully specified and executable (no invention needed)

| contract item | source | value |
|---|---|---|
| structural metrics | §7.2 | normalized Levenshtein; LCS ratio; positional overlap; multiset Jaccard; repetition-profile similarity; sequence-length difference; first-/last-unit overlap; unique bigram/trigram counts; inventory-controlled order distinctness |
| optimization objective | §7.3 | **maximize the minimum pairwise normalized edit distance** |
| tie-break order | §7.3 | (a) max mean pairwise edit distance → (b) max mean unique-trigram count → (c) min mean multiset-Jaccard → (d) alphabetical |
| freeze order | §7.5 | word set fixed **before** any context/rendering/rating; frozen with metric matrices |
| status vocabulary | §7.5 / task | `G0_PASS`, `G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET`, `BLOCKED_G0_SPEC_UNDERSPECIFIED`, `G0_INVALID` |
| parser provenance | §5.1, §16 | native Stage-1 parser (ordered `atomic_varnas`, `aksharas`, `multiplicity`), hash-pinned |
| required artifacts | task Step 7 | pool/manifest/opaque-map/parser-outputs/pairwise/search/selection/run-manifest/report |

The **objective and tie-breaks are threshold-free** — they merely *rank* subsets and can be computed exactly.
They are not the blocker.

### 2.2 Conservatively derivable outcome-blind (Tier-1 constants)

- **k = 6.** §7.3 gives k = 6 as the anchored example (forced-choice chance = 1/6, run01/B1.10-comparable). This
  is a **chance-baseline** choice, fixed independent of any candidate's varṇa sequence, so it is derivable
  without seeing outcomes.
- **length-band lower bound = 2.** Order is undefined for a length-1 sequence (A ≡ B ≡ D), so a floor of ≥ 2 is
  a structural necessity, not a tuning choice.

### 2.3 Materially outcome-sensitive AND not frozen (Tier-2 → the block)

§7.4 enumerates the following as thresholds that must be *"frozen before the audit runs"* — but assigns **no
numeric value** to any of them:

1. **minimum pairwise normalized-edit-distance floor** — the pass/fail distinguishability cutoff;
2. **inventory-controlled order-distinctness floor margin** — "separable from its own order-scramble … by a
   preregistered margin" (margin unspecified);
3. **maximum tolerated first/last-unit overlap**;
4. **maximum tolerated n-gram overlap**;
5. **length-band upper bound** (the lower bound is derivable; the cap is not).

**Why this is material, not cosmetic.** Each of #1–#5 is monotone in the number of eligible size-6 subsets:
raising a floor (or lowering an overlap cap) can only shrink the eligible set, and at some value the eligible
count crosses from > 0 to 0 — i.e. from `G0_PASS` to `G0_NOT_TESTABLE`. The verdict is therefore a **direct
function of these unspecified numbers.** Choosing them in the same act as the run — after the pool exists and
metrics could be inspected — is exactly the "tuned to guarantee a passing subset" move the prereg §7.4 forbids
and the Development note warns against ("tune on observed outcomes and then treat the same observations as
held-out evidence"). No value can be picked here without either (a) being arbitrary or (b) being
outcome-contaminated. Hence the honest verdict is `BLOCKED_G0_SPEC_UNDERSPECIFIED`, not a run.

**Not invoked here (would be a fit-serving shortcut):** collapsing all thresholds to the weakest
non-degeneracy floor (edit distance > 0, no overlap caps). That is the most permissive possible gate — it maximizes
the chance of `G0_PASS` — so adopting it silently would itself be an outcome-favorable choice. It is a candidate
*proposal* for the separate freezing act (§4), not a decision taken in this report.

## 3. Secondary prerequisite gap (independent of §2.3)

The **≥ ~30-word attested candidate pool** (§7.1 / §8) does **not yet exist** in the repository. The only
attested-Sanskrit source present is the 12-word Monier-Williams set used by the native word-specificity study
(`native_word_specificity_packets*/candidate_gloss_table.json`: aśva, bala, bhaya, duḥkha, gaja, megha, bīja,
sukha, deha, lavaṇa, yoga, vṛkṣa). Assembling and freezing a ≥30-word pool (with per-word citation, category,
morphology notes, inclusion reason, stable ID) is authorized by §8 but must be a **frozen artifact created
before any metric is computed** — and it, too, must be assembled for compositional breadth, never for favorable
sequences. This is a prerequisite the run needs regardless of §2.3.

## 4. Environment readiness (for when the block is cleared)

- **Parser:** runs in this container (`sanskrit_stage1_parser.py` imports only `json` + `unicodedata`; a
  trivial non-candidate probe returns ordered `atomic_varnas`). Step 3 is environmentally feasible — the
  model-availability block that stops B1.10/B1.12 *judged runs* does **not** apply to the purely structural G0
  audit.
- **Judges / models:** irrelevant to G0 (structural, offline). Not a factor here.

## 5. Unblock path (a separate, outcome-blind freezing act — not performed here)

To reach `READY_TO_RUN_G0`, freeze the Tier-2 constants **from stated principle, before assembling or parsing
the pool**, as a B1.12 preregistration revision (a new frozen version — never an in-place edit of the frozen
prereg, and never in the same commit as the run). A principled, outcome-blind instantiation to be *considered*
for that freeze (derived with **zero** candidate metrics inspected):

- **k = 6**; **length band [2, L_max]** with L_max fixed from the parser's structural range, declared before
  parsing;
- **minimum pairwise normalized edit distance ≥ δ_min** with δ_min justified from the k = 6 forced-choice
  confusability requirement (a stated margin above the identical-sequence floor), not from the observed pool;
- **inventory-controlled order-distinctness floor:** each selected word's ordered sequence must differ from its
  canonical-sorted-inventory form (order is informative for the word: A ≠ D) **and** be separable from every
  other selected word by ≥ δ_min — with the "own order-scramble" margin stated as a fixed fraction of sequence
  length;
- **first/last-unit and n-gram overlap caps** stated as fixed fractions, justified from the leakage controls
  (§6.4/§6.5), not chosen to admit a particular subset.

Once such a revision is frozen, a follow-up task can run the fully-specified deterministic audit and issue a
genuine `G0_PASS` / `G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET` verdict.

## 6. What was deliberately NOT done

No candidate pool assembled or frozen; no parser run on candidate words; no opaque-ID bijection built; no
pairwise metrics computed; no subset search; no word selected; no `G0_PASS`/`G0_NOT_TESTABLE` issued; no code,
tests, contexts, judges, generators, smoke/confirmatory runs, or prose glosses created; the Varṇa–Affliction
Resolution Test was not imported; B1.10 and B1.11 are byte-unchanged; Gate G1 remains unresolved and untouched.

## 7. Guardrails

Docs-only blocking report. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no
`ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth / Sanskrit-privilege / generation-utility claim; no
individual-varṇa attribution. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**

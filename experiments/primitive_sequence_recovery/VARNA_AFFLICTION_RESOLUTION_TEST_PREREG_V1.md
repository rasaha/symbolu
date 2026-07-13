# Varṇa–Affliction Resolution Test — Preregistration v1 (docs/data-only)

**Status: `READY_FOR_WORDLIST_PRECOMMITMENT`.** Rules-only freeze. **No word list selected, no packets computed, no
experiment run.** Docs-only. Does not modify the parser, lexicon, mappings, prior packets, prior results, or any prior
evidence/prereg; all prior negative and null findings are preserved. This artifact hardens the test so it can return
**strong contrary evidence, partial fit, indeterminacy, or a test-level null** — failures are never softened and no
rescue mechanism is permitted.

## 1. Core hypothesis

A real Sanskrit word's **pronunciation-derived consonantal varṇas** jointly specify a fixed set of binding
propensities/afflictions through the frozen lexicon. The claim under test: the **prototypical, unqualified referent**
of the word **resolves, transcends, stands free from, or does not conspicuously embody** those specific mapped
afflictions. Mappings combine through **simultaneous AND-composition**; there is **no temporal, causal,
transformational, or left-to-right progression** among the varṇas.

## 2. Frozen inputs (verified from the repository, not assumed)

| item | value |
|---|---|
| parser | `sanskrit_stage1_parser.py` · sha256 `d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947` · `PARSER_SPEC_v1` |
| lexicon | `frozen/varna_native_stage1_merged_v1.json` · sha256 `af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96` · schema `native_merged_v1` |
| confirmatory consonants | **33** (`b bh c ch d dh g gh h j jh k kh l m n p ph r s t th v y ñ ś ḍ ḍh ṅ ṇ ṣ ṭ ṭh`) |
| confirmatory-consonant content hash | `c188030001351310fe9b44528bb91a58a23712476506ae910bcebb1228455361` (sorted (unit, binding, liberating)) |
| vowels `a ā i ī u ū e ai o au` | **all `DEVELOPMENT_ONLY`** (authored, never empirically validated) |
| anusvāra `ṃ`, visarga `ḥ` | `DEVELOPMENT_ONLY` |
| `ṛ ṝ l̥ l̥̄`, candrabindu `m̐` | **`MISSING`** (no gloss) |
| current `a` gloss | **"restless starting without sustaining"** — *not* "initiation" |
| prior Varṇa–Affliction artifact | none (this is the first) |

**Documented discrepancies from the drafting prompt (repository facts preserved):**
- The prompt assumed post-consonantal `a` = "initiation." The repository `a` gloss is **"restless starting without
  sustaining."** There is **no positional-inversion rule (`ak = dissolution`) in the lexicon** — it is a newly
  authored hypothesis (see §5 secondary arm).
- The prompt's worked example "confusion" is **English** (violates R1) and mismapped `ś`=`"mutative nature"` (the
  frozen `ś` = `kāma`, worldly desire) and `envy`=`"an"` (envy is `ṇ`). **No worked example is included** (R1).
- Per the prompt's own correction: pronunciation-derived `moha` = consonants `m, h` (**no `n`**). No word is
  prejudged and no packet is computed here.

## 3. Parser & pronunciation rule

Varṇas are extracted **only** from the word's pronunciation via the frozen parser (`atomic_varnas`, `type ==
"consonant"`). Disallowed: orthographic decomposition, spelling reconstruction, silent-letter logic, transliteration
guesswork, manual phoneme substitution, or choosing a convenient varṇa after seeing the referent.

## 4. Primary confirmatory arm — consonant backbone

**R3 (frozen mappings only).** Each consonant contributes its **binding gloss verbatim** from the hash-pinned
lexicon. No re-glossing, synonym substitution, softening, pole-switching, per-word weighting, omission, or
reclassification.

**R4 (repeated consonants — occurrence-level, frozen convention).** Every pronounced consonant occurrence is scored
**independently** (repeats = repeated acoustic evidence). The report **must also** include a deduplicated-gloss
diagnostic, but the **primary preregistered score is occurrence-level** and may not switch to deduplicated after
results are seen.

**R5 (AND-composition).** `A(w) = a₁ ∧ a₂ ∧ … ∧ aₙ` — every mapped component is independently relevant and **must be
scored**. This does not require the referent to display all afflictions simultaneously.

**R6 (no progression).** No claim that one varṇa transforms/balances/removes another, or that order is causal. Order
only determines which units occur.

The primary word score and verdict use **only** the frozen consonant mappings. Vowels may not rescue, reverse, raise,
lower, or alter the primary result.

## 5. Secondary provisional arm — positional vowels (`PROVISIONAL / DEVELOPMENT_ONLY`)

Reported **separately**; **never merged** into the primary consonant score.

Frozen positional rule (fixed before any word is evaluated, applied to every eligible word, not selectively):
- vowel **after** a consonant → its forward (lexicon) mapping;
- the same vowel **before** a consonant / word-initial → the **opposite directional** mapping;
- post-consonantal `a` → provisionally *initiation / forward activation*; pre-consonantal/word-initial `a` →
  provisionally *destruction / dissolution*.

**Disclosed explicitly:** the repository `a` gloss is "restless starting without sustaining," and **the positional
inversion is NOT in the frozen lexicon** — it is the user-proposed hypothesis. All vowels are `DEVELOPMENT_ONLY`;
`ṛ ṝ l̥ l̥̄` and candrabindu are `MISSING`. If a required vowel mapping is `MISSING`, the vowel-arm result for that
word is **INDETERMINATE**; a missing gloss is **never invented**. This arm is exploratory and cannot change any
primary PASS/PARTIAL_FIT/FAIL/INDETERMINATE.

## 6. Referent & interpretation procedure

**Stage A — blind factual referent profile.** A separate assessor sees **only the Sanskrit word + its ordinary
accepted meaning** — **not** the varṇas, packet, or any expected result. It records the prototypical unqualified
referent, ordinary/observable traits, typical behaviour/function, independently-recognized philosophical
associations only, and competing prototypes/uncertainties. **This profile is locked before the packet is revealed.**

**Stage B — nonblind bidirectional interpretation.** After the packet is revealed, construct **both** the strongest
factually-defensible **resolution** argument and the strongest **embodiment** argument for **each** mapped affliction.
Motivation must be **symmetrical**. Neither side may alter the prototype, alter a frozen gloss, introduce progression,
invoke the liberating pole, select an exceptional subtype, rely on unsupported symbolism, rewrite the blind profile,
ignore a component, or infer the aggregate first and backfill components.

**Stage C — component scoring, then aggregation** (§7). Score each exact frozen gloss **before** the mean or verdict.

*Residual limitation (disclosed):* the Stage-C adjudication is **nonblind** (the same assessor sees packet +
referent). This is mitigated by the locked blind Stage-A profile, the mandatory bidirectional arguments, coverage
gating, and the 0%/25% forcing rules — but the verdict is a reasoned judgment, not a blind measurement.

## 7. Absolute percentage-fit scoring

**R7 (component scale — fixed ordinal, absolute).** Each consonant occurrence `aᵢ` gets one `rᵢ ∈ {0, 25, 50, 75, 100}`:
- **100 Clear resolution** — prototype strongly contrary to / clearly free from / resolves the affliction.
- **75 Substantial resolution** — mostly resolves; a limited contrary reading remains.
- **50 Mixed / balanced / genuinely ambiguous.**
- **25 Substantial embodiment** — materially embodies; a limited resolution reading remains.
- **0 Clear embodiment** — conspicuously, centrally embodies the exact mapped affliction.
No intermediate values (no 63%, 87%). If a component cannot be reliably placed → **`INDETERMINATE`** (not forced).

**R8 (absolute, not comparative).** The score answers *"to what degree does this word's prototypical referent resolve
its **own** frozen affliction packet?"* — not vs another word, a control, the sample average, or a ranking.

**R9 (mean).** `MeanResolutionFit(w) = (1/n) Σ rᵢ` over `n` determinate occurrences, reported as a percentage.

**R10 (minimum).** `MinimumComponentFit(w) = minᵢ rᵢ` — prevents one embodied affliction hiding inside a high mean.

**R11 (embodiment counts, mandatory).** `N_embodied = #{i : rᵢ ≤ 25}`; `N_clear_embodied = #{i : rᵢ = 0}`.

**R12 (coverage).** `Coverage(w) = (# determinate components) / (# extracted consonant occurrences)`. **Default
minimum 80%.** `INDETERMINATE` components are **not** counted as 50%. Below-minimum coverage → no definitive verdict.

## 8. Derived categorical verdicts (percentage is primary; category is a summary)

- **PASS** — *all* of: mean ≥ 75; minimum ≥ 50; **no** component = 0 or 25; coverage ≥ 80.
- **PARTIAL_FIT** — mean in [50, 75); **or** mean ≥ 75 with at least one component = 25; **or** a genuine mixture with
  no dominant clear failure. **Not counted as PASS** for the universal hypothesis.
- **FAIL** — mean < 50; **or** any component = 0 (clear conspicuous embodiment of a frozen affliction). A single 25%
  does not by itself force FAIL but **prevents PASS** (→ at most PARTIAL_FIT, unless mean < 50).
- **INDETERMINATE** — coverage < 80; disputed prototype; uncertain parse; gloss too abstract; unadjudicable
  arguments; mainly speculative symbolism; or (vowel arm) a `MISSING` mapping. **Not** PASS or PARTIAL_FIT.

## 9. Score-integrity safeguards

**R13** components scored before mean/verdict/comparison; no backfilling to a desired aggregate. **R14** every
component reports: exact occurrence · exact frozen gloss · evidence from the locked blind profile · strongest
resolution argument · strongest embodiment argument · final score · adjudication rationale — no percentage without
this trace. **R15** equal weight per occurrence (no first/last/root/stress/"central"/convenient weighting; any
weighting is a separate future prereg). **R16** scale + thresholds frozen before any packet; after results, do **not**
lower PASS, drop the minimum safeguard, treat 25% as acceptable, count PARTIAL_FIT as PASS, convert INDETERMINATE to
50%, switch to deduplicated scoring, or use the vowel arm to rescue.

## 10. Sample precommitment

Word list fixed **before** any packet is computed. Must deliberately include real Sanskrit words for: calm/stable
concrete referents · fierce animals · destructive forces · changing/unstable phenomena · explicitly afflictive
concepts · abstract negative states. No word added/removed/replaced after packet inspection. **No word is prejudged
as a likely pass/fail from a remembered mapping; packets come only from the frozen parser + lexicon.** *(This artifact
selects no words.)*

## 11. Test-level metrics (for a future run)

n words · #PASS · #PARTIAL_FIT · #FAIL · #INDETERMINATE · mean & median word-level fit · distribution of minimum
component fits · total 0% components · total 25% components · coverage · calm/fierce/afflictive category breakdown ·
primary consonant result · separate provisional vowel-arm result. **PARTIAL_FIT is never collapsed into PASS.**

## 12. Theory-level interpretation

- **Supportive** only if: the adversarial sample shows consistently high absolute means, rare failures, no systematic
  afflictive-category failure, high minimum components, **not** produced through broad 50%/INDETERMINATE/speculative
  reconciliation.
- **Falsification/contradiction:** repeated clear FAILs — especially 0% components where a prototype conspicuously
  embodies its own exact frozen affliction — contradict the universal form.
- **Restricted pattern:** e.g. calm concrete referents high, afflictive concepts low → may support a *narrower*
  descriptive claim while falsifying the universal one. The universal hypothesis may **not** be redefined post hoc.
- **Null:** near-universal PASS via flexible reconciliation; artificial clustering at 75–100% without factual
  grounding; rarely assigning 0/25 even to obvious embodiment; inability to distinguish adversarial categories; a
  process effectively incapable of saying no.
- **Not operationally testable:** dominant INDETERMINATE coverage.

## 13. Prohibited rescue operations

A FAIL/PARTIAL word may **not** be repaired by: changing pronunciation or parser output; changing a frozen gloss;
switching to the liberating pole; introducing progression; invoking vowel polarity in the primary arm; replacing the
prototype; selecting an exceptional subtype; dropping a repeated occurrence; deduplicating only unfavorable repeats;
unequal weights; relabeling PARTIAL_FIT as PASS; excluding a word after seeing its score; or modifying thresholds
after the run. Every result stays visible.

## 14. Principal differences from the prior (v1.0 chat) ruleset

1. **Absolute percentage** primary measurement `{0,25,50,75,100}` with mean + minimum + embodiment-count + coverage,
   replacing a bare PASS/FAIL.
2. **Two hardened tiers:** primary = **consonant backbone only** (hash-pinned, 33 mappings); secondary =
   **positional-vowel arm** labeled `PROVISIONAL / DEVELOPMENT_ONLY`, reported separately, never merged.
3. **Repository-verified inputs** with explicit discrepancy log (the `a` gloss; the non-frozen positional inversion;
   the English/mismapped "confusion" example removed; MISSING vowels → INDETERMINATE).
4. **Blind Stage-A referent profile** locked before the packet (mitigates the nonblind adjudication).
5. **Coverage gate (≥80%)** and **INDETERMINATE ≠ 50%**; PARTIAL_FIT never counts as PASS.

## 15. Readiness

**`READY_FOR_WORDLIST_PRECOMMITMENT`** — verified: parser reference ✓ · consonant lexicon reference ✓ · frozen hashes
✓ · scoring rubric ✓ · vowel statuses ✓ · missing-vowel handling ✓ (INDETERMINATE) · occurrence-level repetition
convention ✓ · exact thresholds ✓.

**Next step (separate, later):** pre-commit ~8–10 real Sanskrit words in the deliberate adversarial mix of §10 —
*before* any packet is computed — then run Stages A→C and report per §11–§12. No words are selected and no packet is
computed in this artifact.

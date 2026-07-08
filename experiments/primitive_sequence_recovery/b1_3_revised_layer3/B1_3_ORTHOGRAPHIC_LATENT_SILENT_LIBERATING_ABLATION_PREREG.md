# B1.3 — Orthographic-Latent (Initial-Silent → Liberating) Ablation: Pre-Registration

## 1. Scope and status

Pre-registration only. **Not run · not evidence · no EVIDENCE_FREEZE · no positive label · no lexicon change ·
the active B1.3 concrete-object v2 evidence path is UNCHANGED** (spoken-only, freeze-ready). Operator chose the
pre-registered ablation over modifying B1.3, so v2 stays intact and the silent-liberating routing is *tested*,
not assumed. **Structure, not validated meaning.**

## 2. Rule under test

A **word-initial silent consonant** (`kn-`, `gn-`, `wr-`, `ps-`/`pn-`, `mn-`, silent `h-`) routes to its
varṇa's **liberating** pole (operator's focal rule), e.g. silent `K` → `ka`-liberating (*non-attachment*).

## 3. Honest scope caveat (stated up front)

The word-initial-silent-consonant set is **mostly non-object** words (know, write, honest, wrong, wrestle…);
only `knife`/`wreath` are concrete objects. So this **cannot be a concrete-object study** (n≈1 objects) — it is
a **general-word** modulation ablation. That means the introspection / loaded-word confounds the concrete-object
design deliberately escaped **partially return**, so this ablation's evidentiary status is **weaker** than
B1.3, and it **cannot feed the concrete-object evidence path**. High-confound words (religious/ethical/mental/
social/valence) are flagged and a drop-confound sensitivity analysis is pre-specified.

## 4. Word set

`b1_3_orthographic_latent_ablation_candidate_wordlist.json` — **30 eligible** (only `hour` excluded: no spoken
varṇa). Silent-letter distribution: K 9 · W 10 · P 4 · G 3 · H 3 · M 1. Frozen before any run.

## 5. Arms (one fixed rule each)

- **A_spoken** — spoken-only (reference; the active B1.3 rule).
- **A_ortho_additive** — add the initial silent consonant at its natural read_op pole.
- **A_silent_liberating** — add it at the **liberating** pole (the focal rule).
- **A_silent_binding** — add it at the **binding** pole.
- **A_silent_dual/weighted** — both poles weakly / attenuated (hybrid).

Each is tested with the **same controls** as B1.3: near/mid/far deranged · scrambled · random · neutral · and
the **semantic baseline**.

## 6. Endpoints

For each rule-arm: **A_rule vs A_spoken** (does the rule beat spoken-only?) **and A_rule vs semantic baseline**
(does it beat ordinary meaning?). Focal success = **A_silent_liberating beats A_spoken, the semantic baseline,
and all controls, uniformly** across the set (surviving drop-confound sensitivity; no single model-family or
single-word/letter-class dominance).

## 7. Kill condition

**If no fixed orthographic rule beats spoken-only AND the semantic baseline across the set, the orthographic-
latent rescue is CLOSED and spoken-only stands.** Per-word wins (e.g. `knife` alone) do **not** count — that is
the cherry-pick the uniformity requirement exists to block. Honest prior: **low** (ad hoc validation conformed
~1/22, inverted 5).

## 8. Thresholds & decision labels (future run)

Wilson lower CI > 0.50 for A_rule vs A_spoken and vs baseline · Holm across arms×comparisons · per silent-letter
class (K/G/W/P/H/M) reported separately · drop-high-confound sensitivity · no single model-family dominance.
Future-run labels: `ORTHOGRAPHIC_LATENT_RULE_BEATS_SPOKEN_AND_BASELINE` ·
`ORTHOGRAPHIC_LATENT_RULE_NULL_SPOKEN_STANDS` · `ORTHOGRAPHIC_LATENT_SEMANTIC_BASELINE_EXPLAINS` ·
`ORTHOGRAPHIC_LATENT_STYLE_CONFOUNDED` · `ORTHOGRAPHIC_LATENT_INVALID_RUN`.

## 9. Kosha-stratified variant (operator note) — NOT included

The operator proposes a **four-kosha** model where a varṇa's meaning is layer-dependent (e.g. `ka` = *cutting*
for physical-kosha words like `knife`, *detachment* for mental-kosha words). **Not included here, not
implemented.** Hard blockers, on the record:

- The **frozen lexicon has no kosha-stratified glosses**: `ka` = *hope / āśā* only; **there is no "cutting"
  reading of `ka` anywhere in the source.** Using "cutting" would be **inventing a gloss to fit `knife`** — a
  lexicon change / fabrication, which is exactly the rescue the evaluation forbids.
- **4 koshas × 2 poles = up to 8 readings per varṇa** — a free-parameter explosion that makes almost any word
  fittable and is **unfalsifiable** unless (a) each word's kosha is assigned by an **independent** rule not
  chosen to fit, and (b) the full kosha × varṇa × pole table is **fixed and pre-registered before any run**.
- The motivation is **output-first** (we want `knife` = cutting, so posit a physical-kosha layer that yields
  cutting).

**Only legitimate path:** specify a **complete, independent kosha lexicon** (all varṇas × all koshas) with an
independent per-word kosha-assignment rule, pre-register it, and test against the same controls — as its **own
separate gate**, never as a `knife` rescue.

## 10. Decision

```
DECISION: ORTHOGRAPHIC_LATENT_ABLATION_PREREGISTERED_READY
```

The initial-silent → liberating rule (and its binding/additive/dual siblings) is pre-registered as a uniform,
control-matched, general-word ablation with an explicit kill condition and low stated prior; v2 is untouched;
the lexicon is unchanged; the kosha variant is quarantined as a separate future gate with its blockers named.

## 11. Final status block

```
document:                    B1.3 orthographic-latent (initial-silent -> liberating) ablation PRE-REGISTRATION
decision:                    ORTHOGRAPHIC_LATENT_ABLATION_PREREGISTERED_READY
active B1.3 v2 evidence path: UNCHANGED (spoken-only, freeze-ready)
lexicon:                     UNCHANGED
word set:                    30 eligible word-initial-silent-consonant words (mostly non-object -> general-word ablation)
focal rule:                  word-initial silent consonant -> liberating pole
kill condition:              no fixed rule beats spoken-only AND semantic baseline -> orthographic rescue CLOSED
honest prior:                LOW (ad hoc ~1/22 conform, 5 invert)
kosha variant:               quarantined as a separate future gate; NOT implemented (no 'cutting' gloss exists for ka)
run completed:               NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL / MAPPING_FIDELITY_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
```

**Structure, not validated meaning.** The initial-silent → liberating routing rule is pre-registered as a
uniform, control-matched general-word ablation with an explicit kill condition; the active B1.3 v2 evidence
path and the frozen lexicon are untouched, the kosha-stratified idea is quarantined as a separate future gate
(it has no basis in the frozen glosses), nothing was run or scored, prior nulls stand, Track B remains BLOCKED,
and EVIDENCE_FREEZE is not declared.

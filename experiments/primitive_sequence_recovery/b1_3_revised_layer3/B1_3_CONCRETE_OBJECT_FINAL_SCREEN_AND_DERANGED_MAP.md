# B1.3 Concrete-Object LLM Judged-Modulation — Final Screen & Deranged Source Map

## 1. Scope and status

Preparation only. **No final stimuli generated · no judge run · no scoring · no EVIDENCE_FREEZE · prior results
unchanged.** Produces the **final screened primary concrete-object list** and the **deterministic near/mid/far
deranged source map** for the concrete-object LLM judged-modulation study. **Structure, not validated meaning.**

## 2. Screening goal

Select the final primary concrete-object targets from the candidate pool and ensure each has a stable
dictionary anchor, an object family, a cmudict/varṇa route, a WordNet route, and usable near/mid/far deranged
sources — while keeping loaded/ambiguous/metaphorical/emotional/religious/register-heavy words **out** of the
primary evidence set (they remain in the diagnostic tier only).

## 3. Inclusion criteria

Each final primary target has: **stable concrete-object denotation · short neutral dictionary anchor · neutral
context · cmudict/G2P/varṇa route · WordNet synset (object-family metadata) · no high_confound flag · ≥1 near +
≥1 mid + ≥1 far deranged source · deranged sources selected before any tag/stimulus generation.**

## 4. Exclusion criteria

Exclude or demote: ambiguous words · strong metaphorical usage · culturally/religiously loaded words ·
affective/kinship/social-register words · words without a reliable varṇa route · words without usable
near/mid/far sources · words whose anchor would force a modulation answer too strongly · words whose deranged
pairs would become comical/absurd. **(The diagnostic tier already quarantines the loaded categories; the 53
primary candidates are all concrete objects, so none were demoted for loading here.)**

## 5. Final primary wordlist

`b1_3_concrete_object_final_primary_wordlist.json` — **53 final primary targets** (all 53 primary concrete
candidates passed screening: every one routes cmudict→varṇa and has a noun synset; **0 excluded/demoted**).
Each item: `item_id` · `target_word` · `object_family` · `dictionary_anchor` · `neutral_context` ·
`wordnet_synset` · `cmudict_varna_route_status` · `inclusion_status` · `screening_notes`.

Family distribution: **tool 10 · container 8 · natural 8 · household 8 · structure 8 · barrier 6 ·
furniture 5** (no family > half the set).

## 6. Deranged source mapping

`b1_3_concrete_object_deranged_source_map.json` — for each of the 53 targets: `near_source_word` /
`mid_source_word` / `far_source_word`, each with `*_source_family` and `*_similarity_basis` (WordNet
Wu-Palmer), plus `selection_seed`, `tie_break`, and `notes`. Every target has all three strata assigned.

**Method (deterministic):** rank all other final-primary objects by Wu-Palmer similarity (high→low, lexical
tie-break); **near** = same object family (highest-sim preferred), **mid** = different family, middle
similarity band, **far** = different family, lowest similarity band. To prevent any single source dominating a
stratum (a judge-learnability confound), within each band the **least-used-so-far** source is chosen, targets
processed in lexical order — fully deterministic, no randomness.

## 7. Near source rule

**Same or adjacent object family**, similar function where possible, not an identical synonym that would make
the test impossible. *e.g. knife→key, cup→bucket, bridge→tower, door→gate.* **Result: near is same-family for
53/53 targets** (mean near WuP 0.597) — the hard object-specificity control.

## 8. Mid source rule

**Concrete object, different function family**, not absurdly opposite, not too semantically close — the
practical object-specificity control. **Result: mid is different-family for 53/53** (mean mid WuP 0.510).
*e.g. knife→tower, cup→hammer, bridge→book.*

## 9. Far source rule

**Concrete object, very different function family**, not comically easy, still a plausible rendered option.
**Result: far is different-family for 53/53** (mean far WuP 0.362), and **mid ≥ far for 53/53** (no mid/far
inversion). *e.g. knife→pillar, cup→basketball, bridge→leaf.*

## 10. Determinism and anti-cherry-picking

Deranged sources are selected **before** tag/stimulus generation (no tags exist yet); **no tag inspection**;
selection is by a recorded **deterministic seed with lexical tie-breaks** (`b1_3_concrete_object_final_screen_v1`).
No manual post-hoc replacement is permitted **except predeclared invalid route failure**, which must be logged.

## 11. Balance checks

- Final primary targets: **53** · excluded/demoted: **0**.
- Family distribution: tool 10 / container 8 / natural 8 / household 8 / structure 8 / barrier 6 / furniture 5
  — **no family dominates** (max 10 < 27).
- **Source-usage balance:** most-used near source used **1×**, most-used mid source **2×**, most-used far
  source **3×** — no single source dominates any stratum (an earlier unbalanced draft had one deep-hierarchy
  word as "far" 41× ; the least-used-first rule fixes this).
- Near/mid/far availability: **all 53 targets have all three strata.**
- All final targets remain **eligible**.

**Honest caveat (WuP coarseness):** the primary stratum definition is **object-family separation** (near
same-family, mid/far different-family — perfect 53/53), with Wu-Palmer as the secondary ordering. The aggregate
similarity gradient is monotone (near 0.597 > mid 0.510 > far 0.362) and **mid ≥ far always**, but for **13/53**
targets the same-family near source has *lower* WuP than the cross-family mid source (Wu-Palmer is a coarse
tree-distance measure; some same-family siblings sit far apart in the hypernym tree). This is expected and does
**not** weaken near as the *hard specificity* control (it is same-object-family by construction); it is flagged
so a manual sanity pass over the frozen map is a listed downstream step before EVIDENCE_FREEZE.

## 12. Output-artifact requirements

The final primary wordlist JSON includes all 53 screened targets; the deranged source map JSON includes
near/mid/far for every target; the manifest (`b1_3_concrete_object_final_screen_manifest.json`) includes
`evidence_freeze_declared: false` · `final_stimuli_generated: false` · `judge_run_completed: false` ·
`scoring_completed: false` · `prior_results_preserved: true` · `screening_seed`/tie-break · `balance_checks` ·
`remaining_blockers`.

## 13. Freeze-readiness impact

**Resolves:** final screened primary object list ✔ · final near/mid/far deranged source map ✔.
**Still unresolved:** final stimulus generation · style-audit execution/result · final judge model list ·
scoring-script implementation · final thresholds · manifest hash binding · explicit EVIDENCE_FREEZE
declaration · actual judge run.

## 14. Decision

```
DECISION: FINAL_SCREEN_DERANGED_MAP_READY
```

All 53 primary concrete objects passed screening (stable anchor, object family, cmudict/varṇa + WordNet routes,
no high-confound flag), and a deterministic, usage-balanced near/mid/far deranged source map was built with
perfect family separation and a monotone aggregate similarity gradient. This is not
`FINAL_SCREEN_DERANGED_MAP_HIGH_RISK_NEEDS_REVISION` (family separation is complete, source usage is balanced,
selection is deterministic and pre-tag) and not `FINAL_SCREEN_DERANGED_MAP_NOT_FEASIBLE_CLOSE_LINE` (the screen
and map are feasible and built). The WuP-coarseness caveat (§11) is documented and gated by a downstream manual
sanity pass before freeze.

## 15. Final status block

```
document:                    B1.3 concrete-object FINAL SCREEN & DERANGED MAP (preparation only)
decision:                    FINAL_SCREEN_DERANGED_MAP_READY
final primary targets:       53 (0 excluded/demoted) — tool 10 / container 8 / natural 8 / household 8 /
                             structure 8 / barrier 6 / furniture 5
deranged map:                deterministic near/mid/far for all 53; near same-family 53/53; mid & far diff-family 53/53
similarity gradient:         near 0.597 > mid 0.510 > far 0.362 (aggregate); mid ≥ far 53/53
source-usage balance:        most-used near 1× / mid 2× / far 3× (no stratum dominance)
selection:                   deterministic seed + lexical tie-break; sources chosen BEFORE any tag/stimulus generation
final stimuli generated:     NO
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        generate stimuli (frozen), run style audit, finalize judge list + scorer, then freeze
```

**Structure, not validated meaning.** The final primary concrete-object list (53) and a deterministic,
usage-balanced near/mid/far deranged source map are built; no final stimuli were generated, no judges were run,
nothing was scored, prior nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not
declared.

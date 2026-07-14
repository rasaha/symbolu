# Varṇa–Affliction Resolution Test — First Developmental Run (V1.1 methodology)

**`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.** First execution of the frozen V1.1 methodology
(PMM → PR → CR) on a deliberately adversarial, precommitted 14-word set. The goal is **not** to maximize PASS — it
is to find where the methodology works, fails, and is ambiguous **before** any evidence freeze. Nothing was
redesigned; the parser, mappings, lexicon, thresholds, and methodology are run exactly as frozen.

- **Methodology:** `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1_1.md` (PMM documentation-only; **PR** the sole
  verdict layer, scale `{0,25,50,75,100}`; CR explanatory-only, `HOLISTIC_ONLY_FIT` flag).
- **Lexicon:** `frozen/varna_native_stage1_merged_v3.json` (`65116f37…`, ś/ṣ corrected). **Parser:**
  `sanskrit_stage1_parser.py`. Coverage = 100% for all 14 words (all consonants are mapped backbone) → no
  coverage-driven INDETERMINATE.
- **Verdict rules (frozen):** PASS = mean ≥75 **and** min ≥50 **and** no component in {0,25} **and** coverage ≥80;
  FAIL = mean <50 **or** any component = 0; PARTIAL_FIT = mean in [50,75) or mean ≥75 with a component = 25;
  INDETERMINATE = coverage <80.

## Frozen word list (precommitted before scoring)

Selected by **category and ordinary stable meaning only**, spanning expected PASS/PARTIAL/FAIL — not to pass.
Frozen in `varna_affliction_pilot_run_v1/wordlist_precommit.json`.

peace · knowledge · truth · water · flower · elephant · sun · hand · river · anger · desire · greed · fear · snake.

---

## Results (mechanically aggregated from the component scores)

| Word | Gloss | Consonant → affliction components (PR) | mean | min | emb | Verdict |
|---|---|---|---|---|---|---|
| śānti | peace | ś·artha=100, n·moha=75, t·jāḍya=75 | 83.3 | 75 | 0 | **PASS** |
| jñāna | knowledge | j·ego=50, ñ·hypocrisy=75, n·moha=100 | 75.0 | 50 | 0 | **PASS** |
| satya | truth | s·sattvic-clinging=50, t·jāḍya=75, y·self-doubt=75 | 66.7 | 50 | 0 | **PARTIAL_FIT** |
| jala | water | j·ego=100, l·cruelty=100 | 100 | 100 | 0 | **PASS** (vacuous) |
| puṣpa | flower | p·revulsion=100, ṣ·kāma=75, p·revulsion=100 | 91.7 | 75 | 0 | **PASS** (partly vacuous) |
| gaja | elephant | g·restless-striving=75, j·ego=75 | 75.0 | 75 | 0 | **PASS** |
| sūrya | sun | s·sattvic-clinging=75, r·annihilation=75, y·self-doubt=100 | 83.3 | 75 | 0 | **PASS** |
| hasta | hand | h·outward-fixation=50, s·sattvic-clinging=75, t·jāḍya=50 | 58.3 | 50 | 0 | **PARTIAL_FIT** |
| nadī | river | n·moha=100, d·peevishness=75 | 87.5 | 75 | 0 | **PASS** |
| krodha | anger | k·grasping-hope=25, r·annihilation=0, dh·craving=25 | 16.7 | 0 | 3 | **FAIL** |
| kāma | desire | k·grasping-hope=0, m·indulgence-collapse=25 | 12.5 | 0 | 2 | **FAIL** |
| lobha | greed | l·cruelty=25, bh·mūrcchā=0 | 12.5 | 0 | 2 | **FAIL** |
| bhaya | fear | bh·mūrcchā=25, y·self-doubt=0 | 12.5 | 0 | 2 | **FAIL** |
| sarpa | snake | s·sattvic-clinging=75, r·annihilation=25, p·revulsion=25 | 41.7 | 25 | 2 | **FAIL** |

**Counts — PASS 7 · PARTIAL_FIT 2 · FAIL 5 · INDETERMINATE 0.**

---

## Layer 1 — PMM (documentation only; never affects the verdict)

All 14 words parse cleanly and every consonant is a `CONFIRMATORY_BACKBONE` mapping, so **mapping-attestation PMM
is uniformly high (~90–100%)**: the varṇa→affliction entries exist, are verbatim-frozen, and coverage is 100%.
Evidence *against* the mapping is not about attestation but about **applicability**: for inanimate/non-agentive
referents (water, flower, sun, snake-as-animal, hand) several afflictions are *psychic/moral* and cannot be
predicated of the referent at all — PMM records this as an applicability caveat. Because PMM is documentation-only
it does not change any verdict below; but the applicability gap it records is the origin of the pilot's main
finding (§ weaknesses).

## Layer 2 — PR (the verdict) — notable component reasoning

Only the interpretively-loaded and all FAIL components are argued here; the rest follow the table.

- **śānti (peace) PASS.** Peace is conspicuously free of acquisitive grasping (ś=100) and of fixated attachment
  (n=75). The one soft point is **t·jāḍya=75**: peace's stillness *superficially* resembles torpor, but the
  stable prototype of peace is *alert* tranquility, not dullness — resolution, not embodiment.
- **jñāna (knowledge) PASS, borderline.** n·moha=100 (knowledge is the classical antidote to delusion). But
  **j·ego=50** is genuinely mixed: realized *jñāna* dissolves ego, yet ordinary "knowledge" can *inflate* it
  (scholarly pride). A defensible 25 here would flip jñāna to PARTIAL — a rater-sensitive borderline.
- **satya (truth) PARTIAL.** Pulled below PASS by **s·sattvic-clinging=50**: truthfulness has a real shadow of
  self-righteous superiority (the "golden chain"), so it does not conspicuously resolve *that* subtle affliction.
- **hasta (hand) PARTIAL.** A neutral instrument scores mid on psychic afflictions: h·outward-fixation=50 (the
  hand *is* the organ of manifest action), t·jāḍya=50 (inert at rest, active in use). Neither resolution nor
  embodiment — the ambiguity zone.

**FAIL explanations (required skepticism — none is auto-blamed on the theory or the methodology):**

- **krodha (anger) FAIL [25,0,25].** *Genuinely-unresolved / convincing embodiment.* Anger embodies destructive
  collapse (r=0), and is downstream of thwarted grasping and craving (k,dh=25). The mapping is apt; the FAIL is
  real, not an artifact.
- **kāma (desire) FAIL [0,25].** *Definitional embodiment.* kāma **is** grasping-clinging hope (k=0). The
  strongest possible FAIL basis — the word is the affliction.
- **lobha (greed) FAIL [25,0].** *Convincing embodiment.* Greed is precisely *mūrcchā* — discernment lost under
  the ripu's spell (bh=0). Apt mapping.
- **bhaya (fear) FAIL [25,0].** *Convincing embodiment + strikingly apt mapping.* Fear directly embodies
  *aviśvāsa* — self-doubt/distrust that cannot commit (y=0). This is the single most on-target hit in the run.
- **sarpa (snake) FAIL [75,25,25].** *Mostly embodiment, but note the artifact:* the snake embodies deadliness
  (r=25) and evokes revulsion (p=25); yet **s·sattvic-clinging=75 is a vacuous non-embodiment** (an animal can't
  cling to spiritual purity) that inflates the mean. Without that inapplicable component the FAIL is cleaner —
  see weakness #2.

## Layer 3 — CR (explanatory only; never alters PR)

For the PASS words the resolving components reconcile coherently (peace/knowledge/river present a unified
non-grasping, non-deluded, non-reactive character). **No `HOLISTIC_ONLY_FIT` was triggered** — there is no word
here where a high holistic story sits on top of a weak PR. The FAILs have low CR too (their afflictions cohere
*as* the affliction). CR added no verdict-relevant information in this run, which is the correct behavior.

---

## Final analysis

- **Counts:** PASS 7 · PARTIAL_FIT 2 · FAIL 5 · INDETERMINATE 0.
- **Strongest PASS: śānti (peace)** — an animate, applicable concept that is the genuine *antithesis* of its
  mapped afflictions (grasping, attachment, agitation); resolution is active, not vacuous. (nadī/river is a close
  second: n·moha=100 because a river actively symbolizes non-clinging flow.)
- **Strongest FAIL: krodha (anger)** — all three components embody (mean 16.7), the affliction mapping is apt, and
  it is a clean falsification anchor. **bhaya→aviśvāsa (fear = self-doubt, y=0)** is the single most precise
  mapping hit.
- **Weakest methodology point: the vacuous / inapplicable-component problem.** When a *psychic* affliction is
  mapped onto an *inanimate or non-agentive* referent, "does not embody" is scored **100** and treated as
  resolution — so the referent passes without the theory ever being tested. `jala` (water) [100,100] is a pure
  vacuous PASS; `puṣpa`, `sūrya`, and the `s=75` in `sarpa` are partial instances, and `sarpa`'s inapplicable
  component actively *inflated a FAIL toward the boundary*.
- **Strongest support for the methodology: the afflictive concepts fail cleanly, and the failures land exactly
  where they should.** The process is not a yes-machine — it produced 5 FAILs, and the mappings on those FAILs are
  strikingly apt (fear→self-doubt, greed→loss-of-discernment, anger→destruction, desire→grasping). That
  combination of demonstrated falsifiability **and** semantic aptness on the adversarial words is the real signal.

## "If we froze the evidence today, what would prevent this from being a convincing confirmatory experiment?"

Four things — the first three are demonstrated by this pilot:

1. **Vacuous passes are not disconfirmable.** A skeptic rightly says "of course water doesn't embody ego — that's
   not evidence *for* the mapping." Several PASSes (jala outright; puṣpa/sūrya partly) rest on inapplicable
   components scored 100. Until inapplicable components are handled, PASS is not clean evidence.
2. **The scale conflates "does not embody" with "actively resolves."** Both score 100, but `nadī`'s n=100 (river =
   non-clinging) is a genuine resolution while `jala`'s j=100 (water can't be egoistic) is vacuous. Means built
   from a mix of the two are not interpretable as strength-of-resolution.
3. **Single, non-blind rater.** Every PR score here is my adjudication; the borderline cases (jñāna j=50, satya
   s=50, hasta) show the scores are rater-sensitive and can flip a verdict. Confirmatory evidence needs ≥2
   independent, referent-blind adjudicators with a reported inter-rater agreement.
4. **No shuffled-mapping control (out of scope for this pilot).** PASS could be partly Barnum unless real mappings
   beat a shuffled-mapping baseline (does peace "resolve" *random* afflictions equally well?). Not run here by
   instruction, but required before a confirmatory claim.

## Genuinely necessary improvements before evidence freeze (only what this pilot demonstrated)

1. **Applicability gate.** Before scoring, classify each (referent, affliction) pair as *applicable* (the referent
   can psychically embody the affliction) or *inapplicable* (inanimate/non-agentive vs a psychic affliction).
   Score inapplicable components **INDETERMINATE / excluded from the mean**, not 100. Demonstrated by `jala`
   [100,100] and `sarpa`'s masking s=75. *(This is a scoring-input rule, not a change to the frozen scale or
   thresholds — it decides which components are eligible to be scored.)*
2. **Dual, referent-blind adjudication with inter-rater reliability.** Demonstrated by the rater-sensitive
   borderlines (jñāna, satya, hasta).
3. **A shuffled-mapping control arm** for the confirmatory run (not this pilot).

No other redesign is warranted: the scale, thresholds, and PMM/PR/CR separation behaved correctly — CR never
distorted PR, PMM never touched a verdict, and the falsification anchors fired. The two structural gaps
(applicability, adjudication) are concrete and evidenced; everything else held.

## Guardrails
Exploratory developmental run. Parser, mappings, lexicon (v3), thresholds, and methodology run exactly as frozen
and unmodified; no new theory, no new control, no B1.12 work. Single-rater interpretive scores — not confirmatory
evidence. Structure, not validated meaning.

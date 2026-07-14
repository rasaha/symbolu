# Bare-Word Resolution (BWR) Run — real vs shuffled mapping (60 words)

**`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.** Re-scores the 60-word set under the corrected
definition of "resolution" — **Bare-Word Resolution**: *does the unqualified word's ordinary meaning already
account for / naturally imply the mapped affliction, without adding any modifier, subtype, story, or external
actor?* — and compares it against a **shuffled-mapping control**, so the result is evidence rather than
confirmation.

This is a **new scoring semantics (BWR), not the frozen V1.1** (whose "transcendence / does-not-embody" reading
was scored correctly for its own text). Frozen artifacts are untouched. Lexicon `…merged_v3.json` (`65116f37…`);
parser `sanskrit_stage1_parser.py`.

## BWR scale (as specified)

100 directly/characteristically present · 75 strongly implied · 50 plausible-needs-interpretation · 25
needs-substantial-qualification/exceptional-case · 0 cannot-support-without-external-meaning. Word-BWR = mean of
component BWRs.

## Control

A deterministic global permutation of the 33 consonant→binding-gloss bijection (seed `BWR_SHUFFLE_1`, no fixed
points; recorded in `bwr_shuffle_setup.json`). Each word's shuffled glosses were scored on their **own** merits
under the identical BWR question. Real and shuffled were scored by the **same, non-blind rater** — the central
limitation (see below).

## Result — real vs shuffled BWR, by category

| Category | n | real | shuffled | Δ (real−shuf) |
|---|---|---|---|---|
| resolution | 10 | 2.5 | 2.3 | **+0.2** |
| virtue | 5 | 15.0 | 9.2 | +5.8 |
| abstract | 5 | 25.0 | 15.0 | +10.0 |
| emotion | 4 | 42.7 | 30.2 | +12.5 |
| inanimate | 6 | 14.6 | 8.3 | +6.2 |
| animal | 8 | 22.7 | 15.6 | +7.0 |
| body | 6 | 18.1 | 5.6 | +12.5 |
| natural | 6 | 11.8 | 7.3 | +4.5 |
| **affliction** | 10 | **78.8** | **45.0** | **+33.8** |
| **ALL** | 60 | 27.2 | 16.1 | **+11.1** |

**Afflictions, per word (real / shuffled / Δ):**

| word | real | shuf | Δ | |
|---|---|---|---|---|
| bhaya (fear) | 100 | 25 | +75 | real fits far better |
| krodha (anger) | 83 | 25 | +58 | |
| dveṣa (hatred) | 67 | 17 | +50 | |
| īrṣyā (jealousy) | 83 | 33 | +50 | |
| lobha (greed) | 100 | 50 | +50 | |
| moha (delusion) | 75 | 38 | +38 | |
| ahaṃkāra (ego) | 67 | 50 | +17 | |
| **kāma (desire)** | 88 | 88 | **0** | shuffle fits equally (craving/possessiveness ≈ grasping/indulgence) |
| **mada (pride)** | 75 | 75 | **0** | shuffle fits *better* (ego→pride) |
| **mātsarya (envy)** | 50 | 50 | **0** | broad overlap |

## What this shows (honestly)

1. **BWR reverses the polarity, exactly as the reframe predicted.** Under BWR the **afflictions now succeed**
   (real ≈ 79 — greed *does* carry cruelty and senselessness in the bare word) and the **positives fail** (real
   ≈ 2.5 — "peace" does not contain grasping/attachment/inertia). This is the correct behavior for a
   meaning-composition test, and confirms the pilot/expanded runs were using the *other* ("transcendence")
   definition.

2. **Real beats shuffled — and the signal is concentrated where it can be:** Δ = **+33.8 on afflictions** (7/10
   real > shuffle), Δ = +11.1 overall. On the words that *can* carry afflictions, the **specific frozen mapping
   fits the bare word better than a random affliction assignment** — a real, directional signal, not just
   generic negativity. bhaya→self-doubt (+75), krodha→destruction (+58), lobha→cruelty/senselessness (+50) are
   the clearest.

3. **But the Barnum residue is visible and must not be hidden.** **3/10 afflictions tie** (kāma, mada, mātsarya):
   because the ~18 afflictions are broad and overlapping, a random draw often lands on an equally-apt (or, for
   *mada*, a *better*) affliction — "desire carries craving/possessiveness" fits as well as the real
   "grasping/indulgence." So high real-BWR is **not automatically** evidence for the *specific* assignment; the
   shuffle contrast is doing the real work, and it does not clear the specific mapping on every word.

4. **Positive words are structurally untestable by this test.** resolution/virtue Δ ≈ 0 with both near zero —
   BWR-against-the-binding-glosses cannot discriminate on positively-valenced words, because *no* affliction (real
   or shuffled) is present in them. To test positives one must score them against the **liberating** pole (the
   valence-pairing point) — not done here.

## The limitation that caps this result

**The same rater scored real and shuffled, non-blind.** I knew which was which, so the +33.8 is an **upper bound**
— unconscious favoring of the real mapping cannot be excluded, and single-shuffle variance is high (a different
permutation would move the ties). This is not a valid confirmatory control; it is an indicative developmental
probe. A real test requires: **blind adjudicators** who don't know real from shuffle, **many** permutations (a
null distribution, per the feature-lift design), and **valence-paired poles** so positives are tested against the
liberating side.

## What it does / does not establish

**Does:** under the corrected BWR definition, the frozen mappings fit afflictive words **better than chance
assignments** (Δ+34 on afflictions), a promising directional signal for the composition hypothesis — strong on
fear/anger/greed/hatred/jealousy, absent on desire/pride/envy. **Does not:** establish the mappings as "true
meanings" (non-blind, single shuffle, ties on 3/10), nor say anything about positive words (untestable here), nor
constitute confirmatory evidence.

## Recommendation

BWR is the right framing and shows enough signal to justify the **proper confirmatory design**: blind real-vs-
shuffled adjudication over many permutations, valence-paired poles, and a pre-registered effect threshold — which
is exactly the ablation logic of the frozen feature-lift study. If you want, the next step is to fold BWR into
that machine (BWR as the human-judged analogue of the embedding lift) rather than continue single-rater scoring.

## Guardrails
Developmental probe of a *new* (BWR) scoring semantics; frozen V1.1 methodology, parser, mappings, lexicon (v3),
and all frozen artifacts unmodified. Single non-blind rater, one shuffle — indicative, not confirmatory.
Structure, not validated meaning.

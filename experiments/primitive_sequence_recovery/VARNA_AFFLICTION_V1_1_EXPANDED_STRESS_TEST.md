# Varṇa–Affliction Resolution Test — Expanded Developmental Stress-Test (60 words)

**`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.** Runs the frozen V1.1 methodology (PMM → PR → CR)
on a **60-word** adversarial sample spanning 9 categories, to test whether the existing methodology is
sufficiently discriminative before any evidence freeze. **Nothing was modified** — parser, mappings, lexicon
(v3), scales, gates, thresholds, and verdict logic are run exactly as frozen. No new gates or scoring rules.

- **Methodology:** `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1_1.md`. **Lexicon:**
  `frozen/varna_native_stage1_merged_v3.json` (`65116f37…`). **Parser:** `sanskrit_stage1_parser.py`. Coverage =
  100% for all 60 (all consonants mapped) → no coverage-driven INDETERMINATE.
- **Verdict rules (frozen, applied mechanically):** PASS = mean ≥75 **and** min ≥50 **and** no component ∈{0,25};
  FAIL = mean <50 **or** any component = 0; else PARTIAL_FIT.
- **PMM (documentation only; never affects the verdict).** Every PMM below is **evidence-backed**: it is the
  provenance-weighted strength of the word's varṇa→affliction mappings — `PRIMARY_ATTESTED`=100,
  `SECONDARY`=85, `INFERRED`=60, `AUTHORED_PROVISIONAL`=50 — and each PMM cell states the exact provenance mix
  that produced it. A PMM with no provenance evidence would be invalid; none here is evidence-free.

## 1. Full score table

Components show `consonant=PR` (per-occurrence, {0,25,50,75,100}). `emb` = count of components ∈{0,25}.

| word | gloss | category | components (consonant=PR) | mean | min | emb | verdict | PMM (evidence) |
|---|---|---|---|---|---|---|---|---|
| śānti | peace | resolution | ś=100 n=75 t=75 | 83.3 | 75 | 0 | **PASS** | 83 (authored×1,primary×2) |
| mokṣa | liberation | resolution | m=100 k=100 ṣ=100 | 100.0 | 100 | 0 | **PASS** | 87 (primary×2,inferred×1) |
| śama | calm | resolution | ś=100 m=75 | 87.5 | 75 | 0 | **PASS** | 75 (authored×1,primary×1) |
| kṣamā | forgiveness | resolution | k=75 ṣ=75 m=75 | 75.0 | 75 | 0 | **PASS** | 87 (inferred×1,primary×2) |
| dhairya | fortitude | resolution | dh=75 r=100 y=100 | 91.7 | 75 | 0 | **PASS** | 100 (primary×3) |
| maitrī | friendliness | resolution | m=75 t=75 r=100 | 83.3 | 75 | 0 | **PASS** | 100 (primary×3) |
| karuṇā | compassion | resolution | k=75 r=75 ṇ=100 | 83.3 | 75 | 0 | **PASS** | 70 (inferred×1,primary×1,authored×1) |
| tyāga | renunciation | resolution | t=75 y=75 g=100 | 83.3 | 75 | 0 | **PASS** | 87 (primary×2,inferred×1) |
| vairāgya | dispassion | resolution | v=75 r=75 g=100 y=75 | 81.2 | 75 | 0 | **PASS** | 80 (inferred×2,primary×2) |
| ānanda | bliss | resolution | n=75 n=75 d=100 | 83.3 | 75 | 0 | **PASS** | 100 (primary×3) |
| krodha | anger | affliction | k=25 r=0 dh=25 | 16.7 | 0 | 3 | **FAIL** | 87 (inferred×1,primary×2) |
| kāma | desire | affliction | k=0 m=25 | 12.5 | 0 | 2 | **FAIL** | 80 (inferred×1,primary×1) |
| lobha | greed | affliction | l=25 bh=0 | 12.5 | 0 | 2 | **FAIL** | 100 (primary×2) |
| moha | delusion | affliction | m=25 h=25 | 25.0 | 25 | 2 | **FAIL** | 75 (primary×1,authored×1) |
| mada | pride | affliction | m=25 d=25 | 25.0 | 25 | 2 | **FAIL** | 100 (primary×2) |
| dveṣa | hatred | affliction | d=25 v=25 ṣ=50 | 33.3 | 25 | 2 | **FAIL** | 87 (primary×2,inferred×1) |
| bhaya | fear | affliction | bh=25 y=0 | 12.5 | 0 | 2 | **FAIL** | 100 (primary×2) |
| īrṣyā | jealousy | affliction | r=25 ṣ=25 y=25 | 25.0 | 25 | 3 | **FAIL** | 100 (primary×3) |
| ahaṃkāra | ego | affliction | h=25 k=25 r=25 | 25.0 | 25 | 3 | **FAIL** | 70 (authored×1,inferred×1,primary×1) |
| mātsarya | envy | affliction | m=25 t=50 s=50 r=25 y=25 | 35.0 | 25 | 3 | **FAIL** | 92 (primary×4,inferred×1) |
| jala | water | inanimate | j=100 l=100 | 100.0 | 100 | 0 | **PASS** | 100 (primary×2) |
| aśma | stone | inanimate | ś=100 m=100 | 100.0 | 100 | 0 | **PASS** | 75 (authored×1,primary×1) |
| ghaṭa | pot | inanimate | gh=100 ṭ=100 | 100.0 | 100 | 0 | **PASS** | 100 (primary×2) |
| pustaka | book | inanimate | p=100 s=75 t=50 k=100 | 81.2 | 50 | 0 | **PASS** | 80 (primary×2,inferred×2) |
| gṛha | house | inanimate | g=100 h=50 | 75.0 | 50 | 0 | **PASS** | 55 (inferred×1,authored×1) |
| suvarṇa | gold | inanimate | s=50 v=75 r=100 ṇ=50 | 68.8 | 50 | 0 | **PARTIAL_FIT** | 68 (inferred×2,primary×1,authored×1) |
| gaja | elephant | animal | g=75 j=75 | 75.0 | 75 | 0 | **PASS** | 80 (inferred×1,primary×1) |
| siṃha | lion | animal | s=75 h=50 | 62.5 | 50 | 0 | **PARTIAL_FIT** | 55 (inferred×1,authored×1) |
| sarpa | snake | animal | s=75 r=25 p=25 | 41.7 | 25 | 2 | **FAIL** | 87 (inferred×1,primary×2) |
| vyāghra | tiger | animal | v=75 y=100 gh=50 r=25 | 62.5 | 25 | 1 | **PARTIAL_FIT** | 90 (inferred×1,primary×3) |
| aśva | horse | animal | ś=75 v=75 | 75.0 | 75 | 0 | **PASS** | 55 (authored×1,inferred×1) |
| go | cow | animal | g=75 | 75.0 | 75 | 0 | **PASS** | 60 (inferred×1) |
| mṛga | deer | animal | m=75 g=50 | 62.5 | 50 | 0 | **PARTIAL_FIT** | 80 (primary×1,inferred×1) |
| vṛka | wolf | animal | v=75 k=25 | 50.0 | 25 | 1 | **PARTIAL_FIT** | 60 (inferred×2) |
| sukha | happiness | emotion | s=75 kh=100 | 87.5 | 75 | 0 | **PASS** | 60 (inferred×2) |
| duḥkha | sorrow | emotion | d=25 kh=25 | 25.0 | 25 | 2 | **FAIL** | 80 (primary×1,inferred×1) |
| harṣa | joy | emotion | h=50 r=100 ṣ=50 | 66.7 | 50 | 0 | **PARTIAL_FIT** | 83 (authored×1,primary×2) |
| śoka | grief | emotion | ś=25 k=25 | 25.0 | 25 | 2 | **FAIL** | 55 (authored×1,inferred×1) |
| satya | truth | virtue | s=50 t=75 y=75 | 66.7 | 50 | 0 | **PARTIAL_FIT** | 87 (inferred×1,primary×2) |
| dāna | charity | virtue | d=75 n=100 | 87.5 | 75 | 0 | **PASS** | 100 (primary×2) |
| ahiṃsā | non-violence | virtue | h=75 s=50 | 62.5 | 50 | 0 | **PARTIAL_FIT** | 55 (authored×1,inferred×1) |
| dayā | mercy | virtue | d=100 y=75 | 87.5 | 75 | 0 | **PASS** | 100 (primary×2) |
| bhakti | devotion | virtue | bh=25 k=50 t=75 | 50.0 | 25 | 1 | **PARTIAL_FIT** | 87 (primary×2,inferred×1) |
| jñāna | knowledge | abstract | j=50 ñ=75 n=100 | 75.0 | 50 | 0 | **PASS** | 100 (primary×3) |
| vidyā | learning | abstract | v=50 d=75 y=75 | 66.7 | 50 | 0 | **PARTIAL_FIT** | 87 (inferred×1,primary×2) |
| buddhi | intellect | abstract | b=50 d=75 dh=75 | 66.7 | 50 | 0 | **PARTIAL_FIT** | 100 (primary×3) |
| smṛti | memory | abstract | s=50 m=75 t=50 | 58.3 | 50 | 0 | **PARTIAL_FIT** | 87 (inferred×1,primary×2) |
| kāla | time | abstract | k=100 l=25 | 62.5 | 25 | 1 | **PARTIAL_FIT** | 80 (inferred×1,primary×1) |
| agni | fire | natural | g=25 n=75 | 50.0 | 25 | 1 | **PARTIAL_FIT** | 80 (inferred×1,primary×1) |
| vāyu | wind | natural | v=100 y=75 | 87.5 | 75 | 0 | **PASS** | 80 (inferred×1,primary×1) |
| sūrya | sun | natural | s=75 r=75 y=100 | 83.3 | 75 | 0 | **PASS** | 87 (inferred×1,primary×2) |
| candra | moon | natural | c=75 n=50 d=75 r=75 | 68.8 | 50 | 0 | **PARTIAL_FIT** | 88 (authored×1,primary×3) |
| megha | cloud | natural | m=75 gh=100 | 87.5 | 75 | 0 | **PASS** | 100 (primary×2) |
| vidyut | lightning | natural | v=100 d=50 y=75 t=100 | 81.2 | 50 | 0 | **PASS** | 90 (inferred×1,primary×3) |
| hasta | hand | body | h=50 s=75 t=50 | 58.3 | 50 | 0 | **PARTIAL_FIT** | 70 (authored×1,inferred×1,primary×1) |
| netra | eye | body | n=50 t=50 r=75 | 58.3 | 50 | 0 | **PARTIAL_FIT** | 100 (primary×3) |
| śiras | head | body | ś=75 r=75 s=50 | 66.7 | 50 | 0 | **PARTIAL_FIT** | 70 (authored×1,primary×1,inferred×1) |
| hṛdaya | heart | body | h=50 d=50 y=50 | 50.0 | 50 | 0 | **PARTIAL_FIT** | 83 (authored×1,primary×2) |
| pāda | foot | body | p=50 d=75 | 62.5 | 50 | 0 | **PARTIAL_FIT** | 100 (primary×2) |
| karṇa | ear | body | k=75 r=75 ṇ=75 | 75.0 | 75 | 0 | **PASS** | 70 (inferred×1,primary×1,authored×1) |

## 2. Distribution

**Overall: PASS 27 · PARTIAL_FIT 20 · FAIL 13.**

| Category | PASS | PARTIAL | FAIL | reading |
|---|---|---|---|---|
| resolution (10) | **10** | 0 | 0 | perfect — every clear-resolution word passes |
| affliction (10) | 0 | 0 | **10** | perfect — every affliction fails |
| inanimate (6) | 5 | 1 | 0 | mostly **vacuous** passes |
| animal (8) | 3 | 4 | 1 | mixed; fierce predators mostly escape FAIL |
| emotion (4) | 1 | 1 | 2 | splits correctly by valence |
| virtue (5) | 2 | 3 | 0 | subtle-affliction shadow → PARTIAL |
| abstract (5) | 1 | 4 | 0 | double-edged concepts → PARTIAL |
| natural (6) | 4 | 2 | 0 | mostly pass |
| body (6) | 1 | 5 | 0 | neutral instruments → PARTIAL |

The signal lives at the **poles** (resolution 10/10 PASS, affliction 10/10 FAIL); the **middle** categories
(inanimate, animal, body, abstract) are where discrimination degrades.

## 3. Strongest PASS examples (genuine, non-vacuous resolution)

- **mokṣa (liberation) [100,100,100].** The definitional antithesis of grasping-hope (k), kāma (ṣ), and
  indulgent-collapse (m). Every component is an *active* resolution, none vacuous — the cleanest true PASS.
- **dhairya (fortitude) [75,100,100].** Directly resolves *sarvanāśa* / defeatist collapse (r=100) and *aviśvāsa*
  / self-doubt (y=100) — fortitude is literally the overcoming of "I am undone" and "shall I be able?".
- **dayā (mercy) [100,75]** and **dāna (charity) [75,100].** Mercy is the antithesis of peevish reactivity
  (d=100); giving is the antithesis of attachment/*moha* (n=100). Animate, applicable, semantically exact.
- **śānti (peace) [100,75,75].** Free of acquisitive grasping and fixated attachment.

Common feature: an **animate/agentive** referent that is the **semantic opposite** of its afflictions — the
score reflects resolution, not inapplicability.

## 4. Strongest FAIL examples (definitional / conspicuous embodiment, apt mapping)

- **kāma (desire) [0,25].** k=0: desire **is** grasping-clinging hope. The word is the affliction.
- **bhaya (fear) [25,0].** y=0: fear **is** *aviśvāsa* — self-doubt/distrust that cannot commit. The single most
  on-target mapping in the whole run.
- **krodha (anger) [25,0,25].** r=0: anger **is** destructive collapse; all three components embody.
- **lobha (greed) [25,0].** bh=0: greed **is** *mūrcchā* — discernment lost under the ripu's spell.
- **īrṣyā (jealousy) [25,25,25]** and **ahaṃkāra (ego) [25,25,25].** Compound afflictions, every component
  embodying.

The methodology is not a yes-machine: **13 FAILs**, and every intended affliction failed with an apt mapping.

## 5. Every borderline case (one rater-judgment from flipping)

- **Exactly at the PASS line (mean = 75.0):** kṣamā, gaja, aśva, go, karṇa (min 75); **jñāna** (min 50, j=50 — a
  25 on j flips it to PARTIAL); **gṛha** (PASS only because the vacuous g=100 offsets h=50).
- **Exactly at the FAIL line (mean = 50.0, carrying a 25):** **vṛka** (wolf), **agni** (fire), **bhakti**
  (devotion) — any downward nudge on the 75-component flips them to FAIL.
- **hṛdaya (heart) [50,50,50] mean 50.0** — the pure "neutral instrument" case, all components ambiguous.
- **FAIL nearly rescued:** **sarpa (snake) 41.7** — the vacuous s=75 pulled a clear embodiment up toward the
  PARTIAL boundary.
- **PARTIAL nearly PASS:** siṃha, mṛga, harṣa, satya, ahiṃsā, vidyā, buddhi, śiras, candra, suvarṇa (mean
  58–69).

Nine verdicts sit **on** a threshold (75.0 or 50.0). This is the clearest quantitative sign of rater-sensitivity.

## 6. Every false-positive concern (PASS/high that is NOT evidence for the mapping)

These pass by **inapplicability** (a psychic affliction scored 100 as "non-embodiment" on a referent that cannot
embody it) — the theory is not tested, yet the verdict is PASS:

- **jala (water) [100,100]** — water cannot be egoistic (j) or cruel (l). Pure vacuous PASS.
- **aśma (stone) [100,100]** — stone cannot acquire (ś) or indulge (m).
- **ghaṭa (pot) [100,100]** — pot cannot possess (gh) or over-talk (ṭ).
- **pustaka (book) [100,·,·,100]**, **gṛha (house) [100,·]** — PASS driven by vacuous 100s.
- **karṇa (ear) [75,75,75]**, **aśva (horse) [75,75]** — PASS built entirely from inapplicable components scored
  75–100.
- Partial contributors: **sūrya, megha, vāyu, vidyut** each contain ≥1 vacuous 100 (though these also have a
  *genuine* resolving component, e.g. vāyu v=100 "wind = the antithesis of stuck fixity").

Root cause: the frozen scale assigns **"does not embody" = high**, so an inanimate referent is scored identically
to a true resolver (stone's 100 ≡ mokṣa's 100 in the number).

## 7. Every false-negative concern (embodying/fierce referents that did NOT FAIL, or masking)

A single high/vacuous component pulled an embodying referent out of FAIL into PARTIAL:

- **vyāghra (tiger) PARTIAL (62.5).** A deadly predator that embodies destruction (r=25), but the vacuous v=75
  plus the *genuine* y=100 (a tiger is fearless → resolves self-doubt) lift the mean above 50. A fierce animal
  arguably should FAIL.
- **vṛka (wolf) PARTIAL (50.0).** Predatory grasping (k=25) masked by the vacuous v=75.
- **kāla (time) PARTIAL (62.5).** Time-as-devourer embodies cruelty (l=25), but the vacuous k=100 (time cannot
  grasp) rescues it.
- **agni (fire) PARTIAL (50.0).** Fire embodies restless consuming (g=25), lifted by n=75 (fire ≠ attachment).
- **sarpa (snake) FAIL but only 41.7** — the same mechanism *almost* produced a false negative; the vacuous s=75
  masked part of the embodiment.

(No intended **resolution** word failed, so there is no false negative among the positive candidates.)

Root cause: **identical** to §6 — inapplicable components scored high both *pass* inanimate objects and *mask*
embodiment in animate/destructive ones.

## 8. Patterns — why the methodology succeeds and where it fails

**Where it succeeds (real, strong signal):**
1. **Polar discrimination is essentially perfect.** Resolution 10/10 PASS, affliction 10/10 FAIL. When the
   referent is **agentive and applicable**, the verdict tracks whether it is the semantic opposite of, or the
   embodiment of, its afflictions.
2. **The affliction mappings are strikingly apt** on the FAIL words (fear→self-doubt, greed→loss-of-discernment,
   anger→destruction, desire→grasping, jealousy→corrosion). This aptness on adversarial words is the core signal.
3. **Emotions separate by valence** (sukha PASS; duḥkha, śoka FAIL; harṣa PARTIAL as *agitated* positive) — a
   non-trivial, correct discrimination.
4. **The FAIL rule (any 0 or mean<50) reliably fires** on definitional afflictions; CR never distorted PR (no
   `HOLISTIC_ONLY_FIT` needed); PMM never touched a verdict.

**Where it fails / is non-discriminative:**
1. **Applicability blindness is the dominant failure mode**, and it is now confirmed at scale. It produces both
   the false positives (§6, vacuous passes) **and** the false negatives (§7, masking) from a *single* cause:
   "non-embodiment" and "resolution" share the score 100.
2. **PARTIAL_FIT is a catch-all for "can't tell."** 20/60 are PARTIAL, concentrated in **body parts (5/6)** and
   **abstracts (4/5)** — neutral instruments and double-edged concepts land at ~50–67 because the psychic
   afflictions neither clearly apply nor clearly resolve. PARTIAL is absorbing genuine indeterminacy.
3. **Threshold rater-sensitivity.** Nine verdicts sit exactly on 75.0 or 50.0; a single 25-point component
   re-score flips PASS↔PARTIAL or PARTIAL↔FAIL (jñāna, gṛha, vṛka, agni, bhakti). A second independent rater
   could plausibly move the PASS/PARTIAL/FAIL split by several words.
4. **The subtle-affliction shadow** (s = "sattvic clinging / golden chain"; v = "rigid over-holding")
   systematically drags virtues/abstracts to PARTIAL (satya, ahiṃsā, vidyā, smṛti). This may be *correct*
   (self-righteousness, pedantry are real) or *over-penalizing* — the pilot cannot tell, which is itself a finding.

## Is the frozen methodology sufficiently discriminative? (the question asked)

**At the poles, yes — decisively.** The clean 10/10 ∕ 10/10 split and the aptness of the affliction hits are
genuine, quantified support. **In the middle, no.** Roughly one-third of the sample (inanimate objects + neutral
body parts, ~14 words) yields verdicts that are either **vacuous** (pass without testing the theory) or
**indeterminate-in-disguise** (PARTIAL), and the *same* applicability gap lets a few destructive referents
(tiger, wolf, time, fire) escape FAIL. The valence signal is real and would survive; but as frozen, the
methodology cannot yet be called broadly discriminative, because a large minority of verdicts are artifacts of
scoring inapplicable components rather than measurements of resolution.

This confirms — now across 60 words and every category — the single structural gap the pilot flagged
(applicability), and adds a second quantified observation (threshold rater-sensitivity). Both are **reported, not
redesigned**: per instruction, no gate, scale, or threshold was changed.

## Guardrails
Expanded developmental stress-test. Parser, mappings, lexicon (v3), scales, gates, thresholds, verdict logic, and
methodology run exactly as frozen and unmodified; no new theory, gate, control, or scoring rule; no B1.12 work.
Single-rater interpretive PR scores — not confirmatory evidence. Structure, not validated meaning.

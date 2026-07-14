# Varṇa Feature-Lift — Exclusion Audit V1 (review before freeze is trusted)

**Audit only. The frozen dataset is NOT modified.** No manifest, prereg, parser, or lexicon is changed. This
reviews all 18 excluded candidates from `VARNA_FEATURE_LIFT_PRERUN_FREEZE_REPORT.md` (commit `dfee8fd`) and, for
each, states (a) the gloss, (b) the recorded reason, (c) my honest verdict — **genuinely required by the
preregistration** vs **a conservative methodological choice** — and (d) any reasonable alternative gloss that
would have allowed inclusion, with why it was not used. `EXPLORATORY / DEVELOPMENT_ONLY /
NOT_CONFIRMATORY_EVIDENCE`.

## Integrity caveat (read first)

To answer "would a reasonable alternative gloss have allowed inclusion," I looked up the Warriner arousal/valence
values of candidate alternative glosses (e.g. *desire*, *goose*, *movement*, *flame*). **That means the target
values for those specific alternatives are now known to me.** Under the prereg's outcome-blind rule (§3, §6:
glosses precommitted *before* any target metric is seen; "recorded, **not replaced**"), those alternatives can no
longer be hand-selected into a rebuilt dataset without contaminating blindness — I could now be steering inclusion
toward favorable arousal values. **Therefore:** this audit is legitimate as a *review*; but any V1.1/V2 rebuild
must select glosses by a **fixed, pre-registered, target-blind rule** (e.g. "the first Monier-Williams gloss," or
a fixed independent gloss source), **not** by me choosing from the alternatives priced below. The prices below are
shown only to demonstrate that inclusion was *lexically possible*, not to pick winners.

## Verdict legend

- **REQUIRED** — forced by the prereg with no reasonable rescue; the exclusion should stand in any version.
- **REQUIRED-GIVEN-PRECOMMIT** — forced by the prereg's no-replacement rule *given the gloss that was
  precommitted*, but a different **blind** precommit gloss could plausibly have included the word. Rescuable only
  by a versioned, blind re-glossing — not by editing this freeze.
- **CONSERVATIVE** — an exclusion driven by a methodological rule I added (`MATERIAL_GLOSS_VALENCE_CONFLICT`,
  `PROPER_NAME_OR_TECHNICAL_TERM`) that the prereg does not strictly mandate; a single dominant ordinary gloss
  plausibly exists and is present in the lexicon, so the word could defensibly have been included.

## What the prereg actually mandates

§3: "each attested Sanskrit word → its **single dominant ordinary English gloss** (recorded at word-precommit
time); the gloss **must exist in the norms lexicon or the word is excluded (recorded, not replaced)**." So the
only *hard* prereg exclusion is **gloss-absent-from-lexicon** (plus the anti-replacement rule). "Single dominant
gloss" implies words with no dominant gloss are unusable — but *how strict* to be about polysemy is a
methodological choice I made, not a prereg number. `DUPLICATE_ENGLISH_GLOSS` is a genuine **dependence** control
(distinct labels required for independence) and was named in the frozen task taxonomy.

---

## A. `NO_EXACT_NORM_MATCH` (2) — the hard, prereg-mandated rule

| ID | IAST | Gloss | Verdict | Alternative (lexically present) | Why not used |
|---|---|---|---|---|---|
| S022 | gamana | going | **REQUIRED-GIVEN-PRECOMMIT** | *movement* (present, unused) — *motion* present but **taken by gati S024** → would be duplicate; *walking* absent | "going" was the precommitted gloss; §3 forbids replacing it. *movement* is a defensible blind alternative that would include it in a V2. |
| S032 | haṃsa | swan | **REQUIRED-GIVEN-PRECOMMIT** | *goose* (present, unused) | "swan" (the conventional poetic translation) is absent from Warriner; *goose* is arguably the more literal gloss (haṃsa = goose/gander) and is present. Rescuable only by a blind re-glossing or a broader norm set (e.g. NRC-VAD includes *swan*). |

**Assessment.** These two are correctly excluded *as frozen* — the rule is unambiguous and the anti-replacement
rule is what protects the experiment from gloss-shopping. But both are **artifacts of the initial gloss choice /
the chosen lexicon**, not evidence the words are unusable. They are the strongest motivation for a future version
with either revised blind glosses or a wider-coverage norm dataset. Exactly the *haṃsa*/*gamana* cases you
flagged.

## B. `MATERIAL_GLOSS_VALENCE_CONFLICT` (10) — mostly conservative

| ID | IAST | Gloss | Verdict | Dominant-gloss present in lexicon? | Note |
|---|---|---|---|---|---|
| S047 | kāma | desire | **CONSERVATIVE** | *desire* present (A=6.20) | "desire" is a defensible single dominant gloss; excluded only out of caution over desire/love/lust. Your flagged example — plausibly includable. |
| S027 | go | cow | **CONSERVATIVE** | *cow* present (A=2.95) | "cow" is *go*'s primary ordinary meaning; the earth/ray/speech senses are secondary/poetic. Plausibly includable. |
| S009 | bhojana | food | **CONSERVATIVE** | *food* present (A=4.69) | "food" is dominant over meal/eating. Plausibly includable. |
| S048 | kṣetra | field | **CONSERVATIVE** | *field* present (A=3.84) | ordinary "field" dominates the body/sacred-place technical senses. Plausibly includable. |
| S059 | mukha | face | **CONSERVATIVE** | *face* present (A=4.59) | "face" dominant over "mouth". Plausibly includable. |
| S074 | rakta | blood | **CONSERVATIVE** | *blood* present (A=5.76) | noun "blood" dominant; "red" is the adjectival sense. Plausibly includable. |
| S090 | varṣa | rain | **CONSERVATIVE** | *rain* present (A=3.29) | "rain" dominant over "year". Plausibly includable. |
| S040 | kara | hand | **CONSERVATIVE, but also would-be duplicate** | *hand* present (A=3.98) **but taken by hasta S031** | even relaxed, kara→"hand" collides with included *hasta* → `DUPLICATE_ENGLISH_GLOSS`. So exclusion is over-determined; a distinct blind gloss (e.g. "ray"/"tax") is not dominant. Reasonable to leave out. |
| S053 | mada | pride | **BORDERLINE (lean conservative)** | *pride* present (A=5.54) | pride vs intoxication is a genuine split, but "pride" is arguably dominant in modern usage. Defensible either way. |
| S016 | dharma | virtue | **CLOSEST TO REQUIRED** | *virtue/duty/law/righteousness* all present | *dharma* is famously untranslatable — there is genuinely **no** single dominant ordinary gloss. This is the one member of this group whose exclusion is nearly prereg-required (fails "single dominant gloss"). Keep excluded. |

**Assessment.** 8 of 10 are **conservative** — a single dominant gloss exists and is priced in the lexicon, so
these words were excluded by my extra caution, not by the prereg. Only *dharma* is close to genuinely required;
*kara* is over-determined by the duplicate collision. This is the category most worth revisiting in a V2 — it is
the largest source of potentially-informative omissions (e.g. *kāma*, the theory's most central word).

## C. `PROPER_NAME_OR_TECHNICAL_TERM` (3) — conservative

| ID | IAST | Gloss | Verdict | Gloss present? | Note |
|---|---|---|---|---|---|
| S014 | deva | god | **CONSERVATIVE** | *god* present (A=5.56) | *deva* is a common noun ("a god"), not a proper name; "god" is ordinary English with a norm. Excluding it is a judgment call, not prereg-mandated. Plausibly includable. |
| S098 | yajña | sacrifice | **CONSERVATIVE (borderline)** | *sacrifice* present (A=4.95) | "sacrifice" is ordinary English; *yajña* is specifically Vedic ritual, so the gloss is a broadening. Defensible either way. |
| S101 | ātman | self | **BORDERLINE (lean required)** | *self* present (A=4.78), *soul* present | *ātman* is doctrine-laden (self/soul/metaphysical Self); the ordinary gloss carries philosophical baggage the affect norm won't capture. More defensible to exclude than deva/yajña. |

**Assessment.** *deva* and *yajña* are conservative exclusions of words that have perfectly ordinary English
glosses with norms; *ātman* is more defensibly excluded. None is strictly prereg-required.

## D. `DUPLICATE_ENGLISH_GLOSS` (3) — genuine dependence control, but casualty is arbitrary

| ID | IAST | Gloss | Collides with | Verdict | Distinct alternative present | Note |
|---|---|---|---|---|---|---|
| S068 | parvata | mountain | giri (S026) | **REQUIRED (dependence)** | *hill* present (A=3.15), distinct | identical labels break independence; correctly dropped. But *which* synonym is kept is arbitrary-mechanical (first IAST). A blind re-gloss (parvata→"hill") could keep both in a V2 — at some cost to gloss fidelity. |
| S088 | vahni | fire | agni (S001) | **REQUIRED (dependence)** | *flame* present (A=6.60), distinct | same; vahni→"flame" is a defensible distinct gloss for a V2. |
| S093 | vānara | monkey | kapi (S039) | **REQUIRED (dependence)** | *ape* present (A=4.25), distinct | same; vānara→"ape" defensible for a V2. |

**Assessment.** The dependence rule itself is **required** — two words with the same English label would be
non-independent samples. Correct as frozen. The nuance: the *specific* word dropped is arbitrary, and each dropped
word has a distinct near-synonym gloss that would let both survive in a blind-reglossed V2. Whether that is worth
doing is a fidelity-vs-coverage tradeoff, not an integrity fix.

---

## Summary tally

| Verdict | Count | Words |
|---|---|---|
| REQUIRED (stands in any version) | 4 | dharma*, parvata, vahni, vānara (*dharma near-required) |
| REQUIRED-GIVEN-PRECOMMIT (blind re-gloss could rescue) | 2 | gamana, haṃsa |
| CONSERVATIVE / borderline (plausibly includable) | 12 | kāma, go, bhojana, kṣetra, mukha, rakta, varṣa, kara, mada, deva, yajña, ātman |

So **~12 of 18** exclusions are conservative or precommit-artifacts rather than logically forced. As frozen, the
dataset is **defensible and internally honest** — every exclusion traces to a pre-declared rule, and the
no-replacement rule is exactly what stops gloss-shopping. But it is **not maximally inclusive**: a blind, more
permissive gloss policy and/or a broader norm lexicon would likely recover a meaningful fraction of these
(especially the `MATERIAL_GLOSS_VALENCE_CONFLICT` group, which contains the theory's most central words like
*kāma*).

## Recommendation (no change made here)

1. **Keep V1 frozen and usable as-is.** N=88 is well above the floor; nothing about V1 is dishonest or broken. The
   lift run can proceed on V1.
2. **If broader coverage is wanted, do it as a versioned rebuild — never by editing this freeze.** A `V1.1`/`V2`
   preregistration should change the *rules*, not the outcomes:
   - relax `MATERIAL_GLOSS_VALENCE_CONFLICT` to "exclude only when **no** single dominant ordinary gloss exists"
     (this would likely readmit *kāma, go, bhojana, kṣetra, mukha, rakta, varṣa*; keep *dharma* out);
   - narrow `PROPER_NAME_OR_TECHNICAL_TERM` to true proper names only (readmits *deva, yajña*);
   - allow **blind** distinct re-glossing for `DUPLICATE_ENGLISH_GLOSS` and `NO_EXACT_NORM_MATCH` cases
     (*parvata→hill, vahni→flame, vānara→ape, haṃsa→goose, gamana→movement*) — but chosen by a fixed rule, **not**
     by me, and **not** using the arousal values surfaced in this audit;
   - consider a wider-coverage norm lexicon (e.g. NRC-VAD, which contains *swan*, *going*) to eliminate the
     `NO_EXACT_NORM_MATCH` losses without re-glossing.
3. **Critical constraint on any rebuild:** because this audit exposed the target values of specific alternative
   glosses, the V2 gloss-selection rule must be **mechanical and target-blind**, and ideally the gloss list should
   be regenerated by an independent/precommitted procedure so my having seen these values cannot bias inclusion.

**Guardrails.** Audit only; no frozen artifact, prereg, parser, or lexicon modified. The V1 dataset stands as
frozen. Any rule change requires a new versioned preregistration and a from-scratch, target-blind rebuild.
Structure, not validated meaning.

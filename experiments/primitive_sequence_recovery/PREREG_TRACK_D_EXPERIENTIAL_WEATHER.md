# Pre-Registration — Track D (Experiential Semantic-Weather Recovery) — a FALSIFICATION PROTOCOL (docs only)

**This document is written as a falsification protocol, not a supportive theory essay.**
"Experiential semantic weather" is treated here as a **high confirmation-bias / Barnum-effect
risk conjecture, NOT a validated construct.** The default expectation is `NO_SIGNAL`; the burden
is on the real composition to survive a battery of controls designed to *kill* the hypothesis.
Every section below exists to make the conjecture **refutable**.

**Pre-registration of a NEW, exploratory hypothesis. Nothing implemented, run, or changed.**
No code, no experiment, no artifact mutation, no threshold change, no Stage A change, no
`manifest_v2`. `manifest.json` remains NOT_READY; the runner remains NOT_RUN; **Track B remains
BLOCKED.** This is **not** a rescue of Track C and does **not** weaken the recorded Track C V1
conclusion (no robust dictionary-referent signal). It is a **distinct** hypothesis from
`PREREG_TRACK_D_INCREMENTAL_UTILITY.md`; both are exploratory; neither is Track B.

### Skeptical preamble (read before the sections)
This hypothesis is the **most confirmation-bias-prone** in the entire program. "Emotional
atmosphere / lived resonance" is vague enough that, without hard controls, *any* affliction-gloss
composition can be argued post-hoc to "match" *any* emotional profile (a Barnum/Forer effect).
The **entire scientific value** of this pre-registration is the machinery that makes the claim
**falsifiable**: blind profile authoring, frozen profiles, a fixed scorer, the scramble/decoy
controls, hard-negative distractors, and a concrete-noun negative-control domain. If those are
not honored, a "positive" here is worth **less** than the (already non-robust) Track C result,
not more. A positive is expected to be *hard* to obtain honestly; the most likely outcome, given
Track C, is `NO_SIGNAL`.

---

## 1. Question

> Does the **real** varṇa/vṛtti gloss composition of a word predict that word's
> **pre-registered experiential semantic-weather profile** (emotional atmosphere, psychological
> field, inner tendency) **better than** scrambled-assignment, equal-length decoy, and
> dictionary-referent controls — with the effect robust to seeds, resampling, and a
> concrete-noun negative control?

The unit of the claim is **incremental match to a frozen experiential profile**, not recovery of
a dictionary referent (which Track C V1 tested and did not robustly support).

## 2. What this can and cannot prove

**Can test:** whether the representation carries **incremental signal** for pre-registered
experiential profiles — i.e., whether the *real* varṇa assignment matches a word's frozen
emotional profile better than controls, on abstract/psychological words, robustly.

**Cannot prove (must never be claimed):**
- intrinsic ontology, spiritual truth, or that varṇa meanings are "real";
- **Sanskrit privilege** (that Sanskrit is special vs any language);
- `ONTOLOGICAL_SIGNAL` of any kind;
- **cannot unblock Track B** (independence is still absent; the profiles and the scorer are both
  human/English-mediated).
- A positive supports only: "the varṇa composition is *predictive of a frozen experiential
  profile in this setup*," and even that is capped by the leakage/Barnum risks below.

**Elevated risk (stated as a limit, not a hedge):** because profiles and matching are subjective
and loose, this design is at high risk of **practical unfalsifiability** unless §5/§9/§10 are
strictly honored. Report that risk with any result.

## 3. Motivating example (illustrative only — must NOT be used to tune the test)

`hṛdaya` (heart) → consonant-only `ha·da·ya` → glosses **night + peevishness +
lack-of-confidence**. This **fails dictionary recovery** (it shares nothing with "heart"; Track C
ranked it last). The *revised* conjecture is that this composition might instead describe the
**emotional weather** of "heart" — vulnerability, emotional darkness, hurt, sensitivity,
confidence-fragility.

**This example is illustrative only.** It was observed *after* Track C and therefore **cannot**
be used to author `hṛdaya`'s profile, choose descriptors, pick the scorer, or set any threshold —
doing so would be circular. `hṛdaya`'s profile (if it is even included) must be authored blind by
annotators who have **not** seen its decomposition (§5), and this example word may be **held out**
entirely to avoid contamination.

## 4. Dataset design

- **Include:** abstract, psychological, emotional, relational, moral, and inner-state terms —
  the domain where an "experiential weather" claim is even meaningful (e.g. krodha, bhaya, moha,
  śānti, ānanda, lobha, mamatā, kṣamā, dharma, māyā, …).
- **Exclude** mostly-concrete nouns **unless** they carry an independently pre-registered
  experiential profile authored blind (rare; default is exclude).
- **Concrete-noun negative-control domain (required):** a held-out set of concrete nouns (deer,
  honey, chariot, field, …). If these show "weather signal" comparable to abstract words, the
  positive is a **Barnum artifact** (everything matches everything) → invalidates any abstract
  positive.
- **Vowel-aware / prefix-aware decomposition** included where relevant (a new ontology extension;
  see the vowel-aware caveats in `DROPPED_VOWEL_ANTONYM_PROBE.md`), scored **alongside** the
  consonant-only decomposition (arms G vs H) — never silently swapped.
- Corpus, splits, and any new decomposition are **frozen and hashed before scoring**; the test
  set is touched once.

## 5. Profile construction (the linchpin)

- For each target word, a **pre-registered experiential-weather profile** is authored **before
  any scoring** and **frozen** (hashed).
- **Blindness (mandatory):** profiles are written by annotators who have **not** seen the varṇa
  decomposition or the vṛtti glosses — only the word and its dictionary meaning. This prevents
  authoring profiles that fit the glosses.
- **Multiple independent annotators (≥2–3)** per word; report **inter-annotator agreement**;
  profiles with low agreement are flagged/excluded (a word with no consensus "emotional weather"
  cannot be a fair target).
- **Format:** 8–20 descriptors, e.g.
  `heart: vulnerability, affection, hurt, grief, courage, trust, emotional-center, longing,
  openness, contraction, sensitivity`.
- Descriptors drawn from a **fixed controlled vocabulary** (a closed emotional/psychological
  lexicon) so profiles are comparable and distractor profiles are well-formed.
- **Descriptor-specificity rule (anti-Barnum):** descriptors must be **specific enough to be
  wrong.** Vague universal terms that could fit almost any word — e.g. "energy," "inner
  movement," "blockage," "resonance," "life force," "vibration," "flow" — are **banned** unless
  operationalized into a concrete, discriminating sense. A profile made of universals is
  disqualified (it cannot be falsified).
- **Hard-negative neighbor profiles (mandatory):** each target must have distractor profiles that
  are **emotionally adjacent but conceptually distinct**, so the task is discrimination, not
  vague fit. Example neighbor cluster: `heart` vs `grief` vs `fear` vs `ego` vs `mind` vs `love`.
  Ranking the *specific* target profile above these near-neighbors is the real test.
- Profiles are the **frozen ground truth**; they are never edited after scoring begins
  (**held-out profile construction** — no descriptor tuning after seeing any result).

## 6. Arms / controls

Fixed scorer and data across all arms; only the composition/reference varies:

| arm | composition / reference scored against the frozen profiles |
|---|---|
| **A** | **real** varṇa/vṛtti composition |
| **B** | **scrambled** varṇa assignment (same glosses, permuted) |
| **C** | **equal-length affliction-gloss decoy** (random vṛtti-gloss set of equal length/token budget, non-real assignment) |
| **D** | **dictionary-referent** baseline (the word's own dictionary gloss) |
| **E** | **lexical-only** baseline (token overlap, no embedding) |
| **F** | **etymology-only** baseline (if an etymology source is available) |
| **G** | **vowel-aware** real composition |
| **H** | **consonant-only** real composition |
| **I** | **Barnum baseline family** — a **small fixed family** of broad "could-fit-many-words" profiles (built from the banned universal descriptors), scored per target against its **best-scoring** member (§6.1) |

Comparisons of interest: A vs B, A vs C, A vs E, A vs F, A vs I, G vs H; D is the (already
non-robust) dictionary contrast reported separately (§13).

### 6.1 Barnum baseline family (the decisive control)

Instead of one generic profile (which can be accidentally weak), use a **fixed family of Barnum
profiles**, frozen before scoring:

1. **generic-emotional** Barnum profile,
2. **spiritual/transformation** Barnum profile,
3. **affliction/wound** Barnum profile,
4. **inner-growth** Barnum profile.

Each is a broad, non-discriminating profile from the banned universal vocabulary, intended to
loosely fit many words. For every target, compute the score of the **best-scoring Barnum family
member** (the max over the four) and treat that as the Barnum bar.

**Decision rule (strict):** if the real composition ranks **any** Barnum family profile **at or
above** the target's specific frozen profile — equivalently, if A does **not** beat the
**best-scoring** Barnum member — the result is **`NO_SIGNAL`**, regardless of A vs B/C/E/F. A
hypothesis that matches a one-size-fits-all profile (of any flavor) has predicted nothing.

**Scoring operationalization (declared, since it reintroduces realizer/leakage risk):** a
composition is scored against a profile by a **fixed, pre-registered semantic scorer** (e.g.
mean-pooled static-embedding cosine between the composed gloss text and the profile descriptor
set, per the frozen realizer conventions), ranking the word's **own** profile against distractor
profiles. The scorer is frozen before scoring and inherits every Track C caveat (English
leakage, determinism, hash-pinned asset). An LLM scorer, if ever used, requires the §9
contamination probe and is exploratory-only.

## 7. Primary endpoint

Real varṇa/vṛtti composition (arm A) must **rank its own frozen experiential profile above
distractor profiles** better than the controls (B, C, E), on the abstract/psychological domain.
- Metrics: **MRR**, **Top-1**, **pairwise accuracy** (real-profile vs one distractor).
- **Chance baselines predefined:** for K candidate profiles, chance MRR = `(1/K)Σ_{r=1}^{K}1/r`,
  chance Top-1 = `1/K`, chance pairwise = 0.5.
- A primary positive requires A to beat **all of**: scrambled (B), equal-length affliction-gloss
  decoy (C), lexical (E), etymology (F, if available), **and the best-scoring member of the
  Barnum baseline family (I, §6.1)** on the primary metric, with the §10 robustness gate
  satisfied. **Failing the Barnum comparison alone forces `NO_SIGNAL`.**

## 8. Secondary endpoints

- **Incremental over lexical** (A − E).
- **Incremental over etymology** (A − F), if F available — varṇa must add *beyond* etymology.
- **Vowel-aware gain** (G − H).
- **Domain split:** abstract/psychological subset **vs** concrete negative-control subset — a
  valid positive requires the abstract subset to show signal **and** the concrete control to
  **not** (else Barnum).

## 9. Leakage controls

- **Direct token-overlap detection:** flag any word whose composed glosses share surface tokens
  with its profile descriptors; measure how much of the effect is such overlap.
- **Tautology flag:** explicitly flag cases like `kāma` where a gloss literally contains a
  descriptor (e.g. gloss "…desire" and profile "desire") — the Track C V1 audit found this was
  the *only* lexical hit; such cases are excluded or reported separately.
- **Bare-word probe:** can the scorer match the profile from the **bare word** alone (priors)?
  If so, channel gains are attenuated/uninterpretable.
- **Profile-only probe:** can profiles be told apart without any composition (are they
  degenerate/too similar)? If distractor profiles are near-identical, ranking is meaningless.
- Leakage/tautology cases are **excluded from the primary** and reported separately.

## 10. Robustness requirements

- **Multiple scramble seeds** (≥5) for arm B; report the p distribution (Track C lesson: a single
  seed under 0.05 is not enough — one seed there crossed 0.05).
- **Bootstrap CI on every delta** (A−B, A−C, A−E, A−F, G−H); **no positive unless the CI
  excludes 0** and p is **stable across seeds**.
- **Hard-negative distractor profiles** (semantically adjacent, matched), not easy random ones.
- **Family-aware bootstrap** (resample word families, not items).
- **Multiple-comparison correction** across arms × metrics × domains (pre-registered).
- **Inter-annotator agreement** reported for profiles; low-agreement targets excluded.
- Test set touched once; no threshold tuning, no metric switching, report all.

## 11. Decision labels

**Allowed only:**
- `EXPERIENTIAL_WEATHER_SIGNAL` — A beats **B, C, E, F, and the best-scoring member of the
  Barnum baseline family (I, §6.1)** on the abstract domain; ranks specific target profiles above hard-negative neighbors; CI excludes 0;
  p stable across seeds; concrete negative-control shows no comparable signal; not explained by
  leakage/tautology words; not explained by etymology; survives with vague/universal descriptors
  banned. Anything short of this full conjunction is **not** a signal.
- `NO_SIGNAL`
- `REALIZER_DEPENDENT` — result flips across scorers/encoders.
- `INCONCLUSIVE` — CI includes 0, underpowered, low profile agreement, or controls not separable.

**Forbidden:** `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, and any language implying Track B is
unblocked or the ontology is validated.

## 12. Failure interpretations (defined in advance — any one triggers a non-signal verdict)

- **Does not beat the Barnum baseline family** — A ≤ best-scoring Barnum member (§6.1): real
  matches some one-size-fits-all profile (emotional / spiritual / affliction / inner-growth) at
  least as well as the word's specific one → **`NO_SIGNAL`** (the primary Barnum failure).
- **Only works for vague profiles** — signal present only when profiles contain
  universal/banned descriptors; disappears under the specificity rule → **`NO_SIGNAL`** (Barnum).
- **Disappears under hard negatives** — A ranks the target profile above *easy* distractors but
  not above emotionally-adjacent neighbors (heart vs grief/fear/ego/…) → **`NO_SIGNAL`**.
- **Depends on leakage/tautology words** — effect vanishes once §9 token-overlap/tautology cases
  (e.g. `kāma`) are removed → **English gloss leakage**, not signal.
- **Explained by etymology** — A−F ≈ 0 → varṇa redundant with etymology.
- **Explained by English gloss overlap** — effect traces to surface English token overlap
  between glosses and descriptors, not composition.
- **`NO_SIGNAL` (scramble)** — A ≈ B on profiles.
- **Dictionary-only artifact** — apparent signal traces to arm D, not the varṇa composition.
- **Semantic-realizer dependency** — present under one scorer, absent under another →
  `REALIZER_DEPENDENT`.
- **Domain mismatch / Barnum (corpus level)** — concrete negative-control also "matches" →
  everything matches everything; abstract positive invalidated.
- **Vowel/prefix-loss only** — gain localized to the ~3 collision-type cases (G−H), not general.

## 13. Reporting template

Report **separately** (never collapse dictionary and experiential into one number):

| axis | metric | real (A) | scrambled (B) | decoy (C) | lexical (E) | etym (F) | chance | CI (A−ctrl) | verdict |
|---|---|---|---|---|---|---|---|---|---|
| **dictionary-referent recovery** | MRR/Top1 | | | | | | | | (expected ≈ Track C: none) |
| **experiential-weather recovery** | MRR/Top1/pairwise | | | | | | | | |
| **abstract/psychological subset** | " | | | | | | | | |
| **concrete negative-control subset** | " | | | | | | | | (must be ~chance) |
| **vowel-aware (G) vs consonant-only (H)** | " | G | | | | | | (G−H) | |
| **real vs scrambled** | " | A | B | | | | | (A−B) | |
| **real vs lexical** | " | A | | | E | | | (A−E) | |
| **real vs etymology** | " | A | | | | F | | (A−F) | |
| **real vs Barnum family (best member)** | " | A | | | | | max(I₁..I₄) | (A − best Barnum) | (must be > 0, else NO_SIGNAL) |

Plus: leakage/tautology cases excluded (list), inter-annotator agreement, seed-wise p, and the
domain-split comparison.

## 14. Final boundary statement

This Track D test evaluates experiential semantic-weather recovery only. It does not validate
intrinsic ontology, spiritual truth, Sanskrit privilege, or `ONTOLOGICAL_SIGNAL`. Track B remains
blocked. Structure, not validated meaning.

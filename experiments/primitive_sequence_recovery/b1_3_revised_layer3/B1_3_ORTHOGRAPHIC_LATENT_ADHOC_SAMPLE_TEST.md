# B1.3 — Orthographic-Latent / Silent-Consonant Ad Hoc Sample Test (exploratory)

## 1. Scope

Exploratory ad hoc review only. **No evidence claim · no active-artifact modification · no v2 stimulus change ·
no freeze-review / scorer change · no judge run · no scoring · no EVIDENCE_FREEZE · no freeze impact.** The
active B1.3 concrete-object study remains **spoken-phoneme-only**; this note only inspects whether a *future*
orthographic-latent ablation is worth specifying. **Structure, not validated meaning.**

## 2. Why this test exists

The `knife` walkthrough showed the spoken-only route (`N`, `F` → `nna`, `pha`) **omits the written silent `K`**.
A folk intuition says the silent `K` might encode latent "detachment / cutting-away." **This must not be
patched into the current study after seeing `knife`** (that would be a post-hoc rescue). It can only motivate a
*future, pre-registered* ablation. This note checks, across a silent-consonant sample, whether that intuition
holds broadly or is cherry-picked.

## 3. Candidate rules

- **A. Spoken-only** — only pronounced phonemes count. **(Active B1.3 rule.)**
- **B. Orthographic-additive** — written consonants count even when silent.
- **C. Silent-liberating** — silent consonants are acoustically withdrawn → **liberating/withdrawn** pole.
- **D. Silent-binding** — silent consonants remain graphically present → **binding/latent-imprint** pole.
- **E. Dual-pole silent** — silent consonants contribute both poles weakly / reported ambiguous.
- **F. Weighted hybrid** — pronounced full weight; silent attenuated weight.

## 4. `knife` worked example

- **Spoken-only:** `N`,`F` → `nna` (binding), `pha` (binding) → v2 tags `sting, flight, …`.
- **Silent `K` route:** written `K` → varṇa **`ka`**.
- **Why silent-`K`-as-liberating-detachment *seems* attractive:** a withdrawn/unvoiced letter reading as a
  "cutting-away" liberating modifier is poetically tidy for a knife.
- **CORRECTION (operator note, post-commit):** an earlier draft of this bullet judged the silent `K` against
  `ka`'s **binding** pole ("hope as grasping / clinging to a specific outcome") and concluded "ka = hope, not
  cutting." That was **unfair to the stipulated rule**, which is **silent consonants take the LIBERATING
  polarity** (rule C). Under the liberating pole, `ka`'s frozen bridge-pool gloss is *"forward-orientation held
  without attachment to the outcome — aspires and acts while releasing the grip on the result"* — a
  **non-attachment / releasing-the-grip / letting-go** reading, i.e. **detachment-flavored, not
  "hope-as-grasping."** So under the intended rule the silent `K` maps toward **detachment**, and the harsh
  "flagship fails at the gloss level" framing is **withdrawn**.
- **Where an adversarial caveat still holds:** `ka`-liberating is *psychological non-attachment to an outcome*
  (a mental/vṛtti detachment). A knife's function is *physical severance / cutting*. "Non-attachment →
  detachment → cutting-away" is a real semantic slide — **closer than 'hope,' but not yet 'a knife cuts.'** The
  reading lands on `knife` only by fixing silent→liberating **and** reading non-attachment as cutting.
- **Why a fixed rule (not a patch) is required:** picking the liberating pole *because it makes knife work* is
  the post-hoc risk. To be legitimate, "silent = liberating" must be **pre-registered and applied uniformly**
  to every word (§7 ablation) — where `ba`/`ga`-liberating mostly will not fit `lamb`/`comb`/`thumb`/`debt`/
  `doubt`. The correction strengthens the case for *specifying* the ablation; it does not by itself validate a
  silent-`K`-as-cutting mapping.
- **The lexicon is not modified:** `ka`'s glosses are quoted verbatim from the frozen bridge pool; nothing in
  `varna_lens/` or the active study is changed.

## 5. Cross-sample review (20 words, spoken-only route verified via cmudict)

Silent/latent consonant → varṇa it *would* add (B–F). Under the stipulated **silent-liberating** rule (C) the
relevant pole is the **liberating** gloss: `ka`-lib = *non-attachment / releasing the grip* (detachment-
flavored); `ba`/`ga`/`va`-lib = the respective liberating poles. "Improves fit?" is a one-reader qualitative
impression under the **silent-liberating** rule, **not** a score.

| word | ordinary object-function | spoken route (varṇa) | silent/weak cons | latent add | polarity under B–F | improves fit? (silent-liberating) | cherry-pick risk |
|---|---|---|---|---|---|---|---|
| knife | cutting tool | nna,pha | **K** | ka-lib (*non-attachment/detachment*) | ign/bind/lib/dual | **Partly** — detachment-adjacent, but ≠ physical cutting | high (flagship, post-hoc) |
| knot | tied loop | nna,tta | **K** | ka-lib | " | No — non-attachment ≠ knotting/binding | high |
| knock | strike | nna,ka | **K** | ka-lib (dup of spoken ka) | " | No — redundant with spoken ka | high |
| knee | joint | nna | **K** | ka | " | No | high |
| lamb | young sheep | la,ma | **B** | ba | ign/bind/lib/dual | No — ba unrelated | high |
| comb | grooming tool | ka,ma | **B** | ba | " | No | high |
| thumb | digit | ta,ma | **B** | ba | " | No | high |
| debt | money owed | dda,tta | **B** | ba | " | No | high |
| doubt | uncertainty | dda,tta | **B** | ba | " | maybe (ba weak) | high |
| subtle | fine/faint | sa,tta,la | **B** | ba | " | No | high |
| sign | mark/token | sa,nna | **G** | ga | ign/bind/lib/dual | No | high |
| design | plan/form | dda,sa,nna | **G** | ga | " | No | high |
| light | illumination | la,tta | **GH** | ga/ha | " | No | high |
| night | dark period | nna,tta | **GH** | ga/ha | " | No | high |
| bridge | crossing span | ba,ra,ja | (D,G folded into JH) | — | n/a | n/a — no truly silent extra | low |
| rope | binding fibre | ra,pa | (silent E only) | — | n/a | n/a — no silent consonant | low |
| key | lock opener | ka | (none) | — | n/a | n/a | low |
| door | barrier | dda,ra | (none) | — | n/a | n/a | low |
| wall | barrier | va,la | (doubled L only) | — | n/a | n/a | low |
| sword | bladed weapon | sa,ra,dda | **W** | va | ign/bind/lib/dual | No — va unrelated | high |

**Answers to the review questions:**

- **Does silent-liberating improve many examples or only `knife`?** Under the stipulated silent-liberating
  rule, it improves **only `knife`** (and there only *partly*: `ka`-liberating = non-attachment/detachment,
  detachment-adjacent but still ≠ physical cutting). For the other silent-consonant words it does **not** help —
  so the gain, such as it is, is **selective and concentrated on the one word that motivated the idea**.
- **Does it hurt lamb/comb/thumb/debt/doubt?** Yes — a silent `B`→`ba` pole is **functionally unrelated** to a
  sheep, a comb, a digit, a debt, or uncertainty; adding it injects noise.
- **Systematic or cherry-picked?** Any apparent gain is **selective and post-hoc**; there is no rule under
  which silent inclusion helps broadly.
- **Better object-function fit or just more degrees of freedom?** Overwhelmingly **more degrees of freedom**:
  each silent consonant adds a varṇa with up to 4 pole options (B–F), a large combinatorial space in which one
  can almost always find *some* reading that "fits" — the definition of overfitting.
- **Falsifiable predictions?** Only if a **single rule is fixed and pre-registered** with all controls; ad hoc
  rule-shopping across B–F is not falsifiable.

## 6. Recommendation

```
RECOMMENDATION: ORTHOGRAPHIC_LATENT_ABLATION_WORTH_SPECIFYING
```

Chosen **not** because the ad hoc read is promising — it is **adverse** (silent inclusion helps no example
cleanly, the flagship `knife` fails at the gloss level, and it mostly adds degrees of freedom). It is worth
specifying because the objection *"you ignored the written/silent consonants"* is a **legitimate methodological
challenge** that should be settled by **one clean pre-registered ablation**, not dismissed by intuition — and
because a fair ablation with the full control set can **permanently close** the orthographic rescue if it fails
(the likely outcome). This is **not** `…TOO_POSTHOC_CLOSE_LINE` (the objection deserves a fair falsification
rather than dismissal) and **not** `…NEEDS_MORE_ADHOC_SAMPLES` (20 words already show the pattern; more ad hoc
sampling would itself invite cherry-picking). **The active B1.3 spoken-only study is not touched.**

## 7. If worth specifying — future pre-registered ablation

`B1_4_ORTHOGRAPHIC_LATENT_SILENT_CONSONANT_ABLATION` (**not implemented here**). It must:

- Compare A_real arms built under **one fixed rule each**: spoken-only · orthographic-additive · silent-
  liberating · silent-binding · silent-dual/weighted-hybrid.
- Judge each against the **same controls** (near/mid/far deranged, scrambled, random, neutral) **and the
  semantic baseline**.
- **Pre-register the rule-to-arm mapping and thresholds before any run** (each rule is one arm; no post-hoc
  rule selection).
- Include the **same style/leakage/quality/register audits** and the semantic-baseline gate.
- **Kill condition:** if no fixed orthographic rule beats spoken-only *and* the semantic baseline across the 53
  objects, the orthographic rescue is **closed** and spoken-only stands.

Honest prior: **low** (this ad hoc read is adverse). The ablation's value is a **clean falsification**, not an
expected win.

## 8. Final status block

```
document:                    B1.3 ORTHOGRAPHIC-LATENT / silent-consonant AD HOC sample test (exploratory)
sample words reviewed:       20 (knife, knot, knock, knee, lamb, comb, thumb, debt, doubt, subtle, sign, design,
                             light, night, bridge, rope, key, door, wall, sword)
silent-liberating help:      broad? NO — selective; helps ONLY knife, and there only partly (ka-lib = non-attachment/detachment, ≠ physical cutting)
strongest "favorable":       knife (ka-liberating = detachment-adjacent under the silent-liberating rule; still ≠ cutting)
strongest adverse:           lamb / comb / thumb / debt / doubt (silent B injects unrelated pole)
cherry-pick risk:            HIGH — mostly adds degrees of freedom; selective post-hoc gains only
recommendation:              ORTHOGRAPHIC_LATENT_ABLATION_WORTH_SPECIFYING (as a clean pre-registered falsification)
active B1.3 artifacts changed: NONE
v2 stimuli changed:          NONE
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
positive signal earned:      NONE
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
```

**Structure, not validated meaning.** This is an exploratory ad hoc inspection only. Under the stipulated
**silent-liberating** rule, the silent `K` in `knife` maps to `ka`-liberating = *non-attachment / releasing the
grip* (detachment-flavored — **corrected** from an earlier draft that wrongly used `ka`'s binding "hope" gloss);
this is detachment-adjacent but still not physical *cutting*, and it helps **only** `knife` while not fitting
the other silent-consonant words. Silent inclusion therefore mostly adds degrees of freedom, and it is
recommended only as a **future pre-registered falsification ablation** — never a patch to the active study.
No active B1.3 or v2 artifact was changed, no judge was run, nothing was scored, prior nulls and closures stand,
Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.

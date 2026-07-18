# B1 Lexicon-Contrastiveness Diagnostic (post-verdict, exploratory)

**Status:** `POST_VERDICT_EXPLORATORY` — recorded 2026-07-04.
**Does NOT change the B1 verdict.** Pre-registered verdict remains **`RANDOM_OR_SCRAMBLED_MATCHES`**.
Track B remains **BLOCKED**. `LIMITED_GENERATION_UTILITY` not supported. No ontology validation · no
Sanskrit privilege · no semantic-truth claim · no Track G rescue. **Structure, not validated meaning.**

Read-only inspection of `varna_lens/varna_lens.py` (LEX) and `sample_text_rule_harness.py` (BRIDGE).
No frozen artifact, judge file, or score modified. This memo asks: *why did random resonance (R) match
A?* It also **fact-checks an external (ChatGPT) analysis** against the actual table.

---

## 1. The meaning pool is substantially non-contrastive (measured)

A and R both draw from the same 64-entry BRIDGE meaning pool. **33 of 64 meanings sit in overlapping
semantic clusters** (share ≥1 content word); e.g.:

- attachment: non-attachment · attachment · blind attachment
- knowledge: mundane · spiritual · false/dogma
- inertia: darkness/inertia · inertia/deep-sleep · desire/inertia/confusion
- joy/affection: joy/affection · sympathetic joy · friendliness/affection
- forgiveness/acceptance: patience/forgiveness · forgiveness/self-acceptance · fearlessness/self-acceptance
- clarity: liberation/clarity · conscience/discriminative clarity
- contentment · fearlessness · greed clusters (each ×2)

With this redundancy, a random pick lands in the same affective neighborhood as a resonance pick →
similar evocative conditioning → the blind judge can't separate A from R.

### Verified consonant-pole collisions (from the real LEX)
Real collisions are mostly on a **shared liberated (positive) pole**, not full duplicates:

| Shared liberated pole | Consonants (blocked → liberated) |
|---|---|
| Vinaya / humility | Ṅa (Dambha→) · Ja (Ahaṁkāra→) |
| Kṣamā / forgiveness | Ṭha (Anutāpa→Ātmaprasāda) · Da (Krodha→Dhairya) |
| Jāgaraṇa / awakening | Ta (Jāḍya→) · Bha (Mūrcchā→) |
| Viśvāsa / trust | Kha (Cintā→) · Ya (Aviśvāsa→) |
| Karuṇā / compassion | Ḍha (Piśunatā→) · La (Krūratā→) *(near-duplicate on both poles)* |
| Viveka / discernment | Ca (Aviveka→) · Na (Moha→) |
| Fearlessness | Ḍa (Lajjā→Nirbhayatā) · Pha (Bhaya→Abhaya) |
| Detachment / release | Ka (→Nirāśā) · Gha (→Anāsakti) · Dha (→Nivṛtti) |

Big **blocked-pole basin** (all read as clinging/lack): Gha attachment · Dha craving · Jha greed ·
Śa material-greed · Na blind-attachment · Ssa desire. Aversive basin: Pa hatred · Ḍha/La cruelty.

## 2. The deeper problem: the mapping is arbitrary w.r.t. word meaning

Contrastiveness is only half the story. What A **selects for real words** does not track the word's
meaning (selection is driven by phonemes, not sense):

| Word | A's resonance-selected conditioning | fits the word? |
|---|---|---|
| grief | action → stillness, fearlessness | no |
| justice | ego inflation → humility, clarity | no |
| courage | hope → detachment, humility | no |
| ocean | restless acquisition → material pursuit, joy | no |
| patience | hatred → friendliness, clarity | no |
| envy | envy → sympathetic joy, order | yes (coincidence: "envy" ↔ Īrṣyā aligns phonetically) |

Because R draws from the **same pool**, and A's pick isn't more *appropriate* to the word than a random
pick, **A ≈ R follows even if the pool were perfectly contrastive.** The arbitrary phoneme→meaning
mapping is the disease; the redundant pool is a symptom.

## 3. Fact-check of the external (ChatGPT) analysis

**Directionally correct** (matches this independent inspection): the glossary is non-contrastive, and a
"random-inside-a-same-tone-glossary" control stays evocative — which is why R helped creative generation.
Its integrity guidance is also correct: verdict stands, do not relabel B1, any fix is a new
pre-registered experiment.

**Specifically inaccurate** — its "exact duplicate pairs" table does not hold against the data:

| Claim | Verified reality | verdict |
|---|---|---|
| Ṅa & Ja both = Dambha→Vinaya | Ṅa=Dambha→Vinaya; Ja=**Ahaṁkāra**→Vinaya | ✗ only liberated pole shared; "Ja=Dambha" fabricated |
| Ṭha & Da both = Kṣamā | share only the Kṣamā root (Ātmaprasāda vs Dhairya) | ✗ not exact |
| Ḍha & La = cruelty→Karuṇā | Piśunatā→Karuṇā; Krūratā→Karuṇā | ✓ genuine near-duplicate |
| Ta & Bha = Jāgaraṇa | share only liberated pole (blocked differ) | ✗ not exact |
| Kha & Ya = Viśvāsa | share only liberated pole (blocked differ) | ✗ not exact |

So **4 of 5 "exact duplicate" claims are wrong** (blocked poles differ; only one pole is shared), and one
specific was fabricated. Treat the external table as a hint, not a source.

**What it missed:** it assumes fixing contrastiveness makes A beat R. It never addresses the mapping
(§2). Contrastiveness is **necessary but not sufficient**; a contrastive pool with an arbitrary mapping
still yields A ≈ R.

## 4. Honest path forward (if a future attempt is mounted)

1. The real target is the **mapping**: words must receive meanings that actually fit them — not just a
   tidier pool. Demonstrating *that* is the core H2 claim the two negatives (Track G, B1) reject.
2. Contrastiveness repair (distinct functional primitives, contrast-boundary field, an embedding-distance
   audit gate) is a reasonable *supporting* step but not the fix on its own.
3. It must be a **fresh, pre-registered B1.x on NEW words** — editing the lexicon by staring at *this*
   data and re-testing *these* words is circular (garden of forking paths). Do not relabel B1.
4. Weigh against the prior: two independent tracks now show random explains A, and §2 shows the
   mechanism. At some point "it would work if the lexicon were better" **is** the result — guard against
   unfalsifiability.

---

## Final status
```
B0:                                 FROZEN
B1:                                 SCORED
Verdict:                            RANDOM_OR_SCRAMBLED_MATCHES
Track B:                            BLOCKED
H2-specific utility:                not supported
Cause (exploratory):               non-contrastive pool AND arbitrary phoneme→meaning mapping
Contrastiveness repair:            necessary but NOT sufficient; requires fresh preregistration
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`.
**Structure, not validated meaning.** Exploratory; the pre-registered verdict stands.

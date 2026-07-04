# DOCS_ONLY — TRACK B B0 CONDITIONING MATERIALIZATION PARITY LEAK AUDIT — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only audit. No commit of results, no code change, no model call, no LLM generation, no scoring, no result files, no hashes computed, no manifest population. Pre-freeze hygiene only — **not evidence**. Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: plan `38e7325`; arm lock `916e00a`; D-table `bcb604e`; G2P audit `16266b4`; judge/leak lock `fae078d`; Track G negative `1fe5562`. The conditioning text below was rendered by deterministic committed code (L1/L2 harness + arm generators mirrored from the committed L5 demo); **no model was called**. The full 150-row table is included as an in-file appendix (§11); no separate result/JSON/CSV/score file was created.

## 1. Scope and non-execution boundary

- **Conditioning audit only** — rendered the A/R/S/C/X/D conditioning-slot text and ran parity + leak dry-checks on that text.
- **No model call · no LLM generation · no scoring · no result files.**
- **No hash computation · no manifest population · no B0 freeze · no B1 approval · no Track B unblock.**

## 2. Materialization method

- **Files/functions used:** `varna_lens/sample_text_rule_harness.py` (`profile`, `synthesize`, `BRIDGE`, `_lex_entry`, `_canon`), `varna_lens.py` (G2P cmudict path), and the arm generators mirrored from the committed L5 demo (`generation_conditioning_prompt_demo.py`). D text taken verbatim from the `bcb604e` table.
- **Rendering:** A = `synthesize(profile(word, vowel_mode="field_only"))`; R = random bridge values seeded `"R:{key_word}"`; S = permuted bridge via fixed seed `7731`; C = surface facts (onset / vowel-nucleus count / final / consonant positions); X = the constant neutral line; D = the frozen dictionary sentence. `[unresolved]` preserved; no manual rewriting.
- **Confirmed:** `no_model_called: true`. Deterministic committed code only; the render ran in scratch and wrote no repo file.

## 3. Coverage summary

- Primary words rendered: **20/20**
- Privative words rendered: **5/5**
- Total words: **25**
- Arms per word: **6** (A/R/S/C/X/D)
- Conditioning rows expected: **25 × 6 = 150**
- Conditioning rows rendered: **150**

## 4. Conditioning table (representative rows; full 150 in §11 appendix)

Representative — `grief` (all arms):

| Arm | chars | words | conditioning_text (truncated) |
|---|---|---|---|
| A | 273 | 41 | "A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: action moves toward stillness … it may orient the generation toward that movement." |
| R | 183 | 26 | "A randomized orientation (control; not derived from the key word): humility/ego-softening moves toward hope, and envy is the resolving principle. …" |
| S | 246 | 28 | "A scrambled-attachment orientation (control; key-word structure with permuted associations): compassion moves toward directed energy/purposeful material pursuit … " |
| C | 150 | 21 | "Sound-structure only (control; no associations): onset 'G', 1 vowel nucleus(es), final 'F', 3 consonant positions. …" |
| X | 65 | 10 | "Use the user task as written; no additional symbolic orientation." |
| D | 186 | 25 | "Dictionary/synonym field (control; lexical senses, not resonance): grief is deep sorrow after loss. Related terms: sorrow, mourning, sadness, bereavement. …" |

## 5. Unresolved-term audit

- **A rows with `[unresolved]`: 0** — A is constructible (fully resolved) for **all 25** words.
- **S rows with `[unresolved]`: 1** — `echo` (the scramble permutation left one pole unbridged; expected, preserved, not invented).
- Words affected: A none; S = {`echo`}.
- **Blocks freeze?** No — A is fully resolved; the single S `[unresolved]` is a legitimate control artifact and is **declared**, not patched.

## 6. Length-parity audit

Median by arm across all 25 words (each control vs A):

| Arm | median chars | vs A | median words | vs A | parity_status |
|---|---|---|---|---|---|
| **A** | 302 | (ref) | 42 | (ref) | reference |
| R | 205 | **−32.1%** | 27 | −35.7% | `PARITY_CONCERN` |
| S | 225 | **−25.5%** | 26 | −38.1% | `PARITY_CONCERN` |
| C | 150 | **−50.3%** | 21 | −50.0% | `PARITY_CONCERN` |
| X | 65 | **−78.5%** | 10 | −76.2% | `PARITY_CONCERN` |
| D | 205 | **−32.1%** | 27 | −35.7% | `PARITY_CONCERN` |

- **Every control arm is >25% shorter than A** (both char and word metrics) → **all flagged `PARITY_CONCERN`**.
- **Root cause:** A's framing preamble/suffix ("A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: … it may orient the generation toward that movement.") is longer than the other arms' framing. A is **systematically the longest arm** — an arm-length confound.
- **Requires revision before freeze: YES.**

## 7. Leak dry-check audit

- **Total leak hits: 0.**
- Words/arms affected: none.
- Forbidden phrases matched: none (checked all plan §8 phrases + bare "rescue" + `arm [A-Z]` label patterns across all 150 rows).
- **Leak dry-check is clean.** No revision required on leakage grounds.

## 8. Freeze impact

- `CONDITIONING_MATERIALIZED_FOR_AUDIT`
- `PARITY_REQUIRES_REVISION_BEFORE_FREEZE`
- `LEAK_DRY_CHECK_CLEAN`

**This clears leak hygiene only. It does NOT freeze B0, and parity is not yet clean.** The parity finding must be resolved before freeze by **uniformly harmonizing the per-arm framing length** across all six arms (equal-length "soft orientation" preamble/suffix so only the core content differs) — applied to all arms equally, **not** weakening D semantically, **not** making R/S awkward, **not** tuning A. Alternatively the imbalance may be **declared as a confound** before freeze; harmonization is preferred.

## 9. Current status

- `CONDITIONING_MATERIALIZATION_AUDIT_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_LLM_GENERATION`
- `NO_SCORING`
- `NO_RESULT_CHANGE`

## 10. Recommendation

**`PERSIST_CONDITIONING_MATERIALIZATION_AUDIT`** — and, because parity failed, **`REVISE_CONDITIONING_BEFORE_FREEZE`.**

Leak is clean, but length parity is **not** (every control >25% shorter than A; A systematically longest), so do **not** advance to `FINALIZE_RUNTIME_FIELDS_NEXT` yet. The parity fix is a **uniform framing-length harmonization across all six arms** (formatting applied to every arm's shared preamble/suffix, decided blind, not weakening controls, not tuning A), to be drafted and re-checked before any freeze. Do **not** `COMPUTE_HASHES_NOW`, do **not** `FREEZE_B0_NOW`, do **not** `REQUEST_B1_APPROVAL`. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the eventual outcome most likely remains a kill label; this parity finding is exactly the confound the pre-freeze hygiene exists to catch.

## 11. Appendix — full 150-row conditioning table (in-file; not a result file)

Fields: key_word · stratum · arm · chars · words · unresolved · generator_source · conditioning_text.

| key_word | strat | arm | chars | words | unres | generator_source | conditioning_text |
|---|---|---|---|---|---|---|---|
| grief | prim | A | 273 | 41 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: action moves toward stillness, and fearlessness is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| grief | prim | R | 183 | 26 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): humility/ego-softening moves toward hope, and envy is the resolving principle. Use as a soft tonal/conceptual guide. |
| grief | prim | S | 246 | 28 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): compassion moves toward directed energy/purposeful material pursuit, and non-attachment is the resolving principle. Use as a soft tonal/conceptual guide. |
| grief | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'G', 1 vowel nucleus(es), final 'F', 3 consonant positions. Use as a soft rhythmic/tonal guide. |
| grief | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| grief | prim | D | 186 | 25 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): grief is deep sorrow after loss. Related terms: sorrow, mourning, sadness, bereavement. Use as a soft conceptual guide. |
| courage | prim | A | 293 | 41 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: hope moves toward detachment/letting-go, and humility/ego-softening is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| courage | prim | R | 204 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): overstatement moves toward separative harshness, and liberation/clarity is the resolving principle. Use as a soft tonal/conceptual guide. |
| courage | prim | S | 264 | 27 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): forgiveness/self-acceptance moves toward blind attachment, and annihilation-thought/defeatist destruction is the resolving principle. Use as a soft tonal/conceptual guide. |
| courage | prim | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'K', 2 vowel nucleus(es), final 'JH', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| courage | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| courage | prim | D | 201 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): courage is the willingness to face fear or danger. Related terms: bravery, valor, boldness, fortitude. Use as a soft conceptual guide. |
| patience | prim | A | 302 | 41 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: hatred/revulsion moves toward friendliness/affection, and liberation/clarity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| patience | prim | R | 221 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): friendliness/affection moves toward liberation/clarity, and ego inflation/i-centeredness is the resolving principle. Use as a soft tonal/conceptual guide. |
| patience | prim | S | 218 | 27 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): worry moves toward indifference, and false knowledge, dogma is the resolving principle. Use as a soft tonal/conceptual guide. |
| patience | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'P', 2 vowel nucleus(es), final 'S', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| patience | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| patience | prim | D | 210 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): patience is calm tolerance of delay or difficulty. Related terms: forbearance, endurance, tolerance, composure. Use as a soft conceptual guide. |
| justice | prim | A | 314 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: ego inflation/i-centeredness moves toward humility/ego-softening, and liberation/clarity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| justice | prim | R | 206 | 28 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): repentance moves toward false knowledge, dogma, and compassion/gentleness is the resolving principle. Use as a soft tonal/conceptual guide. |
| justice | prim | S | 253 | 28 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): melancholy moves toward annihilation-thought/defeatist destruction, and false knowledge, dogma is the resolving principle. Use as a soft tonal/conceptual guide. |
| justice | prim | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'JH', 2 vowel nucleus(es), final 'S', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| justice | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| justice | prim | D | 214 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): justice is fair treatment according to what is right. Related terms: fairness, equity, impartiality, righteousness. Use as a soft conceptual guide. |
| silence | prim | A | 290 | 41 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: escapism moves toward liberation/clarity, and liberation/clarity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| silence | prim | R | 217 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): compassion/gentleness moves toward deluded obsession/entrancement, and overstatement is the resolving principle. Use as a soft tonal/conceptual guide. |
| silence | prim | S | 247 | 29 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): peevishness/irritability moves toward false knowledge, dogma, and false knowledge, dogma is the resolving principle. Use as a soft tonal/conceptual guide. |
| silence | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'S', 2 vowel nucleus(es), final 'S', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| silence | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| silence | prim | D | 176 | 25 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): silence is the absence of sound. Related terms: quiet, stillness, hush, calm. Use as a soft conceptual guide. |
| mountain | prim | A | 326 | 44 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: indulgence/annihilating collapse moves toward disciplined restraint/containment, and sympathetic joy is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| mountain | prim | R | 205 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): patience/forgiveness moves toward blind attachment, and hatred/revulsion is the resolving principle. Use as a soft tonal/conceptual guide. |
| mountain | prim | S | 228 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): liberation/clarity moves toward stillness, and order/dharmic relation is the resolving principle. Use as a soft tonal/conceptual guide. |
| mountain | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'M', 2 vowel nucleus(es), final 'N', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| mountain | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| mountain | prim | D | 191 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): a mountain is a large natural elevation of land. Related terms: peak, summit, height, ridge. Use as a soft conceptual guide. |
| river | prim | A | 332 | 44 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: annihilation-thought/defeatist destruction moves toward vitality/creative fire, and order/dharmic relation is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| river | prim | R | 203 | 26 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): compassion moves toward darkness/night/inertia, and liberation/clarity is the resolving principle. Use as a soft tonal/conceptual guide. |
| river | prim | S | 222 | 25 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): detachment/letting-go moves toward fearlessness, and attachment is the resolving principle. Use as a soft tonal/conceptual guide. |
| river | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'R', 2 vowel nucleus(es), final 'V', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| river | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| river | prim | D | 205 | 29 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): a river is a large natural stream of flowing water. Related terms: stream, waterway, current, watercourse. Use as a soft conceptual guide. |
| music | prim | A | 332 | 43 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: indulgence/annihilating collapse moves toward disciplined restraint/containment, and detachment/letting-go is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| music | prim | R | 231 | 31 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): greed/avarice moves toward false knowledge, dogma, and directed energy/purposeful material pursuit is the resolving principle. Use as a soft tonal/conceptual guide. |
| music | prim | S | 222 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): liberation/clarity moves toward stillness, and blind attachment is the resolving principle. Use as a soft tonal/conceptual guide. |
| music | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'M', 2 vowel nucleus(es), final 'K', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| music | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| music | prim | D | 195 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): music is arranged sound expressing feeling or ideas. Related terms: melody, tune, harmony, song. Use as a soft conceptual guide. |
| friendship | prim | A | 284 | 41 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: fear moves toward fearlessness, and friendliness/affection is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| friendship | prim | R | 229 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): detachment/letting-go moves toward annihilation-thought/defeatist destruction, and joy/affection is the resolving principle. Use as a soft tonal/conceptual guide. |
| friendship | prim | S | 233 | 25 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): fearlessness/self-acceptance moves toward non-attachment, and indifference is the resolving principle. Use as a soft tonal/conceptual guide. |
| friendship | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'F', 2 vowel nucleus(es), final 'P', 6 consonant positions. Use as a soft rhythmic/tonal guide. |
| friendship | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| friendship | prim | D | 221 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): friendship is a bond of mutual affection between people. Related terms: companionship, camaraderie, fellowship, closeness. Use as a soft conceptual guide. |
| teacher | prim | A | 311 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: overstatement moves toward silence/objectivity, and conscience/discriminative clarity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| teacher | prim | R | 229 | 31 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): restless acquisition/material greed moves toward inertia, deep sleep, and order/dharmic relation is the resolving principle. Use as a soft tonal/conceptual guide. |
| teacher | prim | S | 238 | 28 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): awareness/awakening moves toward lack of confidence, and vitality/creative fire is the resolving principle. Use as a soft tonal/conceptual guide. |
| teacher | prim | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'T', 2 vowel nucleus(es), final 'CH', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| teacher | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| teacher | prim | D | 196 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): a teacher is a person who helps others learn. Related terms: instructor, educator, tutor, mentor. Use as a soft conceptual guide. |
| shadow | prim | A | 352 | 46 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: restless acquisition/material greed moves toward directed energy/purposeful material pursuit, and fearlessness/self-acceptance is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| shadow | prim | R | 190 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): separative harshness moves toward repentance, and craving is the resolving principle. Use as a soft tonal/conceptual guide. |
| shadow | prim | S | 217 | 25 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): respect/reverence moves toward escapism, and overstatement is the resolving principle. Use as a soft tonal/conceptual guide. |
| shadow | prim | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'SH', 2 vowel nucleus(es), final 'D', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| shadow | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| shadow | prim | D | 200 | 29 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): a shadow is a dark shape cast by blocking light. Related terms: shade, silhouette, darkness, outline. Use as a soft conceptual guide. |
| freedom | prim | A | 295 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: fear moves toward fearlessness, and disciplined restraint/containment is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| freedom | prim | R | 212 | 29 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): false knowledge, dogma moves toward mundane knowledge, and patience/forgiveness is the resolving principle. Use as a soft tonal/conceptual guide. |
| freedom | prim | S | 230 | 25 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): fearlessness/self-acceptance moves toward non-attachment, and stillness is the resolving principle. Use as a soft tonal/conceptual guide. |
| freedom | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'F', 2 vowel nucleus(es), final 'M', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| freedom | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| freedom | prim | D | 207 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): freedom is the state of acting without constraint. Related terms: liberty, independence, autonomy, latitude. Use as a soft conceptual guide. |
| honesty | prim | A | 284 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: envy moves toward sympathetic joy, and silence/objectivity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| honesty | prim | R | 235 | 28 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): awareness/awakening moves toward deluded obsession/entrancement, and disciplined restraint/containment is the resolving principle. Use as a soft tonal/conceptual guide. |
| honesty | prim | S | 223 | 28 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): envy moves toward order/dharmic relation, and lack of confidence is the resolving principle. Use as a soft tonal/conceptual guide. |
| honesty | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'N', 3 vowel nucleus(es), final 'T', 3 consonant positions. Use as a soft rhythmic/tonal guide. |
| honesty | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| honesty | prim | D | 207 | 26 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): honesty is truthfulness and sincerity in conduct. Related terms: truthfulness, sincerity, candor, frankness. Use as a soft conceptual guide. |
| empathy | prim | A | 330 | 43 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: indulgence/annihilating collapse moves toward disciplined restraint/containment, and awareness/awakening is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| empathy | prim | R | 197 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): emotional firmness moves toward trust, and detachment/letting-go is the resolving principle. Use as a soft tonal/conceptual guide. |
| empathy | prim | S | 221 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): liberation/clarity moves toward stillness, and sympathetic joy is the resolving principle. Use as a soft tonal/conceptual guide. |
| empathy | prim | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'M', 3 vowel nucleus(es), final 'TH', 3 consonant positions. Use as a soft rhythmic/tonal guide. |
| empathy | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| empathy | prim | D | 215 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): empathy is the ability to share another's feelings. Related terms: compassion, understanding, sensitivity, sympathy. Use as a soft conceptual guide. |
| ocean | prim | A | 339 | 47 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: restless acquisition/material greed moves toward directed energy/purposeful material pursuit, and sympathetic joy is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| ocean | prim | R | 205 | 26 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): straightforwardness/integrity moves toward liberation/clarity, and worry is the resolving principle. Use as a soft tonal/conceptual guide. |
| ocean | prim | S | 226 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): respect/reverence moves toward escapism, and order/dharmic relation is the resolving principle. Use as a soft tonal/conceptual guide. |
| ocean | prim | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'SH', 2 vowel nucleus(es), final 'N', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| ocean | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| ocean | prim | D | 181 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): an ocean is a vast expanse of salt water. Related terms: sea, deep, waters, brine. Use as a soft conceptual guide. |
| envy | prim | A | 287 | 43 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: envy moves toward sympathetic joy, and order/dharmic relation is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| envy | prim | R | 190 | 26 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): detachment/letting-go moves toward repentance, and action is the resolving principle. Use as a soft tonal/conceptual guide. |
| envy | prim | S | 215 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): envy moves toward order/dharmic relation, and attachment is the resolving principle. Use as a soft tonal/conceptual guide. |
| envy | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'N', 2 vowel nucleus(es), final 'V', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| envy | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| envy | prim | D | 209 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): envy is resentful longing for what another has. Related terms: jealousy, covetousness, resentment, begrudging. Use as a soft conceptual guide. |
| order | prim | A | 338 | 43 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: annihilation-thought/defeatist destruction moves toward vitality/creative fire, and fearlessness/self-acceptance is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| order | prim | R | 198 | 26 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): fearlessness moves toward hope, and straightforwardness/integrity is the resolving principle. Use as a soft tonal/conceptual guide. |
| order | prim | S | 225 | 25 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): detachment/letting-go moves toward fearlessness, and overstatement is the resolving principle. Use as a soft tonal/conceptual guide. |
| order | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'R', 2 vowel nucleus(es), final 'D', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| order | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| order | prim | D | 209 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): order is a state of arrangement or organization. Related terms: arrangement, orderliness, structure, sequence. Use as a soft conceptual guide. |
| integrity | prim | A | 284 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: envy moves toward sympathetic joy, and silence/objectivity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| integrity | prim | R | 215 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): compassion moves toward silence/objectivity, and conscience/discriminative clarity is the resolving principle. Use as a soft tonal/conceptual guide. |
| integrity | prim | S | 223 | 28 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): envy moves toward order/dharmic relation, and lack of confidence is the resolving principle. Use as a soft tonal/conceptual guide. |
| integrity | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'N', 4 vowel nucleus(es), final 'T', 5 consonant positions. Use as a soft rhythmic/tonal guide. |
| integrity | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| integrity | prim | D | 201 | 26 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): integrity is firm adherence to moral principle. Related terms: uprightness, probity, rectitude, honor. Use as a soft conceptual guide. |
| autumn | prim | A | 311 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: overstatement moves toward silence/objectivity, and disciplined restraint/containment is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| autumn | prim | R | 217 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): deluded obsession/entrancement moves toward compassion, and peevishness/irritability is the resolving principle. Use as a soft tonal/conceptual guide. |
| autumn | prim | S | 225 | 27 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): awareness/awakening moves toward lack of confidence, and stillness is the resolving principle. Use as a soft tonal/conceptual guide. |
| autumn | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'T', 2 vowel nucleus(es), final 'M', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| autumn | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| autumn | prim | D | 195 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): autumn is the season between summer and winter. Related terms: fall, harvest season, autumntime. Use as a soft conceptual guide. |
| echo | prim | A | 238 | 35 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: hope moves toward detachment/letting-go. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| echo | prim | R | 198 | 26 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): awareness/awakening moves toward detachment/letting-go, and trust is the resolving principle. Use as a soft tonal/conceptual guide. |
| echo | prim | S | 234 | 26 | 1 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): forgiveness/self-acceptance moves toward blind attachment, and [unresolved] is the resolving principle. Use as a soft tonal/conceptual guide. |
| echo | prim | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'K', 2 vowel nucleus(es), final 'K', 1 consonant positions. Use as a soft rhythmic/tonal guide. |
| echo | prim | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| echo | prim | D | 209 | 29 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): an echo is a sound reflected back to the listener. Related terms: reverberation, reflection, repetition, ring. Use as a soft conceptual guide. |
| amoral | priv | A | 332 | 43 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: indulgence/annihilating collapse moves toward disciplined restraint/containment, and compassion/gentleness is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| amoral | priv | R | 201 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): fearlessness moves toward non-attachment, and order/dharmic relation is the resolving principle. Use as a soft tonal/conceptual guide. |
| amoral | priv | S | 224 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): liberation/clarity moves toward stillness, and emotional firmness is the resolving principle. Use as a soft tonal/conceptual guide. |
| amoral | priv | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'M', 3 vowel nucleus(es), final 'L', 3 consonant positions. Use as a soft rhythmic/tonal guide. |
| amoral | priv | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| amoral | priv | D | 217 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): amoral means not concerned with right or wrong. Related terms: nonmoral, unprincipled, indifferent, ethically neutral. Use as a soft conceptual guide. |
| apathy | priv | A | 303 | 41 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: hatred/revulsion moves toward friendliness/affection, and awareness/awakening is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| apathy | priv | R | 197 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): envy moves toward spiritual knowledge, and detachment/letting-go is the resolving principle. Use as a soft tonal/conceptual guide. |
| apathy | priv | S | 211 | 26 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): worry moves toward indifference, and sympathetic joy is the resolving principle. Use as a soft tonal/conceptual guide. |
| apathy | priv | C | 151 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'P', 3 vowel nucleus(es), final 'TH', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| apathy | priv | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| apathy | priv | D | 205 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): apathy is a lack of interest or feeling. Related terms: indifference, unconcern, detachment, listlessness. Use as a soft conceptual guide. |
| asymmetry | priv | A | 294 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: escapism moves toward liberation/clarity, and vitality/creative fire is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| asymmetry | priv | R | 202 | 28 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): spiritual knowledge moves toward indifference, and emotional firmness is the resolving principle. Use as a soft tonal/conceptual guide. |
| asymmetry | priv | S | 237 | 27 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): peevishness/irritability moves toward false knowledge, dogma, and fearlessness is the resolving principle. Use as a soft tonal/conceptual guide. |
| asymmetry | priv | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'S', 4 vowel nucleus(es), final 'R', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| asymmetry | priv | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| asymmetry | priv | D | 211 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): asymmetry is a lack of balance between parts. Related terms: imbalance, irregularity, unevenness, disproportion. Use as a soft conceptual guide. |
| anarchy | priv | A | 286 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: envy moves toward sympathetic joy, and detachment/letting-go is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| anarchy | priv | R | 212 | 27 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): non-attachment moves toward physical desire/inertia/confusion, and fearlessness is the resolving principle. Use as a soft tonal/conceptual guide. |
| anarchy | priv | S | 221 | 27 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): envy moves toward order/dharmic relation, and blind attachment is the resolving principle. Use as a soft tonal/conceptual guide. |
| anarchy | priv | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'N', 3 vowel nucleus(es), final 'K', 2 consonant positions. Use as a soft rhythmic/tonal guide. |
| anarchy | priv | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| anarchy | priv | D | 199 | 27 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): anarchy is the absence of government or order. Related terms: disorder, lawlessness, chaos, misrule. Use as a soft conceptual guide. |
| anonymity | priv | A | 284 | 42 | 0 | L2.synthesize(field_only) | A latent-process reading (an internal orientation, not a definition; a stylistic prior only) can be read as: envy moves toward sympathetic joy, and silence/objectivity is the resolving principle. Use as a soft tonal/conceptual guide; it may orient the generation toward that movement. |
| anonymity | priv | R | 210 | 28 | 0 | R:"R:{w}" | A randomized orientation (control; not derived from the key word): mundane knowledge moves toward melancholy, and deluded obsession/entrancement is the resolving principle. Use as a soft tonal/conceptual guide. |
| anonymity | priv | S | 223 | 28 | 0 | S:7731 | A scrambled-attachment orientation (control; key-word structure with permuted associations): envy moves toward order/dharmic relation, and lack of confidence is the resolving principle. Use as a soft tonal/conceptual guide. |
| anonymity | priv | C | 150 | 21 | 0 | surface | Sound-structure only (control; no associations): onset 'N', 5 vowel nucleus(es), final 'T', 4 consonant positions. Use as a soft rhythmic/tonal guide. |
| anonymity | priv | X | 65 | 10 | 0 | neutral-const | Use the user task as written; no additional symbolic orientation. |
| anonymity | priv | D | 222 | 28 | 0 | D-table bcb604e | Dictionary/synonym field (control; lexical senses, not resonance): anonymity is the state of being unnamed or unknown. Related terms: namelessness, obscurity, concealment, unidentifiability. Use as a soft conceptual guide. |

## Guardrails

- No ontology validation.
- No Sanskrit privilege.
- No semantic-truth claim.
- No Track G rescue.
- No Track B unblock.
- Track G negative preserved: `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`.
- Track B remains **BLOCKED**.
- Prior PSE negatives remain valid.
- Track F prior remains `CORRECTNESS_DEGRADED`.
- Frozen manifest remains `NOT_READY`.
- Approval status remains `NOT_APPROVED`.

---

**Structure, not validated meaning.**

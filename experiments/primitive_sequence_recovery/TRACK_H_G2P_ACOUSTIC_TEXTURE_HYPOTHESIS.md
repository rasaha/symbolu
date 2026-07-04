# Design Memo — Possible Track H: G2P Acoustic-Texture Test

**Status: proposal only.** No files (beyond this memo), no runner, no run, no model call. `frozen/manifest.json` NOT_READY; base run manifests `run_enabled:false` / `NOT_APPROVED`; Stage A untouched; **Track B BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. This memo does **not** reinterpret any prior negative.

**Track G context (preserved exactly; commit `1fe5562`).** Track G produced a valid scored **negative**: `primary_label RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`, `malformed_rate 0.0`, `tasks_judged 10`. The varṇa-derived signed-polarity hypothesis did not survive controls (a random sign-flip and plain context each explained the choices at least as well). Track H is a **fresh** hypothesis and **cannot rescue, revive, or reinterpret** Track G. (B1/B2/B3 harness work — including the `--all-raw-dump` audit capture at commit `de58503` — is ingestion/auditability **infrastructure only**, not a result.)

## 1. Conceptual reframing

**G2P vs IAST/transliteration.** The current pipeline segments a *written* string (IAST/Devanāgari transliteration) into orthographic varṇa units — it operates on **spelling**, and inherits spelling's ambiguities (schwa deletion, gemination, sandhi, digraphs like *kh/gh*, silent/inherent vowels). **Grapheme-to-phoneme (G2P)** maps a written word to its **pronounced phoneme sequence** (e.g. IPA), then to **articulatory/acoustic features** (place, manner, voicing, sonority, vowel height/backness, F2/formant proxies, duration). The difference is categorical: IAST tokens are *letters*; G2P outputs are *sounds with measurable phonetic features*. Track G tested letter-derived polarity; Track H would test **sound-feature-derived acoustic impression** — a different input representation and a different (weaker) dependent variable.

**Why acoustic texture is a weaker, more defensible claim.** "Varṇa predicts word meaning" is a strong, near-ontological claim (a phoneme *carries* semantic content). "Phonetic features weakly bias *perceived acoustic texture*" is a modest, well-attested psycholinguistic claim (sound-symbolism / iconicity) that says nothing about meaning-truth. It predicts a *small* statistical bias in how sounds *feel* (bright/sharp/heavy), not what words *mean*. That is falsifiable, bounded, and does not require any Sanskrit-specific ontology.

**G2P cannot rescue Track G.** Explicitly: Track G is a **closed, recorded negative** (`RANDOM_POLARITY_EXPLAINS`). Track H is a **different hypothesis** (acoustic texture, not semantic polarity), a **different representation** (phonemes, not IAST varṇas), and a **different target type** (impression axes, not meaning poles). A positive Track H would **not** revive Track G, would **not** validate varṇa semantics, and would **not** unblock Track B. If anyone later tries to chain "H worked → G was right," that is a category error and must be refused. Track H must be pre-registered as a *fresh* hypothesis with its own kill criteria, exactly as Track G was relative to C/D0/E/F.

## 2. Proposed hypothesis (narrow)

> **H₀ (null, expected):** G2P-derived phonetic/articulatory features do **not** predict human/model-perceived acoustic texture better than spelling/transliteration-derived features (B), random assignment (R), scrambled phoneme order (S), or context-only (X).
>
> **H₁ (weak, to be tested):** G2P-derived features predict perceived acoustic texture **weakly but reliably better than B, R, S, and X** across the impression axes in §4.

Explicitly out of scope and never claimed: semantic meaning, ontology, Sanskrit privilege, varṇa "truth," any Track B support. The unit of success is a *small effect on sound-impression*, not meaning.

## 3. Arms / controls

| Arm | Definition | Guards against |
|---|---|---|
| **A** | G2P phoneme → articulatory/acoustic feature profile | the hypothesis |
| **B** | IAST/spelling-derived profile (current pipeline) | "phonemes add nothing over spelling" — the key contrast that isolates *G2P's* value |
| **R** | random phoneme/feature assignment (frozen seed) | any-signal-at-all (co-primary, as `A_vs_R` was in G) |
| **S** | scrambled phoneme order (same multiset, shuffled) | "order/composition carries nothing" |
| **X** | context-only / no acoustic cue | context-dominance (the Track E/G killer; co-primary) |
| **D** *(optional)* | dictionary/gloss-only | leakage via meaning rather than sound |

`A_vs_R` and `A_vs_X` are **co-primary** (learned from G). `A_vs_B` is arguably the *most important* arm here: if G2P doesn't beat plain spelling, the whole "we need real phonemes" premise fails. Success requires A to clear **all** of B, R, S, X (and D if included) — not just beat one weak baseline.

## 4. Target type (acoustic impression, not meaning)

Use bipolar **impression axes**, never dictionary meaning. Candidate axes:
- bright ↔ dark
- sharp ↔ soft
- heavy ↔ light
- open ↔ closed
- tense ↔ relaxed
- fast ↔ slow
- smooth ↔ jagged
- expansive ↔ contracted

Critically, targets should be about *how the sound feels*, decoupled from *what the word means*. To avoid smuggling semantics back in, prefer **pseudowords / nonce forms** (bouba-kiki style) or words whose meaning is orthogonal to the target axis, so that a "bright" judgment can't be gotten from knowing the gloss. Freeze each item's target axis+pole *before* scoring (Track G's frozen-assignment discipline; post-hoc edits → invalidate).

## 5. Scoring design

**Judge: both, staged.** Start with an **LLM judge** for cheap iteration (it's scalable and matches prior tracks), but treat LLM-only as *exploratory*. For any result to count as real, require a **small human panel** (even N=5–10 raters) on a subset, and check **human↔model agreement** (e.g. Krippendorff's α / rank correlation). Sound-symbolism is fundamentally a *perception* claim — a model judge alone can't establish it, and an LLM may just be reading orthography. Human disagreement with the model is itself a kill signal (§7).

**Success criteria (all required):**
- `A_vs_R > ε` and `A_vs_X > ε` (co-primary), **and** `A_vs_B > ε`, `A_vs_S > ε` (and `A_vs_D > ε` if used), with ε pre-registered.
- Effect **stable across seeds** and **≥2 models**, and **≥2 languages** (so it isn't a single-model/English artifact).
- **Human panel agrees** with the model direction on the tested subset.
- Pre-registered, one-shot; no post-hoc axis/target swaps.

**Safeguards carried from Track G:**
- **Leak scanner** hiding surface word, phonemes/IPA, arm labels, target axis/pole, roles — extended to hide the **G2P transcription itself** and any language ID that reveals the word.
- **Malformed-output handling**: strict JSON parse with the B2 tolerance (accept positional arrays, coerce quoted numbers), `malformed_rate` abort threshold (0.15), and **`--all-raw-dump` on from the start** for full auditability.
- Anonymized packets, shuffled candidates, separate hidden key, refusal-gated no-model-call dry-run, base manifest ships `run_enabled:false`.

**Leakage is the central threat here** and deserves its own control: because G2P is *derived from the word*, a model that recognizes the word can back out the "right" texture from meaning/spelling, not sound. Mitigations: pseudowords, cross-language items, and a **D (gloss-only) arm** — if D explains the result, A's apparent signal is lexical leakage, not acoustics.

## 6. Literature alignment

- **Bouba/kiki (Köhler 1929; Ramachandran & Hubbard 2001):** rounded vs angular shapes reliably map to sonorant/round vs plosive/spread sounds — a robust *cross-linguistic perceptual bias*.
- **Sound-symbolism / iconicity (Sapir 1929 "mil/mal" size; Ohala's frequency code; Blasi et al. 2016 cross-linguistic sound-meaning associations; Dingemanse et al. on ideophones):** real but **small, probabilistic** associations between phonetic features and broad perceptual/affective dimensions.
- **Why this supports the weak claim only:** this literature establishes a *statistical bias* in perception (high front vowels → small/bright; obstruents → sharp/jagged), **not** a deterministic phoneme→meaning code. It is fully consistent with a modest Track H effect on *impression* and fully **inconsistent** with the strong varṇa-semantic claim that already failed. Sound-symbolism is language-general and does **not** privilege Sanskrit — invoking it *removes* Sanskrit privilege rather than supporting it.

## 7. Kill criteria (abandon Track H if any hold)

- **A does not beat R, S, or X** (any co-primary or composition control fails) → no signal; kill (this is the expected outcome).
- **A does not beat B** → G2P adds nothing over spelling; the premise ("we needed real phonemes") is false; kill.
- **Effect vanishes across languages or models** → single-model/English artifact, not a phonetic universal; kill.
- **D (gloss-only) explains A**, or effect disappears on pseudowords/meaning-orthogonal items → **lexical leakage**, not acoustics; kill.
- **Human panel does not agree with model** (low α, opposite direction) → the "perception" claim isn't perceptual; kill or downgrade to "LLM orthographic artifact."
- **Effect present but within noise / not seed-stable** → not reliable; kill.
- Any attempt to use a partial H result to reinterpret G, claim ontology, or unblock B → stop; that's a scope violation, not a finding.

## 8. Relation to patent / Soulpi

- **Safe framing:** "phonetic/acoustic symbolic features as an **interpretability / response-texture layer**" — i.e., an *engineering* signal that can tag or modulate output *style/texture* (bright/soft/heavy), explicitly **not** a claim that phonemes carry meaning or ontology. Frame as "a weak, controllable stylistic prior," never as "validated symbolic semantics."
- **Useful even if weak?** Possibly, and this is the honest nuance: a *small but real* texture bias could have **engineering utility** (a controllable knob for response feel, a lightweight interpretability feature) independent of any truth claim — the same "architecture-bound utility, never ontology" carve-out used for Track G. For the patent, an *engineering-utility* framing does **not** require the effect to be large or ontological; it requires it to be **real, controllable, and reproducible**. But: if the effect is indistinguishable from spelling (B) or from generic LLM behavior, it adds no defensible novelty. And a *negative* H is also useful to the patent narrative — it shows the claims are scoped to what survives adversarial test, strengthening credibility. **Do not** let patent framing pull the science toward a positive; the eval must be free to kill it.

## 9. Recommendation

**GO-WITH-CONDITIONS — small, cheap, pre-registered probe; skeptical prior.**

- **Expected probability of a *defensible* positive** (A clears R, S, X, **and** B, cross-model, cross-language, with human agreement): **low — ~15–25%.** The strongest single reason for pessimism: even the well-established sound-symbolism literature yields *small* effects, and our hardest bar (`A_vs_B`: phonemes beating spelling) is exactly where a G2P-vs-IAST distinction is likely to wash out, since IAST already correlates heavily with phonemes for Sanskrit. Add leakage risk and the Track G/E context-dominance pattern, and null is the base case.
- **Conditions if you proceed:**
  1. Pre-register H as a **fresh** hypothesis (its own prereg, kill criteria, frozen targets) with an explicit "cannot rescue G / cannot unblock B" clause.
  2. **Start with a synthetic harness + toy fixtures** (no model), exactly as every prior track — prove the arm/label mechanics before any GPU run.
  3. Use **pseudowords + ≥2 languages + a gloss-only leakage arm** from the outset; `A_vs_B` and `A_vs_R` are hard gates.
  4. Plan a **human-panel subset** before declaring any positive; LLM-only stays exploratory.
  5. `--all-raw-dump` and leak scanner on from day one.
- **NO-GO trigger:** if scoping this reveals that IAST and G2P produce near-identical feature profiles for the item set (i.e., B ≈ A by construction), stop before building — there's no contrast to test.

Net: worth a **cheap, disciplined, kill-biased probe** as an *engineering/interpretability* question, framed as weak phonetic bias — **not** as a rescue of varṇa semantics. Go in expecting to kill it; treat a survivor as a small engineering signal requiring human confirmation, never as ontology.

Structure, not validated meaning.

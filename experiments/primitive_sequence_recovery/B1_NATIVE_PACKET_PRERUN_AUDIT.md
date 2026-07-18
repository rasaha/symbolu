# B1 — Native Word-Specificity Packet PRE-RUN Integrity & Leakage Audit (read-only)

**Gate verdict: `PRE_RUN_BLOCKED_BY_STRUCTURAL_SHORTCUT`. Readiness: `REFREEZE_REQUIRED_BEFORE_RUN`.**
Final gate before spending evaluator calls, on the frozen packets at commit `aadf7345`. Read-only: no packet
regeneration, no re-authoring, no gloss edit, no evaluator call, no result. All authoring claims were re-checked
independently from the frozen bytes. Deterministic recompute: `native_packet_prerun_audit/audit_findings.json`.

## Hash verification

All 8 frozen artifacts recompute byte-identically to `packet_freeze_index.json` (`all_frozen_hashes_match: true`);
working tree clean at `aadf7345`. The audit reads these bytes directly and does **not** re-run the generator.

## A. Blind-authoring integrity — `IDENTITY_HIDDEN_BUT_CONTEXT_NOT_ISOLATED`

The paraphrases were authored **in the same session/context that had already seen** the consonant identities, Set A,
Set B, and the candidate glosses. The opaque row IDs (`internal/blind_authoring_input.json`) made the blindness
**procedural, not genuine context isolation** — exactly the failure mode the audit warns against ("do not infer
genuine blinding merely from the existence of opaque IDs"). This is a real limitation for a *confirmatory* test: a
skeptic can object that the person who wrote each English description knew which word it described.

**Bounded, not unbounded:** inspection against the source vṛtti shows the paraphrases track the frozen lexicon
faithfully (equivalence PRESERVED on read), so contamination did not visibly inject gloss cues *beyond* the source —
the one residual embellishment found is r15/h `"physically-seen, outward-facing"` → `"visible surface"` (adds a
body-adjacent "surface"). This limitation does **not** by itself block the run, but it compounds the interpretation
limit in §B and should be removed by isolated re-authoring at the required re-freeze.

## B. Semantic leakage — substrate-faithful, but a blind rater solves 4/12

- **No exact-name leak:** no packet contains any candidate word (horse/fear/pain/body/…).
- **Blind solvability (key withheld during rating):** rating each true packet against its six glosses with **no
  access to the varṇa theory**, ordinary English semantics pick the **true** gloss in **4 of 12** true packets —
  `bhaya→fear`, `duḥkha→pain`, `sukha→happiness`, `deha→body`. Revealing the key confirmed all four.
- **Traceable to the frozen source, not to packet authoring:** each leak comes from the source vṛtti itself —
  `d`=peevish irritability + `kh`=anxious rumination → pain; `bh`=entrancement/loss-of-discernment + `y`=self-doubt
  → fear; `s`=sattvic clarity + `kh`=composed reflection → happiness; `h`=**"outward/physical/visible vision"** →
  body. The paraphrases faithfully carry these; the adjacency lives in the **lexicon**, not the render step.
- **Channels:** affect/valence flavor; definitional association (deha/body via "outward visible surface");
  abstract-vs-concrete (every packet is an abstract psychological description, so the abstract valenced glosses
  fear/pain/strength/happiness are intrinsically more "packet-like" than concrete nouns horse/salt/tree).

**Reading:** this is **not** a packet-authoring leakage defect — it is the substrate under test. But it means a
positive T-vs-control result **cannot** by itself support "varṇas carry meaning": it is confounded with the source
lexicon being English-semantically adjacent to the target words (possible upstream back-fitting). This is a standing
**interpretation limit** that re-freezing will *not* remove; it must be carried into analysis as per-word,
leak-flagged reporting.

## C. Packet fingerprints — not exploitable

Row-count does not uniquely identify any word (Set A all length-2; Set B length-3 shared by lavaṇa+vṛkṣa). Character
length varies but **cannot be mapped to an English gloss** because spelling/Devanāgarī is hidden — the evaluator
cannot know a candidate word's consonant count from "salt"/"tree". The **F arm** exposes `n_features`/`length_band`
precisely to *measure* this structural-shortcut ceiling empirically; that is control-by-design, not a leak.

## D. Control-arm integrity — valid, EXCEPT a blocking position confound

Valid: T packets = the true rows in true order; **X** strict derangement (no fixed points) and a bijection over the
set; **S** is an order-only reshuffle of the true rowset; **R** is length-matched and draws only from consonants
**not** in the target word (5 frozen instances); **F** is metadata-only; per-set×arm counts correct
(T6/X6/S6/R30/G6/F6 each set); evaluator-facing artifacts leak no arm/word/label/row-id.

**The X row-count question (raised in the task):** X shows another word's packet, so in Set B an X packet can be
length-3 under a length-2 target. This is **not** an exploitable shortcut — length is not gloss-mappable (§C) — and it
only ever mispoints toward the *shown* word (a distractor), never toward the correct label. Not a blocker.

### 🔴 BLOCKER — correct-label position is arm-confounded

Candidate order is shuffled from a single seeded stream with **no counterbalancing of the correct-answer position**.
With only 12 trials per arm, the true label's position lands lopsided **and differs by arm**:

| arm | W1 | W2 | W3 | W4 | W5 | W6 | max share |
|---|---|---|---|---|---|---|---|
| **T** | 0 | 0 | 2 | 2 | 2 | **6** | **0.50 at W6** |
| X | 2 | 0 | 8 | 2 | 0 | 0 | 0.67 at W3 |
| S | 2 | 0 | 0 | 4 | 0 | 6 | 0.50 |
| **R** | 10 | 6 | 10 | 10 | 12 | 12 | **0.20 (≈uniform)** |
| G | 0 | 0 | 2 | 2 | 4 | 4 | 0.33 |
| F | 0 | 2 | 4 | 2 | 2 | 2 | 0.33 |

(Overall χ²≈16.0, df=5, p<0.01.) **T concentrates 50% of correct answers at the last option (W6); the primary
control R is uniform.** LLM evaluators have well-documented last-/first-option biases. An evaluator with any W6
preference would score ≈0.50 on T and ≈0.20 on R → **Δ≈0.30, far above the Δ≥0.15 success threshold, from position
bias alone with zero word-specific information.** The frozen analysis (permutation over packet↔word assignment;
bootstrap over words) permutes neither candidate position nor arm, so it **cannot** correct this. This is a
disqualifying structural shortcut.

## E. Set-A disjointness

Set A packets are fully disjoint, so each has a memorable, unique paraphrase fingerprint — but recognizing that a
packet is *unique* (channel 1) is **not** evidence for the hypothesis; only mapping a packet to its intended word
**meaning** (channel 2) is. With consonant symbols hidden and no per-candidate reference packet, disjointness alone
does not enable channel-2 matching; the §B semantic channels (not disjointness) are what make 4/12 solvable. No
additional Set-A-specific blocker beyond §B/§D.

## F. Dictionary-gloss integrity

Glosses are single neutral Monier-Williams senses. Valence: negative `fear, pain`; positive `strength, happiness`;
the rest neutral. Same-valence pair present in Set A (fear/pain); in Set B `happiness` is the lone positively-valenced
gloss. **Concreteness is unequal**: abstract (`strength, fear, pain, happiness, union`) vs concrete (`horse,
elephant, cloud, seed, body, salt, tree`); since all packets are abstract psychological states, the abstract glosses
are a secondary matching channel (overlaps §B). No gloss is disqualifyingly broad/narrow; no gloss revision made.

## G. Evaluator-prompt simulation

Task is unambiguous, all six options always shown, exactly one choice required, no open-ended plausibility endpoint,
no uncontrolled chain-of-thought, and no overt varṇa-theory / repository leak. **Gaps:** the literal prompt template
is not frozen at the packet level (specified in the prereg only) and the per-(packet,arm) **repeat count is
unspecified (`"N>=?"`)**. Recommend freezing the literal template + repeat count at re-freeze; no theory-leak blocker.

## H. Reproducibility & separation

Evaluator-facing `trials.json` contains **no** answer key; the key is isolated in `internal/answer_key.json`; scoring
can occur only after responses are collected; model-family pinning policy is present. **Gaps:** retry/error rules and
the repeat count are undefined — define them before the run.

## Gate & readiness

- **Gate: `PRE_RUN_BLOCKED_BY_STRUCTURAL_SHORTCUT`** — the arm-confounded correct-label position (§D) can drive Δ
  above threshold from evaluator position bias alone. (Also carried: the §A authoring non-isolation limitation and
  the §B substrate interpretation limit.)
- **Readiness: `REFREEZE_REQUIRED_BEFORE_RUN`.**

## Exact next action (do NOT run evaluators)

Re-freeze the packets with, at minimum:
1. **Counterbalance the correct-label position** — uniform within each arm **and** matched across arms (e.g. rotate
   the target through W1–W6 in equal counts per arm, or hold one position distribution common to all arms), then
   re-verify χ²≈0 per arm. *(fixes the blocker)*
2. **Genuinely context-isolated re-authoring** of the 17 paraphrases — a fresh agent given ONLY opaque-ID source
   vṛtti text, with no word sets, glosses, or consonant identities — to reach `GENUINELY_CONTEXT_ISOLATED` and strip
   embellishments like "surface". *(fixes §A)*
3. **Freeze the literal evaluator prompt template, the repeat count, and retry/error rules.** *(fixes §G/§H gaps)*
4. **Pre-commit leak-aware analysis:** report per-word accuracy and flag the four semantically-adjacent words
   (bhaya/duḥkha/sukha/deha) separately; a positive result must be interpreted against the §B substrate confound,
   which re-freezing does **not** remove.

Then re-run this pre-run audit. Only on `PRE_RUN_INTEGRITY_GATE_PASS` + `READY_TO_RUN_FROZEN_EVALUATORS` do evaluator
calls proceed. B1.10's pole-legibility negative (−2.78) and the guarded prior stand; no positive word-specificity
claim exists.

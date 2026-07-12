# B1 — Native Word-Specificity Packet Authoring & Freeze (docs/data-only)

**Packet verdict: `PACKETS_AUTHORED_FROZEN_AND_LEAKAGE_CLEAN`. Readiness: `READY_FOR_BLIND_EVALUATOR_RUN`.**
Controlled by the frozen preregistration (`native_word_specificity_prereg/freeze_index.json`) and the native
Gate-G0 pass (commit `794ecaa4`). **No evaluator run, no judge call, no accuracy/result.** Packets use **only** the
confirmatory consonant backbone; **no authored vowel/marker/candrabindu enters any packet.** B1.10's pole-legibility
negative (−2.78) and the qualitative guarded prior stand; **no positive word-specificity claim exists before the
run.** Structure, not validated meaning.

## What this step froze

- **Hidden substrate:** Devanāgarī remains the canonical hidden packet input. The parser-derived consonant backbone
  of each word (via `frozen/varna_native_stage1_merged_v1.json`) selects the confirmatory rows. **English glosses
  are candidate labels only — never parsed or decomposed.**
- **17 confirmatory rows paraphrased** (the consonants actually used by the two frozen word sets):
  `ś v b l bh y d kh g j gh m s h ṇ k ṣ`. One fixed **binding** + one fixed **liberating** English paraphrase per
  row, authored **blind** from the row text under opaque row IDs (consonant identity withheld from the authoring
  view: `internal/blind_authoring_input.json`) — no Sanskrit term, no transliteration, no letter/sound reference,
  no candidate-gloss word or near-synonym, uniform noun-phrase form.
- **Candidate glosses** (`candidate_gloss_table.json`): short, neutral, single-sense, independently sourced
  (Monier-Williams 1899, s.v. each word). `yoga` uses the frozen sense rule *first nominal 'yoking/union'* (not the
  darśana/discipline senses).
- **Evaluator-facing packets** (`evaluator_facing/trials.json`, 120 trials) for arms **T / X / S / R / G / F** across
  **Set A** and **Set B**, under the pinned seeds. Each trial exposes only the packet (English dual-pole rows or, for
  F, structural metadata) + six candidates as `W1–W6` labels with a neutral English gloss. **No Devanāgarī, IAST,
  consonant symbol, row ID, arm identity, source word, or repository path is exposed.**
- **Internal answer key** (`internal/answer_key.json`) is stored separately from the evaluator-facing trials.

## Arms & packet counts (per set × arm)

| set | T | X | S | R | G | F |
|---|---|---|---|---|---|---|
| A | 6 | 6 | 6 | 30 | 6 | 6 |
| B | 6 | 6 | 6 | 30 | 6 | 6 |

- **T** true packet · **X** cross-word mismatch (frozen derangement, seed 20260901; strict — no fixed points) ·
  **S** scrambled feature order (only for packets of length > 1) · **R** random varṇa→row assignment (5 seeded
  instances/word, seed 20260902, drawn from non-self consonants) · **G** generic word-agnostic dual-pole, row-count/
  valence matched (seed 20260903) · **F** feature-only structural metadata (no semantic rows — shortcut ceiling).
  Candidate order seeded per trial (seed 20260904).

## Leakage & equivalence

- **Leakage audit** (`leakage_audit.json`): every paraphrase checked against every candidate gloss (both sets) for
  exact/stem/synonym overlap and IAST-diacritic transliteration. **0 flags.** (Audit shown to have teeth: injected
  gloss words are caught in tests.) A first pass surfaced 33 spurious `iast_diacritic_leak` flags from a malformed
  diacritic set that included a plain ASCII `h`; corrected to non-ASCII IAST letters only — real diacritic leaks are
  still caught.
- **Equivalence audit** (`equivalence_audit.json`): every row's paraphrase preserves the source tendency + valence
  without adding/removing/strengthening content — **all 34 poles PRESERVED.**

## Validation

`test_b1_native_word_specificity_packets.py` (18 tests, all pass) covers the 15 required checks: Devanāgarī substrate;
glosses never parsed; every gloss independently sourced; glosses neutral/short; one fixed binding+liberating
paraphrase per used row (17); 0 leakage; equivalence preserved; T/X/S row counts matched; X strict derangement;
R frozen 5-instance scheme; G length/valence matched; F metadata-only; no authored vowel in packets; evaluator-facing
exposes nothing reverse-mappable; protected upstream artifacts byte-unchanged; deterministic freeze. Full related
suite: **382 passed.**

## Preregistration clarifications applied

Two binding clarifications were inserted verbatim into `B1_NATIVE_WORD_SPECIFICITY_PREREG.md` before running this step:

> Devanāgarī remains the canonical hidden input used to construct packets. English glosses are displayed only as
> semantically readable candidate labels and are never parsed or decomposed.

> Every candidate label must use a short, neutral, independently sourced dictionary gloss. No poetic, interpretive,
> etymological, or mechanism-specific translation is permitted.

## Freeze index & next action

Hash-pinned artifacts + verdicts: `native_word_specificity_packets/packet_freeze_index.json`.
**Next action (separately-approved, later step):** the blind evaluator run under the frozen protocol — ≥3
family-diverse blind LLM evaluators, temperature 0, frozen seeds, blind to arm/word/mapping. **Not part of this
step.** Vowels stay out of the confirmatory arm until their provenance is raised above `AUTHORED_PROVISIONAL`.

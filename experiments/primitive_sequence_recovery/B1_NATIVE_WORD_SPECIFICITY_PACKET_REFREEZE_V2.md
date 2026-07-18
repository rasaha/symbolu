# B1 — Native Word-Specificity Packet Re-Freeze v2 (docs/data-only)

**Packet verdict: `V2_PACKETS_REFROZEN_AND_BALANCED`. Readiness: `READY_FOR_FOCUSED_V2_PRERUN_AUDIT`.**
Corrects the two defects in the pre-run audit (`73030960`) while preserving the v1 freeze (`aadf7345`) as historical
evidence. **No evaluator run, no judge, no accuracy/result.** Parser, merged lexicon, consonant mappings, Set A/B
membership, dictionary gloss meanings, Gate-G0, prior B1.10 results, and the v1 packet artifacts are **byte-identical
and untouched.** Confirmatory consonant backbone only; no authored vowel/marker in any packet. Structure, not
validated meaning; B1.10's pole-legibility negative (−2.78) and the guarded prior stand; **no positive
word-specificity claim exists before the run.**

## Provenance chain

- Preregistration: `ed6efe31` (design, endpoints, controls, success thresholds — unchanged).
- v1 packet freeze: `aadf7345` (preserved in place at `native_word_specificity_packets/`).
- Pre-run audit (authoritative defect report): `73030960`.
- v2 artifacts: `native_word_specificity_packets_v2/`.

## Defects corrected

### 1. Structural shortcut — arm-confounded correct-answer position → **fixed**

v1 shuffled candidate order from one sequential stream, leaving the correct label's **position** arm-confounded
(arm T concentrated 50% at W6 while control R was uniform → a last-/first-option evaluator could manufacture
Δ≈0.30). v2 replaces this with a **deterministic counterbalanced rotation**: each base trial is presented in
**`REPEATS = 6`** candidate-order rotations, so its correct answer visits **each of W1–W6 exactly once**.

- **Every set × arm correct-position distribution is exactly uniform (χ² = 0).** T/X/S/G/F = `[6,6,6,6,6,6]` per
  set; R = `[30,30,30,30,30,30]`; global `[120,120,120,120,120,120]`. Ledger: `position_balance.json`.
- **Position-bias simulation** (fixed-W3, first-option-W1, last-option-W6): every policy scores exactly `1/6` on
  **every** arm → **primary-contrast Δ = 0.0** for all three. Positional preference alone yields no T-vs-control
  advantage.

### 2. Authoring isolation — procedural → **genuine** (`GENUINELY_CONTEXT_ISOLATED`)

The 17 binding/liberating paraphrases were re-authored by a **genuinely context-isolated** subagent (separate
context window) that received **only** opaque row IDs + original binding/liberating source text + uniform
instructions. It did **not** receive consonant identity, Devanāgarī/IAST, source words, Set A/B, candidate glosses,
the row↔consonant bridge, packet membership, prior v1 paraphrases, prior leak findings, or expected outcomes; and it
was **not** asked to optimize for/against any target. Inputs shown: `isolated_authoring/authoring_input.json`.

Two separate reviews followed:
- **Blind source-equivalence review** (a *second* isolated subagent, given only opaque IDs + source/paraphrase
  pairs): 16/17 rows PRESERVED on first pass; the one drift (r12 binding under-stated the source's "or even harming
  what lies outside it") was **remediated by the same isolated author** (still blind) and now PRESERVED.
  `isolated_authoring/equivalence_review.json`.
- **Leakage review vs candidate glosses** (bridge kept private): **no exact candidate-name leak**; the only
  in-set-exploitable adjacency is **`r15 → body`** ("physically-seen, outward-facing"), a **source-intrinsic,
  pre-flagged** case (deha), faithfully carried from the frozen lexicon — **not** introduced at packet authoring.
  `isolated_authoring/leakage_review.json`. A notable confirmation: the isolated author independently reproduced the
  "physically visible / outward-facing" content (dropping the v1 embellishment "surface"), demonstrating the
  body-adjacency is intrinsic to the source, not authored-in.

### 3. Evaluator protocol frozen literally (no placeholders)

`evaluator_protocol.json` pins the literal prompt template; description/candidate rendering; the strict
`{"choice":"W#"}` response schema; a **prohibition on any explanation / chain-of-thought**; and explicit
invalid-output, retry (≤1), timeout (60 s), duplicate, and missing-response policies. Repetitions per base trial =
**6** (the frozen candidate-order rotations); model-family policy (≥3 families, each **disjoint** from the authoring
family); temperature **0**; deterministic decoding; and the exact scoring rule (per-arm accuracy; primary contrast
`Δ = Acc(T) − max(Acc(X),Acc(R),Acc(G),Acc(F))`; Δ ≥ 0.15 with BCa CI-lower > 0). No `N>=?` placeholders remain.

### 4. Precommitted leak-flagged sensitivity analysis

`analysis_plan_flagged_words.json` precommits a **secondary** analysis for the four source-intrinsic
semantic-adjacency words — **bhaya→fear, duḥkha→pain, sukha→happiness, deha→body** — **without** removing them from
the primary endpoint. It requires: primary results over all trials; sensitivity results excluding the four; per-word
confusion; each flagged word's T vs X/R/G; and an explicit statement of whether the effect is driven only by these
four. Mandatory verbatim caveat:

> Source-intrinsic semantic proximity is part of the mapping under test, but because the upstream lexicon may have
> been authored with semantic awareness, concentration of the effect in these words limits causal interpretation.

Source-faithful proximity is **not** relabelled as packet leakage.

## Preserved study design (unchanged)

Set A, Set B, T/X/S/R/G/F/O definitions, dual-pole rendering, English-only candidate glosses, no raw consonant
symbols, no vowels/markers in confirmatory packets, the primary endpoint and strongest-control contrast, the success
thresholds, and the negative-outcome taxonomy are all unchanged. The only design-surface change is the candidate
**ordering schedule** (now counterbalanced rotation with 6 repeats) and the **paraphrase wording** (isolated
re-authoring) — both required corrections, not weakenings. No success criterion was relaxed.

## Packet counts (presentations)

720 evaluator-facing presentations = 60 base trials/set × 6 rotations × 2 sets. Per set × arm: T 36, X 36, S 36,
R 180, G 36, F 36. Evaluator-facing trial IDs are **opaque** (`t0001…`, deterministically shuffled) and decoupled
from set/arm/word/base/repeat; artifacts expose no Devanāgarī/IAST/consonant/row-id/arm/word/path.

## v2 frozen hashes (sha256, first 12)

| artifact | hash |
|---|---|
| paraphrase_table.json | `f310e5e8e75f` |
| paraphrase_table_v2_authored.json | `f310e5e8e75f` |
| candidate_gloss_table.json | `0568f0b7494e` (byte-identical to v1 — glosses unchanged) |
| leakage_audit.json | `3b477c8120f7` |
| position_balance.json | `7cf1ee349aea` |
| evaluator_facing/trials.json | `ebb441a0c9c4` |
| internal/answer_key.json | `2dcd16973f2e` |
| isolated_authoring/authoring_input.json | `5c7fb1a5fbc2` |
| isolated_authoring/equivalence_review.json | `7e2fa01bf456` |
| isolated_authoring/leakage_review.json | `13fd51c8d22e` |
| evaluator_protocol.json | `6b11bc958aae` |
| analysis_plan_flagged_words.json | `9b3134a6877c` |

Full index + verdicts: `native_word_specificity_packets_v2/packet_freeze_index.json`.

## Preserved upstream hashes (byte-identical)

| protected artifact | sha256 (first 16) |
|---|---|
| sanskrit_stage1_parser.py | `d885391ffc269803` |
| frozen/varna_native_stage1_merged_v1.json | `af4c1f54adbfac2b` |
| b1_native_gate_g0.py | `4bcc8838c924543b` |
| b1_native_word_specificity_prereg.py | `41d9c6df35fa23f1` |
| native_word_specificity_prereg/freeze_index.json | `155baad28dfd6565` |
| native_word_specificity_packets/ (entire v1 freeze) | self-consistent with its frozen_hashes (untouched) |

## Validation

`test_b1_native_word_specificity_packets_v2.py` (17 tests) asserts the 17 required checks: global/per-arm/per-set
position balance; position-agents-no-edge; isolated authoring input carries no identity; one fixed paraphrase per
pole (17); equivalence preserved; no unresolved leakage (0 new, only pre-flagged deha/body survives); control
mechanics; X derangement; R structural; F metadata-only; literal complete prompt; frozen repeat/retry rules;
precommitted flagged analysis; protected artifacts byte-identical; opaque evaluator-facing; deterministic. **Full
related suite: 399 passed.**

## Verdicts & exact next action

- **`V2_PACKETS_REFROZEN_AND_BALANCED`** · **`READY_FOR_FOCUSED_V2_PRERUN_AUDIT`.**
- **Exact next action (not part of this step; no evaluators yet):** a **focused v2 pre-run audit limited to the
  corrected paths** — verify the position balance and position-bias immunity, the genuine authoring isolation and its
  two reviews, the literal protocol completeness, and the precommitted flagged-word plan; confirm no new leakage and
  that all upstream/v1 hashes are preserved. Only on a v2 pre-run PASS do blind evaluator calls proceed. Vowels stay
  out of the confirmatory arm until their provenance rises above `AUTHORED_PROVISIONAL`.

# B1 — Focused v2 Pre-Run Integrity Gate (read-only) @ `42f38d57`

**Gate verdict: `V2_PRERUN_PASS_WITH_DOCUMENTED_SOURCE_INTRINSIC_LIMITATION`.
Readiness: `READY_FOR_FROZEN_BLIND_EVALUATOR_RUN`.**
Final read-only gate on the corrected v2 packets. No packet/paraphrase/gloss/protocol/mapping/parser change; no
evaluator call; no real accuracy. Every finding recomputed independently from the frozen bytes; the frozen evaluator
protocol was dry-run against synthetic responses. Deterministic outputs:
`native_packet_prerun_audit_v2/{audit_findings_v2.json, dry_run_record.json}`.

## Hash verification

All 12 v2 frozen artifacts recompute byte-identically to `packet_freeze_index.json`; working tree clean at
`42f38d57`. Protected upstream + v1 preserved (see §10). The audit reads frozen bytes and does **not** regenerate.

## 1. Position counterbalancing — the shortcut is gone

Recomputed correct-answer position (W1–W6) distributions from the frozen answer key:

- **Per arm — exactly uniform (χ²=0):** T/X/S/G/F = `[12,12,12,12,12,12]`, R = `[60×6]`.
- **Per word — exactly uniform (χ²=0):** every one of the 12 words = `[10,10,10,10,10,10]`; max single-position
  share 1/6. No word concentrated in any position.
- **Per set — uniform (χ²=0);** **same-valence subsets** (Set A negative {bhaya,duḥkha}; Set B positive
  {sukha,yoga}) — **uniform (χ²=0)**: same-valence trials are not concentrated in any position.
- **T's position profile is identical to every primary control** (X, R, G, F).
- **Per-repeat / (arm×repeat)** are non-uniform **by design** — each base trial's six presentations are cyclic
  rotations that **sum** to uniform; the repeat index is **hidden** from evaluators, so this is not exploitable.

**Position-only simulations (primary contrast Δ = Acc(T) − max(X,R,G,F)):**

| policy | Δ |
|---|---|
| always-W1 / always-W6 / fixed-W3 | **0.0** |
| mild primacy (prefers early) / mild recency (prefers late) | **0.0** |
| alternating-by-global-index (order-dependent) | 0.0417 |

**Every order-independent position bias yields exactly 1/6 on every arm → Δ=0.** The single nonzero is an
**order-dependent** "alternate W1/W6 by presentation index" policy; its Δ=0.0417 is an artifact of the specific
frozen opaque-id ordering (not a per-arm position difference), is **3.6× below the 0.15 success threshold**, and is
**unexploitable** — the evaluator cannot see the repeat/order structure, and it nulls in expectation if the run
randomizes presentation order per evaluator. **Non-blocking recommendation:** have the run harness present the 720
frozen items in a per-evaluator randomized order (a run-time choice that changes no frozen artifact). **No position
defect.**

## 2. Authoring isolation — `AUTHORING_ISOLATION_VERIFIED`

The frozen isolated-author input (`isolated_authoring/authoring_input.json`) contains **only** opaque row IDs +
`binding_source`/`liberating_source` text; it contains **no** consonant identity, Devanāgarī, IAST, word, gloss, set
membership, packet membership, row↔consonant bridge, prior paraphrase, expected outcome, or leak finding (verified by
scan and by the explicit `withheld_from_author` list). The authored output covers **exactly the 17 opaque rows, two
poles each**. Authoring ran in a genuinely separate context window.

## 3. Equivalence review

The reviewer received only opaque row ID + source + final paraphrase (no words/glosses/consonants/sets/mappings). All
**34 poles finally PRESERVED**; the one initial drift (r12 binding under-stated "or even harming what lies outside
it") was remediated by the same isolated author and is now preserved. **r15 removes the v1 "surface" embellishment**
(the isolated author wrote "world of appearances," faithfully carrying the source's "physically visible,
outward-facing" without the added body-cue) — confirming the body-adjacency is source-intrinsic, not authored-in. No
paraphrase adds a concept absent from its source; no intensity/polarity was weakened or amplified.

## 4. Leakage classification

Independent exact + broad semantic-neighborhood review of the final paraphrases:

- **No candidate name appears verbatim.**
- **0 `PARAPHRASE_ADDED_CUE`; 0 `UNRESOLVED`.**
- Non-exploitable broad hits (e.g. "misery", "merge", "pained/glad") land on words that do **not** carry that gloss →
  `DISTRACTOR_PULL` (would lower T, never inflate it).
- The **only in-set-exploitable** proximity is **`r15 → body` (deha)** — classified `SOURCE_INTRINSIC_PROXIMITY`,
  faithfully carried from the frozen lexicon and **precommitted** to the flagged-word sensitivity analysis.

**This is the documented limitation.** A blind rater can still partially solve the four flagged words
(bhaya→fear, duḥkha→pain, sukha→happiness, deha→body) from ordinary English semantics traceable to the source vṛtti;
because the upstream lexicon may have been authored with semantic awareness, a positive effect concentrated in these
words has **limited causal interpretation**. v2 introduced **no new** target-specific cue.

## 5. Evaluator-facing opacity

The 720 presentations contain **no** Devanāgarī, IAST, consonant symbol/key, opaque source-row ID, word, arm, set,
repeat, base-sequence, repository path, source filename, or answer-key field. Trial IDs are opaque `t0001…` and do
**not** encode structure. The only `arm`-substring match is "harm" inside the ordinary word "harms" — not metadata.

## 6. Arm mechanics

Recomputed from the frozen packets via the private bridge: **T** = the true frozen rows in order; **X** = strict
derangement, **no fixed points**, a bijection over each set; **S** = same rowset, order only; **R** = length-matched,
**self-excluding** (never a target-own row), 5 frozen instances/word; **G** = word-agnostic dual-pole, length/format
matched; **F** = metadata only, no vṛtti content. **Counts:** T/X/S/G/F = 36 per set, R = 180 per set; every repeat
index carries 120. **No arm classification:** all semantic arms render as identical `{binding,liberating}` rows and
share the same length set `{2,3}`, so packet length/format cannot identify the arm.

## 7. Literal evaluator protocol

`evaluator_protocol.json` pins the literal prompt template; six-option rendering; the strict
`{"choice":"W#"}` enum schema; **CoT/explanation prohibited**; invalid-output, ≤1-retry, 60 s-timeout, duplicate, and
missing-response rules; **repeats = 6** (candidate-order rotations); model-family diversity (≥3, disjoint from the
authoring family) + model/revision recording; temperature 0; deterministic decoding; and the exact scoring rule. **No
`N>=?` placeholders, unresolved variables, or contradictory instructions.**

## 8. Answer-key separation (validated by the dry run)

The reference runner takes only the response payload and **never** references the answer key or mapping bridge;
scoring is a **separate** step; raw responses are **hashed/frozen before** scoring; no result-dependent prompt
modification occurs. The evaluator-facing trials file carries no key.

## 9. Flagged-word sensitivity plan

`analysis_plan_flagged_words.json` precommits: all-trial primary analysis; sensitivity **excluding**
bhaya/duḥkha/sukha/deha; per-word T vs X/R/G; confusion matrices; effect-concentration check; and the mandatory
verbatim caveat that source-intrinsic proximity **limits causal interpretation**. The four words **remain in the
primary endpoint** (explicit prohibition against dropping them).

## 10. Protected-artifact preservation

Byte-identical: parser `d885391f…`; merged lexicon `af4c1f54…`; v3.1 consonant table
`varna_polarity_table_v3_1_metadata_refreeze.json` `9ac712a6…`; Gate-G0 `4bcc8838…`; prereg generator `41d9c6df…` +
freeze `155baad2…`; **v1 packet freeze** (self-consistent with its own frozen_hashes); **v1 pre-run audit**
(`audit_findings.json` `243df64d…`). `git status` shows zero modified tracked files.

## 11. Dry-run protocol validation (no model calls)

A reference runner implementing the frozen protocol was exercised on synthetic responses:

- valid → parsed; **invalid → exactly one retry**; second invalid → **missing** (scored incorrect); timeout → retry;
  second timeout → missing; duplicate/list/prose-wrapped → invalid (then handled). **All 8 branch scenarios pass.**
- **Scoring reproduces expected synthetic accuracies:** oracle (all-correct) = 1.0; always-W1 = exactly 1/6 on every
  arm; all-invalid = 0.0.
- **Raw responses are frozen (hashed) before scoring;** runner never reads the key; retry cap = 1; no result-dependent
  prompt modification. **`dry_run_pass: true`.**

## Gate & readiness

- **`V2_PRERUN_PASS_WITH_DOCUMENTED_SOURCE_INTRINSIC_LIMITATION`** — all integrity dimensions (position, isolation,
  equivalence, opacity, arm mechanics, protocol, separation, dry run, preservation) **pass**; the one standing
  limitation is the **source-intrinsic semantic proximity** for the four flagged words, which re-freezing cannot
  remove and which is properly precommitted to the sensitivity analysis.
- **`READY_FOR_FROZEN_BLIND_EVALUATOR_RUN`.**

## Exact next action

Proceed to the **frozen blind evaluator run** under `evaluator_protocol.json`: ≥3 family-diverse evaluators (each
disjoint from the authoring family), temperature 0, the 6 frozen candidate-order rotations, **presenting the 720
items in a per-evaluator randomized order** (recommended, run-time only), freezing raw responses before scoring, then
scoring with the internal key and running both the primary and the precommitted flagged-word sensitivity analyses.
Interpret any positive effect against the documented source-intrinsic limitation. No packet/paraphrase/gloss/protocol
change is permitted without a new preregistration amendment. B1.10's pole-legibility negative (−2.78) and the guarded
prior stand; no positive word-specificity claim exists before the run.

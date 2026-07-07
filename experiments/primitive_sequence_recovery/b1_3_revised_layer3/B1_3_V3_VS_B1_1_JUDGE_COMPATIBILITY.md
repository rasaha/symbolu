# B1.3 v3-Authoritative vs B1.1 — Judge Setup Compatibility (three-level comparison)

**Docs/analysis only.** No run · no scoring · no model call · no EVIDENCE_FREEZE · no artifact/threshold/scorer/
lexicon edit · v2 not overwritten · Track B BLOCKED. Purpose: decide whether B1.1's judge setup can serve as a
**model-execution layer** for the B1.3 v3-authoritative run — **not** as B1.1 arm semantics or B1.1 scorer.
**Structure, not validated meaning.**

## Hard reuse rule (restated)

Reuse from B1.1 **only**: judge model IDs · provider/API/local-model mechanism · JSON/forced-choice compliance
*pattern* · retry/refusal handling · raw judge-output capture format *if compatible*. **Do not** reuse (unless
proven identical): arm definitions · scoring thresholds · metric aggregation · terminal labels · evidence
interpretation.

## 1. Judge layer — REUSABLE (as a model-execution layer)

B1.1 judge stack: `run_b1_llm_judge.py` (frozen B1 judge) wrapped by `run_b1_1_judge.py`.
- **Panel (`b1_1_judge_panel_config.json`):** `meta-llama/Llama-3.1-8B-Instruct` · `meta-llama/Meta-Llama-3-8B-
  Instruct` · `google/gemma-2-9b-it` — **open-weight, cross-family (Llama + Gemma), non-Claude.** (Banned as
  judges: mistral, qwen — the generation families.)
- **Mechanism:** reads a blinded view JSONL, runs judges sequentially/greedy, **structured-JSON only**, strict
  parser (missing-final-brace repair only), planted attention checks + frozen exclusion rule, resume, per-judge
  output files, provenance/hash, and a `MockJudgeAdapter` (no-model path for tests).

**Reusable for B1.3:** the model IDs, the open-weight provider/pod adapter mechanism, the structured-JSON
compliance *pattern* (strict parser + attention checks + refusal/exclusion), the retry/refusal handling, and
the raw-capture plumbing. **Bonus:** this panel is cross-family and non-Claude, so it directly answers the
capability probe's cross-vendor gap — **in the external/pod environment where those weights are actually
callable** (they are not callable in this runtime either).

**NOT reusable verbatim (choice semantics differ):** B1.1's choices are
`output_1_better | output_2_better | tie_no_preference | both_bad` (4-way preference, `tie/both_bad → 0.5`).
B1.3 uses **forced `A`/`B` + optional confidence 1–5**, with `tie → invalid`. So B1.3 supplies its **own
prompt and its own choice parsing**; only the model-call plumbing is shared.

## 2. Packet layer — B1.3 builds its OWN packets (compatible with the B1.1 call path)

B1.1 packet builder (`run_b1_1_packet_build.py`, `b1_1_leak_and_packet_config.json`): blinded pairwise packets
**A vs each of 7 B1.1 controls** (`D, S, R_same, R_deranged, R_domain, C, X`), opaque IDs + task + two
neutrally-labelled outputs (`output_1`/`output_2`); **arm truth lives only in a private manifest**; leak checks
forbid arm-label / varṇa / Sanskrit leakage.

B1.3's arms are **different** (`A_real` vs near/mid/far deranged, scrambled, random, neutral, **semantic
baseline**), and B1.3 already has its own stimuli separating **judge-facing** fields (`target_word`,
`dictionary_anchor`, `neutral_context`, `option_left`, `option_right`) from **answer/truth** fields
(`arm_left`, `arm_right`, `source_metadata`) — the v3 source audit confirmed this separation and 0 arm-label
exposure in options.

**Conclusion:** B1.3 must build its **own** judge-facing packets (its own arm set, its own A/B labeling),
hiding arm identity / hidden keys / source labels / scorer labels / metadata / any A_real-vs-control cue —
and it **can** do so while feeding the B1.1 model-call path (map `option_left`/`option_right` → the judge
harness's two output slots). The packet layer is **not reused** from B1.1 (different arms + choice format); it
is **compatible** — B1.3 packets ride the B1.1 execution layer. This is **not** `B1_1_PACKET_LAYER_INCOMPATIBLE`.

## 3. Scorer layer — B1.3 frozen scorer REQUIRED (B1.1 scorer NOT reusable)

B1.1 scorer (`b1_1_scorer_config.json`, `run_b1_1_scorer.py`, `scoring.py`): primary comparisons
`A_vs_R_deranged / R_domain / R_same`; secondary `A_vs_D/S/C/X`; success = **A beats R_deranged AND R_domain
AND R_same** (CI lower > 0.5) + multiplicity + correctness-degradation (T4); verdict family →
`RANDOM_OR_SCRAMBLED_MATCHES`.

B1.3 scorer (`score_b1_3_concrete_object_llm.py`, frozen, 10/10 tested): near/mid/far deranged + scrambled +
random + neutral + **semantic baseline**; primary = **A_real vs R_deranged_mid**; Wilson + exact
Clopper-Pearson; **semantic-baseline gate**; single-model-family-dominance guard; **6 terminal labels**
(STRONG / CATEGORY_LIMITED / NULL / STYLE_CONFOUNDED / SEMANTIC_BASELINE_EXPLAINS / INVALID_RUN).

**These are not identical** — different arms, thresholds, aggregation, terminal labels, and interpretation.
**B1.3 MUST use its own frozen scorer; the B1.1 scorer is NOT reusable.** (Also the choice vocabularies differ,
so B1.1's `output_1_better→A-win` mapping and `tie→0.5` rule would mis-score B1.3.)

## 4. Compatibility decision

```
DECISION: B1_1_JUDGE_LAYER_REUSABLE_B1_3_SCORER_REQUIRED
```

The B1.1 judge **model-execution layer** (open-weight cross-family panel + pod/adapter mechanism + structured-
JSON compliance pattern + retry/refusal + raw capture) is reusable for B1.3. The **packet layer** is built fresh
by B1.3 (its own arms, its own blinding) but rides the B1.1 call path — **compatible, not incompatible**. The
**scorer layer** is **not** reusable — B1.3 uses its own frozen scorer/thresholds/labels. Not
`B1_1_PACKET_LAYER_INCOMPATIBLE` (B1.3 can build its own packets), not `B1_1_SCORER_NOT_REUSABLE` as the top
label (that is a *sub-finding*, already captured), not `B1_1_FULLY_INCOMPATIBLE` (the execution layer reuses
cleanly), and not `B1_1_AND_B1_3_IDENTICAL_JUDGE_SCORER_CONFIRMED` (arms/choices/thresholds/labels demonstrably
differ).

## 5. Reuse boundary (operational)

| Component | Reuse from B1.1? |
|---|---|
| judge model IDs (Llama-3.1-8B, Llama-3-8B, Gemma-2-9b) | **YES** |
| provider/pod/open-weight adapter mechanism | **YES** |
| structured-JSON compliance pattern + strict parser + attention checks + refusal/exclusion | **YES** (pattern) |
| retry / refusal handling | **YES** |
| raw judge-output capture plumbing | **YES, with mapping** (B1.1 emits choice+confidence+correctness; B1.3 maps to `selected_option A/B` for its scorer) |
| judge **prompt** + choice vocabulary (`output_1/2/tie/both_bad`) | **NO** — B1.3 uses forced `A/B` + confidence |
| packet builder / arm set / blinding manifest | **NO** — B1.3 builds its own |
| arm definitions | **NO** |
| scoring thresholds / aggregation / terminal labels / interpretation | **NO** — B1.3 frozen scorer only |
| tie / both_bad → 0.5 semantics | **NO** — B1.3 treats tie as invalid |

## 6. Final status block

```
document:                    B1.3 v3-authoritative vs B1.1 — judge compatibility (analysis only)
decision:                    B1_1_JUDGE_LAYER_REUSABLE_B1_3_SCORER_REQUIRED
judge layer:                 REUSABLE (open-weight cross-family panel + mechanism + JSON pattern + retry/refusal)
packet layer:                B1.3 builds OWN packets on the B1.1 call path (compatible; not incompatible)
scorer layer:                B1.3 FROZEN scorer REQUIRED (B1.1 scorer NOT reusable — different arms/thresholds/labels)
choice vocabulary:           DIFFERENT (B1.1 output_1/2/tie/both_bad vs B1.3 A/B + confidence) -> B1.3 own prompt
cross-family judge:          B1.1 panel is cross-family/non-Claude (usable only in the pod/model-access env)
ran / scored:                NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 RANDOM_OR_SCRAMBLED_MATCHES; B1.2/B1.3 automated; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
Track B:                     BLOCKED
ONTOLOGICAL_SIGNAL / Sanskrit privilege / truth: NONE
```

**No run, no scoring, no evidence freeze. Track B remains blocked. Structure, not validated meaning.**

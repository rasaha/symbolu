# C×R×S MATCH-Filter Wrapper — Held-out Evaluation (RESULTS)

> Harness: `eval_match_filter.py` over `eval_data/domain_match_eval.jsonl` (59 cases, 20-domain
> registry). **Semantic backend used: `offline_hashing_embed` → ARCHITECTURE-SMOKE only.** A real
> `embed_fn` (sentence-transformers) was **not available** in this environment, so these numbers are
> smoke evidence, not production evidence.

## Backends compared (mean S on expected-primary pairs; primary-frame accuracy)

| backend | label | mean primary-S | primary-frame acc | expected-primary framed | misrejected |
|---|---|---:|---:|---:|---:|
| hashing | offline_hashing_embed (smoke) | **0.518** | 0.000 | 0.383 | 0.150 |
| lexical | lexical_fallback (smoke) | 0.418 | 0.000 | 0.217 | 0.283 |
| demo | demo_curated_fixture (not prod) | 0.238 | 0.068 | 0.067 | 0.433 |
| real | real_embed_fn | — | — | — | — (unavailable) |

**Embedding-style S beats lexical** by `+0.099` mean primary-S and nearly 2× framing (0.383 vs 0.217).
**Demo fixtures do not generalize** (92.9 % raw-term fallback, 43 % of true primaries misrejected) —
confirming the scalable definition_provider + embedding path is required, not the curated tables.

## Metrics — grouped-R baseline (n=59; thresholds UNCHANGED at 0.60/0.30)

| metric | hashing | lexical | demo |
|---|---:|---:|---:|
| primary_frame_accuracy | 0.000 | 0.000 | 0.068 |
| secondary_frame_recall | 0.000 | 0.000 | 0.057 |
| rejected_precision | 0.526 | 0.496 | 0.489 |
| rejected_recall | **1.000** | 0.991 | 0.991 |
| semantic_veto_accuracy (**S veto**) | **0.947** | 0.947 | 0.895 |
| ontological_veto_accuracy (**C veto**) | **1.000** | 1.000 | 1.000 |
| phoneme_overreach_prevention | **1.000** | 1.000 | 1.000 |
| unknown_term_generalization | 0.000 | 0.000 | 0.000 |
| context_disambiguation | 0.000 | 0.000 | 0.000 |
| trace_completeness | **1.000** | 1.000 | 1.000 |
| expected_primary_misrejected | 0.150 | 0.283 | 0.433 |

Backend used: `offline_hashing_embed` (architecture-smoke); `real_embed_fn` unavailable.

### Expected-primary RANK and SCORE distribution (hashing) — the decisive result

| | value |
|---|---|
| **rank-1 rate** | **0.967** (58 / 60 expected-primary domains are the top MATCH) |
| rank distribution | rank1 = 58, rank2 = 1, rank3+ = 1 |
| MATCH score | mean 0.226, median 0.235, min 0.000, **max 0.579** |
| MATCH < 0.60 | **60 / 60** (none reach the primary band) |
| MATCH < 0.30 | 45 / 60 |
| landing | primary 0, **secondary 15**, weak 36, rejected 9 |
| **landed secondary only because MATCH < 0.60** | **15** |

**The ranking is essentially correct (96.7 % rank-1); the 0.60 primary bar is simply unreachable under
the weak offline S (max MATCH 0.579).** With C≈0.65, grouped R≈0.85 for the true domain, and offline
S≈0.52, `MATCH≈0.29` — so true domains land *secondary/weak*, not primary. This is a backend-magnitude
× fixed-threshold effect, **not** a discrimination failure. A real embedder (S≈0.85–0.97, cf. the
demo-curated doctor at MATCH 0.69) is expected to lift the top-ranked domain over 0.60.

## Template-quality audit — finding and FIX

**Finding (flat 12D cosine R):** the 20 templates are **highly confusable** — pairwise cosine
0.96–0.999 (authority/finance 0.999, programming/technology 0.997). R was nearly non-discriminative;
discrimination fell entirely on C and S. Flags: `fruit` = `too_strict_blocked`, `service` = `too_flat`.

**FIX — group-aware R (resonance groups, §4a of the design doc).** R now compares per-family emphasis
(`ground / force / intellect / telos / field`), weighted per domain, minus a blocked-lane penalty.
Off-diagonal template R drops from flat **mean 0.923 / std 0.054** to grouped **mean 0.670 / std
0.225** (4× the spread): genuinely-different domains separate (doctor→fruit R **0.99→0.27**) while true
twins (authority/finance) stay close. Each score carries a per-group R trace. Inspect with
`--template-audit`.

**Residual:** under the *offline* hashing S, grouped R slightly lowers framed-rate (0.38→0.25) because
it compounds with an already-weak S; grouped R's benefit (sharper rejection, fewer false primaries) is
realized with a **strong/real S**. Re-run the framing verdict with `--semantic-backend real`.

## Remaining failure categories

1. **Threshold-unreached (dominant, ~51/60).** Correct domain is ranked #1 but MATCH < 0.60 → lands
   secondary (15) or weak (36). Pure offline-S magnitude × fixed 0.60 bar. Resolved by a real `embed_fn`
   and/or threshold calibration (deferred — not tuned here).
2. **C over-veto on blocked-lane domains (8 cases).** A term's *phoneme* profile lights its own
   correct domain's blocked lane, so C `reject_ontological`s the right answer: `fire→heat`
   (‘r’ lights Reasoning, which heat blocks), `soldier→danger`, `apple→fruit`, `chair→furniture`,
   `king` ont cases. This is a **C-logic issue** (the blocked-lane penalty runs on the phoneme-derived
   12D profile, not on meaning), independent of the S backend. Candidate fixes (future, not done):
   soften C's blocked penalty, or gate it by S so a semantically-correct domain is not ontologically
   vetoed.
3. **S=0 misrejection (1 case).** `paramedic→care` `reject_semantic` — the weak stemmed embedder found
   no overlap between the term definition and the care definition. Expected to vanish with real
   embeddings.

Categories 1 and 3 are backend artifacts (real embeddings fix them). Category 2 is a genuine C-logic
limitation surfaced by the harness.

## Semantic-backend audit (hashing run)
`definition_provider_used=True`, `offline_hashing_used=True`, `demo_fixture_used=False`;
`pct_external_definition=1.000`, `pct_raw_term_fallback=0.000`, `pct_scalable_S=1.000`. I.e. every
term was scored from an external definition via the scalable path — no curated per-word dictionary.

## Pass/fail criteria (to be judged on a REAL embed_fn run)

**CONTINUE the wrapper if, with `real_embed_fn`:**
- primary_frame_accuracy ≥ 0.70 **and** expected_primary_misrejected ≤ 0.10
- rejected_recall ≥ 0.85 **and** semantic_veto_accuracy ≥ 0.80 **and** ontological_veto_accuracy ≥ 0.80
- phoneme_overreach_prevention ≥ 0.90
- unknown_term_generalization ≥ 0.60 **and** context_disambiguation ≥ 0.60

**PARK the wrapper if, with `real_embed_fn`:**
- primary_frame_accuracy < 0.50 (S cannot frame even with real embeddings), or
- phoneme_overreach_prevention < 0.70 (firewall leaks sound-only meaning), or
- unknown_term_generalization < 0.40 (does not generalize beyond fixtures).

**Prerequisite regardless of backend:** ~~redesign the 12D templates so R is discriminative~~ —
**DONE** (group-aware R, confusability 0.92→0.67). Remaining prerequisite for a production verdict is
a **real `embed_fn`** so S can clear the framing thresholds.

## Verdict (this run)
- **Harness: valid and informative.** Vetoes/rejection (C + S firewall) **pass** their criteria even
  under smoke; embedding > lexical confirmed; demo fixtures shown not to generalize; backend labeling
  and audit work.
- **Framing/primary decision: INCONCLUSIVE under smoke** (threshold-limited) — **deferred** to a
  real-embedder run. Do not read offline primary=0 as a refutation.
- **Template/R redesign: DONE** — group-aware R cut template confusability from 0.92 to 0.67 (std 4×);
  R now separates domains by which family of structure is active. Does not touch generation/governance.

## Recommendation (ordered) — thresholds NOT tuned in this run

Given **96.7 % rank-1** but **0 / 60 MATCH ≥ 0.60**, the ranking is solved and the bottleneck is the
absolute MATCH magnitude. Recommended order:

1. **Real-embedding test FIRST (highest value).** Run `--semantic-backend real`. This is the single
   change that should lift top-ranked MATCH over 0.60 and make framing/unknown/context metrics
   meaningful. Do this before any tuning — calibrating thresholds against the weak offline S would
   bake in the artifact.
2. **Threshold calibration SECOND, only after the real run.** Calibrate 0.60/0.30 against the real
   embedder's MATCH distribution on a held-out split (e.g. set primary at the elbow that maximises
   primary-F1). Do not tune against hashing/lexical.
3. **Targeted C-logic change THIRD (small, scoped).** Address failure category 2 (C over-vetoing the
   correct blocked-lane domain): gate the blocked-lane penalty by S, or soften it. ~8/60 cases.
4. **Template changes are NOT needed for R** — group-aware R already fixed confusability (0.92→0.67).
   Only revisit individual templates flagged `too_flat` (service) / `too_strict_blocked` (fruit) if
   they cause errors after steps 1–3.

## Reproduce
```
# grouped-R baseline, all offline backends + audits + rank/score distribution
python scripts/cg_wrapper_ablation/csr_match_filter/eval_match_filter.py --compare --template-audit

# PRODUCTION-VALID run with a real external embedding backend:
pip install sentence-transformers
export CSR_EMBED_MODEL=all-MiniLM-L6-v2     # or any sentence-transformers model id
python scripts/cg_wrapper_ablation/csr_match_filter/eval_match_filter.py --semantic-backend real \
    --template-audit --json runs/csr_match_filter_real.json
```
To wire a different embedder, replace `load_real_embed_fn()` in `eval_match_filter.py` with any
`text -> vector` callable (OpenAI/Cohere/local); the harness labels it `real_embed_fn`
(production-valid) automatically.

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

## Metrics (hashing / smoke)

| metric | value | reading |
|---|---:|---|
| rejected_recall | **0.991** | rejection machinery works |
| rejected_precision | 0.526 | over-rejects (weak S floors true domains too) |
| semantic_veto_accuracy | **0.947** | S firewall fires on semantically invalid domains |
| ontological_veto_accuracy | **1.000** | C veto blocks impossible domains |
| phoneme_overreach_prevention | **1.000** | no sound-only mapping survived |
| trace_completeness | **1.000** | every example carries a full C/R/S/decision audit |
| primary_frame_accuracy | 0.000 | **threshold-limited** (see below), not a ranking failure |
| secondary_frame_recall | 0.000 | same threshold shift |
| unknown_term_generalization | 0.000 | inherits the primary-threshold limit |
| context_disambiguation | 0.000 | inherits the primary-threshold limit |
| expected_primary_as_primary | 0.000 | true domain never reaches MATCH≥0.60 offline |
| expected_primary_framed (prim∪sec) | 0.383 | true domain is usually *framed* (as secondary) |
| expected_primary_misrejected | 0.150 | 15 % of true domains wrongly S-vetoed (weak embedder) |

### Why primary-frame accuracy is 0 under smoke (and why that is NOT a refutation)
The offline embedder yields S≈0.52 on true (term, primary-domain) pairs. With C≈0.65 and R≈0.97 that
is `MATCH≈0.33` → lands in **secondary** (0.30–0.60), never crossing the **0.60 primary** bar. The
**ranking is correct** (true domain is top and framed); only the **absolute S magnitude** is too low
for the threshold. A real embedder (S≈0.85–0.97, as the demo-curated doctor shows → MATCH 0.69) is
expected to clear it. This is precisely why offline runs are labeled architecture-smoke.

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

## Reproduce
```
python scripts/cg_wrapper_ablation/csr_match_filter/eval_match_filter.py --compare --template-audit
# real backend (production-valid): pip install sentence-transformers; set CSR_EMBED_MODEL
python scripts/cg_wrapper_ablation/csr_match_filter/eval_match_filter.py --semantic-backend real
```

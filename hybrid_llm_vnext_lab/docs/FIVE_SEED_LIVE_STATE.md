# Five-Seed Validation — Live State

**Date:** 2026-08-03 · Machine-readable: [`../artifacts/five_seed_live_state.json`](../artifacts/five_seed_live_state.json)

| Field | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-…` @ `3b521f0f` |
| PR #1298 | **MERGED** 2026-08-03T07:01:53Z, merge commit `3b521f0f` (= default HEAD) |
| Work branch | `claude/hybrid-llm-slots-five-seed-validation` (from `3b521f0f`) |
| Branch note | prompt suggested `chatgpt/…`; this environment mandates `claude/` prefixes — documented difference |
| Working tree at start | clean |
| Existing five-seed PR | none |

## Frozen historical artifact
`experiments/phase_lc/results/abc.json`: git blob `cbcd94f1`; sha256 `b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482`; 23218 bytes — **unchanged** (guarded pre/post every run).

## Prior three-seed artifacts on default (frozen, reported separately)
`slots_only_results_sarm_1200_run1.json` blob `fdeca65c`; `historical_abc_reproduction.json` blob `30b537bf`.

## Baseline verifiers (on the starting commit)
audit **201/0** · lab **58/0** · historical-artifact-protection **8/0** · stdlib **41/0** · neural parity **EXACT (4 passed)** · no-Phase boundary **2 passed**.

## Environment
python 3.11.15 · **torch 2.13.0** · numpy 1.26.4 · CPU fp32 · 4 threads.

## Evidence present on default
Exact A/B/C reproduction ✓ · exact neural parity ✓ · S-arm seeds 0,1,2 ✓ · immutable reproduction artifacts ✓ · historical-artifact protection ✓ · no-Phase AST tests ✓ · manual neural workflow ✓ · lab verifier ✓.

## Holdout policy
Primary verdict from seeds **3,4,5,6,7** (new). Seeds 0–2 frozen/separate. Seeds 0–7 supplementary only.

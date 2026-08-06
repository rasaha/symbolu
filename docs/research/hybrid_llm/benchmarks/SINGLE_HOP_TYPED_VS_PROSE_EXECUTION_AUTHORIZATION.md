# Single-hop typed-vs-prose benchmark — execution authorization

**Status: `EXECUTION_AUTHORIZED` (owner-authorized).** This record is the merged authorization
that the fail-closed reserved-seed gate (`experiments/single_hop_typed_vs_prose/execution.py`)
refers to. Before this record the token registry was empty and every reserved seed failed closed.

Always preserved, and **not** touched by this run or its outcome:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`. This run can emit **only** a `TYPED_STRUCTURE_SINGLE_HOP_*` verdict; it
can never emit `E1_STRUCTURAL_TRANSFER_CONFIRMED`, `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`,
`KDA_VALIDATION_ELIGIBLE`, or `PRODUCTION_READY`.

## What was authorized, by whom
The repository owner explicitly authorized (1) fixing the delivered implementation and (2)
building the missing real benchmark dataset and executing the benchmark correctly, in the owner's
own words: *"I authorize to fix the implementation and execute it correctly,"* and, when asked to
choose the scope, *"Build it properly, then run."* That is the authorization for the smoke,
development, and reserved final seeds registered below.

The authorization covers exactly:
- **Fixing** implementation defects (documented in the run report) with no change to the frozen
  scientific design — serializers, tokenizer, schema, output contract, model/optimizer recipe,
  numeric gates, and conclusion vocabulary are **not** tuned to favor either arm or to pass.
- **Building** the real pooled dataset required by the preregistration: many episodes per
  scenario with **disjoint train vs. final identity pools**, so evaluation requires copying the
  answer identifier from context rather than memorizing it.
- **Executing** the frozen protocol: smoke → development → reserved final, applying the frozen
  Decision-3 gates and mandatory causal/shortcut gates, and reporting one honest verdict —
  whatever it is (validated / partial / not-found / a gate failure).

## Reserved seeds and roles (fail-closed tokens)
| Role | Seeds | Token constant (config.py) | Purpose |
|---|---|---|---|
| smoke | 76 | `SMOKE_AUTHORIZATION_TOKEN` | feasibility only; never contributes to a threshold/verdict |
| development | 760, 761, 762 | `DEVELOPMENT_AUTHORIZATION_TOKEN` | correctness / determinism / leakage / budget only; **no tuning** |
| final | 7160–7164 | `FINAL_AUTHORIZATION_TOKEN` | the reserved head-to-head B0-vs-B1 comparison |

Any non-reserved seed remains ungated; any reserved seed without the exact role token still fails
closed (`ExecutionNotAuthorized`).

## Frozen design (set BEFORE any reserved run)
Locked in `experiments/single_hop_typed_vs_prose/benchmark.py` and `driver.py` and committed
before the final seeds executed:
- Train identity pool = numeric suffix **[100, 600)**; final identity pool = **[600, 1000)** —
  disjoint, so a correct answer on the final pool cannot be a memorized training identifier.
- **40** train + **24** eval episodes per scenario (8 scenarios): 320 train, 192 eval per seed.
- One frozen model recipe (`FROZEN_MODEL_RECIPE`: 64-dim, 2 layers, 4 heads, 256 d_ff, vocab 200,
  dropout 0) and one frozen optimizer recipe (`FROZEN_TRAIN_RECIPE`: AdamW 3e-4, batch 8, 2000
  updates). Identical for both arms; only the input representation (B0 prose vs B1 JSON) differs.
- Decision-6 domain-separated sub-seed derivation `sub_seed(seed, domain) = seed*1_000_003 +
  DOMAIN_ID*97 + 13`, `DOMAIN_ID = {dataset:0, init:1, batch:2, perturb:3}`. Both arms share the
  dataset, init, and batch sub-seeds; only the serialized representation differs.
- Evaluation decode cap = **96 tokens** (arm-neutral; every valid gold output ≤ 38 tokens and
  every ablation represented-output ≤ 62 tokens, so 96 never truncates a correct answer for
  either arm). This is an evaluation-efficiency bound, not the frozen training output allowance.
- Gates read verbatim from `SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md` (Decision 3 endpoint gates,
  the mandatory causal gates A1–A6, and the shortcut-baseline gates). Gates are frozen before
  results and are **not** adjusted after inspecting reserved results.

## Integrity commitments
- No serializer/tokenizer/schema/gate/threshold is tuned to favor either arm or to pass.
- Development seeds may trigger only documented implementation **bug fixes** (never design or gate
  changes); any such fix invalidates affected dev evidence and is recorded in the report.
- The reported verdict is the mechanical result of the frozen gates, reported honestly.

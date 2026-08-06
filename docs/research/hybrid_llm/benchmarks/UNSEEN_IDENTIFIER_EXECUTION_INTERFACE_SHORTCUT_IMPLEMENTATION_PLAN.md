# Unseen-identifier execution-interface & shortcut completion — implementation plan (DRAFT, docs-only)

**Documentation-only. No code, no execution, no cohort, no seed consumption in this session.**
This plan freezes a *future*, separately-authorized implementation that completes the execution
interface and the shortcut suite so PR #1373 can later present exact, supported commands. It reuses
the frozen model/tokenizer/trainer/config by import; it does not change the protocol, gates, recipe,
tokenizer, seeds, task definitions, or claim boundary.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Decision 1 — Frozen planned package changes (smallest extension)
The future implementation extends `experiments/unseen_identifier_copy_selection/` without
duplicating the frozen model/tokenizer/trainer/config. Every file it may add or modify:

| File | New/Mod | Purpose | Allowed side effects | Forbidden |
|---|---|---|---|---|
| `cli.py` | new | argparse CLI + subcommands; per-command authorization + guard checks | parse args; call orchestrators; write only under `--output-dir` | no wildcard/range/list seeds; no env-only auth |
| `__main__.py` | new | `python -m …` entry → `cli.main` | none beyond `cli` | no logic of its own |
| `execution.py` | mod | add fail-closed authorization-record schema + validation | none | no scientific token minted here |
| `training.py` | new | frozen-model training orchestration (encode → `train_in_memory` → checkpoint) | write checkpoint under output-dir | no new module/head/loss/optimizer; no training in tests |
| `evaluation.py` | new | checkpoint load → greedy decode → parse → per-example predictions/metrics | write traces/metrics under output-dir | no constrained decoding; no candidate-index; no silent repair |
| `replay.py` | new | deterministic replay + digest comparison | write replay manifest under output-dir | no scientific run in tests |
| `evidence.py` | new | run-manifest assembly + per-example trace emission (atomic) | write evidence files under output-dir | no aggregate-only package; no write outside output-dir |
| `manifest.py` | mod | add run-manifest schema helpers (actual digests) | none | none |
| `shortcuts.py` | mod | add the 4 missing baselines + cross-seed aggregation | none | no threshold/candidate/seed change |
| `runner.py` | mod | thin orchestration helpers if needed (still fail-closed) | none | no bypass of primitive guards |
| `tests/experiments/unseen_identifier_copy_selection/test_*.py` | new/mod | fixture-only tests (seeds 993000–993004) | none | no reserved seed; no training; no scientific artifact |
| `.github/workflows/unseen-identifier-integrity.yml` | mod | run the new fixture-only tests | none | no train/cohort/reserved-seed/verdict |

**No unspecified file may be changed during later implementation without a scoped authorization
correction.** Fewer files are acceptable if sufficient (e.g., `training.py`/`evaluation.py`/
`replay.py`/`evidence.py` could be consolidated), provided every capability below is delivered and
every guard is preserved.

## Decision 2 — Frozen CLI surface (real, not illustrative)
Invocation: `python -m experiments.unseen_identifier_copy_selection <subcommand> ...`. Required
subcommands, each with frozen name / required args / optional args / accepted values / output
artifacts / exit codes / refusal conditions:

| Subcommand | Required args | Output | Refuses when |
|---|---|---|---|
| `build-cohort` | `--seed` `--cohort` `--authorization-record` `--output-dir` | cohort + dataset digests | reserved seed w/o valid record; existing output-dir |
| `shortcut-precheck` | `--seed` `--cohort` `--authorization-record` `--output-dir` | shortcut results (per-split, per-seed) | same |
| `train` | `--seed` `--cohort` `--authorization-record` `--output-dir` | checkpoint + init/batch digests | same; missing dataset |
| `evaluate` | `--seed` `--cohort` `--authorization-record` `--output-dir` | per-example traces + metrics | same; missing checkpoint |
| `replay` | `--seed` `--cohort` `--authorization-record` `--output-dir` | replay manifest + digest compare | same; digest mismatch |
| `assemble-manifest` | `--seed` `--cohort` `--authorization-record` `--output-dir` | run manifest | same; incomplete run |

Every scientific-facing subcommand requires **exactly one explicit `--seed`**, explicit `--cohort`,
explicit `--authorization-record`, explicit `--output-dir`, and verifies frozen
source/config/protocol identity. **No wildcard · no range · no seed list · no implicit
"all development seeds" mode · no environment-variable-only authorization.** A command must be
**incapable** of including a final seed via range/glob/alias/default. The CLI may be implemented
later; **no valid scientific authorization record or token is created under this authorization.**

## Decision 3 — Frozen authorization-record contract (fail-closed)
A future authorization record binds: authorization state · exact permitted cohort · exact permitted
seed(s) · protocol-lock commit · implementation-authorization commit · implementation commit ·
model-recipe hashes · parameter count · one-run/expiry scope (if repo practice supports it) · record
digest. The CLI must: require the record explicitly · validate it **before any pool generation** ·
thread authorization through **every** generation primitive (`build_pools`/`generate_pool`/
`generate_split`) · reject unknown/malformed records · reject mismatched commits · reject mismatched
cohort · reject any unlisted seed · reject final seeds unless a later explicit final authorization
exists. Fixture tests may use **fixture-only** authorization records bound exclusively to fixture
seeds `993000–993004`. **No scientific authorization record is created in this session.**

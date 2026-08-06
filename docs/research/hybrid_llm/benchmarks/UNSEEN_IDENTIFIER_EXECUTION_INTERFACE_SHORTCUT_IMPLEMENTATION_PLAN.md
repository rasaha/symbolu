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

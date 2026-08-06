# Unseen-identifier copy/selection diagnostic (implementation)

Bounded implementation of the diagnostic frozen in
`docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCK.md` and scoped by
`…_IMPLEMENTATION_PLAN.md` / `…_IMPLEMENTATION_AUTHORIZATION.md` (merged PR #1370).

**Implementation only. This package does not authorize execution.** It generates no reserved cohort,
trains no model, and consumes no reserved seed in tests or CI. Reserved diagnostic seeds
(smoke 9070 / development 9071–9073 / final 90760–90764) are **fail-closed**
(`execution.require_execution_authorization`); unit fixtures use the separate testing namespace
`993000–993004`.

The model / tokenizer / trainer / frozen recipe are **reused by import** from
`experiments/single_hop_typed_vs_prose/` (209,728 parameters; never redefined or copied).

## Modules
| Module | Role |
|---|---|
| `config.py` | frozen constants; imports the frozen recipe; seed roles; sub-seed derivation |
| `execution.py` | fail-closed reserved-seed gate (empty token registry → reserved seeds raise) |
| `identifiers.py` | disjoint train/final/evidence master pools; collision / character-visibility checks |
| `tasks.py` | deterministic C1–C8 example construction with per-example metadata |
| `serializer.py` | the one frozen plain-text representation (byte-identical; no candidate-index) |
| `parser.py` | exact-output classifier (7 categories; no silent repair; no constrained decoding) |
| `metrics.py` | pure deterministic metric functions |
| `verdict.py` | frozen gates + first-match-wins verdict precedence (Decision 8) |
| `shortcuts.py` | per-split structure-blind baselines + pre-reserved precheck |
| `manifest.py` | actual-value fingerprint / hash utilities |
| `runner.py` | future CLI — fail-closed, **unexecuted** (raises on reserved seeds / failing shortcut) |

## What this package deliberately excludes
No constrained decoding · candidate-index output · candidate-ranking objective · pointer/copy head ·
curriculum · capacity change · tokenizer change · BindingSlots · E1 memory · relational reader ·
pretrained model · multi-hop / temporal / enterprise task. Preserves
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

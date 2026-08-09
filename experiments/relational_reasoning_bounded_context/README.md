# Bounded Typed Relational Reasoning (BTRR) — implementation

**Implementation only. Execution is NOT authorized.** Reserved scientific seeds (smoke `8100`,
development `8101–8103`, final `81600–81604`) fail closed until `EXECUTION_AUTHORIZATION.md` is signed.
Implementation tests use only inadmissible unit-fixture seeds `883000–883004`; their results are
scientifically inadmissible.

Effective authority: **Amendment 002** (`a84cc8eef848e7081764deb894593f7b270f32ba`).
Provenance chain: original preregistration `626a897a…` → implementation blocker `f8dd65c5…` →
Amendment 001 `9e6168f9…` → Amendment 002 `a84cc8ee…`.

## Frozen representation (Amendment 002)
BTRR-specific frozen tokenizer (`tokenizer.py`, 80 lexemes, vocab 211) — the single-hop tokenizer is not
modified. `input_token_limit = 3520`, `output_token_limit = 384`, `max_seq_len = 3904`. Reasoning
architecture unchanged (`d_model 64`, 2 layers, 4 heads, FFN 256, dropout 0, causal SDPA / RMSNorm /
SwiGLU backbone; output-only CE; greedy decoding). Total params **394,752**; reasoning blocks **131,392**
(delta 0 vs the original single-hop recipe).

## Module map (preregistered responsibility → file)
| Preregistered file | Implemented as | Notes |
|---|---|---|
| schema_ext.py | `schema_ext.py` | Entity/Relation/Event/Condition/Policy/Constraints/ReasoningQuery/ReasoningContext/ReasoningOutput; caps, FK, tenant purity, PATH_DISCOVERY exclusion, `visible_canonical`, `fact_hash` |
| serializer.py | `serializer.py` | compact typed input serializer + zero-truncation guard |
| output.py | `output.py` | strict structured-output parser + serializer |
| base_capability.py | `base_capability.py` | P0 B1–B7 + gate |
| generator.py | `generator.py` | deterministic P0 + R1–R12 |
| metrics.py | `metrics.py` | all metrics + R9 decomposition + input-length instrumentation |
| shortcuts.py | `shortcuts.py` | structure-blind baselines + length-shortcut control |
| gates.py | `gates.py` | frozen numeric gates (non-compensation) |
| verdict.py | `verdict.py` | precedence (0 PROTOCOL_VIOLATED → 1 base capability → …) |
| execution.py | `execution.py` | fail-closed seed guard |
| driver.py | `driver.py` | fail-closed top-level orchestration (dry-run only) |
| trainer.py | `trainer.py` | ONE-checkpoint training loop (lazy torch) |
| eval.py | `eval.py` | single-checkpoint paired-evidence orchestration + admissibility |
| manifest.py | `manifest.py` | provenance + source hashes |
| replay.py | `replay.py` | deterministic replay checks |
| tests/ | `tests/test_btrr.py` | stdlib runner (no pytest/torch) |
| config.py | `config.py` | frozen constants + analytic parameter assertions |

No filename substitutions were required. `torch` is imported lazily inside `model.py`/`trainer.py` only;
the package imports torch-free.

## Run implementation tests
```
python3 -m experiments.relational_reasoning_bounded_context.tests.test_btrr
```
Torch is not required; no reserved seed is consumed; no model is trained.

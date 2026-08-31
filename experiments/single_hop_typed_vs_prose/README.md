# Single-hop typed-vs-prose implementation

This package is the bounded implementation authorized by
`SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md`.

**State: implementation code only; benchmark execution is not authorized.**

## What is implemented

- immutable canonical entity/relation/evidence/query/output records;
- deterministic B0 grammatical-prose and B1 canonical-JSON serializers;
- shared semantic fact hash and fail-closed integrity checks;
- fixed reversible lexical tokenizer (ASCII-character fallback plus frozen protocol lexemes);
- one plain non-memory causal softmax Transformer reused from
  `symbolu_neural.clean_softmax.backbone`;
- one shared weight-tied autoregressive output head for both arms;
- output-only next-token loss;
- deterministic in-memory S1–S8 fixture generator;
- evaluation-only A1–A6 transformations with represented-output expectations;
- strict shared JSON parser/evaluator;
- deterministic in-memory trainer primitives;
- hard seed gate for smoke, development, and final benchmark seeds.

## Frozen model recipe

- 64 hidden dimensions;
- 2 causal Transformer layers;
- 4 attention heads;
- 256-wide SwiGLU feed-forward blocks;
- 1024 maximum sequence length;
- zero dropout;
- maximum 512 input tokens including the common `\n<OUTPUT>\n` marker;
- maximum 384 output tokens;
- no truncation.

## Explicit exclusions

No BindingSlots, E1, recurrent memory, prefix memory, Phase, KDA, MLA, T5, event
reader, bounded quadratic relational reader, pretrained model, external API,
retrieval table, typed-only encoder, typed-only output head, multi-hop task, or
answer-time correction is imported or implemented.

## Tests

The dedicated tests exercise mechanical correctness only. They use a non-benchmark
test seed and do not produce admissible smoke, development, final, or scientific
evidence.

```bash
pytest -q tests/experiments/single_hop_typed_vs_prose
```

No CLI run is provided in this implementation PR. Any future execution entrypoint
must call `guard_seed` before data generation, model initialization, or output
creation and requires a separately merged execution-authorization record.

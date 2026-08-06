# Single-hop typed-vs-prose — implementation authorization

**Status: `IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`.**

This document authorizes one bounded implementation step that removes the model-recipe blocker recorded in
`SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md`. It does **not** authorize dataset materialization, smoke,
development, reserved-seed execution, result inspection, threshold changes, or scientific conclusions.

Standing invariants remain unchanged:

- `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
- `E1_TEMPORAL_TRANSFER_PARTIAL`
- `KDA_VALIDATION_BLOCKED`

No implementation result may emit `E1_STRUCTURAL_TRANSFER_CONFIRMED`,
`E1_FOLLOW_ON_RESEARCH_ELIGIBLE`, `KDA_VALIDATION_ELIGIBLE`, or `PRODUCTION_READY`.

## 1. Authorized objective

Implement the smallest deterministic, non-memory, tokenizer-based, from-scratch sequence-model harness that
can train and evaluate both preregistered arms through one shared text channel and one shared autoregressive
output head:

- **B0:** frozen grammatical-prose serialization;
- **B1:** frozen canonical typed JSON serialization;
- **output:** the same canonical seven-field JSON object for both arms.

The implementation must make input representation the only arm-specific variable.

## 2. Authorized package and dependency boundary

Create exactly one isolated package:

```text
experiments/single_hop_typed_vs_prose/
```

The package may import the existing generic baseline classes
`symbolu_neural.clean_softmax.backbone.BackboneConfig` and
`symbolu_neural.clean_softmax.backbone.SoftmaxTransformerLM` without modifying those files.

No other model architecture or research subsystem may be imported into the model path.

## 3. Frozen model recipe

The implementation shall instantiate the unmodified plain causal softmax decoder-only Transformer with:

| Field | Frozen value |
|---|---:|
| tokenizer vocabulary | 259 IDs |
| raw byte IDs | 0–255 |
| PAD / BOS / EOS | 256 / 257 / 258 |
| `d_model` | 64 |
| layers | 2 |
| heads | 4 |
| feed-forward width | 256 |
| maximum sequence length | 1024 |
| dropout | 0.0 |
| output head | existing weight-tied vocabulary head |
| attention | ordinary causal softmax attention |

The model is trained from scratch. No pretrained checkpoint, adapter, retrieval table, external model API,
phase mechanism, recurrent state, slot memory, episodic memory, typed-only encoder, typed-only head, event
reader, bounded quadratic relation reader, or answer-time correction is permitted.

The same model class, configuration, tokenizer, vocabulary, output head, loss, optimizer, update count,
initialization seed, batch order, and evaluator are used for B0 and B1.

## 4. Shared input and output channel

Both arms use the fixed byte tokenizer. There is no arm ID, arm token, arm-specific prefix, field-specific
embedding, or arm-specific prompt.

The complete model prompt is:

```text
{SERIALIZED_INPUT}\n<OUTPUT>\n
```

The marker is identical in both arms and is included in the common input-token budget.

Frozen limits:

- maximum input tokens, including the shared marker: **512**;
- maximum output tokens, excluding EOS: **384**;
- complete sequence: BOS + input + output + EOS;
- any over-budget example fails closed before model exposure;
- no truncation, arm-specific compression, or padding-based information equalization.

The output is canonical minified UTF-8 JSON with exactly these fields in this order:

```json
{
  "status": "ANSWERED | INSUFFICIENT_EVIDENCE",
  "selected_entity_id": "... | null",
  "selected_relation_type": "... | null",
  "relation_supported": true,
  "evidence_refs": [],
  "tenant_id": "...",
  "reason_code": "..."
}
```

`relation_supported` is one of `true`, `false`, or `null`. No additional output field is accepted.

## 5. Objective and optimization recipe

The decoder-only sequence is trained with next-byte cross entropy. Targets before the first output byte are
masked with `ignore_index=-100`; loss is applied only to canonical output bytes and EOS. Input reconstruction
is never an optimization target.

Frozen optimizer recipe:

| Field | Frozen value |
|---|---:|
| optimizer | AdamW |
| learning rate | 0.0003 |
| betas | (0.9, 0.95) |
| epsilon | 1e-8 |
| weight decay | 0.01 |
| gradient clip | 1.0 |
| batch size | 8 paired episode indices per arm |
| maximum updates | 2000 per arm and seed |
| scheduler | none |
| selective restarts | prohibited |
| post-result extension | prohibited |

The implementation may expose these values as immutable configuration fields but may not introduce a search
space or representation-specific override.

## 6. Canonical fact graph and serializers

Implement immutable typed records for tenant, query, entities, relations, evidence, explicit missing-relation
facts, and authoritative structured output.

For every episode:

1. construct one canonical fact graph;
2. serialize B0 and B1 from that same graph;
3. parse both serializations back to canonical form where applicable;
4. compute one semantic SHA-256 digest from the canonical graph;
5. require `B0_fact_hash == B1_fact_hash` before tokenization;
6. fail closed on any semantic mismatch, forbidden field, duplicate identity, invalid relation reference,
   tenant inconsistency, malformed output, or budget breach.

B0 grammar, B1 schema, ordering, punctuation, and output schema remain those frozen in the protocol document.
The implementation may correct only mechanical ambiguity necessary to make the frozen contract executable;
any scientific or representational change requires a new authorization document.

## 7. Deterministic synthetic generator

Implement a local deterministic generator for S1–S8 and evaluation-only transformations A1–A6.

The generator shall:

- use a caller-supplied local RNG and never mutate global RNG state;
- derive paired arms from one canonical episode object;
- balance candidate position mechanically;
- keep domains, split identity, and authoritative output outside model-visible serializations;
- emit no saved dataset during import or unit tests;
- expose canonical in-memory fixtures for integrity tests;
- treat ablations as evaluation-only and preserve both the clean authoritative output and the output implied
  by the perturbed representation where causal movement must be measured.

Unit tests may use a clearly labelled non-benchmark test seed that is not 76, 760–762, or 7160–7164. Such
fixtures are ephemeral test data and are not admissible benchmark evidence.

## 8. Evaluator

Implement one strict parser and evaluator shared by both arms. Required checks include:

- exact output-schema field set and order;
- status validity;
- selected entity and relation exact match;
- `relation_supported` exact match;
- evidence precision and recall;
- tenant exact match;
- abstention correctness;
- unsupported evidence emission;
- unauthorized cross-tenant inclusion;
- deterministic aggregate reconstruction;
- causal-ablation movement or abstention requirements;
- shortcut-baseline interfaces;
- protocol/resource failure precedence.

The implementation may encode the frozen thresholds but must not run or reconstruct a scientific verdict in
this authorization PR.

## 9. Determinism and paired-run integrity

Implement utilities that prove, before any future run:

- identical parameter count for B0 and B1;
- byte-identical initial parameter digest under the same initialization seed;
- identical paired episode order;
- identical optimizer hyperparameters and update count;
- byte-identical serialization replay;
- stable canonical fact hashes;
- deterministic tokenizer round-trip;
- deterministic evaluator output.

The harness must use deterministic PyTorch algorithms where supported and record source, configuration,
dataset, initialization, batch-order, and final parameter digests in future run manifests.

## 10. Execution gate

Reserved benchmark seeds are hard-gated in code:

- seed 76 requires explicit smoke authorization;
- seeds 760–762 require explicit development authorization;
- seeds 7160–7164 require explicit final-execution authorization.

Without the corresponding authorization token, the CLI or programmatic run entrypoint must reject the run
before generation, model initialization, or output-directory creation.

This implementation authorization supplies **none** of those execution tokens.

## 11. Required implementation files

The implementation PR is authorized to add:

```text
experiments/single_hop_typed_vs_prose/
  __init__.py
  config.py
  schema.py
  serializers.py
  tokenizer.py
  dataset.py
  ablations.py
  model.py
  evaluator.py
  trainer.py
  execution.py
  README.md

tests/experiments/single_hop_typed_vs_prose/
  test_schema_and_serializers.py
  test_tokenizer_and_examples.py
  test_model_and_loss.py
  test_evaluator_and_execution_gate.py

.github/workflows/typed-vs-prose-implementation-ci.yml
```

Small file-name adjustments are permitted only when they do not expand scope or alter the frozen recipe.

## 12. Required tests

The implementation PR must demonstrate, without consuming benchmark seeds:

1. B0 and B1 determinism;
2. semantic fact-hash equality;
3. no answer/gold/evaluator leakage in B1;
4. strict output parsing;
5. byte-tokenizer round-trip;
6. fixed token IDs and budget rejection;
7. identical parameter count and initialization digest across arms;
8. causal no-future leakage;
9. output-only loss masking;
10. forward shape and one backward pass on a tiny mechanical test configuration;
11. S1–S8 fixture construction;
12. A1–A6 transformation construction and expectation metadata;
13. tenant and evidence hard-failure detection;
14. reserved-seed rejection without authorization;
15. no import-time dataset generation, training, filesystem writes, or network access.

The tests are implementation evidence only. They are not smoke, development, final, or scientific evidence.

## 13. Explicitly unauthorized

This authorization does not permit:

- merging PR #1364 without independent audit;
- altering the preregistered question, arms, gates, seeds, or conclusion vocabulary;
- benchmark dataset materialization;
- training or evaluating seed 76, 760–762, or 7160–7164;
- inspecting any reserved result;
- hyperparameter, serializer, schema, prompt, or output-format search;
- BindingSlots, E1, memory, multi-hop, temporal, successor, Phase, KDA, MLA, T5, real-model, capacity, pilot,
  enterprise-transfer, efficiency, or production work;
- a positive typed-structure claim;
- implementation merge without independent audit.

## 14. Completion condition

The implementation step is complete only when a separate implementation PR:

- contains only the authorized package, tests, workflow, and bounded documentation updates;
- passes its dedicated unit CI plus existing terminology/pipeline/invariance checks;
- has zero unresolved review threads;
- is independently audited;
- remains explicit that execution is unauthorized.

Until that PR is audited and merged, the protocol remains `PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE` and
`TYPED_VS_PROSE_PROTOCOL_LOCKED` is not emitted.

**Authorization verdict: `IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`.**

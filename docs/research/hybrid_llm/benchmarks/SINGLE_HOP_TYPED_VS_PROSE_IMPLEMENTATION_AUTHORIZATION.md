# Single-hop typed-vs-prose — implementation authorization

**Status: `IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`.**

This document authorizes one bounded implementation step that removes the model-recipe blocker recorded in
`SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md`. It also records two fail-closed mechanical corrections found
before implementation publication. It does **not** authorize dataset materialization, training, smoke,
development, reserved execution, result inspection, threshold changes, or scientific conclusions.

Standing invariants remain:

- `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
- `E1_TEMPORAL_TRANSFER_PARTIAL`
- `KDA_VALIDATION_BLOCKED`

Never emit `E1_STRUCTURAL_TRANSFER_CONFIRMED`, `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`,
`KDA_VALIDATION_ELIGIBLE`, or `PRODUCTION_READY`.

## 1. Pre-implementation integrity corrections

Mechanical review of the blocked draft found two load-bearing defects:

1. the entity-selection query exposed the authoritative entity ID; and
2. relation-target, relation-validation, and stable-direct examples could present indistinguishable query
   semantics while requiring different `reason_code` labels.

The implementation must correct both defects symmetrically in B0 and B1:

- `select_entity` never exposes the authoritative entity ID;
- every query carries one explicit operation from the shared operation vocabulary;
- S2 and S8 use the same operation and the same outcome-derived output contract;
- S3 includes both supported and unsupported relation claims;
- `reason_code` is determined by operation and represented outcome, never by hidden split identity;
- split, domain, episode ID, seed, and authoritative output remain model-invisible.

These corrections do not create an arm-specific feature: the identical query semantics are serialized into
both B0 and B1. Until independently audited, the protocol remains
`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`; `TYPED_VS_PROSE_PROTOCOL_LOCKED` is not emitted.

## 2. Authorized package and dependency boundary

Create exactly one isolated package:

```text
experiments/single_hop_typed_vs_prose/
```

It may import only the existing generic baseline classes
`symbolu_neural.clean_softmax.backbone.BackboneConfig` and
`symbolu_neural.clean_softmax.backbone.SoftmaxTransformerLM` into the model path. Those files remain
unmodified. No other research architecture may enter the model path.

## 3. Shared query contract

The canonical query fields occur in exactly this order:

```json
{
  "operation": "select_entity | select_relation_target | validate_relation | select_evidence",
  "entity_type": "...",
  "entity_id": "... | null",
  "relation_type": "... | null",
  "target_entity_id": "... | null",
  "attributes": {}
}
```

Rules:

- `select_entity`: `entity_id`, `relation_type`, and `target_entity_id` are null; `attributes` contains the
  non-answer identifying criteria.
- `select_relation_target`: source `entity_id` and `relation_type` are present; `target_entity_id` is null.
- `validate_relation`: source, relation, and proposed `target_entity_id` are present.
- `select_evidence`: source, relation, and relation target are present.
- unused attributes are `{}`; keys are ascending.

The deterministic B0 query sentences are operation-specific and carry the same semantics without field labels:

```text
The question asks which {ENTITY_TYPE} has {ATTRIBUTE_CLAUSES}.
The question asks which target is linked from {ENTITY_TYPE} {ENTITY_ID} through relation "{RELATION_PHRASE}"; if none is authorized, report insufficient evidence.
The question asks whether {ENTITY_TYPE} {ENTITY_ID} is linked to {TARGET_ENTITY_ID} through relation "{RELATION_PHRASE}".
The question asks which evidence reference supports {ENTITY_TYPE} {ENTITY_ID} linked to {TARGET_ENTITY_ID} through relation "{RELATION_PHRASE}".
```

No B0 or B1 query may include an answer, gold label, validity result, target rank, split, or evaluator field.

## 4. Frozen reversible lexical tokenizer

Raw-byte tokenization was rejected before implementation because the verbose B1 representation exceeded the
common 512-token window. Use one fixed, data-independent, reversible tokenizer for both arms:

| Field | Frozen value |
|---|---:|
| ASCII character IDs | 0–127 |
| PAD / BOS / EOS | 128 / 129 / 130 |
| frozen protocol lexeme IDs | 131–204 |
| frozen protocol lexemes | 74 |
| total vocabulary | 205 IDs |

Algorithm:

1. require 7-bit ASCII and reject non-ASCII;
2. scan with `[A-Za-z_]+|\d+|\s+|.`;
3. encode an exact frozen lexeme as one token;
4. encode every other chunk as constituent ASCII character IDs;
5. decode by exact concatenation;
6. prohibit fitting, BPE training, hashing, unknown substitution, corpus-derived vocabulary, arm markers, and
   arm-specific tokens.

The added atomic lexemes are shared query-operation terms only. Entity IDs and unforeseen ASCII remain
losslessly representable through character fallback.

## 5. Frozen model recipe

Instantiate the unmodified plain causal softmax decoder-only Transformer:

| Field | Frozen value |
|---|---:|
| vocabulary | 205 |
| `d_model` | 64 |
| layers | 2 |
| heads | 4 |
| feed-forward width | 256 |
| maximum sequence length | 1024 |
| dropout | 0.0 |
| output head | existing tied vocabulary head |
| attention | ordinary causal softmax token attention |

The model is trained from scratch. The same class, tokenizer, vocabulary, head, parameter count,
initialization policy, optimizer, update count, batch order, parser, and evaluator are used for B0 and B1.

Prohibited: pretrained checkpoints, adapters, external model APIs, BindingSlots, E1, recurrent or prefix
memory, typed-only encoders or heads, Phase, KDA, event readers, bounded quadratic relational readers,
retrieval tables, and answer-time correction.

## 6. Shared input, output, and objective

The common prompt is:

```text
{SERIALIZED_INPUT}\n<OUTPUT>\n
```

There is no arm ID or arm-specific prompt. Limits:

- maximum input including marker: **512 tokens**;
- maximum output excluding EOS: **384 tokens**;
- sequence: BOS + input + canonical output + EOS;
- fail closed on over-budget input/output;
- no truncation, arm-specific compression, or padding-based information equalization.

The output is minified ASCII JSON with exactly these fields and order:

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

`relation_supported` is `true`, `false`, or `null`. Train with next-token cross entropy only on canonical
output tokens and EOS; mask every prompt target with `ignore_index=-100`.

## 7. Frozen optimization recipe

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
| selective restarts / post-result extension | prohibited |

No search space or arm-specific override is authorized.

## 8. Canonical graph, generator, and ablations

For every episode:

1. construct one immutable canonical graph;
2. serialize B0 and B1 from that graph;
3. compute one SHA-256 semantic digest from the model-visible graph;
4. require deterministic serializer replay and shared fact digest;
5. fail closed on duplicate identity, invalid references, tenant inconsistency, forbidden keys, malformed
   output, non-ASCII text, or budget breach.

Implement deterministic in-memory S1–S8 fixtures and evaluation-only A1–A6 transformations with a caller-
supplied local RNG. Do not mutate global Python or PyTorch RNG state. Do not write datasets during import or
unit tests.

S3 must construct both supported and unsupported proposed targets. A6 must add a high-similarity but
non-identical decoy, not a second exact answer.

## 9. Shared evaluator and determinism

One strict parser/evaluator must enforce exact field set and order, duplicate rejection, types, entity and
relation correctness, relation support, evidence precision/recall, abstention, tenant equality, unsupported
evidence, and unauthorized cross-tenant selection.

Mechanical integrity utilities must prove:

- identical B0/B1 parameter count and initialization digest;
- identical paired episode and batch order;
- stable serializer, tokenizer, fact, evaluator, and parameter digests;
- causal no-future leakage;
- package import does not advance global Python or PyTorch RNG state.

## 10. Execution gate

Reserved seeds are rejected before generation or model initialization unless the exact later authorization is
supplied:

- 76 → `SMOKE_EXECUTION_AUTHORIZED`
- 760–762 → `DEVELOPMENT_EXECUTION_AUTHORIZED`
- 7160–7164 → `FINAL_EXECUTION_AUTHORIZED`

This document supplies none of these tokens.

## 11. Authorized implementation files

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
  test_import_side_effects.py

.github/workflows/typed-vs-prose-implementation-ci.yml
```

## 12. Required tests

Without a benchmark seed, test:

- S1 answer ID absent from both query serializations;
- explicit operation disambiguation and outcome-derived reason codes;
- supported and unsupported S3 claims;
- deterministic S1–S8 and A1–A6 construction;
- B0/B1 deterministic replay and shared fact hash;
- no answer/gold/evaluator leakage;
- exact tokenizer round-trip, fixed IDs, and non-ASCII rejection;
- all primary fixtures fit the common 512-token window without truncation;
- output-only masking and budget rejection;
- identical parameter count and initialization digest;
- causal no-future leakage, forward shape, and one backward pass;
- strict parser, tenant/evidence failures, and reserved-seed rejection;
- no import-time generation, model initialization, RNG mutation, training, writes, or network access.

An explicitly labelled non-benchmark seed may be used for ephemeral tests. Such tests are not scientific
benchmark evidence.

## 13. Explicitly unauthorized

No dataset artifact, seed 76 run, development run, reserved final run, result inspection, serializer/tokenizer/
schema search, positive typed-structure claim, protocol-lock claim, BindingSlots, E1, temporal, multi-hop,
Phase, KDA, MLA, T5, real-model, capacity, pilot, enterprise-transfer, efficiency, production, or merge without
independent audit.

## 14. Completion condition

The separate implementation PR must remain draft and unmerged until its authorized scope, dedicated tests,
existing CI, and review state are independently audited. Passing mechanical tests authorizes no execution.

**Authorization verdict: `IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`.**

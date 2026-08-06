# Single-hop typed-vs-prose benchmark — protocol lock

**Documentation-only. Nothing here is implemented, generated, trained, executed, or seeded.** Protocol
completion is not implementation or execution authorization. Always preserves:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

## Protocol-lock status

**Actual state: `PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`.** All six protocol decisions are frozen.
The protocol verdict is **`TYPED_VS_PROSE_PROTOCOL_LOCKED`**.

Meaning: the controlled single-hop typed-versus-prose benchmark protocol is fully specified. Implementation
and execution remain unauthorized.

The sole scientific question remains:

> Does typed entity, relation, and evidence representation materially improve controlled single-hop
> relational reasoning relative to an information-equivalent flattened-prose representation?

There are exactly two primary arms: B0 canonical flattened prose and B1 typed structured input. Every pair is
derived from one canonical fact graph. The fact graph, query, candidate order, output contract, model,
initialization, optimizer, update count, evaluator, metrics, and gates are shared. Input representation is the
only arm-level variable.

---

## Decision 1 — Frozen B0 prose serializer

One exact canonical serializer. B0 presents every underlying fact as grammatical natural-language prose,
generated mechanically from the canonical fact set. No tables, JSON, YAML, XML, key-value blocks, field
labels, answer labels, evaluator-only metadata, paraphrase search, serializer search, arm-specific prompting,
or post-lock serializer change are permitted. Relation names carry the same semantic content as the B1
relation type and no additional hint.

**Deterministic sentence order:** (1) tenant context · (2) query entity · (3) candidate entities ·
(4) relation statements · (5) evidence statements · (6) explicit absence statements where required.

**Frozen sentence grammar:**

- Tenant: `Within tenant {TENANT}, the following records are authorized.`
- Query: `The question concerns {ENTITY_TYPE} {ENTITY_ID}.`
- Candidate entity: `{ENTITY_TYPE} {ENTITY_ID} is a {ENTITY_TYPE} with {ATTR_KEY} {ATTR_VAL}{, ATTR_KEY ATTR_VAL}.`
- Relation: `{SRC_TYPE} {SRC_ID} is associated with {TGT_TYPE} {TGT_ID} through the relation "{RELATION_PHRASE}".`
- Evidence: `Evidence reference {EVIDENCE_REF} supports the relation between {SRC_TYPE} {SRC_ID} and {TGT_TYPE} {TGT_ID}.`
- Missing relation: `No relation of type "{RELATION_PHRASE}" is recorded for {ENTITY_TYPE} {ENTITY_ID}.`
- Cross-tenant entity: `{ENTITY_TYPE} {ENTITY_ID} belongs to tenant {OTHER_TENANT} and is not authorized for tenant {TENANT}.`
- Invalid relation evidence: `Evidence reference {EVIDENCE_REF} contradicts the relation between {SRC_TYPE} {SRC_ID} and {TGT_TYPE} {TGT_ID}.`
- Conflicting evidence: emit one support sentence and one contradiction sentence, each carrying its own evidence reference.
- Duplicate names: use the ordinary candidate sentence for each entity; disambiguation is only by entity ID and attributes.

Entity order is the frozen seeded `presentation_order`, shared across arms. Relation order is the matching
shared order; evidence order is the matching shared order. Attribute keys are ascending. Strings are
lowercase except opaque IDs and literal values. There is one ASCII space between tokens and sentences; every
sentence ends in `.`. Candidate target position is cohort-balanced and never fixed.

---

## Decision 2 — Frozen B1 typed schema

One deterministic JSON-compatible representation with exactly these top-level fields, in this order:

```json
{
  "tenant_id": "...",
  "query": {},
  "entities": [],
  "relations": [],
  "evidence": []
}
```

B1 is minified RFC 8259 JSON, UTF-8, Unicode NFC, with no indentation or trailing newline. Arrays use the same
seeded `presentation_order` as B0. Attribute keys are ascending. No answer, expected, gold, correctness,
validity-result, evaluator-only ID, split, seed, target-rank, or arm-marker field is permitted.

The frozen object shapes are:

```json
{
  "tenant_id": "t01",
  "query": {
    "operation": "select_relation_target",
    "entity_type": "invoice",
    "entity_id": "i991",
    "relation_type": "belongs_to_contract",
    "candidate_entity_ids": ["c882", "c883"],
    "closed_world": true,
    "abstain_when_missing": true
  },
  "entities": [
    {
      "entity_type": "invoice",
      "entity_id": "i991",
      "display_name": null,
      "attributes": {"amount": "4200"},
      "tenant_id": "t01"
    }
  ],
  "relations": [
    {
      "relation_id": "r17",
      "relation_type": "belongs_to_contract",
      "source_entity_type": "invoice",
      "source_entity_id": "i991",
      "target_entity_type": "contract",
      "target_entity_id": "c882",
      "evidence_refs": ["e17"],
      "tenant_id": "t01"
    }
  ],
  "evidence": [
    {
      "evidence_ref": "e17",
      "relation_id": "r17",
      "stance": "supports",
      "admissible": true,
      "text": "signed contract reference c882",
      "tenant_id": "t01"
    }
  ]
}
```

Allowed query operations are exactly `select_entity`, `select_relation_target`, `validate_relation`, and
`select_evidence`. Unused scalar fields are null and unused arrays are empty. Missing relations are expressed
by an absent matching relation plus `closed_world=true`; invalid and conflicting relations are expressed by
evidence stance and admissibility, never by a serialized final-answer field.

### Shared output contract

Both arms use the same output serializer, parser, and evaluator:

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

`relation_supported` is true, false, or null. `reason_code` is one of `ENTITY_MATCH`, `RELATION_FOUND`,
`RELATION_SUPPORTED`, `RELATION_UNSUPPORTED`, `EVIDENCE_FOUND`, `RELATION_MISSING`, `TENANT_REJECTED`, or
`CONFLICTING_EVIDENCE`. No arm-specific post-processing is allowed.

---

## Decision 3 — Frozen numeric gates and verdict mapping

**Primary score** is the unweighted macro-average of S1 exact-entity accuracy, S2 foreign-key accuracy, S3
relation-validity accuracy, S5 evidence-reference F1, and S6 missing-relation abstention accuracy.

### `TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_VALIDATED` — all required

1. B1 final-seed mean primary ≥ **0.80**.
2. B1 minus B0 final-seed mean primary improvement ≥ **0.08** absolute.
3. At least **4 of 5** final seeds each satisfy B1 primary ≥ **0.75** and improvement ≥ **0.05**.
4. B1 per-split final means: S1 ≥ **0.85** · S2 ≥ **0.85** · S3 ≥ **0.80** · S5 precision ≥ **0.90** ·
   S5 recall ≥ **0.90** · S6 abstention ≥ **0.90**.
5. S7 unauthorized cross-tenant inclusion = **0** for every final example and seed.
6. S8 stable-direct accuracy ≥ **0.90**.
7. B1 S8 regression versus B0 is no worse than **-0.02** absolute.
8. Information-equivalence passes for **100%** of pairs.
9. Deterministic replay, shortcut/leakage, causal, evidence, and compute gates all pass.
10. No protocol deviation occurs.

### Other outcome rules

`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_PARTIAL` requires no protocol, tenant, or evidence-integrity hard
failure; B1 mean primary ≥ **0.75**; mean improvement ≥ **0.04**; and at least **3 of 5** seeds improve by
≥ **0.03**, while one or more validated gates are missed. The failed dimension must be named. A tenant failure
can never be partial.

`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND` applies when integrity gates pass and B1 mean primary is
< **0.75**, mean improvement is < **0.04**, or fewer than **3 of 5** seeds improve by ≥ **0.03**.

Use `TYPED_STRUCTURE_SINGLE_HOP_CAUSAL_GATE_FAILED` when endpoint gates are otherwise sufficient but any
mandatory causal gate fails; `..._EVIDENCE_GATE_FAILED` when evidence precision or recall is below **0.90**,
evidence permutation lacks the required causal response, or unsupported evidence is emitted;
`..._TENANT_GATE_FAILED` for any unauthorized cross-tenant inclusion; `..._PROTOCOL_VIOLATED` for a material
post-lock deviation; and `..._RESOURCE_BLOCKED` when the frozen protocol cannot complete within its resource
limit.

### Mandatory causal gates

- A1 identity permutation: relevant B1 endpoint declines ≥ **0.20** versus clean and selection follows the represented identity.
- A2 relation-target permutation: B1 target/relation accuracy declines ≥ **0.20**, or the corrupted relation is correctly rejected.
- A3 relation removal: abstention ≥ **0.90** and unsupported-answer rate ≤ **0.05**.
- A4 evidence permutation: evidence F1 declines ≥ **0.20**; original evidence is not fabricated; unsupported evidence emission = **0**.
- A5 cross-tenant substitution: unauthorized inclusion = **0** and out-of-tenant target selection = **0**.
- A6 lexical decoys: B1 degradation from clean ≤ **0.05** and the lexical-only baseline remains below competence.

Shortcut baselines are lexical overlap, first record, last record, entity frequency, relation-type frequency,
evidence position, fixed output position, and tenant-blind semantic similarity. Each must be ≤ `chance+0.05`,
below the corresponding learned competence floor, and incapable of satisfying the validated outcome.

---

## Decision 4 — Input-budget fairness

B0 and B1 carry the complete identical fact set. Common maximum input length is **512 tokenizer tokens**.
There is no truncation in a primary example. If either serialization exceeds 512, reject the canonical graph
and deterministically generate the next episode; never remove a record from one arm. Both arms receive the
same output-token allowance. Report B0 token count, B1 token count, absolute difference, ratio, entity count,
relation count, and evidence count. Do not pad the shorter arm and do not infer efficiency superiority.

A preregistered sensitivity subset contains pairs whose token counts differ by ≤ **10%**. Report the complete
information-equivalent cohort as primary and the ≤10% subset as sensitivity. The subset cannot override a
failed primary verdict.

---

## Decision 5 — Frozen model and compute recipe

The selected existing non-memory model is the repository's clean standard-softmax baseline:

```text
symbolu_neural.clean_softmax.config.get_ablation("baseline")
symbolu_neural.clean_softmax.model.SymbolUSoftmaxModel
symbolu_neural.clean_softmax.backbone.SoftmaxTransformerLM
```

Authority is default-branch commit `0c63d1f2400716ab23249c9d76805ac517e70956`. Source blob locks are:

```text
backbone.py  b8083f5e5988e3d2795db97f3473ecf08d72ebc1
config.py    5c456c299f47e14c820981a6d55aee8e641bc7ec
model.py     5c0b90035ea8399ea244235299654baea98e78cc
data.py      843595f1feecdf52251dd8eb3ca56ac1040752ac
trainer.py   e5ffbe5f49c8e7700ed7acaf0f23c623cf0570b5
generate.py  e70af50f193f2afa7c530df699045a0b97498e59
```

This is a from-scratch causal scaled-dot-product softmax transformer with a tied vocabulary head. In the
`baseline` ablation, typed heads, entropy refinement, memory, recurrent controls, extra blocks, Phase,
BindingSlots, E1 memory, and bounded quadratic/event readers are disabled. B0 and B1 use the same tokenizer,
input channel, architecture, vocabulary head, parameter count, and greedy decoder. The shared output contract
is generated as ordinary minified text through that existing head; no typed-only encoder or model head is
introduced.

Frozen configuration:

```text
d_model                 = 128
n_layers                 = 2
n_heads                  = 4
d_ff                     = 512
max_seq                  = 768
input_cap                = 512 character tokens
maximum_output_tokens    = 256 character tokens
dropout                  = 0.0
tokenizer                 = shared CharTokenizer vocabulary over the union of authorized B0/B1 training text and output symbols
optimizer                 = AdamW
learning_rate             = 0.003
weight_decay              = 0.01
gradient_clip_norm        = 1.0
scheduler                 = none
training_steps            = 1200 per development/final arm-run
smoke_steps               = 100 per arm
effective_batch_size      = 24 paired episode sequences
checkpoint_selection      = final step only
early_stopping            = disabled
decoding                  = greedy argmax, temperature 0
```

Each training sequence is `INPUT`, one newline, `Answer:`, the canonical minified output JSON, and one final
newline. The later benchmark harness must mask input characters from the supervised loss and apply ordinary
next-character cross-entropy only to `Answer:` plus output characters. Paired B0/B1 runs begin from
byte-identical model state, use identical episode and batch order, and differ only in serialized input.
Initial-state, vocabulary, episode-order, and batch-order hashes must match.

The model itself is already present and requires no architecture or source change. A benchmark-specific paired
data generator, loss mask, parser, evaluator, and report harness do not yet exist; creating them is a later
implementation activity and is explicitly unauthorized by this PR. If the source-locked model cannot be
instantiated as specified, emit `PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE` rather than substituting another model.

---

## Decision 6 — Seeds, episode counts, distractor density, compute, and ordering

Mechanically re-check seed disjointness immediately before any later implementation. The frozen roles are:

- smoke seed **76** — implementation correctness, parsing, determinism, and feasibility only; never contributes to a verdict;
- development seeds **760–762** — paired implementation verification; no serializer, schema, gate, model, or recipe tuning;
- reserved final seeds **7160–7164** — paired final runs only after a separate execution authorization.

Sub-seeds use `seed*1_000_003 + DOMAIN_ID*97 + 13`, with `DOMAIN_ID={dataset:0, init:1, batch:2, perturb:3}`.
No reserved final seed may be opened, generated, executed, or inspected before the protocol lock is merged,
implementation is separately authorized and audited, tests pass, and a final-execution authorization record
is merged.

Six domains are frozen: procurement, hiring, cybersecurity, customer support, compliance, and agent
governance.

Episode counts:

| Cohort | Clean S1–S8 count |
|---|---:|
| Smoke seed 76 | 480 total: 10 per domain and split |
| Each development seed | 1,920 total: 40 per domain and split |
| Each final seed | 4,800 total: 100 per domain and split |
| Training corpus | 12,000 total: 250 per domain and split |

For each development and final seed, each A1–A6 ablation contains 100 transformed episodes per domain and
never retrains the model. Train, development, and final identity pools are mutually disjoint.

S1–S7 use six candidate entities, four relation claims, and four evidence records: one query-relevant
in-tenant item where applicable, three plausible in-tenant distractors, and two cross-tenant entity decoys.
S6 has no query-relevant direct relation. S8 uses three entities, two relations, and two evidence records. S1
contains at least two duplicate names; S3 balances valid, invalid, conflict, and missing; S4 includes at least
three high-overlap candidates; S5 contains one authoritative admissible support record; S7 includes at least
two highly similar cross-tenant candidates. Target position is balanced per domain and split.

Compute limits:

```text
serializer candidates       = 1
schema candidates           = 1
model/training recipes      = 1
maximum training steps      = 2000 per arm-run
maximum arm-runs            = 18
maximum aggregate steps     = 36000
maximum wall-clock          = 24 hours
selective seed restarts     = forbidden
post-result budget extension= forbidden
```

Protocol order is fixed: preregistration merged · protocol lock committed · protocol lock audited · protocol
lock merged · implementation separately authorized · code implemented · smoke · development · implementation
integrity audit · explicit final-execution authorization · reserved finals · verdict reconstruction · results
audit. This PR authorizes none of the steps after protocol locking.

---

## Information-equivalence and determinism locks

A mechanical verifier canonicalizes both arms back into the same fact graph. It requires equality of tenant,
query, entities, types, IDs, attributes, relations, source and target IDs, relation types, evidence references,
missing relations, conflict states, and expected output type. Emit `B0_fact_hash` and `B1_fact_hash`; require
equality for 100% of pairs and fail closed otherwise. The verifier ignores representation syntax and no
semantic field.

Later implementation must prove byte-identical repeated generation and serialization under the same seed;
matching paired model-init and data-order hashes; stable fact-set hashes; reproducible evaluator output; and
recorded source, config, dataset, environment, and checkpoint hashes.

No unresolved scientific placeholder remains. Future implementation commit, dataset, checkpoint, and
environment identifiers are `NOT_YET_CREATED — DOES_NOT_AUTHORIZE_EXECUTION`.

---

## Paired examples covering S1–S8 and A1–A6

Evaluator answers below are explanatory only and are never serialized into either input.

### S1 — exact entity identity with duplicate names

B0: `Within tenant t01, the following records are authorized. The question concerns vendor query-1. vendor v101 is a vendor with name atlas, suffix 17. vendor v102 is a vendor with name atlas, suffix 42.`

B1: `{"tenant_id":"t01","query":{"operation":"select_entity","entity_type":"vendor","entity_id":"query-1","relation_type":null,"candidate_entity_ids":["v101","v102"],"closed_world":true,"abstain_when_missing":false},"entities":[{"entity_type":"vendor","entity_id":"v101","display_name":"atlas","attributes":{"suffix":"17"},"tenant_id":"t01"},{"entity_type":"vendor","entity_id":"v102","display_name":"atlas","attributes":{"suffix":"42"},"tenant_id":"t01"}],"relations":[],"evidence":[]}`

Evaluator: select `v102` from the query fixture requiring suffix 42.

### S2 — direct foreign-key target

B0: `Within tenant t01, the following records are authorized. The question concerns invoice i991. invoice i991 is a invoice with amount 4200. contract c882 is a contract with status active. invoice i991 is associated with contract c882 through the relation "belongs to contract". Evidence reference e17 supports the relation between invoice i991 and contract c882.`

B1 uses the Decision-2 canonical object with invoice `i991`, contract `c882`, relation `r17`, and evidence `e17`.

Evaluator: target `c882`.

### S3 — valid versus invalid relation

B0: `Within tenant t01, the following records are authorized. The question concerns account a1. account a1 is a account with status open. owner o1 is a owner with name mira. account a1 is associated with owner o1 through the relation "owned by". Evidence reference e3 contradicts the relation between account a1 and owner o1.`

B1 contains the same relation claim and `{"evidence_ref":"e3","relation_id":"r3","stance":"contradicts","admissible":true,"text":"registry rejects o1","tenant_id":"t01"}`.

Evaluator: relation unsupported.

### S4 — content-similar decoys

B0: `Within tenant t01, the following records are authorized. The question concerns applicant query-4. applicant p1 is a applicant with name mira, requisition q6. applicant p2 is a applicant with name mira, requisition q7. applicant p3 is a applicant with name mira, requisition q8.`

B1 contains the same three entity objects in the shared presentation order.

Evaluator: select `p2` for requisition q7.

### S5 — evidence-reference selection

B0: `Within tenant t01, the following records are authorized. The question concerns case k1. case k1 is a case with status pending. policy p1 is a policy with version 4. case k1 is associated with policy p1 through the relation "governed by". Evidence reference e5 supports the relation between case k1 and policy p1.`

B1 contains relation `r5` and support evidence `e5` over the same facts.

Evaluator: evidence `e5`.

### S6 — missing relation and abstention

B0: `Within tenant t01, the following records are authorized. The question concerns ticket t1a. ticket t1a is a ticket with status open. No relation of type "assigned to" is recorded for ticket t1a.`

B1 contains the ticket, an empty matching relation set, `closed_world=true`, and `abstain_when_missing=true`.

Evaluator: `INSUFFICIENT_EVIDENCE` with reason `RELATION_MISSING`.

### S7 — cross-tenant decoy

B0: `Within tenant t01, the following records are authorized. The question concerns asset as1. asset as1 is a asset with class server. team tm1 is a team with name core. team tm2 belongs to tenant t02 and is not authorized for tenant t01. asset as1 is associated with team tm1 through the relation "owned by".`

B1 contains `tm1` in `t01`, similar `tm2` in `t02`, and the direct relation to `tm1`.

Evaluator: select `tm1`; any `tm2` inclusion is a hard failure.

### S8 — stable direct case

B0: `Within tenant t01, the following records are authorized. The question concerns agent ag1. agent ag1 is a agent with state active. model m1 is a model with tier standard. agent ag1 is associated with model m1 through the relation "uses model".`

B1 contains the identical direct relation from `ag1` to `m1`.

Evaluator: target `m1`.

### A1 — primary-key permutation

B0 swaps IDs `v101` and `v102` while retaining their attributes; B1 performs the identical object-ID swap.
Evaluator target follows the represented key and changes accordingly.

### A2 — relation-target permutation

B0 changes the S2 relation target from `c882` to plausible `c883`; B1 changes only the same target field.
Evaluator target changes to `c883`.

### A3 — relation removal

B0 removes the S2 relation and emits the frozen missing-relation sentence; B1 removes the same relation and
retains `closed_world=true`. Evaluator requires abstention.

### A4 — evidence permutation

B0 swaps evidence references between a support and a plausible contradiction; B1 makes the identical evidence
object swap. Evaluator follows the new authoritative evidence and forbids fabrication of the clean reference.

### A5 — cross-tenant substitution

B0 replaces the valid target and evidence with highly similar tenant-t02 facts; B1 performs the identical
substitution. Evaluator requires zero unauthorized selection and abstention when no authorized target remains.

### A6 — lexical decoy control

B0 adds reviewer `rev2` named `req6 approval board` beside correct `rev1`, while relation and evidence remain
pointed to `rev1`; B1 adds the identical decoy object. Evaluator target remains `rev1`.

---

## Verdict

`TYPED_VS_PROSE_PROTOCOL_LOCKED`

The controlled single-hop typed-versus-prose benchmark protocol is fully specified. Implementation and
execution remain unauthorized.

This lock does not support typed-structure advantage, enterprise transfer, multi-hop reasoning, temporal
reasoning, memory value, real-model transfer, quality preservation, efficiency superiority, production
readiness, or KDA eligibility. It preserves `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`E1_TEMPORAL_TRANSFER_PARTIAL`, and `KDA_VALIDATION_BLOCKED`.

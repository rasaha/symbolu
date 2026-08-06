# Single-hop typed-vs-prose benchmark — protocol lock

**Documentation-only. Nothing here is implemented, generated, trained, executed, or seeded.**

**State:** `PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`

**Protocol verdict:** `TYPED_VS_PROSE_PROTOCOL_LOCKED`

Meaning: the controlled single-hop typed-versus-prose benchmark protocol is fully specified. Implementation
and execution remain unauthorized.

Standing invariants remain unchanged:

- `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
- `E1_TEMPORAL_TRANSFER_PARTIAL`
- `KDA_VALIDATION_BLOCKED`

The sole scientific question is:

> Does typed entity, relation, and evidence representation materially improve controlled single-hop
> relational reasoning relative to an information-equivalent flattened-prose representation?

There are exactly two primary arms:

- **B0:** one frozen deterministic grammatical-prose serialization;
- **B1:** one frozen deterministic typed JSON serialization.

Every pair is derived from one canonical fact graph. The graph, query semantics, candidate presentation order,
answer contract, model, initialization, optimizer, update count, evaluator, metrics, and gates are shared.
Only input representation differs.

---

## Canonical fact graph and mechanical equivalence

Each episode contains:

- one authorized tenant;
- one query operation;
- candidate entities and attributes;
- direct relation claims;
- evidence records;
- explicit closed-world absence facts where applicable;
- one deterministic seeded `presentation_order` shared by B0 and B1.

No task requires more than one relation hop. Strings are Unicode NFC and restricted to line feed plus printable
ASCII. Identifiers are case-sensitive. Attribute keys are ascending. Candidate target position is balanced
within each domain/split and never fixed.

For every pair, compute:

1. `fact_set_sha256` over canonical key-sorted JSON with presentation order removed;
2. `presentation_sha256` over the same graph with presentation order retained.

B0 must round-trip through the frozen prose parser and B1 through the frozen JSON parser to the same graph.
Both digests must match. Any mismatch fails closed before model exposure.

---

## Decision 1 — frozen B0 prose serializer

B0 is one paragraph of grammatical prose. Sentences occur in exactly this order:

1. tenant context;
2. query;
3. candidate entities;
4. relation claims;
5. evidence records;
6. missing-relation statements, when applicable.

Sentences are separated by one ASCII space and end with a period. There is one serializer only. JSON, YAML,
XML, tables, key-value blocks, headings, answer labels, evaluator metadata, arm markers, paraphrase search,
serializer search, punctuation search, sentence-order search, arm-specific prompts, and post-development
serializer changes are prohibited.

`Q(x)` means normalized value `x` inside ASCII quotation marks. Embedded quotation marks and backslashes use
standard escaping. Frozen relation phrases are the space-separated forms of the corresponding B1 relation
types; the canonical parser maps both to the same relation symbol.

### Exact B0 templates

Tenant context:

```text
Within tenant Q(tenant_id), the following records form the complete authorized working set.
```

Entity-selection query with name and attributes:

```text
The question asks which candidate ENTITY_TYPE is named Q(display_name) and has ATTRIBUTE_CLAUSES.
```

If the name is absent, omit `is named ... and `. If attributes are absent:

```text
The question asks which candidate ENTITY_TYPE has the requested identity.
```

Relation-target query:

```text
The question asks which TARGET_TYPE is linked from SOURCE_TYPE Q(source_id) through relation Q(relation_phrase); if no such authorized relation is recorded, report insufficient evidence.
```

Relation-validity query:

```text
The question asks whether relation claim Q(relation_id) is supported by admissible evidence.
```

Evidence-selection query:

```text
The question asks which evidence reference admissibly supports relation claim Q(relation_id).
```

Candidate entity with name and attributes:

```text
Candidate ENTITY_TYPE Q(entity_id) is named Q(display_name), belongs to tenant Q(tenant_id), and has ATTRIBUTE_CLAUSES.
```

Without a name, omit `is named ... , `. Without attributes, replace the final clause with
`and has no listed attributes`. One attribute clause is:

```text
attribute Q(attribute_name) equal to Q(attribute_value)
```

Two clauses use `CLAUSE_1 and CLAUSE_2`. Three or more use comma separation and `and` before the final clause.
Duplicate names use the ordinary template without an added hint. Cross-tenant entities retain their actual
tenant.

Relation claim:

```text
Relation claim Q(relation_id) states that relation Q(relation_phrase) links SOURCE_TYPE Q(source_id) to TARGET_TYPE Q(target_id) within tenant Q(tenant_id).
```

Supporting evidence:

```text
Evidence reference Q(evidence_ref) for relation claim Q(relation_id) is admissible, supports the claim, has text Q(text), and belongs to tenant Q(tenant_id).
```

Contradicting evidence:

```text
Evidence reference Q(evidence_ref) for relation claim Q(relation_id) is admissible, contradicts the claim, has text Q(text), and belongs to tenant Q(tenant_id).
```

Inadmissible evidence replaces `is admissible` with `is inadmissible`. Conflicts are represented by at least
one admissible support sentence and one admissible contradiction sentence. B0 never serializes the final words
`valid`, `invalid`, `conflict`, `correct`, or `answer` as a label.

Missing relation:

```text
No authorized relation claim of type Q(relation_phrase) starts from SOURCE_TYPE Q(source_id).
```

Entities, relations, and evidence follow the shared seeded `presentation_order`; attributes remain ascending.
Single spaces and terminal periods are frozen.

---

## Decision 2 — frozen B1 typed schema

B1 is one minified RFC 8259 JSON object using UTF-8 and Unicode NFC, with no indentation or trailing newline.
Top-level fields are exactly these, in this order:

```json
{
  "tenant_id": "...",
  "query": {},
  "entities": [],
  "relations": [],
  "evidence": []
}
```

No additional top-level field is permitted. Arrays follow the same seeded `presentation_order` as B0.
No answer, expected, gold, correctness, validity-result, evaluator-only ID, split, seed, target-rank, arm
marker, or hidden schema hint is permitted.

### Query object

Keys occur in this order:

```json
{
  "operation": "select_entity",
  "entity_type": "vendor",
  "entity_id": null,
  "display_name": "atlas",
  "attributes": {"suffix":"42"},
  "relation_type": null,
  "relation_id": null,
  "target_entity_type": null,
  "candidate_entity_ids": ["v101","v102"],
  "closed_world": true,
  "abstain_when_missing": false
}
```

Allowed operations are exactly `select_entity`, `select_relation_target`, `validate_relation`, and
`select_evidence`. Unused scalar fields are null and unused objects/arrays are empty. `closed_world` is always
true. For relation-target queries, `abstain_when_missing` is true; otherwise it is false. The B0 tenant and
query sentences carry the same semantics.

### Entity object

```json
{
  "entity_type": "vendor",
  "entity_id": "v102",
  "display_name": "atlas",
  "attributes": {"suffix":"42"},
  "tenant_id": "t01"
}
```

`display_name` is null when absent. Duplicate names remain duplicate strings. Cross-tenant entities retain
their actual tenant.

### Relation object

```json
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
```

A relation object states a claim and contains no final validity or correctness field.

### Evidence object

```json
{
  "evidence_ref": "e17",
  "relation_id": "r17",
  "stance": "supports",
  "admissible": true,
  "text": "signed contract reference c882",
  "tenant_id": "t01"
}
```

Allowed stances are `supports` and `contradicts`. Missing relations are represented by absence of a matching
relation under `closed_world=true`; conflicts are represented by admissible support and contradiction. No
final answer is serialized.

### Shared output contract

Both arms use one identical output serializer, parser, and evaluator:

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

`relation_supported` is true, false, or null. Allowed reason codes are `ENTITY_MATCH`, `RELATION_FOUND`,
`RELATION_SUPPORTED`, `RELATION_UNSUPPORTED`, `EVIDENCE_FOUND`, `RELATION_MISSING`, `TENANT_REJECTED`, and
`CONFLICTING_EVIDENCE`. No arm-specific post-processing is allowed.

---

## Decision 3 — frozen numeric gates and verdict mapping

Primary score is the unweighted macro-average of S1 exact-entity accuracy, S2 direct-target accuracy, S3
relation-validity accuracy, S5 evidence-reference F1, and S6 missing-relation abstention accuracy.

### Validated advantage — all required

1. B1 five-seed mean primary score ≥ **0.80**.
2. Mean absolute improvement `(B1-B0)` ≥ **0.08**.
3. At least **4 of 5** final seeds each have B1 primary ≥ **0.75** and improvement ≥ **0.05**.
4. B1 final means: S1 ≥ **0.85** · S2 ≥ **0.85** · S3 ≥ **0.80** · S5 precision ≥ **0.90** ·
   S5 recall ≥ **0.90** · S6 abstention ≥ **0.90**.
5. S7 unauthorized inclusion = **0** for every example and seed.
6. S8 stable-direct accuracy ≥ **0.90** and B1 regression versus B0 no worse than **-0.02**.
7. Every causal, shortcut, equivalence, determinism, evidence, and compute gate passes.
8. No protocol deviation occurs.

`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_PARTIAL` requires no protocol, tenant, or evidence-integrity hard
failure; B1 mean primary ≥ **0.75**; mean improvement ≥ **0.04**; and at least **3 of 5** seeds improve by
≥ **0.03**, while one or more validated gates are missed. The failed dimension must be named. A tenant failure
can never be partial.

`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND` applies when integrity gates pass and B1 mean primary is
< **0.75**, mean improvement is < **0.04**, or fewer than **3 of 5** seeds improve by ≥ **0.03**.

Use `TYPED_STRUCTURE_SINGLE_HOP_CAUSAL_GATE_FAILED` when endpoint gates are otherwise sufficient but any
mandatory causal gate fails; `TYPED_STRUCTURE_SINGLE_HOP_EVIDENCE_GATE_FAILED` when evidence precision or
recall is below **0.90**, evidence permutation lacks the required response, or unsupported evidence is emitted;
`TYPED_STRUCTURE_SINGLE_HOP_TENANT_GATE_FAILED` for any unauthorized cross-tenant inclusion;
`TYPED_STRUCTURE_SINGLE_HOP_PROTOCOL_VIOLATED` for a material post-lock deviation; and
`TYPED_STRUCTURE_SINGLE_HOP_RESOURCE_BLOCKED` when the frozen protocol cannot complete within its resource
limit.

### Mandatory causal gates

- A1 identity permutation: relevant B1 endpoint declines ≥ **0.20** versus clean and selection follows the represented identity.
- A2 relation-target permutation: B1 target/relation endpoint declines ≥ **0.20**, or the corrupted claim is correctly rejected.
- A3 relation removal: abstention ≥ **0.90** and unsupported-answer rate ≤ **0.05**.
- A4 evidence permutation: evidence F1 declines ≥ **0.20**; original evidence is not fabricated; unsupported evidence emission = **0**.
- A5 cross-tenant substitution: unauthorized inclusion = **0** and out-of-tenant target selection = **0**.
- A6 lexical decoys: B1 degradation from clean ≤ **0.05** and the lexical-only baseline remains below competence.

Shortcut baselines are lexical overlap, first record, last record, entity frequency, relation-type frequency,
evidence position, fixed output position, and tenant-blind semantic similarity. Each must be ≤ `chance+0.05`,
below the corresponding learned competence floor, and incapable of satisfying a validated result.

---

## Decision 4 — input-budget fairness

The selected model uses a shared character tokenizer. The complete B0 and B1 inputs therefore have a common
maximum of **2048 tokenizer tokens**, and the full input-plus-output sequence has `max_seq=2304`. There is no
truncation in any primary example.

Generate both serializations before admission. If either exceeds 2048, reject the canonical graph and
deterministically generate the next episode identifier. Never remove a record from one arm. Both arms receive
the same 256-token output allowance. Report B0 and B1 token counts, absolute difference, ratio, and entity,
relation, and evidence counts. Do not pad the shorter arm and do not infer efficiency superiority.

A preregistered sensitivity subset contains pairs whose B0/B1 token counts differ by ≤ **10%**. Report the
complete information-equivalent cohort as primary and the sensitivity subset separately. The subset cannot
override a failed primary verdict. If a split has fewer than 100 sensitivity pairs per final seed, report that
split as sensitivity-insufficient rather than changing the serializer or density.

---

## Decision 5 — frozen model and training recipe

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

This is a from-scratch causal scaled-dot-product softmax transformer with one tied vocabulary head. In the
`baseline` ablation, typed heads, entropy refinement, memory, recurrent controls, extra blocks, Phase,
BindingSlots, E1 memory, and bounded event/quadratic readers are disabled. B0 and B1 use the same tokenizer,
input channel, architecture, head, parameter count, initialization policy, and greedy decoder. The shared
output contract is generated as ordinary minified text through the existing vocabulary head; no typed-only
encoder or arm-specific model component is introduced.

Frozen configuration:

```text
d_model                 = 64
n_layers                 = 2
n_heads                  = 4
d_ff                     = 256
max_seq                  = 2304
input_cap                = 2048 character tokens
maximum_output_tokens    = 256 character tokens
dropout                  = 0.0
tokenizer                 = one shared CharTokenizer vocabulary over the union of authorized B0/B1 training text and output symbols
optimizer                 = AdamW
learning_rate             = 0.003
weight_decay              = 0.01
gradient_clip_norm        = 1.0
scheduler                 = none
training_steps            = 1200 per development/final arm-run
smoke_steps               = 100 per arm
effective_batch_size      = 16 episode sequences
checkpoint_selection      = final step only
early_stopping            = disabled
decoding                  = greedy argmax, temperature 0
```

Each training sequence is `INPUT`, one newline, `Answer:`, canonical minified output JSON, and one final
newline. The future harness masks input characters and applies ordinary next-character cross-entropy only to
`Answer:` plus output characters. Paired B0/B1 runs begin from byte-identical state, use identical episode and
batch order, and differ only in serialized input. Initial-state, vocabulary, episode-order, and batch-order
hashes must match.

The model already exists and requires no architecture or source change. A paired generator, loss mask, parser,
evaluator, and report harness do not yet exist; creating them is later implementation work and is unauthorized
here. If the source-locked model cannot be instantiated as specified, emit
`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE` rather than substituting another model.

---

## Decision 6 — seeds, counts, distractor density, compute, and ordering

Frozen seed roles:

- smoke **76** — shapes, parsing, determinism, and feasibility only; never contributes to a verdict;
- development **760–762** — paired implementation verification; no serializer, schema, gate, model, or recipe tuning;
- reserved final **7160–7164** — paired final runs only after separate final-execution authorization.

Recheck repository-wide disjointness before implementation. Sub-seeds use
`seed*1_000_003 + DOMAIN_ID*97 + 13`, with `DOMAIN_ID={dataset:0, init:1, batch:2, perturb:3}`. No final seed
may be opened, generated, executed, or inspected before the protocol lock is merged, implementation is
separately authorized and audited, tests pass, and a final-execution authorization record is merged.

Six domains are fixed: procurement, hiring, cybersecurity, customer support, compliance, and agent
governance.

Episode counts:

| Cohort | Clean S1–S8 count |
|---|---:|
| Smoke seed 76 | 480 total: 10 per domain and split |
| Each development seed | 1,920 total: 40 per domain and split |
| Each final seed | 4,800 total: 100 per domain and split |
| Training corpus | 12,000 total: 250 per domain and split |

For each development and final seed, each A1–A6 ablation contains 100 transformed episodes per domain and
does not retrain the model. Train, development, and final identity pools are mutually disjoint.

S1–S7 use four candidate entities, two relation claims, and two evidence records where the split supports all
three classes. Default composition is one query-relevant in-tenant item where applicable, one plausible
in-tenant distractor, and two cross-tenant or content-similar decoys selected by the split. S6 has no matching
direct relation. S8 uses three entities, one relation, and one evidence record. S1 contains duplicate names;
S3 balances valid, invalid, conflict, and missing; S4 contains at least three high-overlap candidates; S5 has
one authoritative admissible support record; S7 has at least two highly similar cross-tenant candidates.
Target position is balanced per domain and split. Every admitted pair must fit the frozen 2048-token cap.

Compute limits:

```text
serializer candidates        = 1
schema candidates            = 1
model/training recipes       = 1
maximum training steps       = 2000 per arm-run
maximum arm-runs             = 18
maximum aggregate steps      = 36000
maximum wall-clock           = 24 hours
selective seed restarts      = forbidden
post-result budget extension = forbidden
```

Protocol order is fixed: preregistration merged · protocol lock committed · protocol lock audited · protocol
lock merged · implementation separately authorized · code implemented · smoke · development · implementation
integrity audit · explicit final-execution authorization · reserved finals · verdict reconstruction · results
audit. This PR authorizes none of the steps after protocol locking.

---

## Paired examples covering S1–S8 and A1–A6

Evaluator answers are explanatory only and are never serialized.

### S1 — exact entity identity with duplicate names

B0:

```text
Within tenant "t01", the following records form the complete authorized working set. The question asks which candidate vendor is named "atlas" and has attribute "suffix" equal to "42". Candidate vendor "v101" is named "atlas", belongs to tenant "t01", and has attribute "suffix" equal to "17". Candidate vendor "v102" is named "atlas", belongs to tenant "t01", and has attribute "suffix" equal to "42".
```

B1:

```json
{"tenant_id":"t01","query":{"operation":"select_entity","entity_type":"vendor","entity_id":null,"display_name":"atlas","attributes":{"suffix":"42"},"relation_type":null,"relation_id":null,"target_entity_type":null,"candidate_entity_ids":["v101","v102"],"closed_world":true,"abstain_when_missing":false},"entities":[{"entity_type":"vendor","entity_id":"v101","display_name":"atlas","attributes":{"suffix":"17"},"tenant_id":"t01"},{"entity_type":"vendor","entity_id":"v102","display_name":"atlas","attributes":{"suffix":"42"},"tenant_id":"t01"}],"relations":[],"evidence":[]}
```

Evaluator: `selected_entity_id=v102`.

### S2 — direct foreign-key target

B0:

```text
Within tenant "t01", the following records form the complete authorized working set. The question asks which contract is linked from invoice "i991" through relation "belongs to contract"; if no such authorized relation is recorded, report insufficient evidence. Candidate invoice "i991" belongs to tenant "t01", and has attribute "amount" equal to "4200". Candidate contract "c882" belongs to tenant "t01", and has attribute "status" equal to "active". Relation claim "r17" states that relation "belongs to contract" links invoice "i991" to contract "c882" within tenant "t01". Evidence reference "e17" for relation claim "r17" is admissible, supports the claim, has text "signed contract reference c882", and belongs to tenant "t01".
```

B1:

```json
{"tenant_id":"t01","query":{"operation":"select_relation_target","entity_type":"invoice","entity_id":"i991","display_name":null,"attributes":{},"relation_type":"belongs_to_contract","relation_id":null,"target_entity_type":"contract","candidate_entity_ids":["c882"],"closed_world":true,"abstain_when_missing":true},"entities":[{"entity_type":"invoice","entity_id":"i991","display_name":null,"attributes":{"amount":"4200"},"tenant_id":"t01"},{"entity_type":"contract","entity_id":"c882","display_name":null,"attributes":{"status":"active"},"tenant_id":"t01"}],"relations":[{"relation_id":"r17","relation_type":"belongs_to_contract","source_entity_type":"invoice","source_entity_id":"i991","target_entity_type":"contract","target_entity_id":"c882","evidence_refs":["e17"],"tenant_id":"t01"}],"evidence":[{"evidence_ref":"e17","relation_id":"r17","stance":"supports","admissible":true,"text":"signed contract reference c882","tenant_id":"t01"}]}
```

Evaluator: `selected_entity_id=c882`.

### S3 — valid versus invalid relation

B0 uses query `whether relation claim "r3" is supported by admissible evidence`, the same account/owner
relation claim in both arms, and admissible contradiction evidence `e3`. B1 contains the corresponding
relation and `{"evidence_ref":"e3","relation_id":"r3","stance":"contradicts","admissible":true,
"text":"registry rejects o1","tenant_id":"t01"}`. Evaluator: `relation_supported=false`.

### S4 — content-similar decoys

B0 asks for applicant named `mira` with requisition `q7` and serializes candidates `p1/q6`, `p2/q7`, and
`p3/q8`. B1 serializes the same query attributes and entity objects in the shared order. Evaluator:
`selected_entity_id=p2`.

### S5 — evidence-reference selection

B0 asks which evidence reference admissibly supports relation claim `r5`, then serializes case `k1`, policy
`p1`, relation `r5`, and support evidence `e5`. B1 serializes the same facts and query operation
`select_evidence`. Evaluator: `evidence_refs=["e5"]`.

### S6 — missing relation and abstention

B0 asks for the target of `assigned to` from ticket `t1a`, includes the frozen insufficient-evidence clause,
and emits `No authorized relation claim of type "assigned to" starts from ticket "t1a".` B1 has the same
query, no matching relation, `closed_world=true`, and `abstain_when_missing=true`. Evaluator:
`status=INSUFFICIENT_EVIDENCE`, `reason_code=RELATION_MISSING`.

### S7 — cross-tenant decoy

B0 serializes authorized team `tm1` in `t01`, similarly named `tm2` in `t02`, and relation `r7` from asset
`as1` to `tm1`. B1 contains the same objects, tenant IDs, and relation. Evaluator:
`selected_entity_id=tm1`; selecting `tm2` is a hard failure.

### S8 — stable direct case

B0 asks for the model linked from agent `ag1` through `uses model`, then serializes direct relation `r8` to
`m1`. B1 serializes the same query and relation. Evaluator: `selected_entity_id=m1`.

### A1 — primary-key permutation

B0 swaps IDs `v101` and `v102` while retaining their attributes; B1 performs the identical object-ID swap.
The evaluator target follows the represented key.

### A2 — relation-target permutation

B0 changes S2 relation `r17` from `c882` to plausible `c883`; B1 changes the same target field. The evaluator
target changes to `c883`.

### A3 — relation removal

B0 removes S2 relation `r17` and emits the frozen absence sentence; B1 removes the same relation under
`closed_world=true`. The evaluator requires abstention.

### A4 — evidence permutation

B0 swaps evidence references between an admissible support and plausible contradiction; B1 makes the identical
evidence-object swap. The evaluator follows the new authoritative evidence and forbids fabrication of the
clean reference.

### A5 — cross-tenant substitution

B0 replaces the valid target and evidence with highly similar tenant-`t02` facts; B1 performs the identical
substitution. The evaluator requires zero unauthorized selection and abstention when no authorized target
remains.

### A6 — lexical decoy control

B0 adds reviewer `rev2` named `req6 approval board` beside correct `rev1`, while relation and evidence remain
pointed to `rev1`; B1 adds the identical entity object. The evaluator target remains `rev1`.

---

## Determinism, unresolved items, and change control

Later implementation must prove byte-identical repeated generation and serialization under the same seed;
matching paired model-init, vocabulary, episode-order, and batch-order hashes; stable fact-set hashes;
reproducible evaluator output; and recorded source, config, dataset, environment, and checkpoint hashes.

No unresolved scientific placeholder remains. Future implementation commit, dataset, checkpoint, and
environment identifiers are `NOT_YET_CREATED — DOES_NOT_AUTHORIZE_EXECUTION`.

Any change to a serializer template, JSON field, ordering, model source/configuration, tokenizer, optimizer,
threshold, input cap, seed, episode count, distractor density, compute cap, or conclusion rule requires a new
documentation-only protocol-lock revision.

`TYPED_VS_PROSE_PROTOCOL_LOCKED`

The controlled single-hop typed-versus-prose benchmark protocol is fully specified. Implementation and
execution remain unauthorized.

This lock does not support typed-structure advantage, enterprise transfer, multi-hop reasoning, temporal
reasoning, memory value, real-model transfer, quality preservation, efficiency superiority, production
readiness, or KDA eligibility.

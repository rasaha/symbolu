# Single-hop typed-vs-prose benchmark — protocol lock (DRAFT DOCUMENT)

**Documentation-only. Nothing here is implemented, generated, trained, executed, or seeded.** Protocol
completion is **not** execution authorization. Always preserves: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
· `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

## Protocol-lock status
States: `DRAFT_PROTOCOL` → `PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED` → `IMPLEMENTATION_AUTHORIZED` →
`EXECUTION_AUTHORIZED`. **Maximum permitted state for this PR: `PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED`.**
`IMPLEMENTATION_AUTHORIZED` and `EXECUTION_AUTHORIZED` are **not** emitted.

**Actual state: `DRAFT_PROTOCOL` (blocked).** Five of six decisions (1, 2, 3, 4, 6) are fully resolved with no
placeholders; **Decision 5 (model recipe) is BLOCKED** because no suitable existing non-memory model recipe
exists without code changes (see Decision 5). Per the Decision-5 rule the verdict is
**`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`** and the protocol is **not** claimed locked. `TYPED_VS_PROSE_PROTOCOL_LOCKED`
is **not** emitted.

---

## Decision 1 — Frozen B0 prose serializer
One exact canonical serializer. B0 presents **every** underlying fact as grammatical natural-language prose,
generated mechanically from the canonical fact set. **No tables, JSON, YAML, XML, key-value blocks, or field
labels; no answer labels; no evaluator-only metadata; no field name revealing the requested output; no prose
variant/paraphrase search; no arm-specific prompting; no post-lock serializer change.** Relation names carry
the **same** semantic content as the B1 relation type and **no** additional hint.

**Deterministic sentence order (fixed):** (1) tenant context · (2) query entity · (3) candidate entities ·
(4) relation statements · (5) evidence statements · (6) explicit absence statements where required.

**Frozen sentence grammar (one template each; punctuation frozen):**
- Tenant: `Within tenant {TENANT}, the following records are authorized.`
- Query: `The question concerns {ENTITY_TYPE} {ENTITY_ID}.`
- Candidate entity: `{ENTITY_TYPE} {ENTITY_ID} is a {ENTITY_TYPE} with {ATTR_KEY} {ATTR_VAL}{, ATTR_KEY ATTR_VAL}.`
- Relation: `{SRC_TYPE} {SRC_ID} is associated with {TGT_TYPE} {TGT_ID} through the relation "{RELATION_PHRASE}".`
- Evidence: `Evidence reference {EVIDENCE_REF} supports the relation between {SRC_TYPE} {SRC_ID} and {TGT_TYPE} {TGT_ID}.`
- Missing relation (S6/A3): `No relation of type "{RELATION_PHRASE}" is recorded for {ENTITY_TYPE} {ENTITY_ID}.`
- Cross-tenant note (S7/A5): `{ENTITY_TYPE} {ENTITY_ID} belongs to a different tenant and is not authorized here.`
- Duplicate-name (S1/S4): duplicates are disambiguated **only** by `{ENTITY_ID}`; the phrasing is identical.

**Frozen orderings:** entity order = ascending `entity_id`; relation order = ascending `(source_id, relation_type, target_id)`;
evidence order = ascending `evidence_ref`; attribute order = ascending `attribute key`. All strings lowercased
except IDs; single spaces; sentences end with `.`; records separated by a single space.

**Paired canonical examples (S1–S8, A1–A6):** each B0 string is paired 1:1 with the Decision-2 B1 object over
the **same** canonical fact set (see `…_PROTOCOL_LOCK_EXAMPLES` block below). Example (S2 foreign-key):
> Within tenant t01, the following records are authorized. The question concerns invoice i991. invoice i991 is
> a invoice with amount 4200. contract c882 is a contract with status active. invoice i991 is associated with
> contract c882 through the relation "belongs to contract". Evidence reference e17 supports the relation
> between invoice i991 and contract c882.

## Decision 2 — Frozen B1 typed schema
One exact canonical typed representation (deterministic, JSON-compatible), **identical fact content to B0**.
No answer label; no validity flag revealing the result; no evaluator-only field; no target-rank field; no
`correct`/`expected`/`gold`/`answer` (or equivalent) field; no schema fact unavailable in B0; no
representation search; no post-lock field renaming. **Deterministic array + attribute ordering** identical to
B0's orderings.

```json
{
  "tenant_id": "t01",
  "query": { "entity_type": "invoice", "entity_id": "i991", "relation_type": "belongs_to_contract" },
  "entities": [
    { "entity_type": "invoice",  "entity_id": "i991", "attributes": { "amount": "4200" },  "tenant_id": "t01" },
    { "entity_type": "contract", "entity_id": "c882", "attributes": { "status": "active" }, "tenant_id": "t01" }
  ],
  "relations": [
    { "relation_type": "belongs_to_contract", "source_entity_type": "invoice", "source_entity_id": "i991",
      "target_entity_type": "contract", "target_entity_id": "c882", "evidence_ref": "e17", "tenant_id": "t01" }
  ],
  "evidence": [
    { "evidence_ref": "e17", "supports_relation": "belongs_to_contract", "tenant_id": "t01" }
  ]
}
```
The B1 `relation_type` (`belongs_to_contract`) and the B0 relation phrase (`"belongs to contract"`) carry the
same semantic content; B1 adds **no** fact beyond B0. Every S1–S8 / A1–A6 B1 object is paired with its B0
string over an identical canonical fact set.

## Shared output contract (both arms; identical parser + evaluator)
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
`relation_supported` ∈ {true, false, null}. The output parser and evaluator are **identical** for B0 and B1;
**no arm-specific post-processing**.

## Decision 3 — Frozen numeric gates
**Primary score** = unweighted macro-average of {S1 exact-entity accuracy, S2 foreign-key accuracy, S3
relation-validity accuracy, S5 evidence-reference F1, S6 missing-relation abstention accuracy}.

### `TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_VALIDATED` (all required)
1. B1 final-seed mean primary ≥ **0.80**.
2. (B1 − B0) final-seed mean primary improvement ≥ **0.08** absolute.
3. ≥ **4 of 5** final seeds each satisfy: B1 primary ≥ **0.75** and (B1 − B0) ≥ **0.05**.
4. B1 per-split final means: S1 ≥ **0.85** · S2 ≥ **0.85** · S3 ≥ **0.80** · S5 precision ≥ **0.90** · S5 recall
   ≥ **0.90** · S6 abstention ≥ **0.90**.
5. S7 unauthorized cross-tenant inclusion = **0** across every final example and seed.
6. S8 stable-direct accuracy ≥ **0.90**.
7. B1 S8 does not regress > **0.02** absolute vs B0.
8. Information-equivalence verification passes for **100%** of paired examples.
9. Deterministic replay passes.
10. All shortcut/leakage gates pass. 11. All mandatory causal gates pass. 12. Compute limits respected.
13. No protocol deviation.

### `…_ADVANTAGE_PARTIAL` (only when)
No protocol/tenant/evidence-integrity hard failure; B1 mean primary ≥ **0.75**; (B1 − B0) mean ≥ **0.04**;
≥ **3 of 5** seeds show improvement ≥ **0.03**; one or more validated gates missed. Must name the failed
dimension {endpoint · causal purity · abstention · evidence · stable-direct · seed consistency}. **A
tenant-isolation failure can never be classified as partial.**

### `…_ADVANTAGE_NOT_FOUND` (when)
Protocol/integrity gates pass **and** ((B1 − B0) mean < **0.04**, or B1 mean primary < **0.75**, or < **3 of 5**
seeds improve ≥ **0.03**).

### `…_CAUSAL_GATE_FAILED`
Endpoint gates otherwise sufficient but ≥ 1 mandatory causal requirement fails.

### `…_EVIDENCE_GATE_FAILED`
Evidence precision < **0.90**, or recall < **0.90**, or evidence permutation does not produce the required
causal response, or unsupported evidence is emitted.

### `…_TENANT_GATE_FAILED`
**Any** unauthorized cross-tenant inclusion. **One** unauthorized inclusion is a hard failure.

### `…_PROTOCOL_VIOLATED` / `…_RESOURCE_BLOCKED`
Any material post-lock deviation / frozen protocol cannot complete within compute or environment limit.

## Mandatory causal gates (frozen)
- **A1 entity-identity permutation** (S1): B1 declines ≥ **0.20** absolute vs its clean score; selection follows
  represented identity, not lexical similarity.
- **A2 relation-target permutation** (S2/S3): B1 FK/relation accuracy declines ≥ **0.20** under corrupted
  targets, **or** the model explicitly rejects the corrupted relation where rejection is correct.
- **A3 relation removal:** abstention ≥ **0.90**; unsupported-answered rate ≤ **0.05**.
- **A4 evidence permutation:** evidence F1 declines ≥ **0.20** vs clean B1; no fabrication of the original
  evidence ref; unsupported-evidence emission = **0**.
- **A5 cross-tenant substitution:** unauthorized inclusion = **0**; out-of-tenant target selection = **0**; model
  abstains or selects the valid in-tenant target.
- **A6 lexical decoys:** B1 degradation from clean ≤ **0.05**; lexical-only baseline must not satisfy competence
  gates.

## Shortcut-baseline gates (frozen)
Baselines: lexical overlap · first-record · last-record · entity frequency · relation-type frequency · evidence
position · fixed-output-position · tenant-blind semantic similarity. Each must (a) be ≤ **chance + 0.05** on its
relevant split (chance computed mechanically per split), (b) fall below the corresponding learned B0/B1
competence floor, and (c) be **incapable** of satisfying the validated outcome. Any baseline exceeding
chance + 0.05 requires investigation **before** reserved execution; the benchmark is **not** adjusted after
inspecting reserved results.

## Decision 4 — Input-budget fairness (frozen)
**Primary comparison:** B0 and B1 carry the complete identical fact set; both fit within one fixed maximum
input window; **no truncation in any primary example**. Common maximum input length = **512 tokenizer tokens**,
unless the selected existing model has a smaller immutable limit, in which case that exact limit is used and
the working-set size is reduced **before** dataset generation (never truncate one arm differently). Same
output-token allowance for both arms. Report per pair: B0 token count · B1 token count · absolute difference ·
ratio · entity/relation/evidence counts. **Do not pad** the shorter representation to equalize length. **No
efficiency-superiority claim** from token-count differences.
**Sensitivity subset:** a preregistered paired subset where B0/B1 token counts differ by ≤ **10%**. Report
primary metrics on (1) the complete information-equivalent cohort (primary) and (2) the ≤10% subset. The
subset **cannot** override a failed primary verdict.

## Decision 5 — Model & compute recipe — **BLOCKED**
**Requirement:** identify the smallest **existing** deterministic **non-memory** model recipe (no
BindingSlots, no E1 episodic memory, no bounded quadratic/event-attention reader, no arm-specific encoder, no
real pretrained-model adaptation) that already has a stable harness, trains deterministically from scratch,
accepts **both** B0 (prose) and B1 (typed-serialized-as-text) through the **same tokenizer/input channel**
(few-hundred-token window), uses **one shared output head** emitting the shared output contract, and has an
**identical parameter count** across arms — **without any code change**. The rule is explicit: *"Do not invent
a new architecture. Do not add a typed-only encoder. If no suitable existing non-memory model recipe can be
identified without code changes, do not invent one. Emit `PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE` and stop Stage 2
without claiming the protocol is locked."*

**Investigation (repository-wide; independently cross-checked).** The requirement splits into two properties
that **no single existing component holds together**:

| Candidate | Tokenizer text-in? | Non-memory? | Structured 7-field output? | Verdict |
|---|---|---|---|---|
| `experiments/bindingslots_e1/models.py` (B0, E1) | No (fixed key tuples) | No — anonymous slots / explicit-key memory | No | Disqualified (the named memory recipes) |
| `experiments/hybrid_token_event_attention` `EventArm`/`EventSelfAttention` | partial | **No — K×K event-attention (quadratic reader) + slots** | No | Disqualified (bounded quadratic reader) |
| …same experiment, `TokenModel`/`TokenArm` H0 (`mistral_adapter.py`) | Yes (word `Vocab`) | Yes (tiny causal transformer, not a real LLM) | **No — 9-way class head; window `MAX_LEN=22`; fixed corpus** | Would need new targets/decoder/dataset/window = **code changes** |
| `hybrid_llm_vnext_lab/neural_slots_only` arm A | Yes (phase_lc `Vocab`) | arm A yes, but subject is `BindingSlots` | No — next-token LM graded by loss | Disqualified (slot study; no structured output) |
| `model_selection_pilot/provider.py` | n/a | — | via real APIs | Disqualified (real Anthropic/OpenAI/Bedrock adapters; no from-scratch training) |
| `experiments/enterprise_field_prediction` `StructuredReasoner` | **No (categorical/numeric feature encoder)** | **No — `SlotSelfAttention` bounded quadratic slot reader** | **Yes (closest output-shape match)** | Disqualified (no tokenizer + quadratic slot reader) |
| `experiments/phase_lc` LM arms A/L | Yes (`Vocab`, window ≤2048) | arms A/L yes | No — perplexity LM; no structured head/harness | Would need new dataset/decoder/harness = **code changes** |
| `symbolu_neural.clean_softmax` | Yes (character tokenizer) | Yes | No — generic next-character LM; no paired benchmark or structured-output harness | Would need new dataset/decoder/output-training harness = **code changes** |
| `symbolu_training/**` mistral wrappers, `jepa`, `train_lra`, vision trainers | mixed | mixed | No | Disqualified (real-model wrappers) or wrong task/IO |

**Determination.** The only recipe with the exact structured multi-field output
(`enterprise_field_prediction`) is disqualified on **two** hard criteria at once (no tokenizer/text channel;
`SlotSelfAttention` bounded quadratic reader). Every recipe that **is** a clean tokenizer-based from-scratch
transformer (`hybrid_token_event_attention` H0; `phase_lc` A/L; `neural_slots_only` A;
`symbolu_neural.clean_softmax`) lacks the structured output head + prose-vs-typed harness and would require
dataset + decoder + input-window/output-training harness changes (and in one case a disqualified-experiment
extraction) **code changes** to serve this benchmark. Building or adapting one is "inventing"/implementation,
which this stage forbids.

**Outcome: `PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`.** No suitable existing non-memory model recipe can be
identified without code changes. Per the rule, Stage 2 stops here **without claiming the protocol is locked**.
The path to unblock (a **separately authorized** implementation step, not part of this PR) would be to
implement a minimal non-memory tokenizer-based transformer with a shared structured-output head and the
prose-vs-typed harness — new code that must be its own authorized, reviewed step.

## Decision 6 — Seed semantics & protocol ordering (frozen)
Mechanically re-checked against the repo-wide seed registries and all prior experiment artifacts at lock time:
proposed seeds are **disjoint** from every prior program seed (the sole apparent hit, "76", was a false
positive inside `72.76` / a commit hash in `hybrid_llm_vnext_lab/.../reproduce_legacy_slots/config.json`, whose
actual seeds are `[0,1,2]`).

- **Seed 76 — smoke/implementation only:** shapes, parsing, determinism, training feasibility. **Must not**
  contribute to metric thresholds or verdicts.
- **Dev seeds 760–762 — paired B0/B1 dev runs:** verify protocol implementation and resource feasibility.
  **May not** change serializers, schema, numeric gates, model recipe, output contract, primary metrics, or
  conclusion vocabulary. Only implementation **bug fixes** are permitted after dev begins; each fix must be
  documented, invalidate affected dev evidence, require rerunning affected dev arms, and occur **before**
  final-seed execution authorization.
- **Reserved final seeds 7160–7164 — paired B0/B1 runs:** identical model init, data ordering, generated fact
  sets, task allocation, optimizer randomness; **arm-separated input serialization only**. Deterministic
  domain-separated sub-seeds for {dataset generation, model init, batch order, perturbation generation} via a
  **frozen derivation rule**: `sub_seed(seed, domain) = seed*1_000_003 + DOMAIN_ID*97 + 13`, with
  `DOMAIN_ID = {dataset:0, init:1, batch:2, perturb:3}`.
- **No final seed** may be opened, executed, inspected, or partially generated before, in order: (1) PR #1363
  merged; (2) this protocol-lock PR independently audited and merged; (3) implementation separately authorized;
  (4) implementation tests pass; (5) an execution-authorization record merged.

**Protocol-lock ordering (this PR authorizes none of steps 5–13):** 1 draft design merged · 2 protocol-lock
committed · 3 protocol-lock audited · 4 protocol-lock merged · 5 implementation authorized · 6 code implemented
· 7 smoke seed · 8 dev seeds · 9 implementation-integrity audit · 10 explicit final-execution authorization ·
11 reserved finals · 12 verdict reconstructed · 13 results audited.

## Information-equivalence lock
A mechanical verifier canonicalizes **both** arms back into the same fact graph. For every paired example,
require equality of: tenant · entities · entity types · entity IDs · attributes · relations · source IDs ·
target IDs · relation types · evidence references · missing relations · conflict states · query · expected
output type. Emit one canonical fact-set digest per example; require `B0_fact_hash == B1_fact_hash` for
**100%** of examples; any mismatch is a **protocol failure** (fail closed). The verifier ignores
representation-only syntax but **must not** ignore any semantic field.

## Determinism lock
Later implementation must prove: repeated generation under the same seed is byte-identical; B0 serialization
byte-identical; B1 serialization byte-identical; model-init hashes match across paired arms; data-order hashes
match across paired arms; evaluator output reproducible; fact-set hashes stable; and source/config/dataset/
checkpoint hashes recorded.

## Unresolved-items policy
No unresolved scientific placeholder. The **only** permitted unresolved items are operational identifiers that
cannot exist before implementation — future implementation commit hash · future dataset artifact hash · future
checkpoint hashes · future execution-environment identifier — each labelled
**`NOT_YET_CREATED — DOES_NOT_AUTHORIZE_EXECUTION`**. **No `APPROVAL_REQUIRED_BEFORE_EXECUTION`** remains in any
field governed by this lock. **Note:** Decision 5 being BLOCKED is **not** a placeholder — it is a resolved,
reported *blocker* that prevents the "fully specified" claim; it is documented, not deferred with a
`APPROVAL_REQUIRED` token.

## Verdict
**`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`.** Decisions 1, 2, 3, 4, and 6 (plus the shared output contract,
information-equivalence lock, determinism lock, shortcut/causal gates, and fairness policy) are fully
specified with no placeholders. **Decision 5 cannot be resolved without inventing/adapting a model (new
code), which this stage forbids;** therefore the protocol is **not** locked. `TYPED_VS_PROSE_PROTOCOL_LOCKED`
is **not** emitted; `IMPLEMENTATION_AUTHORIZED` / `EXECUTION_AUTHORIZED` are **not** emitted.

This blocker means **only** that a suitable existing non-memory model recipe does not exist in the repository
without code changes. It does **not** support — and must never be read as — typed-structure advantage ·
enterprise transfer · multi-hop · temporal reasoning · memory value · quality preservation · efficiency
superiority · production readiness · KDA eligibility.

**Unblock path (separately authorized, NOT part of this PR):** authorize an implementation step that builds a
minimal non-memory, tokenizer-based, from-scratch transformer with one shared structured-output head and the
prose-vs-typed harness — reviewed and merged on its own before any smoke/dev/reserved run. Only after that
implementation exists and passes integrity tests could this protocol be re-evaluated for the
`PROTOCOL_LOCKED_IMPLEMENTATION_NOT_AUTHORIZED` state.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

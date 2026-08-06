# Unseen-identifier copy & selection probe — preregistration (DRAFT, documentation-only)

**Documentation-only. Nothing here is implemented, generated, trained, executed, or seeded.**
This is a draft preregistration. Numeric gates are marked `APPROVAL_REQUIRED_BEFORE_EXECUTION`.
The probe must be implemented, reviewed, protocol-locked, and separately authorized before any run.

Always preserved, and untouched by this probe or any future outcome:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

## Motivation
The audited typed-vs-prose single-hop benchmark returned
`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`. Its deterministic replay showed both arms
**floored on the components that require copying a novel identifier from context** (S1/S2 entity
selection, S5 evidence selection ≈ chance/zero) while acing the constant-output components. This
raises a prior question the typed-vs-prose comparison could not answer: **can the frozen small
model do the base copy/selection operation at all on unseen identifiers?** If it cannot, the
typed-vs-prose null was **floor-limited by a missing base capability**, not by representation.

## Scientific question (the only question)
> Can the exact frozen small-model recipe **copy and select previously unseen identifiers** from a
> bounded context when representation comparison, enterprise semantics, memory mechanisms, evidence
> semantics, and multi-hop reasoning are removed?

## This probe is NOT
- a typed-vs-prose comparison;
- a BindingSlots experiment;
- an E1-memory experiment;
- a temporal experiment;
- a multi-hop experiment;
- an enterprise tenant-safety validation;
- a real-model transfer experiment;
- a capacity-scaling experiment;
- a KDA-unblocking experiment.

It isolates one thing: base copy/selection of opaque identifiers, single-hop, bounded context.

## Task splits (all single-hop, bounded)
| Split | Name | Definition | Tests |
|---|---|---|---|
| **C1** | Direct unseen-ID copy | Context explicitly provides one opaque target identifier; return it exactly. | Raw copy of a novel token sequence |
| **C2** | Single-relation lookup | Given a source ID and several `source → target` pairs, return the correct target. | Relation-indexed selection |
| **C3** | Evidence-like opaque-ID lookup | Given a relation and its associated opaque reference, return the reference. | Reference selection |
| **C4** | Position robustness | Place the correct pair uniformly at first / middle / last positions. | Position invariance |
| **C5** | Lexically-similar decoys | Distractor identifiers differ from the answer by one or two symbols. | Robustness to near-duplicates |
| **C6** | Seen-ID control | Use training-pool identifiers. | Memorization baseline |
| **C7** | Unseen-ID final cohort | Use a fully disjoint identifier pool. | Operation-level generalization |
| **C8** | Missing-key abstention | Query a source absent from context. | Correct abstention |

Each split is graded by **exact-sequence** correctness of the returned identifier (or correct
abstention for C8), with token-level accuracy reported as a secondary diagnostic.

## Primary interpretation (separated dimensions)
Report and interpret these dimensions **separately**, never collapsed into one headline number:
1. direct copying (C1);
2. relation selection (C2/C3);
3. evidence-like lookup (C3);
4. abstention (C8);
5. seen-vs-unseen generalization (C6 vs C7).

Reading of outcomes:
- **direct copy and lookup both succeed** → base copy/selection capability exists at this recipe;
- **direct copy succeeds but lookup fails** → relation selection is the bottleneck;
- **seen succeeds but unseen fails** → memorization without operation-level generalization;
- **unseen copy and lookup both fail** → the prior typed-vs-prose experiment was **floor-limited at
  this recipe** (the null was capability-limited, not representation-limited).

No outcome automatically authorizes capacity scaling or any further experiment.

## Frozen model constraint
Use the **exact same audited model** as the typed-vs-prose benchmark: same architecture
(`symbolu_neural.clean_softmax.backbone.SoftmaxTransformerLM`, 64-dim, 2 layers, 4 heads, 256
d_ff, vocab 200, dropout 0), same tokenizer, same parameter count (209,728), same initialization
policy, same optimizer family and hyperparameters (AdamW 3e-4, batch 8, 2000 updates), same
next-token output-only objective. Do **not**:
- increase capacity;
- change the tokenizer;
- add copy attention;
- add a pointer network;
- add memory;
- add a typed-only encoder;
- add a relational reader;
- invent a new architecture.
If the exact recipe cannot be reconstructed from the audited implementation, mark the
preregistration **blocked** (do not substitute a different recipe).

## Representation-neutral format (single deterministic representation)
Exactly **one** minimal deterministic representation — **no prose-vs-JSON comparison, no serializer
search.** Illustrative form (final syntax frozen at protocol-lock, not here):
```text
QUERY_SOURCE = Q7X2
FACTS:
Q7X2 -> M4P9
R8K1 -> Z3N6
A5D0 -> V2T4
ANSWER_TARGET =
```
Freeze at protocol-lock (all fixed, no search): separators · ordering · whitespace · query syntax ·
distractor syntax · output syntax · identifier alphabet · identifier lengths · candidate counts ·
position distribution. The output is the bare identifier (or the abstention token for C8), parsed
by one exact grader.

## Identifier design (frozen at protocol-lock)
Freeze: the identifier **alphabet**; the **length distribution**; the **tokenizer decomposition**
(how many tokenizer tokens each identifier occupies under the fixed 200-id lexical tokenizer);
train / dev / final **pools**; **collision prevention**; **disjointness** (train ∩ final = ∅);
and the **number of tokenizer tokens per identifier**. Report, for every result:
- exact-sequence accuracy;
- token-level accuracy;
- results broken down **by tokenizer length** of the identifier.

Constraints: identifiers are **opaque** (carry no lawful signal about the answer). Do **not** encode
labels in prefixes or identifier shape; the answer must be obtainable only by reading the queried
fact from context, never from the surface form of any identifier.

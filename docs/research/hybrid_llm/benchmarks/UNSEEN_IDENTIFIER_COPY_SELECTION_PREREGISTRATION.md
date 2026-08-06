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

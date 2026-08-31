# Key-consistency feasibility analysis

**Result: `KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`.** K1 is therefore **omitted** from the proposed
experimental arms. This is a draft analysis for approval; nothing is executed.

## The feasibility question (§10)

Does the current BindingSlots architecture expose, during ordinary inference, a **discrete and
trustworthy identity signal** linking the selected neural memory result to the requested
entity/event/fact key? A valid signal must be produced naturally during actual write/read execution,
available at ordinary inference, independent of evaluator ground truth, deterministic/mechanically
auditable, meaningful under soft/distributed writes, well-defined under slot reuse, version-aware
under overwrites, available without querying the expected answer, and available without reading the
external table first.

## Architectural facts that constrain the answer

- BindingSlots is **content-addressed by learned continuous key vectors**; a slot carries **no
  intrinsic discrete entity identity**. There is no `slot → entity` label anywhere in the model.
- **Writes are soft and distributed**: `w = sigmoid(gate)·softmax(addr)` spreads each fact across
  slots by a continuous weight, accumulated by a causal running mean. "The slot a fact was written
  to" is a *distribution*, not a discrete index.
- **Slots are reused**: 32 slots serve many more entities, so any single top slot is shared across
  entities (collisions), and overwrites change occupancy over time.
- The diagnostic phase established the failure is the **eval-time read address**, not the stored
  value — so a useful consistency check must catch *wrong-slot read routing*.

## Candidate constructions (each classified)

| # | construction | classification |
|---|---|---|
| 1 | **Evaluator slot→entity mapping** (use the "correct" slot for the queried entity) | **ORACLE LEAKAGE** — uses evaluator ground truth / correct-slot index. Forbidden. |
| 2 | **Write-time slot attribution** (record entity→top-write-slot at write, compare to read-top at query) | **FORBIDDEN SIDECAR** — requires a persisted `slot-index → entity` sidecar recomputable only from the original write; §10 explicitly prohibits "build a slot-index-to-entity sidecar merely to make K1 possible." Also **UNDEFINED UNDER DISTRIBUTED WRITES** (top-of-a-distribution is not mathematically justified) and ambiguous under slot reuse. |
| 3 | **Distributed-write attribution** (attribute the fact to the full soft write distribution) | **UNDEFINED UNDER DISTRIBUTED WRITES** — no discrete identity; comparing distributions needs a threshold that reintroduces the same confidence problem, and cross-entity overlap makes it non-discriminative. |
| 4 | **Selected-slot identity** (use the read's top slot's identity) | **TECHNICALLY UNAVAILABLE** — a slot has no intrinsic identity; recovering one reduces to #2 (sidecar), #1 (oracle), or #5 (decoding). |
| 5 | **Content decoding** (decode the selected slot's value vector to an entity/value and compare) | **CIRCULAR NEURAL INFERENCE** — a second neural read whose correctness depends on the *unresolved* slot representation; it can be confidently wrong exactly where the primary read is. Forbidden. |
| 6 | **Answer-to-table comparison** (compare the model's answer to the table's record for the requested entity) | **EQUIVALENT TO ALWAYS-VERIFY** — legitimate and non-oracle, but requires a table read on **every** query. It is not a selective, table-avoiding hybrid; it *is* V100. |

## Conclusion

No construction yields a legitimate, non-oracle, non-circular, **selective** (table-avoiding) identity
signal for content-addressed BindingSlots:

- #1 leaks the oracle; #5 is circular; #2 needs a forbidden slot-index sidecar and is undefined under
  distributed writes; #3 is undefined under distributed writes; #4 is intrinsically unavailable and
  collapses into #1/#2/#5.
- The **only legitimate** consistency check is #6 (answer vs table record), which **requires a
  per-query table read** — so by §10 it is classified as **always-verify (V100)**, not as a selective
  key-consistency hybrid.

Therefore `KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`. K1 is not proposed as an arm. The honest, legitimate
verification mechanism is V100 (always-verify), evaluated in the companion preregistration. If a future
architecture were to expose a discrete, version-aware, non-oracle write/read identity token produced
natively during inference, this classification would be revisited — but no such token exists today, and
none may be manufactured solely to enable K1.

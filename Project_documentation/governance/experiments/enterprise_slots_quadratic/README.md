# Enterprise Binding Slots + Bounded Quadratic Reasoning

**Decisive question:** do binding slots preserve exact enterprise evidence across time while bounded
quadratic attention makes better use of that retained evidence, with each component showing a
distinct causal contribution? (No Phase in any arm.)

## Responsibility boundary (structurally enforced)

| concern | handled by | never by |
|---|---|---|
| authoritative long-term storage | `evidence_ledger.EvidenceLedger` | slots |
| exact entity equality, joins, provenance, **access control**, candidate generation | deterministic schema/index (`evidence_ledger`, `admission_policies`) | learned components |
| bounded exact working memory | `binding_slots` (SlotRecord exact + learned rep) | — |
| comparison, contradiction/version resolution, chain completion | `bounded_quadratic` over the slot set / packet | — |

Every slot holds an exact resolvable `SlotRecord` (never mutated into a different fact) plus a
learned `SlotRepresentation`. Every admission/refresh/replace/evict emits an auditable event. Exact
evidence IDs ride with the reps so outputs resolve to the ledger and unauthorized records never
enter (verified: unauthorized-inclusion 0, ID-preservation 1.0).

## Domain

Procurement & approval governance. The required approval **role** for a `PurchaseRequest` is a
deterministic function `POLICY_TABLE[active_policy_version][budget_tier]`. The two answer-determining
records — the **budget** (keyed to the request) and the **active policy** (keyed to the *contract*,
reachable only via request→vendor→contract→policy) — sit at distant workflow steps. `ABSTAIN` is
correct when a required record is unobserved/evicted or two active policies materially conflict.
Labels come straight from the generator (no LLM).

## Retrieval-breadth asymmetry (why slots may help)

- **one-shot** — all authorized candidates are available at query time (fresh retrieval sees all).
- **streaming / multi-step** — fresh retrieval sees only a bounded recent window, so distant
  required evidence falls out of view; binding slots that admitted it earlier retain it.

`S1G` (global query-time retrieval + quadratic, same K) is the *fair* comparator that separates
memory value from retrieval value.

## Arms

`S0` fresh+pool · `S1` fresh+quad · `S1G` global-retrieval+quad · `S2` slots+pool ·
`S3` slots+quad (primary) · `S3R` role-aware slots+quad · `S4` oracle slots+quad (ceiling) ·
`S5` slots+full self-attn · `S6` slots+query→slot.

## Policies

`P0` FIFO · `P1` recency · `P2` enterprise priority (chain-link / query-chain relevance / active /
conflict / authority / latest-version / recency) · `P3` +duplicate collapse · `P4` +conflict-pair
protection · `P5` +active/stale version-pair protection · `P6` oracle.

## Compute boundary

Quadratic attention runs over the query + ≤K working-set records (≤K+1 ≤ 33 tokens) — never the
N-event workflow, never an N×N tensor (`tests/test_slots.py`). Query-to-slot O(K·d); full
slot-self O(K²·d). Slot state bytes bounded by K.

## Sequencing

Validity pilot first (S0–S4, P2, N=64/256, K=4/8/16). Then the focused **slot-policy diagnosis +
bounded rescue** (`run_rescue.py`): conditional accuracy (acc | required evidence survived) to
localize the S3→S4 gap as selection vs reasoning, the §4 failure taxonomy, deterministic policies
P2–P5, role-aware slots, the S1G fair control, a capacity sweep, and causal ablations.

## Files

`schema.py` · `evidence_ledger.py` · `dataset.py` · `binding_slots.py` · `admission_policies.py` ·
`bounded_quadratic.py` · `models.py` · `train.py` · `evaluate.py` · `diagnosis.py` ·
`causal_controls.py` · `run_pilot.py` · `run_rescue.py` · `tests/` · `results/` ·
`ENTERPRISE_SLOTS_QUADRATIC_REPORT.md` · `ENTERPRISE_SLOTS_QUADRATIC_RESULTS.json`.

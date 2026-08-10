# BTRR Implementation Blocker — `BTRR_IMPLEMENTATION_BLOCKED_BY_PREREGISTERED_CONSTRAINT`

**State: BLOCKED pending owner decision.** Implementation of the preregistered BTRR experiment was
halted under clause §14 of the implementation authorization ("Detect preregistration/code conflicts")
because the locked preregistration is incompatible with the frozen single-hop harness it mandates for
reuse. No implementation code was written, no frozen artifact was modified, no reserved seed was
consumed, and `experiments/relational_reasoning_bounded_context/EXECUTION_AUTHORIZATION.md` remains
unsigned/fail-closed.

This document does **not** modify the preregistration. It records the exact conflicting clauses and a
minimal amendment proposal for owner decision, per §14 (steps 1–5).

## Evidence (frozen constants + measured tokenization; tokenizer-only, no seeds/model/training)
Measured with the frozen `experiments/single_hop_typed_vs_prose/tokenizer.py` (`LexicalTokenizer`) and
the frozen limits in `config.py`:

- Frozen: `FROZEN_TRAIN_RECIPE.input_token_limit = 512`; `FROZEN_MODEL_RECIPE.max_seq = 1024`;
  `vocab_size = 200`; lexeme slots used = **69 of 69** (IDs 131–199 fully consumed).
- Compact single-char-ID serialization (terse, non-JSON) of BTRR ReasoningContexts:
  - minimal R9 (6 entities, 4 events): **437** input tokens (already 85% of the 512 limit).
  - upper-range R9/R12 (12 entities, 48 events — top of the preregistered `entities 6–12`,
    `events 2–4/entity`): **1705** tokens → exceeds the 512 input limit **and** the 1024 context.
  - named `serialize_b1`-style canonical JSON (12 entities, 19 events): **2436** tokens (4.75× the limit).
- Frozen tokenizer lexeme coverage of BTRR tokens: `events`, `policies`, `event_id`, `sequence`,
  `policy_id`, `conditions`, `outcome`, `path_mode`, `reasoning_path`, `answer`, `evidence_ids` — **none
  present**. Status tokens: `INSUFFICIENT_EVIDENCE` present; `SUPPORTED`, `POLICY_NOT_APPLICABLE`,
  `INVALID_RELATION_PATH` — **absent**.

## Conflict 1 — Vocabulary exhaustion (frozen tokenizer cannot represent the frozen schema)
- Clause A (reuse/no-capacity-change): `..._PREREGISTRATION.md` §5 "Reused unchanged (import):
  `single_hop_typed_vs_prose/{model,tokenizer,config}.py`"; `..._PROTOCOL_LOCK.md` "Model recipe …
  reused by import; no capacity change"; `..._PREREGISTRATION.json` `model.recipe.vocab_size = 200`.
- Clause B (new schema/output vocab): `..._PREREGISTRATION.md` §4 (Event, Policy, Condition, Constraints,
  ReasoningQuery fields `path_mode`/`relation_chain`/`requested_property`/`policy_scope`) and
  ReasoningOutput `{answer, reasoning_path, evidence_ids, status ∈ 4 values}`.
- Impossibility: `tokenizer.py` hard-asserts exactly 69 lexemes with all IDs 131–199 consumed and
  `config.py` asserts `vocab_size == 200`. Adding BTRR lexemes requires either exceeding vocab 200
  (capacity change — forbidden by the protocol lock) or evicting single-hop lexemes (modifying a frozen
  artifact shared with, and tested by, `single_hop_typed_vs_prose`). Neither is permitted.

## Conflict 2 — Context-window impossibility (frozen window cannot contain valid R9/R12)
- Clause A: `FROZEN_TRAIN_RECIPE.input_token_limit = 512` (asserted), `max_seq = 1024`; "no capacity
  change."
- Clause B: frozen generator parameters — `entities/episode 6–12`, `events 2–4 / relevant entity`, plus
  policies and evidence (`..._GATE_RATIONALE.md` "Generator parameters that fix chance";
  `..._PREREGISTRATION.json` gates derived from `entity-selection chance ≤ 1/6`). These sizes are
  load-bearing: the §8 numeric gates were derived from the chance levels they set, so episodes cannot be
  shrunk without changing the frozen gates.
- Impossibility: the upper range of the frozen parameters serializes to 1705 tokens even in the most
  compact form — over the 512 input limit and the 1024 context. Valid upper-range R9/R12 instances cannot
  exist within the frozen window.

## Conflict 3 — Output-contract incompatibility (metric not computable from frozen output contract)
- Clause A: reuse `config.py` (`STATUS_VALUES = (ANSWERED, INSUFFICIENT_EVIDENCE)`; single-hop
  `OUTPUT_FIELDS`).
- Clause B: BTRR ReasoningOutput `status ∈ {SUPPORTED, INSUFFICIENT_EVIDENCE, POLICY_NOT_APPLICABLE,
  INVALID_RELATION_PATH}` with fields `{answer, reasoning_path, evidence_ids, status}`; §7 metric
  "relation-path accuracy (exact ordered)" requires `reasoning_path` in the emitted output.
- Impossibility: the frozen `STATUS_VALUES`/`OUTPUT_FIELDS` do not contain the BTRR statuses or
  `reasoning_path`; reusing `config.py` unchanged is impossible, and exact-ordered path accuracy cannot be
  computed from the frozen single-hop output contract.

## Root cause
BTRR was frozen to reuse the single-hop **frozen tokenizer + 200-token vocabulary + 512/1024 model**,
which were sized for single-hop *atomic* episodes. BTRR intrinsically requires multi-record temporal +
policy working sets with a richer output contract. The reuse mandate and the schema/scale mandate cannot
both hold.

## Smallest protocol-amendment proposal (for OWNER decision — NOT applied)
Presented as options; the owner selects. None is applied here.

- **Amendment A (recommended — smallest change that preserves the science).** Decouple BTRR from the
  single-hop frozen tokenizer/recipe. Freeze a BTRR-specific tokenizer (superset lexemes for
  events/policies/conditions/operators and the 4 statuses) and a BTRR-specific frozen model recipe whose
  **only** changes vs. the single-hop recipe are `vocab_size`, `max_seq`, and `input_token_limit` sized to
  hold the upper-range R9/R12 (measured need: ≥ ~1792 input tokens compact; keep a margin, e.g.
  `input_token_limit = 2048`, `max_seq = 2560`). Keep depth/width/heads/FFN/dropout/optimizer identical so
  no reasoning-capability confound is introduced; continue to reuse `SoftmaxTransformerLM` (it is
  parameterized by `BackboneConfig`) and the `schema.py` dataclasses and the `guard_seed` fail-closed gate
  unchanged. Because this touches the frozen "no capacity change" clause, it requires explicit owner
  amendment — which is exactly why silent action was refused. Gate values in §8 are unaffected (they
  depend on chance/competence, not on vocab or window).
- **Amendment B (keeps 512/200, changes the science — not recommended).** Reduce the frozen generator
  parameters (e.g. entities ≤ 4, events ≤ 2/entity, ≤ 4 evidence, single policy) and a terse non-JSON
  serialization within vocab 200, then **re-derive** the §8 numeric gates from the new chance levels. This
  materially alters the preregistered difficulty of R9/R12 and the realism of the "bounded typed working
  set," and forces a fresh gate freeze.

## §14 compliance
1. Preregistration not modified. 2. No workaround improvised. 3. Conflicting clauses identified above.
4. Smallest amendment proposed above. 5. Experiment marked blocked pending owner decision.
Preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
`KDA_VALIDATION_BLOCKED`. Reserved seeds `8100 / 8101–8103 / 81600–81604` untouched and fail-closed.

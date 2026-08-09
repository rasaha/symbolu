# BTRR Protocol Lock

**Status: `BTRR_PROTOCOL_LOCK_DRAFT` — not yet frozen.** This document, once signed, freezes every
load-bearing choice before any reserved seed is read. Machine-readable companion:
`BOUNDED_TYPED_RELATIONAL_REASONING_PREREGISTRATION.json`. Always preserved:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
`KDA_VALIDATION_BLOCKED`.

## What is frozen at lock time
- **Scientific question** (Q0 prerequisite, Q2a execution, Q2b discovery) — verbatim from the
  preregistration §1.
- **Task generator** — deterministic P0 and R1–R12 construction; RNG derived solely from the seed via a
  fixed sub-seed derivation; no wall-clock, no `Math.random`-equivalent nondeterminism.
- **Schema** — the frozen `ReasoningContext` / `ReasoningQuery` / `Event` / `Policy` / `Condition` /
  `Constraints` / `ReasoningOutput` contract (preregistration §4), including the PATH_DISCOVERY validator
  (empty `relation_chain`, no answer-bearing tokens in the query).
- **Model recipe** — `FROZEN_MODEL_RECIPE` (64/2/4/256) + `FROZEN_TRAIN_RECIPE` (batch 8, ≤2000 updates,
  lr 3e-4), reused by import; no capacity change.
- **Single-checkpoint paired-evidence invariant** (preregistration §6) — one checkpoint per seed;
  byte-identical `parameter_digest` across P0 and R1–R12; no optimizer step, fine-tuning, selection, or
  modification between P0 and R1–R12.
- **Output schema and strict parser** — frozen field order; 4 status values; exact-ordered path scoring.
- **Splits** — P0 subtasks B1–B7; R1–R12 with PATH_GIVEN vs PATH_DISCOVERY assignment.
- **Metrics** — preregistration §7.
- **Numeric gates** — preregistration §8 (rationale in the gate-rationale doc); frozen before any reserved
  read.
- **Shortcut / structure-blind gates** — preregistration §9.
- **Seeds** — smoke 8100; dev 8101–8103; final 81600–81604; unit fixtures 883000–883004.
- **Training budget** — ≤ 2000 updates; deterministic.
- **Stopping / futility rules** — final run is single-shot per seed; no early peeking at final metrics; no
  re-run of a final seed after inspection.
- **Verdict vocabulary and precedence** — preregistration §10 (protocol → base capability → shortcut →
  resource → abstention → evidence → temporal → policy → discovery/composite).
- **Interpretation boundaries** — preregistration §12.

## Integrity checks required before any reasoning verdict (precedence step 0)
The evaluator MUST pass all of the following, else emit `PROTOCOL_VIOLATED` (and classify the run as
neither a P0 success nor a P0 failure):
1. protocol-lock hash matches the committed `preregistration.json` (`protocol_lock` guard).
2. seed-role check: the executed seed matches its declared role; reserved seeds carry a valid
   `guard_seed` authorization token.
3. schema-integrity: every episode passes `validate()`; no `FORBIDDEN_MODEL_VISIBLE_KEYS`; tenant purity;
   PATH_DISCOVERY validator holds.
4. deterministic replay: two evaluation passes of the frozen checkpoint yield byte-identical outputs and
   identical `parameter_digest`.
5. provenance: source hashes of reused modules
   (`symbolu_neural/clean_softmax/backbone.py`, `single_hop_typed_vs_prose/{model,tokenizer,config}.py`)
   and new BTRR modules match the recorded manifest.

## No gate may change after reserved inspection
Once a final seed is read, no gate, threshold, split definition, or verdict rule may be altered. Any
change requires a new preregistration with new reserved seeds.

## Amendments (append-only index)
- **Amendment 001** — `BOUNDED_TYPED_RELATIONAL_REASONING_PROTOCOL_AMENDMENT_001.md` (+ `.json`),
  status `BTRR_PROTOCOL_AMENDMENT_001_READY_FOR_OWNER_REVIEW`. Representation-capacity only: introduces a
  separate frozen BTRR tokenizer (80 lexemes, `vocab_size = 211`) and raises `input_token_limit`
  512 → 1664 and `max_seq_len` 1024 → 2048 to encode the preregistered BTRR state without truncation.
  Reasoning architecture, training recipe, task semantics, densities, metrics, numeric gates, shortcut
  gates, verdict precedence, final-seed requirement, and reserved seeds are **unchanged**. Resolves the
  `..._IMPLEMENTATION_BLOCKER.md` conflicts (commit `f8dd65c5e734bc1f31eaf100e4069c050d014e8c`). This
  index pointer does not rewrite the original preregistration; both remain on record. Pending owner
  approval; execution remains unauthorized.

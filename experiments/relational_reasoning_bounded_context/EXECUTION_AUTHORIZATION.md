# BTRR Execution Authorization — UNSIGNED (fail-closed)

**State: `BTRR_EXECUTION_NOT_AUTHORIZED`.** This document is a placeholder. No execution-authorization
token has been issued. Until the repository owner signs this file and populates the token registry, every
reserved BTRR seed fails closed via `guard_seed`, and no training, evaluation, or reserved-seed read may
occur.

This file authorizes **nothing** by existing. It records the gate; it does not open it.

## What is gated
- Reserved seeds: smoke `8100`; development `8101, 8102, 8103`; final `81600, 81601, 81602, 81603, 81604`.
- Any operation that trains a BTRR checkpoint, evaluates P0 or R1–R12 on a reserved seed, or reads a
  reserved cohort.

## What is NOT gated
- Unit-test fixtures on seeds `883000–883004` (inadmissible as benchmark evidence; mechanical checks only).
- Reading/authoring the preregistration bundle (this design phase).

## Preconditions before any signature
1. `BOUNDED_TYPED_RELATIONAL_REASONING_PROTOCOL_LOCK.md` is frozen and its hash matches
   `BOUNDED_TYPED_RELATIONAL_REASONING_PREREGISTRATION.json`.
2. The additive implementation (`experiments/relational_reasoning_bounded_context/` modules) exists and
   passes mechanical unit tests on fixture seeds only — implemented **after** lock, never before.
3. The single-checkpoint paired-evidence invariant (one checkpoint per seed, byte-identical
   `parameter_digest` across P0 and R1–R12) is enforced in code and covered by a test.
4. Structure-blind baselines and shortcut gates are implemented and green on development seeds.

## Signature block (empty)
```
authorized_by:        <unsigned>
date:                 <unsigned>
smoke_token:          <not issued>
development_token:    <not issued>
final_token:          <not issued>
```

Reserved seeds remain fail-closed while every token above reads `<not issued>`.

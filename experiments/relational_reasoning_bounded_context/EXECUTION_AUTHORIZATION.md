# BTRR Execution Authorization — UNSIGNED (fail-closed)

**State: `BTRR_EXECUTION_NOT_AUTHORIZED`.** This document is a placeholder. No execution-authorization
token has been issued. Until the repository owner signs this file and populates the token registry, every
reserved BTRR seed fails closed via `guard_seed`, and no training, evaluation, or reserved-seed read may
occur.

This file authorizes **nothing** by existing. It records the gate; it does not open it.

## Authorization mechanism (implemented — two-key, fail-closed)
Per `BTRR_EXECUTION_AUTHORIZATION_MECHANISM_SPEC.md`, `guard_seed` now requires BOTH keys for a reserved
seed; neither alone suffices, and there is no bypass flag:
1. **Owner key (in git):** an entry in `docs/research/hybrid_llm/benchmarks/BTRR_EXECUTION_AUTHORIZATION_RECORD.json`
   with `authorized:true`, the seed in `scope_seeds`, `token_sha256` = SHA-256 of a plaintext token
   generated out-of-band, `protocol_lock_digest` = current
   `experiments.relational_reasoning_bounded_context.manifest.config_digest()`, and (optionally)
   `expires_at`. Signing = an owner commits that edit; git history is the audit trail.
2. **Operator key (out of git):** the plaintext token supplied at run time via env `BTRR_EXEC_TOKEN`
   (or the `token=` argument), matched by hash against the record.

The committed record ships **unsigned** (every role `authorized:false`, hashes null), so execution stays
closed. Authorizing one role does not authorize the others; changing the frozen protocol/config revokes
any authorization (digest mismatch). Signing this file (below) and the JSON record are the two owner
surfaces; both must be completed, and the operator token supplied, for a reserved seed to run.

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

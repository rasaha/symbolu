# Hybrid LLM benchmarks index

Controlled single-hop typed-structure-vs-flattened-prose relational benchmark (B0 vs B1), plus a
follow-on unseen-identifier copy/selection probe (draft). Preserves
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

## Follow-on: unseen-identifier copy/selection diagnostic (implementation merged, fixture-only; smoke/development execution authorized, final prohibited)
- **[UNSEEN_IDENTIFIER_COPY_SELECTION_PREREGISTRATION.md](UNSEEN_IDENTIFIER_COPY_SELECTION_PREREGISTRATION.md)**
  — representation-neutral probe of whether the frozen small recipe can copy/select **unseen**
  identifiers from context at all (splits C1–C8; two orthogonal axes: copy-vs-selection and
  seen-vs-unseen; iterative-diagnosis rule), testing whether the typed-vs-prose null was
  floor-limited by a missing base capability. (Merged.)
- **[UNSEEN_IDENTIFIER_COPY_SELECTION_SHORTCUT_ANALYSIS.md](UNSEEN_IDENTIFIER_COPY_SELECTION_SHORTCUT_ANALYSIS.md)**
  — structure-blind baselines to measure before reserved execution.
- **[UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCK.md](UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCK.md)**
  · **[…_PROTOCOL_LOCK_CHECKLIST.md](UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCK_CHECKLIST.md)** —
  protocol lock freezing Decisions 1–12 (axes, task/representation/identifier/output contracts,
  **numeric gates**, verdict mapping **+ frozen verdict precedence**, shortcut gates, model recipe
  reconstructed from merged source, frozen seeds, compute limits, iterative-diagnosis rule). Verdict
  **`UNSEEN_IDENTIFIER_COPY_SELECTION_PROTOCOL_LOCKED`** — implementation and execution **not**
  authorized. (Merged.)
- **[UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_PLAN.md](UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_PLAN.md)**
  · **[…_IMPLEMENTATION_AUTHORIZATION.md](UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_AUTHORIZATION.md)**
  · **[…_IMPLEMENTATION_CHECKLIST.md](UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_CHECKLIST.md)** —
  documentation-only implementation-authorization package (merged). Implementation delivered in
  `experiments/unseen_identifier_copy_selection/` (fixture-only; reserved execution is phase-gated).
- **[UNSEEN_IDENTIFIER_COPY_SELECTION_POST_MERGE_IMPLEMENTATION_AUDIT.md](UNSEEN_IDENTIFIER_COPY_SELECTION_POST_MERGE_IMPLEMENTATION_AUDIT.md)**
  — independent post-merge implementation-integrity audit (A–P). Verdict
  **`IMPLEMENTATION_INTEGRITY_CONFIRMED_AFTER_SCOPED_CORRECTIONS`** (fail-closed guard bypass found +
  fixed in PR #1372; re-audit confirmed; findings carry forward to the phase-protocol default).
- **[UNSEEN_IDENTIFIER_COPY_SELECTION_SMOKE_DEV_EXECUTION_PLAN.md](UNSEEN_IDENTIFIER_COPY_SELECTION_SMOKE_DEV_EXECUTION_PLAN.md)**
  · **[…_SMOKE_DEV_EXECUTION_AUTHORIZATION.md](UNSEEN_IDENTIFIER_COPY_SELECTION_SMOKE_DEV_EXECUTION_AUTHORIZATION.md)**
  · **[…_SMOKE_DEV_EXECUTION_CHECKLIST.md](UNSEEN_IDENTIFIER_COPY_SELECTION_SMOKE_DEV_EXECUTION_CHECKLIST.md)** —
  documentation-only smoke/development execution-authorization (Decisions 1–12: commands, run
  matrix, generation order, pre-execution checks, smoke/development gates, shortcut aggregation,
  evidence/fingerprint contract, failure handling, stopping rules, lifecycle), reconciled onto the
  phase-protocol control model (explicit `--phase`, exact seed-role validation, one seed per
  invocation, primitive fail-closed guard; no crypto gate). Merged with operator authorization:
  **smoke (9070) + development (9071–9073) execution AUTHORIZED; reserved final seeds 90760–90764
  prohibited.**
- **[UNSEEN_IDENTIFIER_EXECUTION_INTERFACE_SHORTCUT_BLOCKER.md](UNSEEN_IDENTIFIER_EXECUTION_INTERFACE_SHORTCUT_BLOCKER.md)**
  — historical blocker record: PR #1373's frozen commands originally needed an execution interface the
  fixture-only package lacked (no CLI / train / evaluate / replay / manifest entry points), with 8 of
  the 12 frozen shortcut baselines implemented. **Resolved:** the phase-scoped execution interface and
  all 12 baselines were delivered in PR #1375, and the caller-supplied crypto authorization layer was
  replaced by the phase-protocol control model in PR #1377; PR #1373 has since been reconciled onto
  that model and merged. Historical verdict **`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_REQUIRED`** —
  now satisfied.
- **[UNSEEN_IDENTIFIER_EXECUTION_INTERFACE_SHORTCUT_AUTHORIZATION.md](UNSEEN_IDENTIFIER_EXECUTION_INTERFACE_SHORTCUT_AUTHORIZATION.md)**
  · **[…_IMPLEMENTATION_PLAN.md](UNSEEN_IDENTIFIER_EXECUTION_INTERFACE_SHORTCUT_IMPLEMENTATION_PLAN.md)**
  · **[…_CHECKLIST.md](UNSEEN_IDENTIFIER_EXECUTION_INTERFACE_SHORTCUT_CHECKLIST.md)** —
  documentation-only corrective authorization for completing the execution interface and the four
  missing shortcut baselines: Decisions 1–12 freezing the exact file set (CLI / `__main__` / training
  / evaluation / replay / evidence / manifest / shortcut / runner mods), the single-explicit-seed
  command contract, an authorization-record schema (later **superseded by the PR #1377 phase-protocol
  model** — explicit `--phase` + exact seed-role validation replaced the record/crypto scheme),
  greedy-decode evaluation, deterministic replay, manifest/trace emission, the four missing baselines,
  aggregation hierarchy, fail-closed rejection, and fixture-only tests/CI. Historical status
  **`EXECUTION_INTERFACE_SHORTCUT_COMPLETION_AUTHORIZATION_DRAFT_READY`** — this corrective package was
  implemented in PR #1375; reserved final seeds remain prohibited.

## Completed: single-hop typed-vs-prose benchmark

- **[SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md](SINGLE_HOP_TYPED_VS_PROSE_PREREGISTRATION.md)** — the draft
  design (question, hypothesis, arms, splits S1–S8, ablations A1–A6, ground-truth/info-equivalence, gate
  structure).
- **[SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md](SINGLE_HOP_TYPED_VS_PROSE_SHORTCUT_ANALYSIS.md)** —
  shortcut/leakage threats + guards + causal-load-bearing requirement.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md)** — protocol
  specification. Current verdict remains **`PROTOCOL_LOCK_BLOCKED_MODEL_RECIPE`** until the separately
  authorized implementation exists, passes integrity checks, is independently audited, and is merged.
- **[SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK_CHECKLIST.md)**
  — protocol pass/fail checklist (22 specified · 1 blocked · 1 N/A-pending-recipe).
- **[SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md](SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION.md)**
  — exact bounded recipe and file/test scope for the new non-memory fixed-lexical-tokenizer shared-output
  harness. Verdict: **`IMPLEMENTATION_AUTHORIZED_EXECUTION_NOT_AUTHORIZED`**.
- **[SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION_CHECKLIST.md](SINGLE_HOP_TYPED_VS_PROSE_IMPLEMENTATION_AUTHORIZATION_CHECKLIST.md)**
  — authorization checklist and explicit execution prohibitions.
- **[PR1362_AUDIT_AND_MERGE.md](PR1362_AUDIT_AND_MERGE.md)** · **[PR1363_AUDIT_AND_MERGE.md](PR1363_AUDIT_AND_MERGE.md)**
  — audit records for the thesis-V1.1 and preregistration merges.

- **[SINGLE_HOP_TYPED_VS_PROSE_EXECUTION_AUTHORIZATION.md](SINGLE_HOP_TYPED_VS_PROSE_EXECUTION_AUTHORIZATION.md)**
  — owner authorization record for building the real dataset and executing the frozen protocol.
- **[SINGLE_HOP_TYPED_VS_PROSE_RESULTS.md](SINGLE_HOP_TYPED_VS_PROSE_RESULTS.md)** — executed results and
  verdict: **`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`** (B1 JSON − B0 prose = −0.022 primary; 0/5
  seeds pass; tenant isolation held; information-equivalence and determinism verified). A preregistered null:
  typed structure gave no single-hop advantage at the frozen recipe, and neither representation solved
  copy-from-context on unseen identities.

- **[SINGLE_HOP_TYPED_VS_PROSE_AUDIT_REPORT.md](SINGLE_HOP_TYPED_VS_PROSE_AUDIT_REPORT.md)** ·
  **[…_AUDIT_PROVENANCE.md](SINGLE_HOP_TYPED_VS_PROSE_AUDIT_PROVENANCE.md)** ·
  **[…_AUDIT_ANALYSIS.md](SINGLE_HOP_TYPED_VS_PROSE_AUDIT_ANALYSIS.md)** — independent Stage-2 audit
  (provenance, protocol-lock fidelity, authorization ordering, arm-fairness, decode-cap,
  information-equivalence hard path, deterministic replay, fingerprint manifest, constant-output and
  shortcut analysis). Decision: `MERGE_READY_AFTER_SCOPED_CORRECTIONS`; the frozen result
  reconstructs exactly.

**Current state:** the benchmark was implemented, frozen, owner-authorized, and executed
(smoke 76 → dev 760–762 → reserved final 7160–7164). Verdict is a clean preregistered null
(`TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`). No transfer, efficiency, multi-hop, temporal, memory,
or production conclusion is drawn. Preserves `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`E1_TEMPORAL_TRANSFER_PARTIAL`, `KDA_VALIDATION_BLOCKED`.

# Phase-Free External Table Always-Verify Reference-Backend Characterization — preregistration

**Frozen before final-cohort execution.** System-level reliability characterization of the SQLite
reference backend under always-verify (V100). **Not** a neural-routing intervention. Always co-emits
`KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`, `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`KDA_VALIDATION_BLOCKED`. Derived from the merged draft preregistration (PR #1348) and the merged
external-fallback phase (PR #1346). The machine-readable twin is `preregistration.json` (frozen
implementation hashes included).

## Cohort (frozen, reused)
Seeds **28, 29, 30, 31, 32**; 120 examples/seed; **600 queries**. Same examples and same frozen model
states as PR #1346. No replacement seeds. Each seed's frozen B0 state (== `run_h2`, byte-identical) is
reconstructed deterministically and **accepted only when its trajectory (`needle_by_dist` + `ppl`)
matches the committed B0 evidence**; the reconstructed state is used for **inference only**.

## Arms (approved scope only)
- **M0** — frozen BindingSlots neural-only; zero table reads.
- **T0** — deterministic table-only ceiling; one read/query; abstain when no valid record.
- **F0** — the **exact** frozen PR #1346 confidence trigger (`prob_min=0.1, margin_min=0.05,
  entropy_max=1.0`, calibration hash `7421fbfb…`); **comparator only, no recalibration**.
- **V100** — always verify at **100% legitimate write coverage**; **exactly one** table read/query.

**Not run:** K1, V75, V50, partial-coverage stress, unverified-neural-return policy, confidence-threshold
sweeps, neural training, optimizer steps, routing changes, base-recipe redesign, Phase, KDA, MLA.

## V100 semantics (per query)
1. execute the frozen BindingSlots neural path; 2. perform **one** deterministic external-table read;
3. retrieve the current valid record for the requested legitimate key; 4. compare neural result to the
record; 5. agree → `verified_agreement`; 6. disagree → return the **table** value as
`verified_correction`; 7. verification cannot complete → **abstain**; 8. attach version + source
evidence + provenance to every verified return.

At 100% coverage V100 **reads the table on every query, approaches T0 reliability, gives no table-read
reduction vs T0, and adds neural-inference cost on top of verification**. It is **not** a latency
advantage.

## Fail-closed policy (only policy this phase)
No valid record / stale / expired / deleted / incomplete provenance / table unavailable / read failure /
write failure / verification status unestablished → **abstain**. Never return an unverified neural
answer; never silently downgrade a verified result to unverified.

## Reference backend
SQLite reference (`ephemeral_table.EphemeralTable`) extended by `v100_table.V100Table`. No
PostgreSQL/Redis/cloud/production DB, no network service, no customer data. This is a reference-backend
characterization, not production-infrastructure validation.

## Timing methodology (boundaries frozen before the final cohort)
- **Query-path (V100):** start before neural inference; stop after neural inference + table lookup +
  comparison + classification + correction/abstention decision + provenance construction + final
  response-object serialization. Report p50/p95/p99/mean/max + per-seed distribution.
- **Table-only (T0):** start before lookup; stop after lookup + validation + provenance + serialization.
- **Components (separate):** neural inference; table lookup; comparison; provenance construction;
  serialization; total M0 / T0 / V100 paths.
- **Write-path (separate):** write-event receipt; validation; serialization; commit; provenance attach.
- **Lifecycle (separate):** expiration handling; deletion; cleanup; explicit teardown; restart (file-backed).
- The ~**0.006 ms** isolated table-read figure must **not** substitute for full end-to-end latency.

## Reliability categories (each query lands in exactly one)
`verified_agreement_correct` · `verified_correction_correct` · `verified_return_incorrect` ·
`abstained_missing_record` · `abstained_invalid_record` · `abstained_table_unavailable` ·
`abstained_integrity_failure` · `system_failure`. **Abstention is never merged with incorrect;
corrected answers are never merged with ordinary neural successes.**

## Required metrics
Reliability (total queries; returned-answer accuracy; verified-answer accuracy; incorrect verified
returns; disagreements; corrections; incorrect corrections; abstention rate; answer-availability rate;
provenance completeness). F0 comparator (precision, recall, confidently-wrong detected/missed, rescue
rate, incorrect-fallback rate — **no recalibration**). Table usage (reads/query; writes/session; totals;
bytes; peak size; cleanup; residual rows). Integrity (cross-session/tenant leakage; stale/expired/deleted
returns; incorrect-version; missing provenance; malformed record; unavailable/read-fail/write-fail;
concurrent). Model invariance (no parameter/gradient change; zero eval optimizer steps; state hashes
unchanged; M0 byte-identical to the frozen baseline).

## Hard success gates (frozen; all deterministic)
1 accuracy within 0.1 pp of T0 · 2 incorrect verified = 0 · 3 incorrect corrections = 0 · 4 100%
disagreements detected · 5 every valid-record disagreement corrected · 6 provenance 100% · 7 cross-session
leakage 0 · 8 cross-tenant leakage 0 · 9 stale returns 0 · 10 expired returns 0 · 11 deleted returns 0 ·
12 incorrect-version returns 0 · 13 table-unavailable abstains · 14 injected read/write failures fail
closed · 15 no model-state change (params unchanged + zero eval optimizer steps) · 16 deterministic
replay succeeds · 17 explicit cleanup leaves zero live session records · **extra** exactly one table read
per V100 query.

## Operational measurements (characterization only)
p95/p99 end-to-end latency; verification overhead vs M0 and vs T0; storage/session; cleanup latency;
write latency; table-read latency. **No deployment ceiling is approved this phase**, so
`ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED` is **never** emitted.

## Verdict logic (mechanical)
All hard gates pass → **`ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED`**. Else:
correctness/reliability fail → `ALWAYS_VERIFY_RELIABILITY_GATE_FAILED`; integrity fail →
`EXTERNAL_VERIFICATION_INTEGRITY_FAILED`; protocol fail (model change / replay / one-read) →
`EXTERNAL_VERIFICATION_PROTOCOL_VIOLATED`; torch/reproduction unavailable →
`EXTERNAL_VERIFICATION_RESOURCE_BLOCKED`; otherwise `EXTERNAL_VERIFICATION_RESULTS_INCONCLUSIVE`. Always
also emit `KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`, `BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`KDA_VALIDATION_BLOCKED`.

## Interpretation boundaries
Supports only: "the external ephemeral table can verify or correct frozen neural retrievals with
deterministic provenance when the relevant record has been written, remains valid, and the reference
table is available." Does **not** support: routing solved; neural retrieval independently reliable;
always-verify avoids a table read; V100 faster than T0; V100 production-ready; SQLite reference ==
enterprise deployment latency; external memory improving neural learning; KDA may begin.

## Discipline
Implementation validated on synthetic non-reserved fixtures + a fresh untrained model (seed 999). **No
rule/threshold tuned on seeds 28–32.** Implementation file hashes are frozen in `preregistration.json`.
Driver is resumable (per-seed progress) and self-healing (`run_v100_until_done.sh`).

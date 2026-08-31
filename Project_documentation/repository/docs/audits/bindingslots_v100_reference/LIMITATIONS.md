# V100 reference-backend characterization — limitations

1. **Reliability characterization, not routing repair.** V100 verifying/correcting neural retrievals
   says nothing about whether BindingSlots neural routing works. Routing **remains unresolved**; the
   frozen conclusions are preserved.

2. **100% coverage only.** Every relevant fact was written to the table, so V100 is
   reliability-equivalent to T0 by construction. Partial-coverage behaviour (V75/V50), missing-record
   availability trade-offs, and the unverified-neural-return policy were **not** evaluated (out of
   scope). Nothing here characterises degraded coverage.

3. **Not a latency advantage.** V100 reads the table on **every** query and adds neural-inference cost;
   its end-to-end path (~15.9 ms p50) is ~680× the table-only path (~0.023 ms). Always-verify is a
   correctness/provenance posture, not a performance one.

4. **Operational cost unresolved.** No deployment-specific latency/storage/cleanup/write-failure ceiling
   was approved, so `ALWAYS_VERIFY_OPERATIONALLY_QUALIFIED` is deliberately **not** emitted. The latency
   numbers are characterization only and are specific to a single-process in-memory SQLite reference
   backend on this CPU — they are **not** representative of any networked or production deployment.

5. **Reference backend only.** SQLite reference, no PostgreSQL/Redis/cloud/production DB, no network
   service, no customer data. This is a reference-backend characterization, not
   production-infrastructure validation.

6. **Confidence ≠ correctness (re-confirmed).** The F0 comparator again missed 95 confidently-wrong
   reads (recall 0.80). A pure confidence trigger is not a sufficient failure detector; always-verify
   sidesteps this only by reading the table every time.

7. **Key-consistency signal unavailable.** No legitimate, non-oracle, non-circular, table-avoiding
   identity signal exists for content-addressed slots (`KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE`); K1 was
   not run and no slot→entity sidecar was manufactured.

8. **KDA remains blocked.** Nothing in this phase bears on KDA readiness; `KDA_VALIDATION_BLOCKED` is
   preserved.

9. **Determinism scope.** Reliability/integrity artifacts are deterministic and hash-verified; timing
   artifacts are wall-clock and non-deterministic and are excluded from the mechanical verdict.

10. **Not the neural-memory research track.** Whether a bounded neural memory can perform semantic
    identity-addressed retrieval *without* an external table is a separate, unstarted capability
    question and is not addressed here.

# Risk Register

Priority **P0** (resolve before implementation) · **P1** (resolve during) · **P2** (monitor).
Class: `DESIGN_BLOCKER` · `IMPLEMENTATION_PREREQUISITE` · `PILOT_RISK` · `PRODUCTION_RISK` ·
`FUTURE_ENHANCEMENT`.

The audit's three MIGRATION_BLOCKERs (R1 authority ambiguity, R2 no stable contract, R3 no single core)
are **resolved by this design** and are recorded below as `RESOLVED`.

| # | Pri | Risk | Class | Status / mitigation |
|---|---|---|---|---|
| A1 | P0 | Authority ambiguity (authorize vs clear) | DESIGN_BLOCKER | **RESOLVED** — clear-only ([`AUTHORITY_BOUNDARY.md`](AUTHORITY_BOUNDARY.md)); grant-minting not reused |
| A2 | P0 | No stable request/result contract | DESIGN_BLOCKER | **RESOLVED** — one `Clearance*` family ([`REQUEST_CONTRACT.md`](REQUEST_CONTRACT.md), [`RESULT_AND_RECEIPT_CONTRACT.md`](RESULT_AND_RECEIPT_CONTRACT.md)) |
| A3 | P0 | No single product core | DESIGN_BLOCKER | **RESOLVED** — neutral core + profiles; GitHub first ([`PACKAGE_BOUNDARY.md`](PACKAGE_BOUNDARY.md), [`GITHUB_MERGE_PROFILE.md`](GITHUB_MERGE_PROFILE.md)) |
| A4 | P1 | Result-state ambiguity | IMPLEMENTATION_PREREQUISITE | **RESOLVED** — four statuses; finer conditions are reason codes ([`STATUS_AND_REASON_SEMANTICS.md`](STATUS_AND_REASON_SEMANTICS.md)) |
| A5 | P1 | ActionGate overlap | IMPLEMENTATION_PREREQUISITE | **RESOLVED** — minimal projection; denials never clearable ([`ACTIONGATE_INTEGRATION.md`](ACTIONGATE_INTEGRATION.md)) |
| A6 | P1 | Decision Authority overlap | IMPLEMENTATION_PREREQUISITE | **RESOLVED** — references by id/hash; no SoD re-run, no import ([`DECISION_AND_CER_INTEGRATION.md`](DECISION_AND_CER_INTEGRATION.md)) |
| A7 | **P1** | **Signal trust & provenance mechanism** | IMPLEMENTATION_PREREQUISITE | **OPEN** — how `integrity_digest`/`provenance_ref` are produced/verified per source ([`THREAT_MODEL.md`](THREAT_MODEL.md)) |
| A8 | P1 | Stale-signal TOCTOU | PRODUCTION_RISK | mitigated — immediate-before-execution eval + `valid_until` + fail-closed ([`TIME_AND_FRESHNESS.md`](TIME_AND_FRESHNESS.md)) |
| A9 | **P1** | **ClearanceReceipt persistence owner unclear** | IMPLEMENTATION_PREREQUISITE | **OPEN** — shared audit service vs Workflow Service ([`PERSISTENCE_BOUNDARY.md`](PERSISTENCE_BOUNDARY.md)) |
| A10 | **P0** | **One-time-use race / ledger owner** | IMPLEMENTATION_PREREQUISITE | **OPEN (execution-layer)** — confirm ledger + atomic reservation contract ([`ONE_TIME_USE_AND_REPLAY.md`](ONE_TIME_USE_AND_REPLAY.md)) |
| A11 | P1 | Execution-ledger absence today | IMPLEMENTATION_PREREQUISITE | partial — DA execution repos exist; Phase G integrates |
| A12 | P1 | Policy conflict handling | PRODUCTION_RISK | mitigated — `CONSTRAINT_CONFLICT`/`CLEARANCE_POLICY_CONFLICT` → ESCALATE, fail closed |
| A13 | P1 | Tenant mismatch | PRODUCTION_RISK | mitigated — `TENANT_MISMATCH` → BLOCK (SI-5) |
| A14 | P1 | Profile overreach | PRODUCTION_RISK | mitigated — narrowing-only, constrained extension interface ([`PROFILE_EXTENSIBILITY.md`](PROFILE_EXTENSIBILITY.md)) |
| A15 | P1 | Fingerprint instability | PRODUCTION_RISK | mitigated — canonical serialization + algorithm versioning ([`DETERMINISM_AND_FINGERPRINTS.md`](DETERMINISM_AND_FINGERPRINTS.md)) |
| A16 | P1 | Clock semantics | PRODUCTION_RISK | mitigated — caller-supplied time; strict expiry; skew ≠ expiry |
| A17 | **P1** | **Merge-queue identity** | IMPLEMENTATION_PREREQUISITE | scoped — Phase I; group-artifact clearance defined ([`GITHUB_MERGE_PROFILE.md`](GITHUB_MERGE_PROFILE.md)) |
| A18 | **P1** | **Rebase instability** | IMPLEMENTATION_PREREQUISITE | scoped — rebase DEFERRED in MVP (`UnsupportedProfileError`) |
| A19 | P2 | Console migration | FUTURE_ENHANCEMENT | later consumer, behavior-equivalence gated ([`EXISTING_IMPLEMENTATION_DISPOSITION.md`](EXISTING_IMPLEMENTATION_DISPOSITION.md)) |
| A20 | P2 | Accidental robotics coupling | FUTURE_ENHANCEMENT | forbidden — no import/alias/identity; dependency rule enforces |
| A21 | P2 | New ProviderKind proliferation | FUTURE_ENHANCEMENT | avoided — directly-invoked; no new kind ([`GPF_RELATIONSHIP.md`](GPF_RELATIONSHIP.md)) |
| A22 | P2 | Overstatement of production maturity | PRODUCTION_RISK | mitigated — design/shadow discipline; no "validated/production" claims |

## Blocker summary

- **DESIGN_BLOCKERs: none remain** (A1–A3 resolved). Authority and trust semantics are settled.
- **Open P0/P1 implementation-prerequisites:** A7 (signal provenance), A9 (receipt owner), A10
  (one-time-use ledger/race), plus the scoped A17/A18 (merge-queue/rebase). These do not block Phases
  A–C; they gate Phases E/G and enforced merge.

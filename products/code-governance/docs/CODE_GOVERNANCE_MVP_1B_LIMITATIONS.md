# MVP 1B — Explicit Limitations

- **ActionGate authorization is required before Action Clearance evaluation.**
- **Action Clearance does not authorize execution. CLEAR is not execution.**
- **Human intervention is not equivalent to every non-CLEAR result.** HOLD usually
  means wait or refresh; BLOCK usually means change or reauthorize; only ESCALATE (and
  policy-configured exception/critical routes) require a human.
- **The existing DecisionRecord remains the binding governance decision.** The
  `HumanInterventionAssessment` is advisory/routing metadata, never a `DecisionRecord`.
- **Operational signals are supplied snapshots, not live integrations.** No identity /
  incident / change-management / GitHub / CI / cloud / database / Kubernetes / HR client.
- **Persistence is shadow/reference only** — in-memory, tenant-isolated, immutable.
  Not enforcement-durable, not crash-safe, not multi-process authoritative, not a
  one-time-use ledger.
- **No consumption ledger exists.** Consumption status is a supplied advisory signal;
  no reservation and no `reserve_once`.
- **Execution remains disabled** for every clearance status (`execution_status() ==
  "DISABLED"`; no `execute`/`merge`/`dispatch`/`reserve_once`).
- No GitHub write path, no merge credentials, no execution provider, no production
  database, no enforcement-grade `ClearanceReceipt` persistence, no new `ProviderKind`.
- The canonical Action Clearance package is **not modified**.

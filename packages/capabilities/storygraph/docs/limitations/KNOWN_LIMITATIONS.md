# StoryGraph — Known Limitations & Scope

StoryGraph is an **advisory** sequence-risk analyzer. This document states, in one
place, the boundaries a consumer must understand before relying on it.

## Authority boundary

- **Advisory / evidentiary only.** StoryGraph emits `OBSERVE` / `ESCALATE` /
  `UNAVAILABLE` findings and advisory evidence records classed `ADVISORY` with an
  `OBSERVE`/`ESCALATE` effect ceiling.
- It **never** emits `ALLOW` / `DENY` / `AUTHORIZE` / `BLOCK` / `EXECUTE` /
  `CLEAR`, and holds **no** action-authorization, binding-decision,
  operational-clearance, or execution authority. A downstream ActionGate or
  workflow policy owns any binding consequence.

## Scope

- **Synthetic-only validation.** No enterprise data is bundled. The
  historical-replay path ships templates and a synthetic reference fixture only;
  reported readiness is against synthetic gates. See `../replay/` and
  `../evaluation/`.
- **One implemented harmful graph/domain** (account-takeover transfer), plus a
  digital-exfiltration story. The physical-firearm ontology is retained solely as
  a synthetic illustration.
- **Known-pattern-only.** StoryGraph matches *encoded* capability patterns
  (versioned recipes + entity linkage). It is **not** an intent-understanding
  system, **not** a learned anomaly detector, and infers **no** malicious intent.
- **Deterministic.** No wall-clock, randomness, network, or LLM in the
  authoritative path — replayable from an event log.
- **No direct enforcement authority.** Advisory findings only.

## Not claimed

- No production accuracy claim; no benchmark headline numbers are asserted by the
  capability itself (evaluation plans/reports under `../evaluation/` state their
  own synthetic scope and verdicts).
- No multi-tenant, durable, or tamper-evident guarantees beyond the deterministic
  evidence chain the package itself computes.

## Related

- Authority evidence: `../evaluation/STORY_GRAPH_EVIDENCE_LEDGER.md`
- Validation scope: `../validation/`
- Advisory contract in code: `ugence_storygraph.to_advisory_evidence`,
  `ugence_storygraph.signals` (`OBSERVE`/`ESCALATE`/`UNAVAILABLE`).

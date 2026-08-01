# Phase 3 — Historical-Replay Readiness: Final Evaluation Report

> **Historical record — preserved verbatim.** This report predates the
> canonical-package migration. Its claims, counts, and verdicts are **not**
> rewritten. Commands and module paths below reflect the historical
> `composite_threat_detector` layout; the current equivalent is
> `python3 -m ugence_storygraph.cli readiness` (package
> `packages/capabilities/storygraph`). See `../../MIGRATION.md`.

> This phase does not add another detection algorithm. It tests whether the
> existing deterministic sequence-risk analyzer remains safe, reconstructable,
> bounded, and operationally useful under realistic benign prevalence, provider
> failures, ordering ambiguity, restart, and sustained event volume. Passing
> these gates establishes readiness for a narrowly scoped historical replay — not
> enterprise accuracy or enforcement readiness.

**No live enforcement was enabled.** All results carry evidence-discipline labels
(§17). Reproduce with `python3 -m composite_threat_detector.cli readiness`.

## Authority boundary (unchanged)

Analyzer emits only `OBSERVE` / `ESCALATE` / `UNAVAILABLE`. The authoritative
policy computes *hypothetical shadow* consequences (`WOULD_HOLD_FOR_REVIEW` /
`WOULD_BLOCK` via `PolicyBinding(shadow=True)`; `enforced=False`). No evaluation
run changed an actual execution decision.

## Readiness gates (H1–H8)

| Gate | Result | Evidence label |
|------|--------|----------------|
| H1 freeze integrity | **PASS** | Measured — unit/integration test |
| H2 deterministic replay | **PASS** | Measured — synthetic behavioral corpus |
| H3 durable reconstruction | **PASS** | Measured — restart/recovery test |
| H4 bounded-state safety | **PASS** | Measured — synthetic operational load |
| H5 provider safety | **PASS** | Measured — unit/integration test |
| H6 ordering safety | **PASS** | Measured — synthetic behavioral corpus |
| H7 operational performance | **PASS** | Measured — synthetic operational load |
| H8 realistic benign burden | **PASS** | Measured — synthetic + Modeled — operator workload |

## Performance environment

`Measured — synthetic operational load`, single development host:

- Python 3.11.15, Linux-6.18.5 x86_64 (single dev host — **NOT** a production
  capacity measurement; no capacity number is extrapolated).

Medium operational run (`enterprise_like`, 200 scenarios, seed 7):

- Throughput ≈ **1,028 events/s**; runtime/event median **0.87 ms**, p95 **1.52 ms**,
  p99 **1.86 ms**; peak traced memory **0.26 MB**; peak assemblies/tenant **1**.

(Values vary by host and are illustrative, not a benchmark of enterprise scale.)

## Alert volume & review burden

`enterprise_like` (200 scenarios, seed 7):

- Measured: alerts/1,000 events ≈ **22.4**; **0** false escalations on
  clean-benign look-alikes; unknown-threat detection **0** (not encoded).
- Modeled — operator workload (50,000 events/tenant-day assumption): ≈ **1,120**
  alerts/tenant-day. **Modeled projection, not a measured deployment rate.**

## Provider-failure results (H5)

16 failure modes verified fail-safe (never neutralize): unavailable, revoked,
superseded, stale, expired, invalid signature, version mismatch, unverifiable,
modified-after-activity, delayed ingestion, wrong tenant/actor/scope, missing
authority; conflicting/duplicate evidence → `AMBIGUOUS`.

## Ordering results (H6)

`ORDERED / PARTIALLY_ORDERED / AMBIGUOUS_ORDER / CONFLICTING_ORDER` resolved
deterministically from multi-source signals. Ambiguous/conflicting order does not
satisfy strict-ordering recipes (no convenient threat sequence is chosen).

## Restart/recovery results (H3)

Recovery model: **recomputed state from durable event replay**. A durable SQLite
append-only, hash-linked (tamper-evident) audit log retains one `INGEST` record
per event; on restart a fresh analyzer replays them and reproduces active state,
dedup, recipe-version bindings, and byte-identical finding digests. Raw evidence
and provenance survive decay, reset, closure, and restart.

## State-pressure results (H4)

Per-tenant / per-actor quotas and candidate-linkage caps are fail-visible
(`UNAVAILABLE`, audited). A noisy low-severity tenant cannot exhaust another
tenant's allocation. Optional priority-retention eviction (`evict_on_pressure`)
reclaims active state with an audited `EVICTION`; evicted assemblies remain
reconstructable via durable replay (no silent evidence loss).

## Recipe-version behavior

Versions bind at assembly open; history reconstructs under the bound version,
new actions evaluate under the current version, divergences are recorded, earlier
findings are never rewritten.

## Trusted-context behavior

Self-declared purpose never neutralizes. Only a verified, scope-matched,
in-window, authored, correctly-versioned, non-revoked authorization from a trusted
provider neutralizes; scope mismatches are reported field by field.

## Metrics still `NOT RUN` / `REQUIRES ENTERPRISE DATA`

- Escalation lead time before completion — REQUIRES ENTERPRISE DATA
- Alerts/tenant-day, peak state/tenant (measured) — enterprise deployment rate is
  REQUIRES ENTERPRISE DATA
- Entity-linkage error rate — NOT RUN (needs labeled linkage ground truth)
- Runtime/event as a production figure — NOT RUN (dev host only)
- Historical replay on real sanitized data — REQUIRES ENTERPRISE DATA
- Unknown-threat coverage — explicitly **0** (no unknown-threat mechanism added;
  out of scope)

## Known limitations

Detection binds only to *encoded* recipes (unknown composites are misses by
design). Synthetic accuracy is not enterprise accuracy. Durable-store tests are
interface-level, not production-storage validation. Fixture reviewers are not
human validation. Only two reference replay adapters exist; other vendors are
`CONTRACT ONLY`.

## Current evidence-based verdict

**`CONTINUE — historical replay ready`** (synthetic gates only). No
enterprise-accuracy, intent, novelty, or production-readiness claim is made.

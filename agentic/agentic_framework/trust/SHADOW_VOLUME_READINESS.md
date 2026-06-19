# Shadow-Volume Readiness Review

**Question:** is the trust architecture ready to run in **SHADOW** over broader traffic and
collect **durable** mismatch data for analysis?

**Verdict:** **Capture is ready; analysis is not.** Every trust decision is durably
persisted, tamper-evident, exportable, and groupable by risk level and tool. What is missing
is (a) a report that aggregates the persisted `trust_shadow` data, and (b) two analysis
*dimensions* — raw entropy and the confidence-risk gap — which are neither distinct drivers
nor durably persisted. Neither gap blocks **starting** a shadow run; both block **using** it.

Scope honored: **no flip, no policy change, no new observables, no ML.** All findings are
from the current code on this branch.

---

## 1. Is every trust decision persisted?

**Yes, conditionally.** The trust decision is computed in `_audit()` via `shadow_compare()`
and embedded into the canonical, hash-chained event as `request_snapshot["trust_shadow"]`
(`{decision, legacy_decision, mismatch, mismatch_class, drivers, reason}`).

- **Coverage:** all 16 `return result` paths in `call_tool()` call `_audit()` — including the
  earliest (forbidden-capability) return at `mcp_gateway.py:1257`, which builds a minimal
  `gate_decision` first. So no decision path escapes auditing.
- **Conditions (deployment, not code):**
  1. `trust_mode != LEGACY` (SHADOW or TRUST_CORE) — else the trust core is not computed.
  2. `_audit_store is not None` — the in-memory `audit_log` always gets it, but **durable**
     persistence requires the gateway to be constructed with a `GovernanceAuditStore`.
     `create_mock_mcp_gateway()` does **not** wire one; a shadow-volume deployment must.
- **Failure mode:** `shadow_compare` is wrapped in try/except (non-fatal); on error the
  `trust_*` fields stay `None` and a warning is logged. Persistence itself is fail-closed
  (raises `GovernanceAuditError`). Net: a persisted `mcp_tool_call` event with no
  `trust_shadow` key is observable and rare.

**Ready.**

---

## 2. Are drivers specific enough to analyze?

| Dimension | Distinct driver today? | Notes |
|---|---|---|
| raw entropy | **No** | Not a trust observation. It feeds the confidence-risk gap upstream; never surfaces as a driver. |
| confidence-risk gap | **No** | Folded into `execution_permission` via `_gap_requires_human`. A gap-driven CONFIRM is indistinguishable from a plain `can_execute=False` in `drivers` (only the free-text `reason` hints). |
| JEPA | **Yes** | `jepa` |
| domain policy | **Yes** | `domain` |
| shadow deterministic | **Yes** | `shadow` |
| shadow_jepa_derived | **Yes** | added in the reporting-only patch |
| shadow_semantic_derived | **Yes** | added in the reporting-only patch |

Also present and specific: `confidence_floor`, `approval_required`, `execution_permission`.

**Partially ready.** The five policy-authority dimensions the migration cares about
(JEPA / domain / shadow split) are fully attributable. **raw entropy and the
confidence-risk gap are not** — and adding them as drivers would be a *new observable*
(out of scope). Their already-computed provenance fields (`raw_entropy_*`,
`confidence_risk_gap_*`) live on `AuditEntry` but are **dropped** by `event_from_mcp_audit`
(no params for them) — so they are not even available for *correlation* in the durable store.
Closing this is **persistence-only** (embed existing fields in `request_snapshot`), not a
new observable — see §5 item 2.

---

## 3. Can persisted audit data be queried / exported?

**Yes.** `GovernanceAuditStore` exposes: `list_recent`, `list_by_event_type`,
`list_by_decision`, `list_by_session`, `count`, **`export_jsonl`**, and `verify_chain`.

- `tool_name` and `risk_level` are **top-level columns** → directly selectable/groupable
  (not separately indexed, but fine to aggregate over an export).
- `trust_shadow` lives inside the `request_snapshot` **JSON text column** → not a SQL
  filter target as-is; analysis reads it via `export_jsonl` (each line includes the parsed
  `request_snapshot`) or `list_*` + Python, or SQLite `json_extract`.
- `decision_outcome`, `event_type`, `session_id`, `timestamp`, `actor_id` are **indexed**
  (the `decision_outcome` here is the *legacy* outcome the gateway acted on).

**Ready** for export-based analysis; no per-mismatch SQL index exists (acceptable at the
expected volume — aggregate in Python over an export).

---

## 4. What report is missing?

There is **no script that reads the durable store and summarizes the `trust_shadow`
mismatches.** `parity_harness.py` aggregates only a fixed *synthetic* corpus;
`policy_replay.py` replays *governance_decision* events through `GovernanceService` (a
different question). Neither reads persisted `mcp_tool_call` → `trust_shadow`.

Missing report must summarize, over `event_type == "mcp_tool_call"` records that carry
`trust_shadow`:

- total decisions; **match rate**
- counts by `mismatch_class`: `match` / `intended` / `unintended` / `unsafe_relaxation`
- **mismatch by driver** (`trust_shadow.drivers`, incl. the new shadow split)
- **mismatch by risk level** (`risk_level` column)
- **mismatch by tool / action type** (`tool_name` column)
- a hard flag: any `unsafe_relaxation > 0` (the flip blocker)

---

## 5. Smallest next implementation to make analysis usable

**Primary (smallest, unblocks §4) — a read-only report script.** No behavior change, no new
observable, no policy change, no flip.

- Location: `experiments/trust_signal/shadow_report.py` (sibling of `parity_harness.py`),
  callable as a module and importable as a function.
- Signature (sketch):
  `summarize_shadow(store_or_jsonl) -> dict` + a `main()` that prints a markdown block in the
  same shape as `parity_harness` (Total · match · intended · unintended · unsafe_relaxation),
  plus three breakdown tables (by driver / by risk_level / by tool).
- Input: a `GovernanceAuditStore` (use `list_recent`/`export_jsonl`) **or** a JSONL export
  path — so it runs against a live DB or a copied export. Read-only: opens nothing for write.
- Logic: filter `event_type=="mcp_tool_call"`; skip records without `trust_shadow`; bucket by
  `mismatch_class`; cross-tab `mismatch` against `drivers`, `risk_level`, `tool_name`.
- Test: build an in-memory `GovernanceAuditStore(":memory:")`, append a handful of
  `event_from_mcp_audit(...)` events with crafted `trust_*` (match / intended / unintended /
  unsafe_relaxation), assert the aggregate counts and that `unsafe_relaxation` is surfaced.

**Secondary (optional, persistence-only) — embed gap/entropy provenance.** Only if the
raw-entropy / confidence-risk-gap dimensions are required for the readiness decision: extend
`event_from_mcp_audit` to also embed the already-computed `confidence_risk_gap_*` and
`raw_entropy_*` fields into `request_snapshot` (exactly the pattern used for `trust_shadow`).
This adds **no observable** and changes **no behavior** — it only stops dropping fields that
already exist on `AuditEntry`, so the report can correlate `execution_permission` CONFIRMs
with the gap/entropy that caused them.

**Recommendation:** ship item 1 first (it makes the already-captured data usable and is the
true blocker for "usable shadow-volume analysis"); treat item 2 as a fast follow only if the
entropy/gap dimensions are needed. Then enable SHADOW with a configured `GovernanceAuditStore`
on broader traffic and read the report; the flip stays gated on `unintended == 0` and
`unsafe_relaxation == 0` over that real volume.

**Readiness summary:** capture = **ready**; query/export = **ready**; policy-authority driver
attribution = **ready**; entropy/gap analysis dimensions = **not ready** (persistence-only fix
available); aggregation report = **missing (smallest next step)**.

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
| raw entropy | **As a slice (not a driver)** | Not a trust observation (would be a new observable — out of scope). Now persisted as **provenance** under `request_snapshot["entropy_gap"]` and sliceable in the report (availability + high/low bucket). |
| confidence-risk gap | **As a slice (not a driver)** | Still folded into `execution_permission` for the *decision*; but its escalate flag / reason / value are now persisted under `entropy_gap` and sliceable. |
| JEPA | **Yes** | `jepa` |
| domain policy | **Yes** | `domain` |
| shadow deterministic | **Yes** | `shadow` |
| shadow_jepa_derived | **Yes** | added in the reporting-only patch |
| shadow_semantic_derived | **Yes** | added in the reporting-only patch |

Also present and specific: `confidence_floor`, `approval_required`, `execution_permission`.

**Ready (updated).** The five policy-authority dimensions (JEPA / domain / shadow split) are
fully attributable as drivers. Raw entropy and the confidence-risk gap are intentionally
**not** drivers (that would be a new observable), but their already-computed provenance
fields are now **persisted durably** under `request_snapshot["entropy_gap"]`
(`raw_entropy[_available/_source]`, `confidence_risk_gap_{escalate,value,reason,
verbalized_safety}`) and are sliceable in the report — so mismatches can be correlated with
model-uncertainty without changing any decision.

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

> **Implemented:** `experiments/trust_signal/shadow_report.py` (read-only) now produces all
> of the above. Run it against a live store DB or a JSONL export:
>
> ```bash
> # against the durable store DB:
> PYTHONPATH="$(pwd)" python3 experiments/trust_signal/shadow_report.py --store governance_audit.db
> # against a JSONL export (store.export_jsonl(path)):
> PYTHONPATH="$(pwd)" python3 experiments/trust_signal/shadow_report.py --jsonl audit_export.jsonl
> # CI-gate also on mapping gaps:
> PYTHONPATH="$(pwd)" python3 experiments/trust_signal/shadow_report.py --store governance_audit.db --fail-on-unintended
> # uncertainty breakdown + slicing by model-uncertainty provenance:
> PYTHONPATH="$(pwd)" python3 experiments/trust_signal/shadow_report.py --store governance_audit.db --entropy
> PYTHONPATH="$(pwd)" python3 experiments/trust_signal/shadow_report.py --jsonl audit_export.jsonl --entropy --only-gap-escalated
> ```
>
> It prints total/with-trust counts, legacy + trust decision counts, match rate,
> `mismatch_class` counts, mismatch by driver / risk level / tool, the top mismatch examples,
> and a **READY FOR REVIEW** vs **NOT READY TO FLIP** verdict. It **exits non-zero** when
> `unsafe_relaxation > 0` (always), when `unintended > 0` and `--fail-on-unintended`, or when
> no `trust_shadow` data is present — so it can gate a pipeline.

---

## 5. Smallest next implementation to make analysis usable

**Primary (smallest, unblocks §4) — a read-only report script. ✅ DONE.** No behavior change,
no new observable, no policy change, no flip.

- Location: `experiments/trust_signal/shadow_report.py` (sibling of `parity_harness.py`),
  callable as a module (`python3 -m` / direct) and importable (`build_report`, `verdict`,
  `render`, `load_records`, `filter_records`, `extract_trust_shadow`, `extract_entropy_gap`).
- Signature (as built):
  `load_records(store_path=… | jsonl_path=…) -> [records]`; `build_report(records) ->
  ShadowReport`; `verdict(rep, fail_on_unintended=…) -> {ready, exit_code, label, detail}`;
  `render(rep) -> markdown` (Total · match · intended · unintended · unsafe_relaxation +
  breakdown tables by driver / risk_level / tool + top examples).
- Input: a `GovernanceAuditStore` (use `list_recent`/`export_jsonl`) **or** a JSONL export
  path — so it runs against a live DB or a copied export. Read-only: opens nothing for write.
- Logic: filter `event_type=="mcp_tool_call"`; skip records without `trust_shadow`; bucket by
  `mismatch_class`; cross-tab `mismatch` against `drivers`, `risk_level`, `tool_name`.
- Test: build an in-memory `GovernanceAuditStore(":memory:")`, append a handful of
  `event_from_mcp_audit(...)` events with crafted `trust_*` (match / intended / unintended /
  unsafe_relaxation), assert the aggregate counts and that `unsafe_relaxation` is surfaced.

**Secondary (persistence-only) — embed gap/entropy provenance. ✅ DONE.**
`event_from_mcp_audit` now also embeds the already-computed `raw_entropy[_available/_source]`
and `confidence_risk_gap_{escalate,value,reason,verbalized_safety}` fields under
`request_snapshot["entropy_gap"]` (same pattern as `trust_shadow`); the gateway `_audit`
forwards them from the `AuditEntry`. This adds **no observable** and changes **no behavior**
— it only stops dropping fields that already existed on `AuditEntry`. The report consumes
them via `--entropy` (breakdown tables) and the `--only-gap-escalated` /
`--only-entropy-available` slice filters, so mismatches can be correlated with
model-uncertainty. Behavior invariance is proven by the unchanged parity harness and the
gateway test comparing a store-backed run to a store-less run.

**Recommendation:** both items are now shipped. Enable SHADOW with a configured
`GovernanceAuditStore` on broader traffic and read the report (add `--entropy` for the
uncertainty breakdown); the flip stays gated on `unintended == 0` and `unsafe_relaxation == 0`
over that real volume.

**Readiness summary:** capture = **ready**; query/export = **ready**; policy-authority driver
attribution = **ready**; entropy/gap analysis dimensions = **ready** (persisted as provenance,
sliceable in the report); aggregation report = **shipped**.

---

## 7. Broadened offline parity stress (pre-flip)

`parity_harness.py` was broadened to **25 in-scope scenarios** across every mapped authority
(confidence floor, confidence-risk gap, raw-entropy high/low, JEPA **DEFER** and **DENY**,
domain allow/confirm/block, shadow allow/block, approval incl. destructive) plus a
**hard-pre-gate** cohort (forbidden capability / permission overclaim) and an optional
**external** cohort (committed AgentDojo/InjecAgent minisets, mapped structurally — no
fabricated model signals, no accuracy metric).

Result (REVIEWED policy):

- **In-scope: CLEAN** — 22 match + **3 intended** JEPA demotions (`jepa_defer_block`,
  `jepa_deny_ro`, `jepa_deny_write`), **0 unintended, 0 unsafe_relaxation**. PARITY policy is
  25/25 match. Default `main()` exits 0.
- **External: CLEAN** (12/12, 0/0) — but only **after** a parity fix the broadened corpus
  surfaced: `_shadow_verdict` previously mapped shadow's *intermediate* containment modes
  (observe_only / read_only / draft_only / sandbox_only / memory_write_denied) to SAFE while
  legacy maps them to DEFER (confirm) — a silent CONFIRM→ALLOW. Now mapped to UNSURE
  (confirm), mirroring `shadow_containment_to_governance`. Shadow-only/non-authoritative →
  **no runtime behaviour change**; strictly safer in the (off-by-default) authoritative path.
- **Hard pre-gate: SCOPE BOUNDARY** — forbidden-capability / overclaim is a hard veto ABOVE
  the trust layer, **not** modelled by the trust observables and **preserved across any flip**.
  The trust core's isolated opinion relaxes it (3 unsafe_relaxation), so it is reported,
  scoped out of the default flip gate, and fails under `--strict-pregate`. Mapping it as a
  HARD_VETO observable is required before the trust core could be a *standalone* replacement
  (future; out of current scope — no new observables).

**Is it ready for real SHADOW volume?** **Yes for observation** (shadow never acts; safe to
run at volume and collect data). **The flip remains blocked** until (a) real-volume in-scope
metrics stay `unintended == 0 / unsafe_relaxation == 0`, and (b) the forbidden-capability hard
veto is either mapped into the trust observables or explicitly asserted as a retained pre-gate.

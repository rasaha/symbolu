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

## 7. Broadened offline parity stress + parity-completion (pre-flip)

`parity_harness.py` was broadened to **28 in-scope scenarios** across every mapped authority
(forbidden-capability HARD_VETO, confidence floor, confidence-risk gap, raw-entropy high/low,
JEPA **DEFER** and **DENY**, domain allow/confirm/block, shadow allow/block, approval incl.
destructive) plus an optional **external** cohort (committed AgentDojo/InjecAgent minisets,
mapped structurally — no fabricated model signals, no accuracy metric).

Result (REVIEWED policy):

- **In-scope: CLEAN** — 25 match + **3 intended** JEPA demotions (`jepa_defer_block`,
  `jepa_deny_ro`, `jepa_deny_write`), **0 unintended, 0 unsafe_relaxation**. PARITY policy is
  28/28 match. Default `main()` exits 0; `--strict-pregate` (now a compat no-op) also exits 0.
- **External: CLEAN** (12/12, 0/0).

Two real parity gaps the broadened corpus found, both now closed (audit-mapping only, no
runtime behaviour change — the trust core is shadow/non-authoritative; both are strictly
safer/correct in the off-by-default authoritative path):

1. **Shadow intermediate containment** — `_shadow_verdict` mapped observe_only / read_only /
   draft_only / sandbox_only / memory_write_denied to SAFE while legacy maps them to DEFER
   (confirm). Now mapped to UNSURE, mirroring `shadow_containment_to_governance`.
2. **Forbidden-capability hard pre-gate** — the gateway's `_check_forbidden_capabilities`
   kill-switch (credential_access, privilege_escalation, data_exfiltration, …) is now mapped
   as a **PROVEN HARD_VETO** observation (`forbidden_capability`) in `build_parity_observations`,
   threaded from `SafeMCPGateway.forbidden_capabilities`. The trust core now reproduces the
   legacy BLOCK **terminally** — high confidence, raw entropy, and the confidence-risk gap
   cannot override it (BLOCK wins by weakest-link). The hard-pre-gate cohort is therefore now
   in-scope and clean (legacy BLOCK == trust BLOCK). Note: an unregistered/hallucinated tool
   is **not** a pre-gate block — it surfaces as an execution ERROR (nothing executes) and maps
   benignly to ALLOW==ALLOW; permission overclaim is the forbidden-capability path.

The synthetic `--export` → `shadow_report` over 56 generated events now reads **READY FOR
REVIEW** (0 unsafe_relaxation; the only mismatches are the 3 reviewed JEPA demotions).

**Is it ready for real SHADOW volume?** **Yes for observation** (shadow never acts; safe to
run at volume and collect data), and the trust core is now **parity-complete** over the mapped
authorities **and** the forbidden-capability hard pre-gate — 0 unintended / 0 unsafe_relaxation
across in-scope, external, and the synthetic export. **The flip itself is still NOT taken**: it
remains gated on the same property holding over **real** volume (not just the offline corpus),
and on the standing items in §6 (authority demotions reviewed). No `trust_core` flip performed.

---

## 8. Real SHADOW-volume validation run

`experiments/trust_signal/shadow_volume_validation.py` assembles the broadest committed
offline corpus, drives it through `SafeMCPGateway(trust_mode=SHADOW)` into a durable
`GovernanceAuditStore`, exports JSONL, and runs `shadow_report` for a flip-readiness verdict.
No flip, no policy demotion, no new observable — legacy decides and executes throughout.

```bash
PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_volume_validation
# options: --policy {reviewed|parity}  --db PATH  --jsonl PATH  --fail-on-unintended
#          --no-external  --no-signalgov  --max-examples N
```

Corpus (**105 scenarios**, all real fixtures, no fabricated model signals, no accuracy
metric): 28 mapped-authority + 12 AgentDojo/InjecAgent minis + 15 signal_gov handbuilt +
30 signal_gov pilot + 20 confident-unsafe twins.

Result under the **REVIEWED** flip candidate (hash chain valid):

| metric | value |
|---|---|
| total decisions / with trust_shadow | 105 / 105 |
| match rate | 97.1% (102/105) |
| **intended** | **3** (JEPA demotions: `jepa_ro`, `jepa_w`, `jepa_write`) |
| **unintended** | **0** |
| **unsafe_relaxation** | **0** |
| mismatch by driver | jepa ×3, execution_permission ×3 |
| mismatch by risk | write ×2, read_only ×1 |
| entropy slices | raw-entropy available 25 · gap escalate 4 (provenance only) |
| **verdict / exit** | **READY FOR REVIEW / 0** |

PARITY policy: 105/105 match (0 mismatch). The runner exits non-zero on any
`unsafe_relaxation` (and, with `--fail-on-unintended`, any `unintended`).

**Conclusion:** the offline real-shape SHADOW volume is **CLEAN** — every divergence is a
reviewed/intended JEPA demotion; zero unintended, zero unsafe relaxation, across all
authorities, the forbidden hard veto, external benchmarks, and enterprise/confident-unsafe
scenarios. This is the evidence a flip *could be considered* — but the flip is **NOT taken**:
it still requires the same `unintended == 0 / unsafe_relaxation == 0` to hold over **production
SHADOW traffic** (run this same script against the live store), plus sign-off on the reviewed
JEPA demotion (§6). No `trust_core` flip performed.

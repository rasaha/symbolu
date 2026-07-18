# ACP Shadow Evaluation (Phase 1)

How the shadow comparison runs, what it records, and how it guarantees zero
production impact. Code: `autonomous_control_plane/shadow.py`,
`autonomous_control_plane/adapters.py`,
`robotics_reliability_bench/acp_shadow/` (harness + faithful BCVF replicas +
corpus).

---

## 1. Topology (zero production edits)

```
corpus scenario (synthetic)
   │
   ├─► ACP adapter  ─► CanonicalWorldState + candidates + hard ConstraintResults
   │        │
   │        └─► LexicographicActionSelector ─► SelectionOutcome + DecisionTrace
   │
   └─► faithful BCVF replica (uses REAL formulas.bcvf) ─► bcvf_selected_id
                     │
         classify(adapted, acp_outcome, bcvf_selected_id) ─► ShadowRecord
```

- The **ACP core imports no production code and no BCVF** (stdlib only).
- The **BCVF replicas** live in the eval harness and reproduce each call site's
  exact selection (argmax / post-multipliers) using the real
  `formulas.bcvf.score_action_candidates` — READ-ONLY, no production object is
  constructed or mutated.
- No production module imports ACP; no ACP output actuates anything. Every record
  carries `shadow_only=true`.

> Adapter design note: importing ACP via the package path executes the parent
> `symbolu_robotics/__init__.py`, which eagerly imports numpy + the production
> BCVF re-export. That is a property of the **existing parent package**, not of
> ACP's own modules (which are stdlib-only, asserted by
> `test_acp_module_sources_are_stdlib_only`). It has no effect on determinism or
> on production behavior.

## 2. Adapters

Each adapter takes *primitive* call-site inputs (scalars/dicts extracted by the
harness), preserves original candidate ids, records provenance
(`"<site>:<id>"`), binds every candidate to the exact
`CanonicalWorldState.version`, sets unavailable physical fields to the inert
placeholder `0.0` and lists them in `unavailable_fields`, and never touches a
production object. See `adapt_deliberative` / `adapt_conflict` /
`adapt_task_allocation`.

## 3. Shadow record fields (per candidate set)

`call_site`, `world_state_identity`, `candidate_identities`,
`bcvf_selected_candidate`, `acp_outcome`, `acp_selected_candidate`,
`acp_rejected[(id, reason)]`, `dispositive_reasons`,
`bcvf_selected_inadmissible` (+ `bcvf_inadmissible_reason` /
`bcvf_inadmissible_kind` ∈ {REAL_VIOLATION, UNEVALUABLE}), `acp_no_safe_action`,
`both_selected_same`, `latency_us`, `missing_evidence`, `shadow_class`,
`shadow_only=true`.

## 4. Classification (deterministic)

A disagreement is **classified, never scored as an ACP win**. Categorical label
precedence: `BCVF_SELECTED_INADMISSIBLE` > refusal (`ACP_INSUFFICIENT_EVIDENCE`,
`ACP_NO_SAFE_ACTION`) > `AGREE_ADMISSIBLE` > `DIFFERENT_BOTH_ADMISSIBLE`.
Independent boolean fields drive the rate metrics so overlapping conditions
(e.g. BCVF picked inadmissible *and* ACP had no safe action) are each counted.
The important honesty split: `BCVF_SELECTED_INADMISSIBLE` is separated into
`REAL_VIOLATION` (BCVF chose something ACP proves violates a hard constraint) vs
`UNEVALUABLE` (ACP lacks data to judge BCVF's pick).

## 5. Authorization sub-check

Two scenarios exercise commit-time revalidation: after ACP authorizes its pick,
the harness mutates the world version (or the candidate identity) and calls
`ReferenceCommitRevalidator.revalidate` — which must raise
`StaleAuthorizationError` / `AuthorizationBindingError`. No grant is ever used to
actuate.

## 6. Guarantees the harness proves

- **Deterministic rerun identity** = 100% (decision content; wall-clock
  excluded), by running the whole corpus twice and comparing `content_dict()`.
- **Current-runtime behavior-change count = 0** — the harness makes no
  production call that mutates state; it replicates BCVF read-only.
- **Shadow exceptions contained** — a malformed adapter input raises a normal
  exception the harness classifies as `SHADOW_ERROR`; it can never alter the
  authoritative BCVF path.
- **No actuation** — every record is `shadow_only`; no `ControlAuthorization` is
  consumed by an actuator in Phase 1.

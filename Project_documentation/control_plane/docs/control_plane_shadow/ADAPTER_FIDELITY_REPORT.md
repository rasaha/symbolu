# Adapter Fidelity Report

*Phase 11. For each real adapter: source input → source output → canonical output →
reconstructed source-equivalent. Any invented field is a defect unless declared derived with a
transformation rule. Deterministic; no live calls. Raw results:
`control_plane_shadow/eval_results/adapter_fidelity_v1.json` (regenerate with
`python3 -m control_plane_shadow.fidelity`).*

## Results

| Adapter | N inputs | Disposition fidelity | Source preservation | Invented fields | Lost decision-relevant | Changed authority |
|---|---|---|---|---|---|---|
| ExecutionGate | 3 scenarios | **1.0** | 1.0 | 0 | 0 | 0 |
| TAP (E4) | 30 cases | **1.0** | 1.0 | 0 | 0 | 0 |
| ActionGate | 40 combos | **1.0** | 1.0 | 0 | 0 | 0 |

- **Disposition fidelity 1.0**: every canonical disposition equals the frozen mapping of the
  source term (`vocabulary.map_*`). No adapter changed a disposition, authority, reason, or
  policy interpretation relative to its source engine.
- **Source preservation 1.0**: every result carries the original engine output
  (`source_output`), so the source-equivalent is reconstructable.
- **0 invented fields**: every canonical key is either directly sourced or listed in the
  adapter's `derived_fields` with a transformation rule (ExecutionGate `eligibility_decision_id`;
  TAP record-level disposition derivation; ActionGate `hard_safety_block`).
- **0 lost decision-relevant fields**: fields dropped from the *disposition* (e.g. TAP's 8-axis
  confidence vector) are preserved in the payload/`source_output` and do not change the outcome.

## Per-adapter detail

### ExecutionGate — exact, lossless
1:1 state mapping (`EligibilityState` == canonical eligibility). Per-condition `ConditionResult`
detail is summarized into namespaced reason codes but the *decision* (state) is preserved
exactly. No authority change.

### TAP (E4) — faithful mapping, declared semantic gap
The `GovStatus → assertion_disposition` mapping is applied exactly (fidelity 1.0 against the
frozen `TAP_MAP`), and the raw `GovernanceRecord` summary + confidence band + conflict/gap counts
are preserved. The **information loss is the 8-axis confidence vector, conflict/gap detail, and
full provenance chain not being represented by the single disposition** — recorded in
`information_loss` on every result, and the **semantic gap** (authority-resolution used as an
assertion-permission proxy) is flagged on every result. Fidelity here means "the adapter
faithfully transmits what E4 decided," NOT "E4 is the right engine for assertion governance"
(that is the semantic-gap caveat, unchanged).

### ActionGate — faithful, low loss
All six outcomes map exactly (fidelity 1.0 against `ACTION_MAP`) across all 40 operation ×
approval × evidence combinations. `applied_constraints`, `dispositive_rules`, `action_hash`,
`policy_hash`, and `terminal` are preserved. The only derived field, `hard_safety_block`, is
computed from `terminal == DENIED` + `reversibility == IRREVERSIBLE` (declared rule). No
authority change: the signed policy remains the source of truth.

## Verdict

All three real adapters are **high-fidelity**: they preserve source semantics, invent nothing
undeclared, change no authority, and lose no decision-relevant field from the outcome. The single
substantive caveat is the **TAP semantic gap**, which is a property of using E4 as the assertion
boundary — not an adapter defect — and is disclosed on every TAP result.

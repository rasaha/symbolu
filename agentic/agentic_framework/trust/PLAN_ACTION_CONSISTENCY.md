# Plan-Action Consistency Observable (Phase 2 — heuristic)

**Status:** PROVISIONAL · advisory/confirm-only · shadow-recorded · inert by default. No ML,
no GPU, no hidden state. Heuristic (keyword + structured) — deliberately conservative.

## Definition

Detect **obvious** contradictions between a model's stated plan and the action it actually
proposes — a coarse intent-consistency check, not a semantic model.

## Inputs

`PlanActionContext`: `stated_plan`, `proposed_action` (tool/action name), `action_args`,
optional `user_goal`, and optional structured hints `plan_targets` / `action_targets` /
`action_mutates` / `action_external` (used only when present).

## Deterministic checks (no ML)

| Kind | Fires when |
|---|---|
| `read_plan_mutating_action` | plan uses read/summarize/view words (and no mutate words) but the action mutates/deletes/sends |
| `confirm_plan_executes` | plan says ask/confirm/clarify but the action executes |
| `no_external_plan_external_action` | plan forbids external access ("no external", "offline", …) but the action uses an external tool |
| `resource_mismatch` | `plan_targets` and `action_targets` are both given and **disjoint** |

Plan/action intent is read from fixed keyword sets over the lowercased plan and action text
(name + args); identical inputs → identical output. `resource_mismatch` only fires on
explicit structured targets, to avoid free-text false positives.

## Taxonomy + verdict

`ObservableType.VALIDATOR`, `EvidenceStatus.PROVISIONAL`. Because it is **heuristic**, it only
ever emits `UNSURE` (→ CONFIRM) on a mismatch, never `UNSAFE` — so it does not block even when
promoted to PROVEN (a PROVEN validator with an `UNSURE` verdict still only CONFIRMs). It only
ever raises trust (a contradiction is a reason to pause); it never relaxes a decision.

## Inert by default (no production behaviour change)

Appended to the trust observation set only when an explicit `PlanActionContext` is supplied
(via `MCPToolCall.plan_action_context`) referencing a plan/action. Production calls carry none
→ the observable is absent → the recorded/authoritative decision is unchanged; existing
parity / shadow-volume corpora are unaffected.

When supplied it participates in **shadow mode**, **parity reporting** (a
`plan_action_consistency` driver; stricter-only escalation classified `intended`), **audit
persistence** (`trust_shadow.drivers` + `trust_observations`), and **shadow_report
aggregation**. It can never produce `unsafe_relaxation`.

## Promotion plan (PROVISIONAL → PROVEN)

Because this is the first *heuristic* (not registry-deterministic) observable, promotion is
deliberately conservative and **does not unlock blocking**:

1. **Precision review.** Over a shadow window, every `plan_action_consistency` escalation
   spot-audited; the false-positive rate (mismatches that were actually fine) below an agreed
   ceiling, with no systematic class (e.g. a missing keyword) driving FPs.
2. **Coverage.** Each mismatch kind observed firing correctly on real traffic, not only the
   validation corpus, over a calibrated minimum volume of plan-bearing calls.
3. **Input provenance.** `stated_plan` / `plan_targets` come from a trusted upstream (the
   agent's own committed plan), not adversary-controlled content — otherwise the signal can be
   gamed both ways.
4. **Safety invariants.** `shadow_report` shows 0 unsafe_relaxation / 0 unintended.
5. **Sign-offs.** Governance/safety + audit/compliance.

On promotion the observable becomes a **PROVEN confirm-only** validator (verdict stays
`UNSURE`); making any kind *block* would be a separate, higher-bar decision (likely requiring a
non-heuristic signal). **Not done here. No authority expansion.**

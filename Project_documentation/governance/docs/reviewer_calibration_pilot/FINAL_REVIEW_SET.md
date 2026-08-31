# Final Review Set (Phase 5)

*`reviewer_calibration_pilot/data/final_review_v1/`. 100 artifacts reviewers would judge **blind** — no
reviewer gold is stored (humans produce it). 60 naturally occurring artifacts absent from all prior sets
+ 40 constructed safety traps. Never used to train, never used to tune the policy.*

## Composition

| Group | Count |
|---|---|
| Natural artifacts (new, not in any prior/training set) | 60 |
| Constructed safety traps (synthetic, 8 types × 5 variants) | 40 |
| **Total** | **100** |

## Safety-category coverage (via synthetic traps)

| Category | Count | Spec minimum |
|---|---|---|
| self-verification + circular-evidence | 10 | ≥ 10 |
| source-authority (stale / impl-as-operational / attribution-as-truth) | 15 | ≥ 15 |
| action-bearing (action-without-approval / high-risk-opinion) | 10 | ≥ 15 action-adjacent* |

## Honest note on balance (per spec: "do not fabricate natural artifacts")

The **natural** artifacts are what the repository supplies: they skew to **E2/E3, low-risk**
`process_description`/`code_behavior` docstrings (obligation levels E2 76 / E3 19 / E4 5; risk low 74 /
medium 12 / high 14 on the policy's own reading). Natural repository text simply does not contain many
high-risk action proposals, source-authority disputes, or ambiguous ER cases. Rather than **fabricate
natural artifacts** to hit those targets (prohibited), the safety-critical categories are covered by
**honestly synthetic traps** (self-verification, circular, stale-authority, fixture-as-telemetry,
impl-as-operational, action-without-approval, attribution-as-truth, high-risk-opinion), 5 variants each.

`*` The action-bearing traps total 10 (action-without-approval + high-risk-opinion); the spec's ≥15
action-adjacent target is **not** fully met because natural artifacts supply almost no action proposals
and the guidance is to not fabricate natural ones. **Conclusions about action-bearing agreement would
therefore be reduced accordingly** — a limitation recorded here and carried into the (unrun) evaluation.

## Blind by construction

Natural final items store only **metadata** (claim family, risk, source role, actionability, temporal)
needed to run the frozen policy — **never** a reviewer gold obligation. The reviewer gold is what real
reviewers would produce independently. Traps carry a `trap_type` but no revealed obligation. Verified by
test: no natural final item has a `gold_obligation` field.

## Separation

`final_review_v1` is disjoint from `training_v1` and excludes every prior final/held-out source path
(bounded_shadow_pilot 857-set, evidence_obligation, minimal_evidence_policy). Deterministic.

## Status

The set exists and is frozen-ready. It is **never reviewed** in this environment (no real reviewers), so
it produces no human labels — consistent with NOT ENOUGH HUMAN EVIDENCE.

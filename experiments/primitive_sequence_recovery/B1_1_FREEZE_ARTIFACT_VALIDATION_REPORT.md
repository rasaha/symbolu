# B1.1 Freeze-Artifact Validation Report

## Status: `READY_FOR_FREEZE_REVIEW`

Pure-stdlib validation of the candidate freeze configs + bridge pool. NO model / embedding / generation /
scoring / judging. B1.1 **not frozen**; generation **not authorized**. B1 verdict
`RANDOM_OR_SCRAMBLED_MATCHES` unchanged; Track B **BLOCKED**. Structure, not validated meaning.

## Checks
- [PASS] exists:b1_1_arm_construction_config.json
- [PASS] exists:b1_1_generation_config.json
- [PASS] exists:b1_1_seeds_config.json
- [PASS] exists:b1_1_judge_panel_config.json
- [PASS] exists:b1_1_scorer_config.json
- [PASS] exists:b1_1_leak_and_packet_config.json
- [PASS] no_placeholder_required
- [PASS] no_unknown_pending
- [PASS] arms_exactly_8
- [PASS] primary_has_all_three_R
- [PASS] generation_authorized_false
- [PASS] b1_verdict_anchor_present
- [PASS] track_b_anchor_present
- [PASS] embedding_status_correct
- [PASS] fallback_qualification_correct
- [PASS] bridge_68
- [PASS] bridge_no_dup
- [PASS] bridge_no_forbidden
- [PASS] no_source_lexicon_target

## Blockers (0)
_none_

## Warnings (1)
- judge panel: Meta-Llama-3-8B requires explicit acceptance (heavy missing-brace repair in B1) before freeze

## sha256 (candidate artifacts)
- `b1_1_arm_construction_config.json`: 167343c28fe15dc88c2b4aa87c03b7a9e0291a09b0f5f6b45a292b99e9769a11
- `b1_1_generation_config.json`: 268d0c02ee968f602ba00e9668572105c1aa4ef313b15f1bc426ccbe1377f011
- `b1_1_seeds_config.json`: 1c044278ff1ee064c35d1ebacfa0ef5b7fea4cc782d020654ee15200c07730c0
- `b1_1_judge_panel_config.json`: 1632b11794a98dd0b864d3e2a3e35e76614da7de8d6cd17c6a85f6f2bb4dfc74
- `b1_1_scorer_config.json`: aac682fe8bf22d51eb530c40440d07fb629ee148a6b822a69c3c1f9f440befd6
- `b1_1_leak_and_packet_config.json`: 0804e3d23a336f55f1d2a176d859f0e3931ab3719eb1c97b56e921e6ebb9db48
- `b1_1_bridge_pool_draft.json`: 1ce2ae14b563621ac495381e8397796e6791aba740978bb817544935c6ba8c15
- `b1_1_experimental_contrastive_lexicon_draft.json`: e8aeb105027907092b28eb17896fc699cf780f180fe38ca645f7ca94751b5bb7

## Final status
```
status:                READY_FOR_FREEZE_REVIEW
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
Bridge:                PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
B1.1 frozen:           NO
Generation authorized: NO
```
`R_deranged` remains the crux. **Structure, not validated meaning.**

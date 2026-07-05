# B1.1 Freeze-Artifact Validation Report

## Status: `NOT_READY_FOR_FREEZE`

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
- [FAIL] no_unknown_pending
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

## Blockers (3)
- UNKNOWN_PENDING_FREEZE_REVIEW in b1_1_arm_construction_config.json: ['$.forbidden_domain_lists_per_word']
- UNKNOWN_PENDING_FREEZE_REVIEW in b1_1_generation_config.json: ['$.prompt_template', '$.task_templates.T1_definition.exact_prompt', '$.task_templates.T2_explanation.exact_prompt', '$.task_templates.T3_metaphor.exact_prompt', '$.task_templates.T4_correctness_sensitive.exact_prompt', '$.task_templates.T5_tone_match.exact_prompt', '$.task_templates.T6_evoke_creative.exact_prompt']
- UNKNOWN_PENDING_FREEZE_REVIEW in b1_1_judge_panel_config.json: ['$.judge_prompt_exact']

## Warnings (1)
- judge panel: Meta-Llama-3-8B requires explicit acceptance (heavy missing-brace repair in B1) before freeze

## sha256 (candidate artifacts)
- `b1_1_arm_construction_config.json`: 019c2ec8ab79cb33619ef4eb1457c7ee7821b1cb0b58df514cca32a3d14bb4d9
- `b1_1_generation_config.json`: 16af2be6de57dd33064e016a94becc9f525d510307f56338d268408a4cd739f2
- `b1_1_seeds_config.json`: 1c044278ff1ee064c35d1ebacfa0ef5b7fea4cc782d020654ee15200c07730c0
- `b1_1_judge_panel_config.json`: 7ba6200c44a1719f216d4b4f40df4f47cf2216744a5985fa49d1bbb06d75e0ad
- `b1_1_scorer_config.json`: aac682fe8bf22d51eb530c40440d07fb629ee148a6b822a69c3c1f9f440befd6
- `b1_1_leak_and_packet_config.json`: 09e869827be3626b327c76897886226741898b1a24187f9dd821111e28242c69
- `b1_1_bridge_pool_draft.json`: 4da248bc622fa4284a2f414252441c371e71519fc068f160bc7278c206a35a5c
- `b1_1_experimental_contrastive_lexicon_draft.json`: b7e83818a9c8aaf63502fb28fe4262f48cf7375bccdd514bafef940e7b7585b1

## Final status
```
status:                NOT_READY_FOR_FREEZE
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
Bridge:                PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
B1.1 frozen:           NO
Generation authorized: NO
```
`R_deranged` remains the crux. **Structure, not validated meaning.**

# Evidence schema

Versioned schemas under `experiments/bindingslots_persistence/schemas/`: `run_manifest`,
`seed_manifest`, `arm_definition`, `checkpoint_metrics`, `causal_ablation_result`,
`routing_trajectory`, `h1_parameter_group_manifest`, `h2_teacher_definition`, `integrity_report`,
`aggregate_classification`, `selection_decision`.

Every future result artifact must include: schema version; arm; seed; source commit; frozen-config
digest; arm-definition digest; classifier digest; environment; checkpoint step; run status; restart
count; artifact hash; provenance chain. In this preregistration-only phase, **schemas and reference
fixtures only** exist — no experiment outcomes are fabricated. Committed curated trajectories will be
the authoritative verdict-reconstruction artifacts in the training phase.

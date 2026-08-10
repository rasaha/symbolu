# safety_state/DESIGN.md

This file is a pointer. The full design lives at the top-level
[`SAFETY_STATE_MACHINE_DESIGN.md`](../SAFETY_STATE_MACHINE_DESIGN.md)
in the package root, where it sits alongside the other top-level
design docs (`HIERARCHICAL_BCVF_DESIGN.md`,
`MULTI_MODAL_PREDICTORS_DESIGN.md`,
`INDUSTRY_FEATURES_ROADMAP.md`).

The doc covers:

* §1 Why this exists (kernel = runtime layer; state machine =
  behavioural contract).
* §2 Four states + state-transition diagram.
* §3 Trigger conditions per transition (drawn from
  `TrustShapedEpisodeRecord`).
* §4 Recovery conditions (sustained-NORMAL dwell + manual reset).
* §5 ASIL decomposition.
* §6 Direct-jump prohibition (machine raises on attempt).
* §7 Composition with `StreamingFleetMonitor` + SOTIF traceability
  + characterization grid.
* §8 What this is NOT.
* §9 Ship-when-ready criteria for STABLE_API graduation.
* §10 API sketch.

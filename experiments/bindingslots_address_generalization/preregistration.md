# Preregistration — BindingSlots Read-Address Generalization (A1) and Routing-Gradient Isolation (G1)

**Intervention-development phase, separate from the completed diagnostic phase. Candidates require
independent confirmation. This phase cannot unblock KDA; `KDA_VALIDATION_BLOCKED` is always emitted.**

Committed before any fresh reserved-seed intervention run. Machine-readable mirror: `preregistration.json`.

## Prerequisite (verified — `prerequisite_audit.json`)
Default tip = value-path merge `ee36e34a`; verdict `BINDINGSLOTS_BOTH_FAILURE_FAMILIES_LOCALIZED` /
`KDA_VALIDATION_BLOCKED`; both mechanisms confirmed (H2 s23 & R0 s23 `ADDRESS_DISTRIBUTION_FAILED`;
O1R s24/s25 & H2 s25 `QUALITY_GRADIENT_CONFLICT_LOCALIZED` in `write_addr_proj`); both classifier
outputs preserved; inherited tests+verifier pass; tree clean.

## Hypotheses (neither assumed true)
- **H-A** a contrastive routing objective across diverse query forms + hard competitor slots makes the
  correct slot reliably top-ranked on held-out eval queries.
- **H-G** projecting conflicting persistence/teacher gradients away from the LM gradient **only** in
  `write_addr_proj` preserves routing supervision without the quality regression.

## Exclusions (§3)
No external memory tables, DB retrieval, multiple read heads, separate key/value arch, new slot
count/dim, sparsemax/entmax/temperature tuning, Phase/KDA/MLA/quadratic attention, model scaling,
enterprise/NL expansion. No combining untested mechanisms in one arm.

## Base + seeds
Base = corrected H2 (exhibited both failure families); architecture/size/slots/optimizer/lr
schedule/teacher schedule/scaffold/task generator/eval distances/quality gate/clean-stable
classifier/max steps all preserved — the only permitted changes are the A1 and G1 levers. Seeds =
**28,29,30,31,32** (mechanically allocated, 13–27 forbidden), same in every arm, no replacement.
Fixture seed 99991 is non-evidentiary.

## Arms (`arm_definitions.json`)
A+ (reference), B0 (frozen H2; levers-off = byte-identical, verified), A1 (read-address
generalization), G1 (routing-gradient isolation), AG (A1+G1, only if both pass).

## A1 lever
`L_A1 = -log r[query_pos, s*]` (frozen `correct_slot_prob_loss`), applied at **real task-query
positions** across diverse **train** templates with hard-negative distractor facts; schedule =
`o1r_lambda`; dedicated batch rng (main stream unchanged). Held-out **test** template = the frozen
needle-eval query, never trained. Details: `HARD_NEGATIVE_AND_TEMPLATES.md`.

## G1 lever
`g_aux_corrected = g_aux - min(0, ⟨g_aux,g_lm⟩/‖g_lm‖²)·g_lm`; final `write_addr_proj` grad =
`g_lm + g_aux_corrected`; applied to `write_addr_proj` **only**, group level; LM gradient never
modified; no backbone projection; no coefficient change; no separate optimizer; global clip and
optimizer unchanged (applied after projection). Zero LM-gradient norm → no projection (deterministic).

## Measurements (§9)
Checkpoints 300/600/700/900/1200. End-to-end (needle, distances, clean-stable, same-seed ppl,
quality). **Primary** eval-time routing on the **held-out** eval queries (correct-slot prob/top-1/
rank/margin/entropy, ordinary-vs-oracle gap); fixed-probe metrics are secondary only. Gradient
behaviour for B0/G1/AG (per-group LM-vs-aux cosine at `write_addr_proj` and other groups, #negative
updates, projected norm, fraction removed).

## Gates (frozen thresholds — `ag_classify.FROZEN_THRESHOLDS`, from clean-control distributions)
Quality: candidate ppl ≤ 1.20×same-seed A+. A1 gate (all of): ≥4/5 quality-qualified; ≥4/5
clean-stable; eval correct-slot prob improves ≥0.15 vs paired B0 on ≥4/5; top-1 improves ≥0.15 on
≥4/5; ordinary ≥0.80×oracle on ≥4/5; improvement is on held-out eval (not probe-only); no template
leakage. G1 gate (all of): ≥4/5 quality; wak negative alignment eliminated (mean ≥ −0.02) or |cos|
reduced ≥50% vs B0 on ≥4/5; retrieval+routing non-inferior to B0 (±0.05) on ≥4/5; no new conflict
(≤ −0.10) in another group; only `write_addr_proj` projected; training semantics unchanged. AG runs
only if A1 and G1 both pass; even if AG passes it is a development candidate requiring untouched
confirmation.

## Adaptive futility (§14)
Sequential over 28–32; stop an arm after the **second** seed making 4/5 mathematically impossible; no
within-seed stopping; no best-checkpoint; no seed replacement; A1 and G1 evaluated independently
before AG.

## Verdicts (§18) + always `KDA_VALIDATION_BLOCKED`; if a candidate is selected, also
`INDEPENDENT_CONFIRMATION_REQUIRED`. Next-phase mapping recorded, not executed (§19). No fix beyond
the two levers; no independent confirmation; no KDA; no next phase in this PR.

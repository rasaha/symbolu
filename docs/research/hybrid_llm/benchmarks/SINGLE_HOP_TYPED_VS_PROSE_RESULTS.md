# Single-hop typed-vs-prose benchmark — results & verdict

**Verdict: `TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND`.**

Typed JSON input (B1) did **not** materially improve controlled single-hop relational reasoning
over an information-equivalent flattened-prose input (B0) at the frozen model recipe. The measured
effect was marginally **negative** (B1 − B0 = −0.022 primary), with no consistent per-seed
direction. Both arms solved the constant-output splits perfectly and both failed the
copy-a-novel-identifier-from-context splits.

Always preserved and untouched by this result:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`. This run emits **only** a `TYPED_STRUCTURE_SINGLE_HOP_*` verdict; it does
**not** emit `E1_STRUCTURAL_TRANSFER_CONFIRMED`, `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`,
`KDA_VALIDATION_ELIGIBLE`, or `PRODUCTION_READY`.

## Setup (frozen before any reserved run)
- Arms: **B0** = canonical prose, **B1** = canonical typed JSON, information-equivalent by
  construction (one canonical episode → two renderings; JSON round-trips to the canonical fact
  graph; prose is a frozen one-sentence-per-fact template). `B0_fact_hash == B1_fact_hash` for
  100% of pairs.
- **Disjoint identity pools:** train IDs [100,600), final IDs [600,1000). A correct final-pool
  answer cannot be a memorized training identifier — it must be copied from the current context.
- 40 train + 24 eval episodes/scenario/seed. One frozen recipe (64-dim, 2-layer, 4-head, 209,728
  params) and optimizer (AdamW 3e-4, batch 8, 2000 updates), identical for both arms; only the
  input representation differs. Decision-6 domain-separated sub-seeds; both arms share
  dataset/init/batch seeds.
- Reserved final seeds 7160–7164, executed under the owner-authorized token (see
  `SINGLE_HOP_TYPED_VS_PROSE_EXECUTION_AUTHORIZATION.md`).

## Primary result (macro-average of S1, S2, S3, S5-F1, S6)
| Seed | B0 (prose) | B1 (JSON) | B1 − B0 |
|---|---|---|---|
| 7160 | 0.533 | 0.467 | −0.067 |
| 7161 | 0.400 | 0.400 | +0.000 |
| 7162 | 0.400 | 0.408 | +0.008 |
| 7163 | 0.400 | 0.500 | +0.100 |
| 7164 | 0.550 | 0.400 | −0.150 |
| **mean** | **0.457** | **0.435** | **−0.022** |

Seeds satisfying the frozen per-seed pass rule (B1 ≥ 0.75 **and** B1 − B0 ≥ 0.05): **0 / 5**.

## Per-split means (both arms)
| Split | Task | Graded field | B0 | B1 |
|---|---|---|---|---|
| S1 | duplicate-name target select | entity | 0.050 | 0.092 |
| S2 | foreign-key target select | entity | 0.233 | 0.067 |
| S3 | relation validity | relation-supported | 1.000 | 1.000 |
| S4 | attribute disambiguation | entity | 0.250 | 0.000 |
| S5 | evidence selection | evidence P/R | ~0.00 | 0.017 |
| S6 | missing-relation abstention | abstention | 1.000 | 1.000 |
| S7 | cross-tenant abstention | abstention | 1.000 | 1.000 |
| S8 | contradicted relation | relation-supported | 1.000 | 1.000 |

**The pattern is the finding.** Splits whose correct output is a *constant* for the scenario
(S3 always "supported", S6/S7 always "abstain", S8 always "unsupported") are solved perfectly by
both arms. Splits that require **copying a fresh, never-trained identifier out of the context**
(S1/S2/S4 entity selection; S5 evidence-ref selection) are at or near floor for both arms. Final
training loss reached ~0.01 (the model memorizes the *training* identities), but that capability
does not transfer to the disjoint final identities — which is exactly what the disjoint-pool design
was built to detect.

## Gate ladder (frozen Decision-3)
`1_b1_mean≥0.80`=FAIL · `2_improvement≥0.08`=FAIL · `3_≥4of5_seeds`=FAIL · `4_per-split`=FAIL ·
`5_tenant_zero`=**PASS** · `6_S8≥0.90`=PASS · `7_S8_no_regress`=PASS · `8_info_equiv`=PASS ·
`9_determinism`=PASS · `10_shortcut`=FAIL · `11_causal`=FAIL · `12_compute`=PASS ·
`13_no_deviation`=PASS. Endpoint gates fail decisively → `ADVANTAGE_NOT_FOUND`.

## Integrity & safety (the parts that passed cleanly)
- **Tenant isolation held:** unauthorized cross-tenant inclusions = **0** across every final
  example, seed, and arm (S7); the A5 cross-tenant-substitution ablation also produced 0
  unauthorized inclusions and 0 out-of-tenant selections. The categorical safety invariant was not
  violated.
- **Information-equivalence:** 100% of paired examples share one fact hash.
- **Determinism:** retraining a seed reproduced the exact parameter digest (dev phase, both runs).

## Honest caveats (do not over-read this null)
1. **This is partly a floored-comparison null.** Both arms fail the copy splits, so the comparison
   there has little power to detect a representation effect *even if one existed at a competent
   operating point*. The correct reading is narrow: **at this frozen small-from-scratch recipe,
   typed structure confers no single-hop advantage, and neither representation solves copy-from-
   context on unseen identities.** It does **not** prove "typed structure never helps" at other
   scales or with a model that can already copy.
2. **Causal gates (A1–A6) fail as a *consequence* of the null,** not as independent evidence: with
   clean entity accuracy ~0.05 there is no competence to "decline" from under perturbation, so the
   ≥0.20-decline thresholds are undefined in practice. A5 (tenant) is the exception and passed.
3. **Shortcut gate fluctuation, reported unadjusted.** On the reserved cohort the lexical-overlap
   heuristic scored 0.639 (> chance+0.05) while the positional heuristic was 0.444 (≤ chance+0.05);
   across ten development-scale cohorts lexical overlap averaged ~0.51, so 0.639 is a high-side
   single-cohort fluctuation. Per protocol the benchmark is **not** adjusted after inspecting
   reserved results. Note the learned models (S1≈0.05–0.09) fell *below* the shortcut — i.e. the
   trained models did not even reach lexical-heuristic competence, which reinforces the null rather
   than indicating exploitable leakage in favor of either arm.

## What this supports — and what it does not
Supports: a clean, un-gamed, preregistered **null** for the "typed input beats prose for single-hop
relational reasoning" hypothesis at this recipe; and a concrete diagnosis that the binding
constraint at this scale is the **copy/lookup capability**, not the input representation.

Does not support (and must never be read as): typed-structure advantage · multi-hop relational
reasoning · temporal-state reasoning · memory value · evidence-grounding validation · efficiency
superiority · real-model transfer · production readiness · KDA eligibility. The V1.0 thesis claim
that typed records/edges are superior to prose remains, on this evidence, an **unproven
hypothesis** — consistent with the current evidence-aligned position.

## Independent audit (Stage 2)
This result was independently audited from Git ground truth (`…_AUDIT_REPORT.md`,
`…_AUDIT_PROVENANCE.md`, `…_AUDIT_ANALYSIS.md`). Deterministic replay of the frozen implementation
reconstructed the reported means, per-seed and per-split values, and verdict **exactly**
(`runs/audit/audit_manifest.json`, `runs/audit/audit_replay_traces.json`); information-equivalence
held over all 960 paired final examples (0 mismatches); arm-fairness (shared initialization),
decode-cap neutrality (max emitted 38 ≪ 96 cap, zero truncation), and provenance were verified.
Audit decision: `MERGE_READY_AFTER_SCOPED_CORRECTIONS`.

Audit-only non-constant diagnostic (mean of the varying-content primary components {S1, S2, S5-F1},
excluding the two constant-gold components S3 and S6): **B0 = 0.094, B1 = 0.058** — both at or near
floor. This does not replace the locked primary (B0 0.457 / B1 0.435); it isolates that the
copy/selection signal, where the real work is, is near floor for both arms.

## Reproduction
`python -m experiments.single_hop_typed_vs_prose.driver <out_dir>` (reserved seeds require the
owner-authorized token resolved by the fail-closed gate). Audit reconstruction:
`python -m experiments.single_hop_typed_vs_prose.audit_replay <out_dir>`. Raw artifacts:
`experiments/single_hop_typed_vs_prose/runs/final_7160_7164/{smoke,dev,final,verdict}.json`.

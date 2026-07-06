# B1.2 Folder Migration Note

Repository-organization change only. No experiment was run, no result changed, no B1.1 artifact was touched.

## 1. Files moved (into `experiments/primitive_sequence_recovery/b1_2_mapping_fidelity/`)

Moved with `git mv` (history preserved; detected as renames):

- `B1_2_MAPPING_FIDELITY_PROPOSAL.md`
- `B1_2_R_DERANGED_CONTROL_VALIDITY_REVIEW.md`
- `B1_2_MAPPING_FIDELITY_PREREG_DECISION.md`
- `B1_2_MAPPING_FIDELITY_PREREG.md`

(Two files named in the reorg request — `B1_2_LAYER3_DERIVATION_FUNCTION_FEASIBILITY.md` and
`B1_2_TWO_AXIS_CONTROL_HIERARCHY_AMENDMENT.md` — do **not** exist: the two-axis change was folded into the
prereg as Amendment A2 rather than a standalone file, and the Layer-3 feasibility doc has not been written
yet. Nothing to move.)

## 2. Files intentionally NOT moved

- All B1.1 artifacts remain in the parent `experiments/primitive_sequence_recovery/`:
  raw outputs, judge packets, judge outputs, scoring files, final reports (`B1_1_FINAL_SCORING_AND_VERDICT.md`,
  `B1_1_POST_RESULT_FORENSIC_REPORT.md`), freeze manifests, configs, generation scripts, judge scripts,
  audit reports.
- `B1_1_THEORY_APPLICATION_MISMATCH_REVIEW.md` — a **B1.1** review (about B1.1's implementation), left in the
  parent folder; it is cited by the B1.2 decision memo but is not a B1.2-only artifact.
- Any B0/B1 frozen artifacts; any `varna_lens/` source lexicons.

## 3. No B1.1 artifacts changed

Only `git mv` renames of the four B1.2 design docs, plus three new files created in this folder
(`README.md`, `STATUS.md`, `MIGRATION_NOTE.md`). No B1.1 file was edited, renamed, or deleted.

## 4. No results changed

No judge output, scoring output, verdict, or freeze manifest was modified. B1.1 verdict remains
`RANDOM_OR_SCRAMBLED_MATCHES`; Track B remains BLOCKED; Track G and Track F negatives preserved.

## 5. No implementation / run / scoring occurred

No model was run, no generation, no judging, no scoring. This change is purely a directory reorganization.

## Reference integrity

- B1.2 → B1.2 sibling references (filename-only) remain valid — all four docs moved together into this
  folder.
- The decision memo references three B1.1 docs by bare filename; those files remain **one level up** in the
  parent folder (noted in `README.md`).
- No document outside the B1.2 set referenced these filenames, so no other doc required updating.

**Structure, not validated meaning.**

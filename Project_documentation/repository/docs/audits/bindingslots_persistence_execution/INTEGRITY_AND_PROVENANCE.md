# Integrity and provenance

## Two-code-commit provenance (authorized H2 correction)

- **Runs A+/R0/O1R/H1 (16 runs):** `execution_code_commit 5cc392e1` (`persistence_arms.py` sha256
  `1f3f6b7d…`).
- **Runs H2/O1 (8 runs):** `execution_code_commit 9380bdb1` (`persistence_arms.py` sha256 `9edbcd8d…`),
  after the **user-authorized** fidelity correction that added the missing `if mask is None:` branch to
  `run_h2` (matching the frozen reference loop `stabilize.py:138`). Diff = 9 insertions / 2 deletions,
  scoped to `run_h2`; the A+/R0/O1/O1R/H1 code paths and the classifier are byte-identical between the
  two commits. See `AUTHORIZED_CORRECTION.md` and `results/code_correction_record.json`.

The **crashed H2 seed23 attempt is INVALID and NON-EVIDENTIARY** — the crash preceded persistence, no
artifact was written, and H2 seed23 was restarted fresh from step 0 under the corrected harness. The
16 pre-correction runs are preserved unchanged. A non-reserved fixture seed (3) was used to validate
the fix and is excluded from all scientific evidence.

## Frozen-state integrity

- Frozen `abc.json` `b31989a3…` unchanged.
- All 7 frozen scientific-definition hashes (arm/classifier/O1R/H1/H2/config/seeds) match the values
  pinned in `adaptive_execution_plan.json` (verified pre-run and post-run).
- amendment integrity 35/0; historical-artifact protection 8/0; lab verifier 81/0.
- No seed replaced; no best-checkpoint selection; no threshold/coefficient/objective/schedule change.

## Reproducible replay

`build_execution_report.py` reclassifies every seed from raw evidence (same-seed A+) and replays
`next_action` over the ledger; the reconstructed sequence and terminal verdict match the actual run
ledger exactly (`replay_reproducible: true`). Every per-seed directory carries `raw_record.json`,
curated metrics, causal ablation, classification, and an `integrity_record.json` with the artifact
sha256.

## Causal-informativeness labeling

Causal ablations on seeds whose post-train baseline retrieval is already ~0 (e.g., H2 s23, R0 s23/s26)
are **non-informative** and are not cited as causal evidence — the dissociation between the routing
diagnostic probe and the eval needle is the operative signal for downstream collapse.

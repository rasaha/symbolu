# GOVERNANCE_ABLATIONS — Governance Semantics Experiment v0.1

## Table 2 — G0–G4 aggregate results (hidden pilot)

| condition | disc P | disc R | class | govG | packP | select | cover | false-ab | unsafe |
|---|---|---|---|---|---|---|---|---|---|
| G0_frozen | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 0.9500 | 0.0000 | 2 |
| G1_supersession_amendment | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 0.9500 | 0.0000 | 2 |
| G2_parallel | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 0.9500 | 0.0000 | 2 |
| G3_operative | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.3860 | 0.9500 | 0.0000 | 2 |
| G4_full | 0.8974 | 0.4167 | 0.9143 | 0.4333 | 0.5167 | 0.5294 | 0.2833 | 0.5000 | 2 |

**The ablation ladder is the core finding.** G1 and G2 change nothing (operative
selection is off, so the operative node stays the frozen primary). **G3 turns on
operative-source selection** and lifts selective accuracy 0.2982 → 0.3860 (+0.0878)
with **coverage, Mode G, false-abstention, and unsafe all unchanged** — a clean,
non-coverage-driven gain. **G4 adds governance abstention** and, while selective
rises to 0.5294, coverage collapses 0.95 → 0.2833 and false-abstention jumps 0 →
0.5: the G4 topline is a coverage artifact, not better answering.

Discovery precision/recall, classification, and packet Mode P are identical across
every condition (protected-stage identity, Table 1).

## Causal attribution of the mechanisms
- **supersession/amendment scope (G1), parallel applicability (G2):** inert on this
  pilot as governing-set annotations (they do not move the answer without operative
  selection).
- **operative-source selection (G3):** the sole clean contributor — +0.088 selective,
  no protected-metric or coverage cost.
- **governance abstention (G4):** over-fires; converts hard answerable cases into
  abstentions, inflating selective through coverage reduction.

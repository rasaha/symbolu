# Review Disagreement Taxonomy (Phase 11)

*How reviewer↔system and reviewer↔reviewer disagreements are classified when real reviews exist. Each
category carries a severity, the decision it affects, expected adjudication, and its policy / guide /
pilot implications. No human disagreements exist in this environment; the taxonomy is the analysis frame,
ready for use.*

| # | Category | Severity | Affected decision | Expected adjudication | Policy implication | Guide implication | Pilot implication |
|---|---|---|---|---|---|---|---|
| 1 | Risk disagreement | high | risk floor → obligation | conservative (higher) | possible floor rule review | clarify risk cues | high-risk gate |
| 2 | Source-authority disagreement | high | E2 eligibility | conservative | authority-metadata review | clarify authority vs type | gate authority cases |
| 3 | Factual vs opinion disagreement | high | E0 eligibility | toward factual | E0 gate review | clarify non-factual bar | block if frequent |
| 4 | Implementation-evidence disagreement | medium | E2 vs E3 | toward E3 | impl-evidence rule review | clarify impl≠operational | — |
| 5 | Telemetry-evidence disagreement | medium | E3 satisfaction | toward E3 | — | clarify measurement bar | — |
| 6 | Stale-authority disagreement | high | E2 vs E3 | toward E3 | INV-7 review | clarify freshness | gate current claims |
| 7 | Self-verification disagreement | **critical** | ≥ E3 raise | toward E3 (never below) | INV-1 must hold | reinforce trap | **stop if system too permissive** |
| 8 | Circularity disagreement | **critical** | ≥ E3 raise | toward E3 | INV-2 must hold | reinforce trap | stop if system too permissive |
| 9 | Obligation-level disagreement | medium | final obligation | acceptable-band check | rule review if systematic | examples | — |
| 10 | Evidence-satisfaction disagreement | medium | EA delivery | reviewer-led | — | clarify sufficiency | — |
| 11 | Qualification disagreement | low | qualify vs allow | reviewer-led | — | clarify qualify | utility signal |
| 12 | Actionability disagreement | high | action floor | conservative | INV-11 review | clarify action authority | gate action cases |
| 13 | ActionGate outcome disagreement | high | native outcome | toward stricter native outcome | none (frozen gate) | clarify 6 outcomes | preserve vocabulary |
| 14 | Reviewer-guidance ambiguity | medium | any | guide fix | none | **revise guide** | re-train |
| 15 | Missing-context disagreement | medium | any | supply context | none | none | intake/context fix |
| 16 | Irreducible domain disagreement | low–high | any | record UNRESOLVED | none (not a defect) | none | note ambiguity |

## How the taxonomy drives the decision

- **Critical (7, 8):** any case where reviewers judge the system **too permissive** on self-verification /
  circular evidence is a **stop condition** and a potential policy defect — the anti-self-verification
  invariants must hold in human judgment, not just in code.
- **High (1, 2, 3, 6, 12, 13):** systematic disagreement here points to a **policy rule** or
  **source-authority metadata** revision (Phase 18 error analysis), not a guide tweak.
- **Guide vs policy separation:** category 14 (guidance ambiguity) is fixed by revising the **reviewer
  guide**, not the policy; distinguishing 14 from 1–13 is the core of the error analysis.
- **Irreducible (16):** recorded as UNRESOLVED, never forced — it bounds the achievable agreement and is
  reported, not engineered away.

## Status

No human reviews exist, so **no disagreements are classified**. The taxonomy is the frame the human-
validation report (Phase 17) and policy error analysis (Phase 18) would populate.

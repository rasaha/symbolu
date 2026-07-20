# GOVERNANCE_FAILURE_ATTRIBUTION — Governance Semantics Experiment v0.1

Each incorrect G4 case is attributed to exactly one PRIMARY stage. The Governance
Semantics Layer is blamed only for errors it owns (applicability, operative source,
abstention); missing-edge errors belong to frozen proposal generation, and
answer-shape errors within a correct governing decision belong to the frozen packet.

## Table 11 — failure attribution (G4)

| primary stage | G4 incorrect cases |
|---|---|
| proposal_generation | 23 |
| governance_applicability | 13 |
| operative_source_or_frozen_packet | 3 |

Most residual errors are `governance_applicability` (the frozen governing set is
itself wrong on the case, inherited by design) or `operative_source_or_frozen_packet`
(the governing set is right but the single-primary packet cannot render the needed
answer). The layer's own new failure mode — over-abstention in G4 — shows up as
false-abstention in the abstention table, not here (those cases are counted as
unanswered, not wrong-answered).

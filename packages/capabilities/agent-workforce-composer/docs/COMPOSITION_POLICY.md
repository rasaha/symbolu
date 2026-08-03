# Composition Policy

`TeamCompositionPolicy` separates **hard team constraints** from **soft team
objectives**. Hard constraints are never offset by objective score.

## Hard team constraints (`_team_feasibility`)
every agent P1-eligible for its role · one primary per role · max roles per agent ·
provider concentration (≤ pct of roles to one provider) · failure-domain
concentration · authority concentration (≤ pct of team proposed authority to one
agent) · minimum provider/deployment diversity · team cost ceiling (sum) · team
latency ceiling (max) · team reliability floor (min / weakest link) · interface
compatibility (each dependency's linking contract supported by both assigned
agents). Any failure ⇒ the team is infeasible.

## Soft objectives (`_objective`, evaluated only after feasibility)
aggregate ranking quality (Σ primary scores) + provider diversity + failure-domain
diversity, each an integer basis-point contribution with a policy weight. Objective
results are exposed transparently (`TeamObjectiveResult`).

## Tie-break
Equal team objective → lexically smallest assignment tuple (role-ordered agent
identities) wins — a deterministic total order.

# CAPABILITY_DECOMPOSITION — Four Independent Stages

The resolver pipeline is decomposed so each capability is measured alone. A
failure at one stage cannot be masked or borrowed by another.

```
evidence ─▶ [1 Discovery] ─▶ [2 Classification] ─▶ [3 Application/Governance] ─▶ [4 Packet]
             endpoints          edge type            which node governs           final answer
```

## Stage 1 — Relationship Discovery  (owner: Discovery)
Question: *did the required relationship (endpoints) exist in the produced graph?*
Type-agnostic: only the ordered `(src, dst)` pair matters.
- `discovery_recall`  = gold endpoint-pairs found / gold endpoint-pairs
- `discovery_precision` = gold endpoint-pairs found / predicted endpoint-pairs
Reference: frozen 0.13 / 0.93 recall (rule/graph); precision 1.00 / 0.88.

## Stage 2 — Relationship Classification  (owner: Classification)
Question: *if the endpoints were discovered, was the type correct?*
Scored ONLY over predicted edges whose endpoints are a gold pair, so discovery
errors cannot leak in.
- `classification_accuracy` = correct-typed / discovered-gold-endpoint edges
Reference: frozen 0.50, rule/graph 0.93.

## Stage 3 — Relationship Application / Governance  (owner: Governance)  [Mode G]
Question: *given a CORRECT graph, was the governing/abstain decision right?*
Evaluated on the **gold graph** (perfect discovery + classification) so only
application logic varies.
- `governance_accuracy_modeG` = decisions matching gold / governance-owned cases
Reference: frozen 0.60, rule 0.73, graph 1.00.

## Stage 4 — Packet Realization  (owner: PacketConstruction)  [Mode P]
Question: *given a CORRECT governance decision, did the packet contain exactly the
governing evidence and the right answer — nothing more, nothing less?*
Evaluated by feeding the **gold governance** to the packet builder only.
- `packet_realization_accuracy_modeP` = correct answers / governance-owned cases
Reference: frozen 0.60, rule/graph 0.87 (residual = the "requires N days" phrasing
gap, now attributed solely to packet construction).

## Why this matters
Previously edge recall 0.94 co-existed with "precedence resolution" 0.33, hiding
that governance was fine and only packet construction failed. With Modes G and P,
that gap is now located at Stage 4 and nowhere else. Discovery, classification,
governance, and packet each have their own number.

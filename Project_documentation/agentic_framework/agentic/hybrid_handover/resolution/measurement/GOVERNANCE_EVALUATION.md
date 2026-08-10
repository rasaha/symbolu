# GOVERNANCE_EVALUATION — Mode G & Mode P Isolation

Two evaluation modes isolate governance and packet construction from graph
discovery, so each is measured on its own.

## Mode G — governance given a perfect graph
```
GOLD relationship graph ─▶ resolver.resolve_governance() only ─▶ compare to gold decision
```
Discovery and classification are held perfect (the gold graph is supplied with
authoritative nodes/types/edges and real parsed attributes). Only the resolver's
application logic varies.

- Metric: `governance_accuracy_modeG` (Governance).
- Result: frozen 0.60, rule 0.73, **graph_traversal 1.00**.
- Reading: given a correct graph, graph_traversal applies precedence, override,
  version-conflict, cycle, and dangling-reference rules correctly on every
  governance-owned case; frozen (supersede-only discard) and rule (no abstention)
  do not. This is application capability, cleanly separated from discovery.

The gold graph builder sets `dangling` (dst ∉ nodes) and `unusable` (scanned)
structurally, so governance is exercised faithfully — this is measurement-side
construction and changes no resolver.

## Mode P — packet construction given a perfect governance decision
```
GOLD governance decision ─▶ packet builder only ─▶ compare answer to expected
```
The governing set / abstain flag is taken from gold; only the packet builder runs.

- Metric: `packet_realization_accuracy_modeP` (PacketConstruction).
- Result: frozen 0.60, rule/graph 0.87.
- Reading: even with a perfect governance decision, packet realization is 0.87 —
  the residual is the deterministic deriver failing to infer "allowed" from
  "termination for convenience requires N days notice". This is now attributed
  solely to packet construction, not governance or discovery.

## Coverage-owned cases
Pure-coverage cases (OCR) are excluded from Mode G / Mode P and the governance
abstention metrics; their abstention is owned by the SafetyGate (SEEB's frozen
coverage validator), not the resolver.

## Consequence
Governance and packet construction can no longer hide behind each other or behind
discovery. A future resolver's governance is testable on gold graphs (Mode G) and
its packet builder on gold decisions (Mode P), independent of how well it
discovers relationships.

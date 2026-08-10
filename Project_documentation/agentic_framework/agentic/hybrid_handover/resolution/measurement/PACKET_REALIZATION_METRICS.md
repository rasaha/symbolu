# PACKET_REALIZATION_METRICS — Stage 4

Question answered by exactly one metric: *given a correct governance decision, did
the packet contain exactly the governing evidence and produce the correct answer —
nothing more, nothing less?*

## Metric (owner: PacketConstruction)
`packet_realization_accuracy_modeP` — evaluated in Mode P (gold governance in),
so discovery/classification/governance are all held perfect.

Correctness per case:
- abstain cases: the builder must yield `unknown` (no answer fabricated).
- answer cases: the built `(tfc, notice, penalty)` must equal the expected answer,
  built only from the governing nodes (no extra evidence pulled in).

## Reference result
| resolver | packet_realization_modeP |
|---|---|
| frozen | 0.60 |
| rule | 0.87 |
| graph_traversal | 0.87 |

## What the residual is
The 0.87 (not 1.0) for rule/graph is two precedence cases (`order_of_precedence`,
`inconsistent_numbering`) where the governing clause phrases permission as
"termination for convenience requires N days notice". The deterministic deriver
does not infer `allowed` from that phrasing, so `tfc` stays `unknown`. Governance
was correct (Mode G = 1.00 for graph); the failure is purely packet construction.

This is exactly the separation the repair provides: a packet-construction gap that
was previously hidden inside outcome-based "precedence resolution" is now isolated
and owned by Stage 4. We did NOT fix the deriver (no resolver optimisation) — the
metric simply now names the owner correctly.

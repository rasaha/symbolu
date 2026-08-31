# COMPETING_EDGE_ANALYSIS — Edge Prioritization Experiment v0.1

On the hidden pilot, 3 cases contain
two or more competing governance sources (elsewhere the layer is a strict no-op).
3 competing edges were
reprioritized; 2 full-pipeline
governance decisions changed as a result.

## Competitions (winner vs demoted source)

| case | winner | competing (demoted) | decisive component |
|---|---|---|---|
| HX59d7a3eb1c | Policy P-8 (effective 2024) p.1 | Order Form §2 (effective 2020) p.1 | authority |
| HXb3def36e76 | Regulatory Directive R-9 p.1 | Corporate Policy G-2 p.2 | authority |
| HPb167985bd5 | MSA §2 p.2 | Order Form §1 p.1 | authority |

In every competition the **authority** component (later / higher instrument) is
decisive — the prioritizer selects the more authoritative governance source as the
frozen packet's `primary`.

## Governance decisions that changed (P0 → P4)

| case | P0 decision | P4 decision | effect |
|---|---|---|---|
| HX59d7a3eb1c | (False, ('Order Form §2 (effective 2020) p.1', 'Policy P-7 p.2', 'Policy P-8 (effective 2024) p.1'), 'unknown', None, None) | (False, ('Order Form §2 (effective 2020) p.1', 'Policy P-7 p.2', 'Policy P-8 (effective 2024) p.1'), 'prohibited', None, None) | fix (wrong→right) |
| HXb3def36e76 | (False, ('Corporate Policy G-2 p.2', 'Regulatory Directive R-9 p.1'), 'prohibited', None, None) | (False, ('Corporate Policy G-2 p.2', 'Regulatory Directive R-9 p.1'), 'unknown', None, None) | break (right→wrong) |

**This is the crux of the NO CLEAR SIGNAL verdict.** The two changed decisions
cancel: one is a genuine fix (a policy-migration case where the later Policy P-8
should dominate — P0 answered `unknown`, P4 correctly answers `prohibited`), and one
is a break (a parallel-overrides case where ranking a Regulatory Directive above a
Corporate Policy by authority causes the frozen packet to drop the operative
prohibition — P0 was correct, P4 is not). Net effect on selective accuracy: zero.

The authority heuristic is *correct* for supersession/migration but *wrong* for the
parallel-authority case, where the right answer depends on which instrument carries
the operative term — a semantic distinction that lives in the frozen governance /
packet, not in edge ordering. Reordering alone cannot separate these two cases.

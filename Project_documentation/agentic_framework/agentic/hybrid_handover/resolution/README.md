# Relationship Resolution Layer — SEEB v1.0.0

A second measurement layer that scores **relationship reasoning independently of
retrieval**. Reads SEEB and the baseline extractors read-only; modifies nothing
frozen. All corpora synthetic.

## Run
```bash
python -m agentic.hybrid_handover.resolution.run     # writes RESOLUTION_RESULTS.json + PER_CASE_RESOLUTION.csv
python -m pytest tests/test_hybrid_handover_resolution.py -q
```

## Four separated stages
Extraction → **Relationship Resolution** → **Governance Resolution** → **Packet
Construction**. Every failure is attributed to exactly one stage.

## Baselines & result (synthetic)
FrozenResolver 6/16 · RuleResolver 9/16 · GraphTraversalResolver 13/16 — the
framework discriminates deterministic resolvers and localises each failure. Any
future HybridPhaseTransformer / SymbolU resolver plugs into the same protocols,
evidence modes, gold graph, and metrics unchanged.

## Docs
`RELATIONSHIP_RESOLUTION_SPEC.md` · `GOVERNANCE_RESOLUTION_SPEC.md` ·
`RESOLVER_BASELINES.md` · `RESOLVER_METRICS.md` · `FAILURE_ATTRIBUTION.md` ·
`RESOLUTION_GRAPH_FORMAT.md`

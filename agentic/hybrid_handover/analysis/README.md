# Capability Isolation — SEEB v1.0.0

Analysis-only phase (reads SEEB; modifies nothing). Determines whether SEEB's
remaining failures are retrieval or reasoning problems, via an oracle-retrieval
counterfactual.

## Run
```bash
python -m agentic.hybrid_handover.analysis.capability_isolation   # writes CAPABILITY_ISOLATION.json
python -m pytest tests/test_hybrid_handover_analysis.py -q
```

## Result
A **maximal retrieval oracle** (returns every sentence — the retrieval upper
bound) solves **0** of the 7 unresolved cases. Retrieval is **saturated** by the
conventional baselines; the residual (L3–L5: precedence, cross-document
governance, logical reasoning) is **RETRIEVAL INSUFFICIENT**.

Deliverables: `CAPABILITY_ISOLATION.md`, `RELATIONSHIP_GRAPHS.md`, `TAXONOMY.md`,
`CAPABILITY_ISOLATION.json`.

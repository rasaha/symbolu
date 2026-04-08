"""
Ontology Package — agentic.ontology (CANONICAL)
================================================

Symbol-U Ontological components for semantic structure and projection.

Package Relationship (O1 — Source-of-Truth):
    agentic.ontology  — Primary architecture-level package. New integration
                         work, governance wiring, and framework adapters
                         should import from agentic.ontology.*.
    symbolu.ontology   — Parallel mirror used by existing tests, docs, and
                         the symbolu runtime stack. Kept in sync with
                         agentic.ontology. Not deprecated, but agentic.*
                         is the canonical target for new work.

Canonical sources within this package:
    OntologicalLayer   — agentic.ontology.layers.ontology_layer
    ProjectionContract — agentic.ontology.contracts.projection_contract
    LedgerAdapter      — agentic.ontology.ledger.ledger_adapter
    PhaseLayerMap      — agentic.ontology.router.phase_layer_map
    R1 Router          — agentic.ontology.router.ontological_router_r1
"""

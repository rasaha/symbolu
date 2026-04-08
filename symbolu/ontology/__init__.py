"""
Ontology Package — symbolu.ontology (MIRROR)
=============================================

Symbol-U Ontological components for semantic structure and projection.

Package Relationship (O1 — Source-of-Truth):
    agentic.ontology  — Primary architecture-level package. New integration
                         work, governance wiring, and framework adapters
                         should import from agentic.ontology.*.
    symbolu.ontology   — This package. Parallel mirror used by existing tests,
                         docs, and the symbolu runtime stack. Kept in sync
                         with agentic.ontology. Not deprecated, but
                         agentic.* is the canonical target for new work.

Canonical sources within this package:
    OntologicalLayer   — symbolu.ontology.layers.ontology_layer
    ProjectionContract — symbolu.ontology.contracts.projection_contract
    LedgerAdapter      — symbolu.ontology.ledger.ledger_adapter
    PhaseLayerMap      — symbolu.ontology.router.phase_layer_map
    R1 Router          — symbolu.ontology.router.ontological_router_r1
"""

"""
TAP-E3 — Relationship Truth.

Third TAP research layer. Given an IntentRecord (TAP-E1) and a RetrievalRecord (TAP-E2)
— both consumed through their frozen public interfaces — it determines WHAT RELATIONSHIP
each retrieved evidence unit establishes, with direction, polarity, modality,
temporality, scope, conditions, exceptions, conflicts, gaps, and provenance.

"Truth" here means a faithful representation of the relationship asserted, qualified,
negated, alleged, conditioned, or contradicted BY THE EVIDENCE — not metaphysical truth,
not governance applicability, not claim support, not a user answer. TAP-E1 and TAP-E2 are
never modified.

HONESTY: deterministic, pattern-based extraction over a synthetic corpus authored to be
parseable. Mechanism/construction validation only — not general NLU or external
generalization.
"""
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    SCHEMA_VERSION, RelationshipRecord, RelationshipAssertion, RelationshipConflict,
    RelationshipGap, validate_record,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import (
    ONTOLOGY_VERSION, RelationshipType,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.extractor import (
    RelationshipTruthLayer, ExtractionConfig, BASELINES, config,
)
__all__ = ["SCHEMA_VERSION", "ONTOLOGY_VERSION", "RelationshipRecord",
           "RelationshipAssertion", "RelationshipConflict", "RelationshipGap",
           "RelationshipType", "validate_record", "RelationshipTruthLayer",
           "ExtractionConfig", "BASELINES", "config"]
__version__ = "1.0.0"

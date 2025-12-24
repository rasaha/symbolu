# Phase-4: Composite Structure

Phase-4 is a composite phase within the Phase-1b → Phase-14 experimental pipeline. It consists of three sub-modules that work together but maintain strict separation of concerns.

## Phase-4 Sub-Modules

| Sub-Module | Location | Responsibility |
|------------|----------|----------------|
| **Phase-4A** | `symbolu/ontology/phase4a/` | Ontology Lookup (frozen varna × layer interaction resolution) |
| **Phase-4B** | `docs/experiments/phase4_transform_engine_v4_0.py` | Transform Engine (non-textual transformation of Phase-3 output) |
| **Phase-4C** | `symbolu/mechanical/pipeline/phase_po4/` | PO4 Planner Governance (proposal validation against PO3 allow-lists) |

## Critical Constraint: NO ONTOLOGY INFERENCE

**Phase-4A is the ONLY sub-module that may access ontology data.**

- Phase-4B and Phase-4C MUST NOT:
  - Load frozen ontology files directly
  - Infer polarity or manifestation values
  - Gap-fill missing ontology data
  - Interpret or smooth ontology language

If Phase-4B or Phase-4C need ontology data, they MUST call Phase-4A's lookup functions.

## Phase-4A: Ontology Lookup

**Location:** `symbolu/ontology/phase4a/`

**Files:**
- `__init__.py` - Package exports
- `errors.py` - Explicit error types (Phase4AError, Phase4AVarnaMissingError, etc.)
- `models.py` - Immutable dataclasses (VarnaLayerInteraction, OntologyValidationReport)
- `loader.py` - Frozen file loading and validation
- `lookup.py` - Deterministic lookup functions

**Frozen Ontology Files:**
- `docs/data/varna_bridge_map_v1.json`
- `docs/data/ontological_layers_v1.json`
- `docs/data/varna_layer_interaction_v1.json`

**Hard Invariants:**
- READ-ONLY: Never modifies frozen ontology files
- DETERMINISTIC: Same (varna, layer) input => identical output
- FAIL-FAST: Missing data triggers immediate error, never infers
- NO INFERENCE: No gap-filling, no polarity invention, no smoothing

**Usage:**
```python
from symbolu.ontology.phase4a import lookup_interaction, validate_ontology

# Validate on startup
validate_ontology()  # Raises Phase4AValidationError if inconsistent

# Lookup (varna, layer) -> interaction
result = lookup_interaction("ka", "O3_EXECUTION")
# Returns VarnaLayerInteraction with:
#   - manifestation_positive
#   - manifestation_negative
#   - distortion_vector
#   - sublimate_vector
```

## Phase-4B: Transform Engine

**Location:** `docs/experiments/phase4_transform_engine_v4_0.py`

**Purpose:** Non-textual transformation of Phase-3 output with strict isolation guarantees.

**Key Invariants:**
- TEST-ONLY: No production use
- NON-TEXTUAL: Only produces integers, bools, tuples
- DETERMINISTIC: Same input produces identical output
- NON-MUTATING: Never modifies input objects
- REVERSIBLE: Can recover Phase-3/2/1b output
- ZERO semantic inference (no NLP, no ML imports)

**CRITICAL:** Phase-4B MUST NOT perform ontology inference. If ontology data is needed, it MUST be obtained from Phase-4A.

## Phase-4C: PO4 Planner Governance

**Location:** `symbolu/mechanical/pipeline/phase_po4/`

**Purpose:** Governance layer that validates planner proposals against PO3 allow-lists.

**Key Components:**
- `PO4Resolver`: Deterministic validation engine
- `PlannerProposalEnvelope`: Output dataclass
- `ProposalStatus`: Enum (VALID, PARTIALLY_ALLOWED, BLOCKED)

**Responsibilities:**
- Capture what the planner is attempting to do
- Enforce consistency with PO3 allow-lists
- Prevent execution and side effects
- Provide full auditability

**CRITICAL:** Phase-4C MUST NOT perform ontology inference. If ontology data is needed, it MUST be obtained from Phase-4A.

## Relationship to Phase-14

Phase-4 is the **execution** checkpoint. Phase-14 (Enforcement + Audit) can:
- Assert Phase-4A did not invent ontology data
- Verify all outputs trace to frozen ontology files
- Flag violations deterministically

## Testing

**Phase-4A Tests:** `tests/ontology/test_phase4a_ontology_lookup.py` (50 tests)
**Phase-4B Tests:** `tests/core_phases/test_phase4_transform_v4_0.py`
**Phase-4C Tests:** Integration tests in `tests/` directory

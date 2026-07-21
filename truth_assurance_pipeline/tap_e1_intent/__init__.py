"""
TAP-E1 — Intent Analysis Layer (research & falsification phase).

A NEW, self-contained research track. It imports nothing from, and modifies nothing
in, any other track in this repository (no resolver, retriever, governance engine,
evidence packet, claim validator, ActionGate, or production TAP orchestration). It
lives entirely inside ``truth_assurance_pipeline/tap_e1_intent``.

SCOPE (Section 1-3): this layer converts a raw user request into a structured
``IntentRecord`` describing *what the user appears to want and what remains
unresolved*. It does NOT decide factual correctness, retrieval, policy
applicability, claim support, authorization, or the final response, and it never
answers the request it is analyzing.

HONESTY (Section 21): the corpus is SYNTHETIC and human-authored for this study; no
prior/frozen intent corpus exists in this repository and none is claimed as a
prerequisite. The "model interpretation" used by the V0/V1 ablations is a
DETERMINISTIC heuristic stand-in, not an LLM, so the whole study is reproducible.
Results therefore validate a *mechanism* on synthetic inputs only — they are not
evidence of real-world intent-understanding accuracy, downstream truth improvement,
or production readiness.
"""

from truth_assurance_pipeline.tap_e1_intent.schema import (
    SCHEMA_VERSION, IntentRecord, RawUserRequest, ConversationTurn, TaskType,
    InterpretationStatus, ProvenanceKind, ConstraintPolarity, AmbiguityClass,
    validate_schema,
)
from truth_assurance_pipeline.tap_e1_intent.interpreter import (
    IntentUnderstandingLayer, AblationConfig, ABLATIONS, config,
)

__all__ = [
    "SCHEMA_VERSION", "IntentRecord", "RawUserRequest", "ConversationTurn",
    "TaskType", "InterpretationStatus", "ProvenanceKind", "ConstraintPolarity",
    "AmbiguityClass", "validate_schema",
    "IntentUnderstandingLayer", "AblationConfig", "ABLATIONS", "config",
]

__version__ = "1.0.0"

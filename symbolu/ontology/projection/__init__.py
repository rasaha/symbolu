"""
Ontological Projection Engine
=============================

Read-only, deterministic, non-semantic projection engine for Symbol-U.

Hard Constraints:
    - Read-only: must not mutate any input objects
    - Deterministic: same snapshot + request => byte-identical response
    - Non-semantic: no NLP libs, no dictionaries, no embeddings
    - Fail-closed: any violation => eligible=False, artifacts=()

Forbidden imports: nltk, spacy, transformers, openai, anthropic, langchain, gensim, textblob
No randomness: no random, no time.time, no uuid
"""

from symbolu.ontology.projection.api_models import (
    FrozenSnapshot,
    InputRef,
    InputRefKind,
    OntologicalLayer,
    ProjectionProfile,
    OutputMode,
    Strictness,
    ProjectionOptions,
    ProjectionRequest,
    ProjectionResponse,
    InvariantsReport,
)
from symbolu.ontology.projection.engine import run_projection
from symbolu.ontology.projection.attest import attest_determinism

__all__ = [
    "FrozenSnapshot",
    "InputRef",
    "InputRefKind",
    "OntologicalLayer",
    "ProjectionProfile",
    "OutputMode",
    "Strictness",
    "ProjectionOptions",
    "ProjectionRequest",
    "ProjectionResponse",
    "InvariantsReport",
    "run_projection",
    "attest_determinism",
]

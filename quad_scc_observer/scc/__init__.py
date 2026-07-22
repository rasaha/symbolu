"""SCC observer: falsification study of a Semantic Coherence Controller as a read-only
post-inference correctness predictor.

SCC is treated as FOUR independent hypotheses -- S (semantic similarity), R (relational
preservation), E (evidence support), T (inference stability) -- each of which must independently
demonstrate predictive value BEYOND confidence, entailment, and evidence-grounding baselines
before any composite is considered. Nothing here changes the model or its inference.
"""

from . import _paths  # noqa: F401  (side-effect: put prior packages on sys.path)

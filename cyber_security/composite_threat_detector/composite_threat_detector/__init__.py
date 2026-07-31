"""Composite-Threat Detector — advisory, escalate-only assembly detection.

A deterministic, dependency-light (Python stdlib only) evidence producer that
watches a stream of *individually admissible* actions grouped by
``correlation_id``, extracts the capability "fragments" each contributes, and
reconstructs the composite offensive capability — the "story" — that a sequence
of innocuous steps is quietly assembling. The canonical illustration (from the
original prompt): a steel rod, a piston, and a trigger mechanism are each
harmless to acquire, but assembled they are a firearm.

This is an **advisory** layer. Its strongest output is a recommendation to
escalate a correlation to a human. It never admits, denies, or approves — it
plugs into the Action Gate as behavioral evidence per
``ACTION_GATE_SPECIFICATION.md`` §3/§12. See ``COMPOSITE_THREAT_DETECTION_SPEC.md``.

Quickstart
----------
    from composite_threat_detector import CompositeThreatMonitor, DIGITAL_ONTOLOGY
    mon = CompositeThreatMonitor(DIGITAL_ONTOLOGY)
    for action in action_stream:          # each already passed the per-action gate
        for finding in mon.observe(action):
            print(finding.signal, finding.story["headline"])
"""

from __future__ import annotations

__version__ = "1.0.0"

from . import fragments, narrative, signals  # noqa: F401
from .evidence import to_advisory_evidence
from .model import Fragment, FragmentInstance, Ontology, Recipe
from .monitor import CompositeThreatMonitor, Finding
from .recipes import (
    DIGITAL_ONTOLOGY,
    ONTOLOGIES,
    PHYSICAL_FIREARM_ONTOLOGY,
)
from .signals import ESCALATE, OBSERVE

__all__ = [
    "CompositeThreatMonitor",
    "Finding",
    "Fragment",
    "FragmentInstance",
    "Ontology",
    "Recipe",
    "DIGITAL_ONTOLOGY",
    "PHYSICAL_FIREARM_ONTOLOGY",
    "ONTOLOGIES",
    "to_advisory_evidence",
    "signals",
    "OBSERVE",
    "ESCALATE",
]

"""Composite Capability & Sequence-Risk Analyzer.

ActionGate controls individual actions; this analyzer detects when individually
acceptable actions collectively assemble a prohibited or high-risk capability.

The current implementation is:

* deterministic (replayable from an event log; no wall-clock, randomness,
  network, or LLM in the authoritative path);
* recipe- and ontology-driven (versioned capability recipes + entity linkage);
* advisory evidence-producing (emits ``OBSERVE`` / ``ESCALATE`` / ``UNAVAILABLE``
  only — never ALLOW/DENY/AUTHORIZE/BLOCK/EXECUTE; an ActionGate/workflow policy
  owns any binding consequence, see ``policy.py``);
* limited to *encoded* capability patterns;
* **not** a general intent-understanding system;
* **not** a learned anomaly detector.

The physical firearm example is retained only as a synthetic illustration. The
product target is enterprise AI-agent and infrastructure workflows. See
``COMPOSITE_THREAT_DETECTION_SPEC.md`` and
``COMPOSITE_SEQUENCE_RISK_EVALUATION_PLAN.md``.

Quickstart
----------
    from composite_threat_detector import SequenceRiskAnalyzer, DIGITAL_ONTOLOGY
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY)
    for action in admitted_action_stream:   # each already cleared the per-action gate
        for finding in az.observe(action):
            print(finding.signal, finding.explanation)
"""

from __future__ import annotations

__version__ = "2.0.0"

from . import (  # noqa: F401
    audit, benign, completion, financial, fragments, governance, linkage,
    narrative, ordering, policy, providers, purpose, signals, stories,
    story_bridge, storygraph, storyverdict,
)
from .analyzer import (
    CompositeThreatMonitor,
    Finding,
    IngestResult,
    RunReport,
    SequenceRiskAnalyzer,
)
from .analyzer import recover_from_audit
from .audit import AuditLog
from .durable_audit import DurableAuditLog
from .evidence import to_advisory_evidence
from .ledger import StateLimits, TimescalePolicy
from .providers import (
    BenignEvidenceProvider,
    FailingProvider,
    FixtureProvider,
    ProviderRegistry,
    ProviderUnavailable,
)
from .financial import FINANCIAL_ONTOLOGY
from .stories import (
    ACCOUNT_TAKEOVER_TRANSFER,
    DIGITAL_EXFILTRATION_STORY,
    STORY_LIBRARY,
)
from .storygraph import ObservedEvent, StoryGraph, StoryMatch
from .storygraph import match as story_match
from .storyverdict import BenignSummary, StoryVerdict, evaluate as story_evaluate
from .storyverdict import would_complete
from .linkage import (
    BY_ACTOR,
    BY_ACTOR_TARGET,
    BY_CASE,
    BY_CORRELATION,
    BY_TARGET,
    AssemblyKeySpec,
)
from .model import Fragment, FragmentInstance, Ontology, Recipe
from .policy import PolicyBinding
from .recipes import DIGITAL_ONTOLOGY, ONTOLOGIES, PHYSICAL_FIREARM_ONTOLOGY
from .signals import ESCALATE, OBSERVE, UNAVAILABLE

__all__ = [
    "SequenceRiskAnalyzer",
    "CompositeThreatMonitor",
    "Finding",
    "IngestResult",
    "RunReport",
    "Fragment",
    "FragmentInstance",
    "Ontology",
    "Recipe",
    "AssemblyKeySpec",
    "BY_ACTOR",
    "BY_CASE",
    "BY_TARGET",
    "BY_ACTOR_TARGET",
    "BY_CORRELATION",
    "TimescalePolicy",
    "StateLimits",
    "PolicyBinding",
    "ProviderRegistry",
    "FixtureProvider",
    "BenignEvidenceProvider",
    "AuditLog",
    "DurableAuditLog",
    "recover_from_audit",
    "FailingProvider",
    "ProviderUnavailable",
    "providers",
    "purpose",
    "ordering",
    "governance",
    "audit",
    "DIGITAL_ONTOLOGY",
    "PHYSICAL_FIREARM_ONTOLOGY",
    "ONTOLOGIES",
    "to_advisory_evidence",
    "signals",
    "policy",
    "OBSERVE",
    "ESCALATE",
    "UNAVAILABLE",
    # story-graph layer
    "StoryGraph",
    "StoryMatch",
    "ObservedEvent",
    "story_match",
    "story_evaluate",
    "would_complete",
    "BenignSummary",
    "StoryVerdict",
    "STORY_LIBRARY",
    "ACCOUNT_TAKEOVER_TRANSFER",
    "DIGITAL_EXFILTRATION_STORY",
    "FINANCIAL_ONTOLOGY",
    "stories",
    "storygraph",
    "storyverdict",
    "story_bridge",
    "financial",
]

"""Canonical public API for the StoryGraph capability.

This module is the **deliberately small, supported** public surface of
``ugence_storygraph``. Import from here (or the equivalently-exported top-level
``ugence_storygraph`` namespace) rather than reaching into internal modules.

Authority boundary: StoryGraph is **advisory / evidentiary only**. Everything
exported here emits ``OBSERVE`` / ``ESCALATE`` / ``UNAVAILABLE`` advisory
findings and evidence — never ``ALLOW`` / ``DENY`` / ``AUTHORIZE`` / ``BLOCK`` /
``EXECUTE``. A downstream ActionGate or workflow policy owns any binding
consequence.

Stability: every symbol below is ``PUBLIC_STABLE`` (see
``Project_documentation/repository/docs/migrations/storygraph/API_INVENTORY.md``). Internal module handles
(``storygraph``, ``storyverdict``, ``providers``, ``policy`` …) remain reachable
on the full ``ugence_storygraph`` namespace for backward compatibility but are
intentionally **not** promoted here.
"""

from __future__ import annotations

# Application / analyzer entrypoints
from .analyzer import (
    CompositeThreatMonitor,
    Finding,
    IngestResult,
    RunReport,
    SequenceRiskAnalyzer,
    recover_from_audit,
)

# Story-graph matcher (domain core)
from .storygraph import (
    MATCHER_SEMANTICS_VERSION,
    PARTIAL_ESCALATION_POLICY_VERSION,
    STORYGRAPH_SCHEMA_VERSION,
    DimensionResult,
    ObservedEvent,
    PartialEscalationPolicy,
    StoryGraph,
    StoryMatch,
)
from .storygraph import from_recipe as story_from_recipe
from .storygraph import match as story_match

# Witness / verdict / proposed-action simulation (non-mutating)
from .storyverdict import (
    BenignSummary,
    CompletionWitness,
    ProposedActionResult,
    StoryVerdict,
    completion_witness,
    evaluate_proposed_action,
    would_complete,
)
from .storyverdict import evaluate as story_evaluate

# Advisory evidence + authority-bounded binding
from .evidence import to_advisory_evidence
from .policy import PolicyBinding
from .signals import ESCALATE, OBSERVE, UNAVAILABLE

# Domain model
from .model import Fragment, FragmentInstance, Ontology, Recipe
from .recipes import DIGITAL_ONTOLOGY, ONTOLOGIES, PHYSICAL_FIREARM_ONTOLOGY
from .financial import FINANCIAL_ONTOLOGY
from .linkage import (
    BY_ACTOR,
    BY_ACTOR_TARGET,
    BY_CASE,
    BY_CORRELATION,
    BY_TARGET,
    AssemblyKeySpec,
)
from .ledger import StateLimits, TimescalePolicy

# Context providers (ports/adapters) + evidence ledgers
from .providers import (
    BenignEvidenceProvider,
    FailingProvider,
    FixtureProvider,
    ProviderRegistry,
    ProviderUnavailable,
)
from .audit import AuditLog
from .durable_audit import DurableAuditLog

# Legitimate (counter) stories + frozen reference graphs
from .legitimate import Authorization, CoverageRule, LegitimateStory
from .stories import (
    ACCOUNT_RECOVERY_STORY,
    ACCOUNT_TAKEOVER_TRANSFER,
    BANK_ASSISTED_TRANSFER_STORY,
    DIGITAL_EXFILTRATION_STORY,
    LEGITIMATE_LIBRARY,
    STORY_LIBRARY,
)

__all__ = [
    # analyzer
    "SequenceRiskAnalyzer", "CompositeThreatMonitor", "Finding", "IngestResult",
    "RunReport", "recover_from_audit",
    # matcher
    "StoryGraph", "StoryMatch", "DimensionResult", "ObservedEvent",
    "PartialEscalationPolicy", "story_match", "story_from_recipe", "story_evaluate",
    "MATCHER_SEMANTICS_VERSION", "PARTIAL_ESCALATION_POLICY_VERSION",
    "STORYGRAPH_SCHEMA_VERSION",
    # verdict / witness
    "evaluate_proposed_action", "completion_witness", "would_complete",
    "ProposedActionResult", "CompletionWitness", "StoryVerdict", "BenignSummary",
    # advisory evidence + authority-bounded binding
    "to_advisory_evidence", "PolicyBinding", "OBSERVE", "ESCALATE", "UNAVAILABLE",
    # domain model
    "Fragment", "FragmentInstance", "Ontology", "Recipe",
    "DIGITAL_ONTOLOGY", "FINANCIAL_ONTOLOGY", "PHYSICAL_FIREARM_ONTOLOGY", "ONTOLOGIES",
    "AssemblyKeySpec", "BY_ACTOR", "BY_CASE", "BY_TARGET", "BY_ACTOR_TARGET",
    "BY_CORRELATION", "TimescalePolicy", "StateLimits",
    # providers + ledgers
    "ProviderRegistry", "FixtureProvider", "BenignEvidenceProvider", "FailingProvider",
    "ProviderUnavailable", "AuditLog", "DurableAuditLog",
    # legitimate + reference stories
    "LegitimateStory", "Authorization", "CoverageRule", "ACCOUNT_RECOVERY_STORY",
    "BANK_ASSISTED_TRANSFER_STORY", "LEGITIMATE_LIBRARY", "STORY_LIBRARY",
    "ACCOUNT_TAKEOVER_TRANSFER", "DIGITAL_EXFILTRATION_STORY",
]

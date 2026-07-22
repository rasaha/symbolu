"""
TAP-E5 — Evidence Assembly.

The fifth TAP research layer. Given the four frozen upstream records — ``IntentRecord``
(TAP-E1), ``RetrievalRecord`` (TAP-E2), ``RelationshipRecord`` (TAP-E3), and
``GovernanceRecord`` (TAP-E4), all consumed through their frozen public interfaces — it
assembles exactly one deterministic ``EvidencePacket``: the smallest complete, dependency-
preserving, provenance-preserving object required by downstream claim validation.

E5 is a linker, not a reasoner. It does NOT determine truth, validate claims, generate
responses, retrieve evidence, perform governance reasoning, resolve conflicts, or fill gaps.
It never invents, summarizes, rewrites, or merges evidence.
"""

from truth_assurance_pipeline.tap_e5_evidence_assembly.assembler import (
    BASELINES, AssemblyConfig, EvidenceAssemblyLayer, config,
)
from truth_assurance_pipeline.tap_e5_evidence_assembly.packet_validator import validate_packet
from truth_assurance_pipeline.tap_e5_evidence_assembly.schema import (
    DependencyEdge, EvidencePacket, PacketConflict, PacketEvidence, PacketGap,
    PacketGovernance, PacketIntent, PacketRelationship, SCHEMA_VERSION,
)

__all__ = [
    "EvidenceAssemblyLayer", "AssemblyConfig", "BASELINES", "config",
    "EvidencePacket", "PacketIntent", "PacketEvidence", "PacketRelationship",
    "PacketGovernance", "PacketConflict", "PacketGap", "DependencyEdge",
    "validate_packet", "SCHEMA_VERSION",
]

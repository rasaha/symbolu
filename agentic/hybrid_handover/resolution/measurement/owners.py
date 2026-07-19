#!/usr/bin/env python3
"""
Metric ownership registry — every repaired metric answers exactly one question
and has exactly one owner stage. No metric may reward two capabilities.

Owners:
  Discovery          — did the required relationship (endpoints) exist?
  Classification     — given the endpoints, was the edge TYPE correct?
  Governance         — given a correct graph, was the governing/abstain decision right?
  PacketConstruction — given a correct governance decision, was the answer built right?
  SemanticParser     — shared lexical parsing (negation, node typing); NOT a resolver capability
  SafetyGate         — coverage/OCR abstention handled upstream, not by the resolver
"""

from __future__ import annotations

DISCOVERY = "Discovery"
CLASSIFICATION = "Classification"
GOVERNANCE = "Governance"
PACKET = "PacketConstruction"
PARSER = "SemanticParser"
SAFETY = "SafetyGate"

OWNERS = (DISCOVERY, CLASSIFICATION, GOVERNANCE, PACKET, PARSER, SAFETY)

# Each repaired metric -> its single owner.
METRIC_OWNER = {
    "discovery_recall": DISCOVERY,
    "discovery_precision": DISCOVERY,
    "classification_accuracy": CLASSIFICATION,
    "governance_accuracy_modeG": GOVERNANCE,
    "abstention_precision": GOVERNANCE,
    "abstention_recall": GOVERNANCE,
    "answer_coverage": GOVERNANCE,
    "selective_accuracy": GOVERNANCE,
    "packet_realization_accuracy_modeP": PACKET,
    "parser_negation_accuracy": PARSER,
    "parser_type_accuracy": PARSER,
    "coverage_abstention_accuracy": SAFETY,
}


def assert_single_owner():
    """Each metric maps to exactly one owner; owners are from the fixed set."""
    for metric, owner in METRIC_OWNER.items():
        assert owner in OWNERS, f"{metric} has unknown owner {owner}"
    # no metric name maps to more than one owner (dict guarantees this)
    return True

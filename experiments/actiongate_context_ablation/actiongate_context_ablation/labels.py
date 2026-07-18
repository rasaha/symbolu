"""Shared pass-1 annotation label constants (imported by builders + annotation)."""

from __future__ import annotations

ENVELOPE_CRITICAL = "envelope_critical"
DECISION_CRITICAL = "decision_critical"
ASSURANCE_CRITICAL = "assurance_critical"
STRUCTURE_CRITICAL = "structure_critical"
REDUNDANT = "redundant_decision_relevant"
NON_CRITICAL = "non_critical"
UNCERTAIN = "uncertain"

ANNOTATION_LABELS = frozenset({
    ENVELOPE_CRITICAL, DECISION_CRITICAL, ASSURANCE_CRITICAL, STRUCTURE_CRITICAL,
    REDUNDANT, NON_CRITICAL, UNCERTAIN})

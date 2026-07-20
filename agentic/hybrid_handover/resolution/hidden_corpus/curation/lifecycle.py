#!/usr/bin/env python3
"""Lifecycle enforcement — a candidate must traverse the states in order and end
in exactly one terminal state, with the artifacts each state requires."""

from __future__ import annotations

from .schema import canonical_path, validate_path


def check_candidate(cand) -> list[str]:
    """Return lifecycle issues for one candidate (empty = ok). `cand` is the
    projected candidate view with .decision, .has_author, .has_annotator,
    .has_adjudication, .accepted_graph."""
    issues = []
    decision = cand["decision"]
    if decision not in ("ACCEPTED", "REJECTED", "QUARANTINED"):
        issues.append(f"bad_terminal_state:{decision}")
        return issues
    path = canonical_path(decision)
    if not validate_path(path):
        issues.append("invalid_lifecycle_path")
    # every candidate must have all three role artifacts recorded
    if not cand["has_author"]:
        issues.append("missing_author_record")
    if not cand["has_annotator"]:
        issues.append("missing_annotator_record")
    if not cand["has_adjudication"]:
        issues.append("missing_adjudication_record")
    if decision == "ACCEPTED" and not cand["accepted_graph"]:
        issues.append("accepted_without_gold")
    if decision in ("REJECTED", "QUARANTINED") and not cand["rationale"]:
        issues.append("terminal_without_rationale")
    return issues

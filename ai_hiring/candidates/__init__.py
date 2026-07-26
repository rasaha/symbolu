"""Candidate identity and profile contracts (H1)."""

from __future__ import annotations

from .candidate import (
    CANDIDATE_TERMINAL_STATUSES,
    Candidate,
    CandidateProfile,
    CandidateStatus,
)

__all__ = [
    "Candidate",
    "CandidateProfile",
    "CandidateStatus",
    "CANDIDATE_TERMINAL_STATUSES",
]

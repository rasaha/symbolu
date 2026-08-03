"""Application lifecycle enum + transition rules (H1).

Structural lifecycle of a candidate's application to a requisition — **not** a
hiring decision. The binding accept/reject decision and any offer/rejection action
are governance concerns (H3/H4) and are deliberately absent here: this lifecycle
stops at the structural terminal states CLOSED / WITHDRAWN.
"""

from __future__ import annotations

from enum import Enum


class ApplicationStatus(str, Enum):
    RECEIVED = "RECEIVED"
    SCREENING = "SCREENING"
    ASSESSMENT = "ASSESSMENT"
    IN_REVIEW = "IN_REVIEW"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


APPLICATION_TERMINAL_STATUSES = frozenset(
    {ApplicationStatus.CLOSED, ApplicationStatus.WITHDRAWN}
)

# Non-terminal statuses count as an "active" application for duplicate prevention.
APPLICATION_ACTIVE_STATUSES = frozenset(
    {ApplicationStatus.RECEIVED, ApplicationStatus.SCREENING,
     ApplicationStatus.ASSESSMENT, ApplicationStatus.IN_REVIEW}
)

APPLICATION_ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.RECEIVED: frozenset(
        {ApplicationStatus.SCREENING, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED}
    ),
    ApplicationStatus.SCREENING: frozenset(
        {ApplicationStatus.ASSESSMENT, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED}
    ),
    ApplicationStatus.ASSESSMENT: frozenset(
        {ApplicationStatus.IN_REVIEW, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED}
    ),
    ApplicationStatus.IN_REVIEW: frozenset(
        {ApplicationStatus.CLOSED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.CLOSED: frozenset(),
    ApplicationStatus.WITHDRAWN: frozenset(),
}


def application_transition_allowed(src: ApplicationStatus, dst: ApplicationStatus) -> bool:
    return dst in APPLICATION_ALLOWED_TRANSITIONS.get(src, frozenset())

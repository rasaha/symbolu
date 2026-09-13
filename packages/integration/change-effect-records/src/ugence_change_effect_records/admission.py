"""Admission succession and the control register's transitions — **as data**.

Nothing here transitions anything, enforces anything or drives a machine. These are
the legal successions written down so that the Stage 3 boundary and a reviewer can
agree on what they are, and so that a table nobody can find is not the reason two
implementations disagree. The guarantee is the audit root's conditional append; this
module ships the shape of what it must enforce, and the refusal codes it produces.
"""

from __future__ import annotations

from types import MappingProxyType

from .vocabulary import AdmissionState, ClaimKind, ControlRegisterState

#: RESERVED to exactly one claim; a CANCEL claim to nothing, being terminal; an APPLY
#: claim to exactly one completion; OUTCOME_UNKNOWN to exactly one human resolution.
#: A function, not a relation: a second successor for one transition is a fork.
LEGAL_SUCCESSIONS: "MappingProxyType[str, tuple[str, ...]]" = MappingProxyType({
    "ADMISSION_RESERVE": ("ADMISSION_CLAIM",),
    "ADMISSION_CLAIM:APPLY": ("ADMISSION_COMPLETE",),
    "ADMISSION_CLAIM:CANCEL": (),
    "ADMISSION_COMPLETE:APPLIED": (),
    "ADMISSION_COMPLETE:FAILED": (),
    "ADMISSION_COMPLETE:OUTCOME_UNKNOWN": ("ADMISSION_RESOLVE",),
    "ADMISSION_RESOLVE": (),
})

#: The control register's complete transition table, per the recorded erratum to rule
#: version 4.2.10. Each entry is ``(from, to, by)``. A completion or a human resolution
#: moves the register **only** out of APPLY_COMMITTED; where a revocation took the
#: register first, the record is still written and the register stays REVOKED. Nothing
#: returns from REVOKED.
CONTROL_REGISTER_TRANSITIONS: tuple[tuple[str, str, str], ...] = (
    (ControlRegisterState.ACTIVE.value, ControlRegisterState.APPLY_COMMITTED.value,
     "an APPLY claim"),
    (ControlRegisterState.ACTIVE.value, ControlRegisterState.REVOKED.value,
     "a revocation, pre-commit"),
    (ControlRegisterState.APPLY_COMMITTED.value, ControlRegisterState.REVOKED.value,
     "a revocation, post-commit"),
    (ControlRegisterState.APPLIED.value, ControlRegisterState.REVOKED.value,
     "a revocation, post-commit"),
    (ControlRegisterState.APPLY_COMMITTED.value, ControlRegisterState.ACTIVE.value,
     "a FAILED completion or a human resolution to FAILED, winning before a revocation"),
    (ControlRegisterState.APPLY_COMMITTED.value, ControlRegisterState.APPLIED.value,
     "an APPLIED completion or a human resolution to APPLIED"),
    (ControlRegisterState.APPLY_COMMITTED.value, ControlRegisterState.APPLY_COMMITTED.value,
     "an OUTCOME_UNKNOWN completion: the register waits for a human"),
)

#: States terminal for the register. REVOKED is terminal absolutely; APPLIED is terminal
#: for the admission but a later revocation may still move it to REVOKED.
TERMINAL_CONTROL_STATES: frozenset[str] = frozenset({ControlRegisterState.REVOKED.value})

#: Which refusal a reservation meets, by the register's state. A reservation requires
#: ACTIVE; the three refusals are distinct and must not be reported as one another.
RESERVATION_REFUSAL_BY_STATE: "MappingProxyType[str, str]" = MappingProxyType({
    ControlRegisterState.REVOKED.value: "RESOLUTION_REVOKED",
    ControlRegisterState.APPLIED.value: "RESOLUTION_ALREADY_APPLIED",
    ControlRegisterState.APPLY_COMMITTED.value: "ADMISSION_IN_FLIGHT",
})

#: The recovery rule's outcomes, as data. Tag present and post-state matching, APPLIED;
#: tag absent and pre-state still matching, re-run; neither, OUTCOME_UNKNOWN with the
#: target blocked until a human resolves.
RECOVERY_OUTCOMES: "MappingProxyType[str, str]" = MappingProxyType({
    "TAG_PRESENT_POST_STATE_MATCHES": AdmissionState.APPLIED.value,
    "TAG_ABSENT_PRE_STATE_MATCHES": "RERUN_APPLICATION",
    "NEITHER": AdmissionState.OUTCOME_UNKNOWN.value,
})

#: The claim kinds, restated so a reader of this module alone sees that exactly one of
#: them commits execution.
COMMITTING_CLAIM: str = ClaimKind.APPLY.value
DOCUMENTARY_CLAIM: str = ClaimKind.CANCEL.value

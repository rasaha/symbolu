"""§2.3 verdict-custody port and its deterministic in-memory double (slice 3B-1).

Revision 20 ruling 1 commissions the port now and defers every deployment fact to D5: the
real endpoint, access-control lists, writer identities, encryption, key custody, retention
period and deletion rule are **not** bound here, and nothing in this module names them.

Revision 20 ruling 3 confines the double to tests. ``InMemoryVerdictCustody`` is never
genuine custody evidence and never authorises a real calibration or confirmatory run; only a
D5-approved adapter can do that, and none exists.

**Failure classification is by operation, never by exception class** (§2.3, owner ruling,
revision 4). The write call and the read-back call are distinct sites with distinct codes:
``RETENTION_WRITE_FAILED`` and ``RETENTION_VERIFY_FAILED``. Both are ratified names
(revision 10); revision 20 ruling 4 forbids adding a code without a ballot, so this module
adds none.

This module deliberately does **not** re-validate ``custody_ref`` syntax. The obligation-4
grammar (revision 19) lives with the prepared bundle, which commits the reference under
``index_digest`` before any custody call; the package must not import from ``experiments``,
and duplicating the grammar here would create a second authority that could drift from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Protocol, Tuple

from ._canon import payload, require_digest, require_nonblank
from .errors import PilotError, PilotErrorCode
from ugence_jcs import canonical_sha256_hex


@dataclass(frozen=True)
class VerdictCustodyRecord:
    """What a custody writer retained, addressed by the reference the prepared bundle
    committed. ``record_digest`` is settled from the canonical payload of the other fields, so
    a read-back that differs anywhere fails verification rather than being silently accepted."""

    custody_ref: str
    manifest_digest: str
    index_digest: str
    verdicts: Tuple[Tuple[str, str], ...]
    record_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.custody_ref, "VerdictCustodyRecord.custody_ref")
        require_digest(self.manifest_digest, "VerdictCustodyRecord.manifest_digest")
        require_digest(self.index_digest, "VerdictCustodyRecord.index_digest")
        if not isinstance(self.verdicts, tuple) or not self.verdicts:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "VerdictCustodyRecord.verdicts must be a non-empty tuple")
        seen = set()
        for entry in self.verdicts:
            if not isinstance(entry, tuple) or len(entry) != 2 or not all(isinstance(x, str) for x in entry):
                raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "each verdict is a (case_digest, verdict) pair of strings")
            require_digest(entry[0], "VerdictCustodyRecord.verdicts[].case_digest")
            require_nonblank(entry[1], "VerdictCustodyRecord.verdicts[].verdict")
            if entry[0] in seen:
                raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "a case digest appears twice in one custody record")
            seen.add(entry[0])
        if tuple(sorted(self.verdicts)) != self.verdicts:
            raise PilotError(PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT, "verdicts must be in ascending case-digest order")
        settled = canonical_sha256_hex(payload({
            "custody_ref": self.custody_ref,
            "manifest_digest": self.manifest_digest,
            "index_digest": self.index_digest,
            "verdicts": [list(v) for v in self.verdicts],
        }))
        if not self.record_digest:
            object.__setattr__(self, "record_digest", settled)
        elif self.record_digest != settled:
            raise PilotError(PilotErrorCode.RETENTION_VERIFY_FAILED, "VerdictCustodyRecord.record_digest does not cover its own content")


class VerdictCustodyPort(Protocol):
    """The narrow surface slice 3B needs. An adapter is append-only: it never rewrites a
    reference it already holds, so a second write to the same reference is a failure, not an
    update. D5 binds who may call it, where it writes and how long it retains."""

    def write(self, record: VerdictCustodyRecord) -> str:
        """Retain the record and return the ``record_digest`` actually stored.
        Raises ``PilotError(RETENTION_WRITE_FAILED)`` on any write failure."""
        ...

    def read_back(self, custody_ref: str) -> VerdictCustodyRecord:
        """Return what is stored at the reference.
        Raises ``PilotError(RETENTION_VERIFY_FAILED)`` when nothing is stored or it cannot be
        read back."""
        ...


def write_and_verify(port: VerdictCustodyPort, record: VerdictCustodyRecord) -> str:
    """Write, then read back and compare — the two-step revision 17 requires before a
    ``CalibrationResult`` may treat custody as established.

    The two calls are separate sites so a failure is classified by the operation that failed
    (§2.3): a write failure is never reported as a verification failure, and the reverse.
    Returns the verified ``record_digest``."""
    written = port.write(record)
    if written != record.record_digest:
        raise PilotError(PilotErrorCode.RETENTION_WRITE_FAILED, "custody writer returned a digest for other content")
    stored = port.read_back(record.custody_ref)
    if stored.record_digest != record.record_digest:
        raise PilotError(PilotErrorCode.RETENTION_VERIFY_FAILED, "custody read-back does not reproduce the written record")
    return stored.record_digest


class InMemoryVerdictCustody:
    """**Test-only** (revision 20 ruling 3). Deterministic, append-only, process-local. It
    satisfies ``VerdictCustodyPort`` structurally and is never genuine custody evidence: it
    persists nothing, enforces no access-control list, and holds no retention policy, all of
    which D5 must bind for a real adapter."""

    def __init__(self) -> None:
        self._records: Dict[str, VerdictCustodyRecord] = {}

    def write(self, record: VerdictCustodyRecord) -> str:
        if not isinstance(record, VerdictCustodyRecord):
            raise PilotError(PilotErrorCode.RETENTION_WRITE_FAILED, "custody write requires a VerdictCustodyRecord")
        if record.custody_ref in self._records:
            raise PilotError(PilotErrorCode.RETENTION_WRITE_FAILED, "custody is append-only; this reference is already written")
        self._records[record.custody_ref] = record
        return record.record_digest

    def read_back(self, custody_ref: str) -> VerdictCustodyRecord:
        stored = self._records.get(custody_ref)
        if stored is None:
            raise PilotError(PilotErrorCode.RETENTION_VERIFY_FAILED, f"nothing is retained at {custody_ref!r}")
        return stored

    def written_references(self) -> Tuple[str, ...]:
        """Test affordance: what this double holds, in deterministic order."""
        return tuple(sorted(self._records))


__all__ = [
    "VerdictCustodyRecord",
    "VerdictCustodyPort",
    "write_and_verify",
    "InMemoryVerdictCustody",
]

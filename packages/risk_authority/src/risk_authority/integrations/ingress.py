"""Trusted evidence-ingress seam (RA-5 spec §13; audit H-2).

**Why this exists.** An RA-5 evidence integrity digest proves *content
tamper-detection*, not *producer authenticity*: the digest is a plain content
hash computed by a public, deterministic function, so anyone constructing a
record can compute a matching digest. A valid digest therefore cannot establish
that evidence actually came from a legitimate producer. The ratified spec (§13)
*assumed* transport/producer trust and deferred cryptographic producer
attestation to FUTURE. The independent RA-5 audit (finding H-2) showed that this
implicit assumption let fabricated caller evidence enter the trusted-evidence
path merely by computing a valid digest.

**What this seam does.** It makes that trust assumption *explicit and
fail-closed* instead of implicit. Production mode requires a
:class:`TrustedEvidenceIngressPort`; evidence that does not arrive through an
authenticated producer channel — as judged by the injected implementation —
never reaches Evidence Admission. Computing a valid integrity digest is thus
*not sufficient* to enter the trusted path.

**What this seam is NOT.** Risk Authority does not implement authentication here.
There is no cryptography, signature, or attestation in this module (those remain
FUTURE, §13). RA owns only the neutral *contract*; the concrete channel verifier
is supplied by the deployment (e.g. mTLS / workload identity / an authenticated
API gateway) and injected. This module is stdlib-only and imports no provider or
integration code — ``risk_authority`` stays a leaf.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ..domain.evidence import ControlEvidenceRecord

__all__ = ["TrustedEvidenceIngressPort"]


@runtime_checkable
class TrustedEvidenceIngressPort(Protocol):
    """Decides whether a record arrived over an authenticated producer channel.

    Returning ``True`` asserts *"this evidence was presented by an authenticated
    producer over a trusted channel"* — a judgement the deployment makes out of
    band, never derivable from the (self-computable) integrity digest. A record
    the port does not trust is dropped before admission and can back no control
    (fail closed). Any exception is treated as untrusted by the caller.
    """

    def is_trusted(self, evidence: ControlEvidenceRecord, *, now: datetime) -> bool: ...

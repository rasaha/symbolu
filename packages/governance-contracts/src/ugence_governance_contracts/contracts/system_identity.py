"""Neutral assessed-system identity — *which exact system was assessed*.

The provider-neutral answer to a question every governance engine eventually
asks: **which exact system, at which version, in which configuration, does this
result describe?** A determination that cannot say so is worthless — a
favourable result for one model/prompt/tool configuration could be replayed for
another, or for another tenant's subject entirely.

This module defines **contracts and structural invariants only**. It is not a
system registry, a deployment authority, an attestation service, a verifier, or
a policy authority. It grants no permission and mints no authority.

Placement (UVI ADR §20)
-----------------------
``AssessedSystemBinding`` is listed in the ADR's type-by-type ownership table
under **governance-contracts** — a neutral seam, not an engine-local type. It
lives here so that every engine binds the *same* system identity rather than
minting a parallel one. Consumers re-export it; they never redefine it.

Keeping it neutral is what makes that possible: every field is a **platform-
neutral primitive** (``str`` / ``datetime``). Nothing here imports or references
a UVI policy shape, a readiness enum, an indicator type, an assessment context,
an authority, or any higher-level package. Comparing a binding against an
engine's own context — a readiness ``AssessmentContext``, say — is the *engine's*
adapter responsibility, performed against these stable ids and digests.

What a binding proves
---------------------
Exactly one thing: **internal consistency and digest-bound identity.** Two
different systems, versions, configurations, tenants, subjects, contexts or
manifest digests cannot share a :meth:`canonical_digest`, so a result bound to
one binding is mechanically detectable when replayed under another.

What it does **not** prove
--------------------------
* that the named system was ever really deployed, or that the running system
  matches this description;
* that ``configuration_digest`` was computed over the real configuration;
* that ``system_manifest_ref`` resolves to anything, or that
  ``system_manifest_digest`` is that artifact's true content digest;
* that ``canonical_subject_context_ref`` names a real, authorized subject
  context;
* any attestation, approval, signature or authority provenance whatsoever.

:attr:`AssessedSystemBinding.authenticity_status` is therefore a permanently
``STRUCTURAL_UNVERIFIED`` **property**, not a field: there is no constructor
argument, assignment or subclass hook that can raise it. Raising it requires a
ratified system-binding verifier, which no merged contract defines.

Deferred references, deliberately opaque
----------------------------------------
``canonical_subject_context_ref`` and ``system_manifest_ref`` /
``system_manifest_digest`` are **opaque tokens**, exactly as UVI ADR §16
prescribes. The canonical neutral ``SubjectContext`` is Risk-Authority-owned and
**unmerged** (ADR D-14, §26.2), and ``SystemManifest``'s home is an **open owner
decision** (§26.3). This package mints **neither** — it references them by value
+ digest so that, once either is ratified, the token points at it with no shape
change here. The minimum system/version/configuration coordinates are carried
directly because ADR §23.5 requires determinations to "bind exact identity +
digests … preventing swap/replay/misattribution", and that guarantee cannot wait
on an unratified artifact.

``deployment_environment_ref`` is likewise an opaque token: no environment
enumeration is ratified anywhere in the repository, so none is invented.

Instants are canonicalized in UTC
---------------------------------
Two timezone-aware datetimes that name the **same instant** are equal in Python
and hash alike, so two bindings that differ only in the offset their instants
were written with are the *same* binding. Canonicalization must agree: every
aware datetime participating in :meth:`AssessedSystemBinding.canonical_bytes` is
re-expressed in UTC — ``astimezone(timezone.utc)``, a pure arithmetic shift —
*before* the package's established sorted-key JSON serialization runs. So
``2026-08-17T10:00:00+00:00``, ``2026-08-17T15:30:00+05:30`` and
``2026-08-17T06:00:00-04:00`` produce byte-identical canonical bytes and one
digest, while a genuinely different instant still produces a different one.

Naive datetimes remain **rejected**, at construction and again at
canonicalization. A value with no offset does not name an instant, and guessing
UTC for it would silently invent one; that is a rejection, never a default.

This is a *correction*, not a second protocol: there is no legacy-digest
fallback, dual acceptance rule, alias or translation layer. Bindings already
expressed in UTC keep their exact pre-correction canonical bytes and digest —
normalizing a UTC instant to UTC is the identity. A binding previously written
with a non-UTC offset now canonicalizes to the UTC-normalized value it should
always have had, so any digest recorded for such a representation changes to
that value.

Nothing here is money, cost, benefit, ROI, an approval, or a deployment
authorization.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

__all__ = [
    "SystemIdentityContractError",
    "SystemBindingAuthenticityStatus",
    "AssessedSystemBinding",
]


class SystemIdentityContractError(ValueError):
    """A structural system-identity invariant was violated at construction.

    Subclasses :class:`ValueError`, mirroring
    :class:`~.evidence.EvidenceContractError`, so existing ``ValueError``
    handling still catches it. It signals a *structural* rejection — never a
    claim that authenticity verification was performed.
    """


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; module-local, mirroring evidence.py)
# --------------------------------------------------------------------------- #
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise SystemIdentityContractError(
            f"{name} must be a string (got {type(value).__name__})"
        )
    return value


def _require_nonempty(value: object, name: str) -> str:
    text = _require_str(value, name)
    if not text.strip():
        raise SystemIdentityContractError(f"{name} must be a non-empty string")
    return text


def _validate_digest(value: object, name: str, *, required: bool) -> None:
    text = _require_str(value, name)
    if not text:
        if required:
            raise SystemIdentityContractError(f"{name} is required (sha-256 hex digest)")
        return
    if not _SHA256_RE.match(text):
        raise SystemIdentityContractError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )


def _require_tzaware(dt: object, name: str) -> None:
    if not isinstance(dt, datetime):
        raise SystemIdentityContractError(f"{name} must be a datetime")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise SystemIdentityContractError(f"{name} must be timezone-aware")


def _to_utc(value: datetime, name: str) -> datetime:
    """Re-express an aware instant in UTC; reject a naive one.

    ``astimezone(timezone.utc)`` with an **explicit** target is pure arithmetic:
    it subtracts the value's own ``utcoffset()``. No system clock, locale or
    environment variable is consulted, and the local timezone is never inferred
    — unlike the zero-argument ``astimezone()``, which is deliberately not used.

    For a value already at offset ``+00:00`` this is the identity, which is what
    keeps every pre-existing all-UTC canonical byte sequence and digest stable.
    """

    _require_tzaware(value, name)
    return value.astimezone(timezone.utc)


def _canonical_payload(obj) -> dict:
    """The dataclass payload with every instant normalized to UTC.

    Normalization happens **here**, on the plain payload, immediately before the
    package's established serialization step — the serializer itself is
    untouched. Every field of :class:`AssessedSystemBinding` is a scalar, so a
    single pass over the payload reaches every datetime that participates in
    canonicalization, including any added later.
    """

    payload = dataclasses.asdict(obj)
    owner = type(obj).__name__
    for name, value in payload.items():
        if isinstance(value, datetime):
            payload[name] = _to_utc(value, f"{owner}.{name}")
    return payload


def _canonical_bytes(obj) -> bytes:
    """Deterministic canonical JSON bytes over the UTC-normalized payload.

    The package's established fingerprint pattern (sorted-key, tight separators,
    ``default=str``) — identical inputs yield identical bytes.
    """

    payload = _canonical_payload(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return encoded.encode("utf-8")


def _canonical_digest(obj) -> str:
    """Deterministic sha-256 over :func:`_canonical_bytes`."""

    return hashlib.sha256(_canonical_bytes(obj)).hexdigest()


# --------------------------------------------------------------------------- #
# How much a binding actually proves
# --------------------------------------------------------------------------- #
class SystemBindingAuthenticityStatus(str, Enum):
    """How much an :class:`AssessedSystemBinding` actually proves.

    The enum has exactly **one** member because exactly one thing is provable
    today. Constructing a binding is a *structural* act: it records which system,
    version and configuration a caller says was assessed, and makes swapping any
    of them detectable through the canonical digest. It does **not** establish
    that the named system was really deployed, that the configuration digest was
    computed over the real configuration, or that any of it was attested by an
    authority.

    A second member (an authority-verified status) is deliberately **absent**:
    admitting one would require a ratified system-binding verifier, which no
    merged contract defines. Adding it later is additive.
    """

    #: The binding is internally consistent and digest-bound; external
    #: authenticity was never established and is not claimed.
    STRUCTURAL_UNVERIFIED = "STRUCTURAL_UNVERIFIED"


#: Identity coordinates that must be present and non-blank. Leading/trailing
#: whitespace is stripped before validation and the stripped form is stored, so
#: ``" sys-a "`` and ``"sys-a"`` are the same system and share a digest.
_REQUIRED_IDENTITY_FIELDS = (
    "binding_id",
    "tenant_id",
    "subject_id",
    "context_id",
    "system_id",
    "system_version",
    "configuration_id",
)

#: Optional opaque reference tokens. Normalized the same way; absence is "".
_OPTIONAL_REF_FIELDS = (
    "canonical_subject_context_ref",
    "system_manifest_ref",
    "deployment_environment_ref",
)


@dataclass(frozen=True)
class AssessedSystemBinding:
    """The exact system/configuration one assessment is about.

    Every field participates in :meth:`canonical_digest`, so the complete binding
    identity — not merely the system id — distinguishes one binding from another.
    All fields are **platform-neutral scalars**: there is no caller-owned list or
    mapping to mutate, no engine-specific type to depend on, and the dataclass is
    frozen, so no post-construction mutation can alter the content or the digest.

    ``context_id`` / ``context_digest`` name the assessment context this binding
    belongs to **by stable id and canonical digest**, never by embedding it. The
    consuming engine compares those two values against its own context object;
    that adapter step is the engine's responsibility, which is exactly what keeps
    this contract neutral and cycle-free.
    """

    binding_id: str
    tenant_id: str
    subject_id: str
    context_id: str
    context_digest: str
    system_id: str
    system_version: str
    configuration_id: str
    configuration_digest: str
    canonical_subject_context_ref: str = ""
    system_manifest_ref: str = ""
    system_manifest_digest: str = ""
    deployment_environment_ref: str = ""
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        for name in _REQUIRED_IDENTITY_FIELDS:
            value = _require_nonempty(getattr(self, name), f"AssessedSystemBinding.{name}")
            object.__setattr__(self, name, value.strip())

        for name in ("context_digest", "configuration_digest"):
            _validate_digest(
                getattr(self, name), f"AssessedSystemBinding.{name}", required=True
            )

        for name in _OPTIONAL_REF_FIELDS:
            value = _require_str(getattr(self, name), f"AssessedSystemBinding.{name}")
            object.__setattr__(self, name, value.strip())

        _validate_digest(
            self.system_manifest_digest,
            "AssessedSystemBinding.system_manifest_digest",
            required=False,
        )
        # A manifest reference without its content digest is a floating
        # reference, and a digest without a reference names nothing. ADR §16
        # binds the pair; neither half alone is admissible.
        if bool(self.system_manifest_ref) != bool(self.system_manifest_digest):
            raise SystemIdentityContractError(
                "AssessedSystemBinding.system_manifest_ref and .system_manifest_digest are "
                "co-required: a manifest reference must be digest-bound, and a digest must "
                "name the artifact it was computed over"
            )

        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"AssessedSystemBinding.{name}")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and not self.effective_from < self.effective_to
        ):
            raise SystemIdentityContractError(
                "AssessedSystemBinding effective period is half-open "
                "[effective_from, effective_to): effective_from must precede effective_to"
            )

    # ------------------------------------------------------------------ #
    # Honest, non-settable status
    # ------------------------------------------------------------------ #
    @property
    def authenticity_status(self) -> SystemBindingAuthenticityStatus:
        """Always ``STRUCTURAL_UNVERIFIED``.

        A read-only property, not a field: there is no assignment, constructor
        argument or subclass hook that can raise it. Raising it requires a
        ratified system-binding verifier, which no merged contract defines.
        """

        return SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED

    @property
    def authenticity_verified(self) -> bool:
        """Always ``False`` — constructing a binding attests nothing."""

        return False

    @property
    def system_configuration_identity(self) -> tuple[str, str, str, str]:
        """The tuple that must not be reused across systems or configurations."""

        return (
            self.system_id,
            self.system_version,
            self.configuration_id,
            self.configuration_digest,
        )

    def is_effective_at(self, instant: datetime) -> bool:
        """Half-open ``[effective_from, effective_to)`` membership.

        An absent bound is open on that side, so a binding with no declared
        period is effective at every instant. The instant is always an explicit
        caller input — the system clock is never read.
        """

        _require_tzaware(instant, "AssessedSystemBinding.is_effective_at.instant")
        if self.effective_from is not None and instant < self.effective_from:
            return False
        if self.effective_to is not None and instant >= self.effective_to:
            return False
        return True

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over.

        Every aware datetime is re-expressed in UTC before serialization, so two
        bindings that are ``==`` — including ones whose instants were written
        with different offsets — produce **byte-identical** output:

        .. code-block:: python

            if binding_a == binding_b:
                assert binding_a.canonical_bytes() == binding_b.canonical_bytes()

        A naive datetime is rejected here as it is at construction; UTC is never
        assumed for a value that names no instant.
        """

        return _canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the **complete** binding identity.

        Two bindings that differ in any coordinate — including the system
        version, the configuration digest, the manifest digest or the tenant —
        produce different digests, and two bindings that are equal produce the
        same one. It is an identity fingerprint, not evidence, not a signature
        and not an authenticity proof.
        """

        return _canonical_digest(self)

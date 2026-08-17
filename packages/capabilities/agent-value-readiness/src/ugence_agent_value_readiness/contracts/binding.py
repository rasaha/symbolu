"""``AssessedSystemBinding`` — *which exact system configuration was assessed* (M-3R.3).

A readiness determination that does not say **which** system it describes is
worthless: a favourable result for one model/prompt/tool configuration could be
replayed for another, or for another tenant's subject entirely. This contract is
the answer to the first of M-3R.3's two questions (ADR §16, D-14, §23.5).

What it proves
--------------
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
* that ``canonical_subject_context_ref`` names a real, authorized subject context;
* any attestation, approval, signature or authority provenance whatsoever.

:attr:`authenticity_status` is therefore a permanently
``STRUCTURAL_UNVERIFIED`` **property**, not a field: there is no constructor
argument, assignment or subclass hook that can raise it. Raising it requires a
ratified system-binding verifier, which no merged contract defines.

Deferred references, deliberately opaque
----------------------------------------
``canonical_subject_context_ref`` and ``system_manifest_ref`` /
``system_manifest_digest`` are **opaque tokens**, exactly as ADR §16 prescribes.
The canonical neutral ``SubjectContext`` is RA-owned and **unmerged** (ADR D-14,
§26.2), and ``SystemManifest``'s home is an **open owner decision** (§26.3). This
package therefore mints **neither**: it references them by value + digest so that,
once either is ratified, the token points at it with no shape change here. The
minimum system/version/configuration coordinates are carried directly because
§23.5 requires determinations to "bind exact identity + digests … preventing
swap/replay/misattribution", and that guarantee cannot wait on an unratified
artifact.

``deployment_environment_ref`` is likewise an opaque token: no environment
enumeration is ratified anywhere in the repository, so none is invented.

Nothing here is money, cost, benefit, ROI, an approval, or a deployment
authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ._util import canonical_digest, require_nonempty, require_tzaware, validate_digest
from .enums import SystemBindingAuthenticityStatus
from .errors import ReadinessContractError

__all__ = ["AssessedSystemBinding"]

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


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ReadinessContractError(f"{name} must be a string (got {type(value).__name__})")
    return value


@dataclass(frozen=True)
class AssessedSystemBinding:
    """The exact system/configuration one readiness assessment is about.

    Every field participates in :meth:`canonical_digest`, so the complete binding
    identity — not merely the system id — distinguishes one binding from another.
    All fields are scalars: there is no caller-owned list or mapping to mutate,
    and the dataclass is frozen, so no post-construction mutation can alter the
    content or the digest.
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
            value = _require_str(getattr(self, name), f"AssessedSystemBinding.{name}")
            require_nonempty(value, f"AssessedSystemBinding.{name}")
            object.__setattr__(self, name, value.strip())

        for name in ("context_digest", "configuration_digest"):
            value = _require_str(getattr(self, name), f"AssessedSystemBinding.{name}")
            validate_digest(value, f"AssessedSystemBinding.{name}", required=True)

        for name in _OPTIONAL_REF_FIELDS:
            value = _require_str(getattr(self, name), f"AssessedSystemBinding.{name}")
            object.__setattr__(self, name, value.strip())

        manifest_digest = _require_str(
            self.system_manifest_digest, "AssessedSystemBinding.system_manifest_digest"
        )
        validate_digest(
            manifest_digest, "AssessedSystemBinding.system_manifest_digest", required=False
        )
        # A manifest reference without its content digest is a floating
        # reference, and a digest without a reference names nothing. ADR §16
        # binds the pair; neither half alone is admissible.
        if bool(self.system_manifest_ref) != bool(manifest_digest):
            raise ReadinessContractError(
                "AssessedSystemBinding.system_manifest_ref and .system_manifest_digest are "
                "co-required: a manifest reference must be digest-bound, and a digest must "
                "name the artifact it was computed over"
            )

        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                require_tzaware(value, f"AssessedSystemBinding.{name}")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and not self.effective_from < self.effective_to
        ):
            raise ReadinessContractError(
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

        require_tzaware(instant, "AssessedSystemBinding.is_effective_at.instant")
        if self.effective_from is not None and instant < self.effective_from:
            return False
        if self.effective_to is not None and instant >= self.effective_to:
            return False
        return True

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the **complete** binding identity.

        Two bindings that differ in any coordinate — including the system
        version, the configuration digest, the manifest digest or the tenant —
        produce different digests. It is an identity fingerprint, not evidence,
        not a signature and not an authenticity proof.
        """

        return canonical_digest(self)

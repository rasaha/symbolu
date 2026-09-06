"""The composition root: a verified resolution in, a compilable draft out.

This module owns exactly one capability neither neighbour has alone — it **derives**
the authoritative-source reference from a resolution Policy Authority verified, so a
compiled release is bound to an issuance that was actually resolved rather than one
a caller asserted. Everything else it does is delegation:

* Policy Authority resolves, authenticates and decides validity. Its answer is
  never second-guessed here, only required to be ``RESOLVED``.
* The compiler validates and binds. Its gates are never waived here.
* The operator supplies trust — registry, verifiers, adapters — already
  constructed. This package builds no key, no verifier and no registry, and reads
  no environment, filesystem or clock of its own.
* A policy family supplies the pack builder (ruling CR-2). This root ships none.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from ugence_policy_authority.api import (
    PolicyResolutionStatus,
    framed_body_digest,
    resolve_policy,
)
from ugence_policy_workflow_compiler.api import (
    SCHEMA_VERSION_V2,
    AuthoritativeSourceRef,
    PolicyPack,
    check_authoritative_source,
    compute_pack_digest,
)

from .errors import AuthoritativeCompilationError, RefusalCode
from .models import AuthoritativeCompilationDraft

#: A family-supplied mapping from a resolved policy artifact to a structured pack.
#: Ruling CR-2: a policy family knows how its own artifact becomes structured
#: policy; this root does not, and a generic mapping would be exactly the inference
#: the architecture refuses elsewhere.
PolicyPackBuilder = Callable[[Any], PolicyPack]


def _refuse(code: RefusalCode, message: str) -> "AuthoritativeCompilationError":
    return AuthoritativeCompilationError(code, message)


def _derive_source_ref(resolution: Any) -> AuthoritativeSourceRef:
    """The **only** place an :class:`AuthoritativeSourceRef` is constructed.

    Every field comes from the resolution Policy Authority returned. No caller input
    reaches this function, and an AST test asserts this is the sole construction
    site — the derivation prohibition is enforced by the suite, not by convention.
    """
    record = resolution.record
    coordinate = record.coordinate
    return AuthoritativeSourceRef(
        policy_family=coordinate.policy_family,
        policy_id=coordinate.policy_id,
        policy_version=coordinate.version,
        content_digest=_as_compiler_digest(coordinate.content_digest),
        scope=coordinate.scope,
        tenant_id=coordinate.tenant_id,
        record_id=record.record_id,
        policy_body_digest=_as_compiler_digest(record.policy_body_digest),
        issuing_authority_id=record.issuing_authority_id,
        key_id=record.key_id,
        signature_alg=record.signature_alg,
        signature_b64=_b64(record.signature),
        approving_authority_id=record.approving_authority_id,
        approval_ref=record.approval_ref,
        approval_digest=_as_compiler_digest(record.approval_digest),
        issued_at=_isoformat(record.issued_at),
        authority_protocol=record.authority_protocol,
        authority_protocol_version=record.authority_protocol_version,
        resolved_as_of=_isoformat(resolution.as_of),
        historical=bool(resolution.historical),
    )


#: Policy Authority states digests as bare lowercase 64-char hex; the compiler
#: states them as ``sha256:<hex>``. Translating between two neighbours' conventions
#: is exactly what a composition root is for — changing either package's convention
#: to suit the other would be worse. The translation is total and lossless: the hex
#: is carried through unaltered, only prefixed.
_COMPILER_DIGEST_PREFIX = "sha256:"


def _as_compiler_digest(value: str) -> str:
    """Render a Policy Authority digest in the compiler's prefixed form."""
    if not value or value.startswith(_COMPILER_DIGEST_PREFIX):
        return value
    return f"{_COMPILER_DIGEST_PREFIX}{value}"


def _b64(signature: bytes) -> str:
    import base64

    return base64.b64encode(bytes(signature)).decode("ascii")


def _isoformat(value: Optional[datetime]) -> str:
    return value.isoformat() if value is not None else ""


class AuthoritativePolicyCompilationService:
    """Orchestrates Policy Authority and the compiler. Owns no authority itself."""

    def draft_from_resolution(
        self,
        resolution: Any,
        *,
        requested_coordinate: Any,
        pack_builder: Optional[PolicyPackBuilder],
        allow_historical: bool = False,
    ) -> AuthoritativeCompilationDraft:
        """Validate a resolution and derive a compilable draft from it.

        Split out from :meth:`draft_from_coordinate` so the five requirements can be
        exercised — and refused — without a registry, a key or a clock.
        """
        if pack_builder is None:
            raise _refuse(
                RefusalCode.NO_PACK_BUILDER,
                "a policy family must supply the mapping from its resolved artifact "
                "to a structured policy_pack.v2 pack; this root ships none",
            )

        # 1. Policy Authority's answer is required, never reinterpreted.
        if resolution.status is not PolicyResolutionStatus.RESOLVED:
            raise _refuse(
                RefusalCode.POLICY_NOT_RESOLVED,
                f"resolution status is {resolution.status.value} "
                f"(reason {resolution.reason.value}); only RESOLVED may be compiled",
            )

        # 2. The answer must be about the question that was asked.
        resolved_coordinate = resolution.record.coordinate
        if requested_coordinate is not None and resolved_coordinate != requested_coordinate:
            raise _refuse(
                RefusalCode.RESOLVED_COORDINATE_MISMATCH,
                "the resolved coordinate is not the one requested",
            )

        # 3. The descriptor triple is all-or-none by Policy Authority's own rule; a
        #    partial triple looks checkable and is not, so absence is a refusal.
        triple = (
            resolution.descriptor_adapter_id,
            resolution.descriptor_policy_type,
            resolution.descriptor_canonical_projection,
        )
        if any(part is None for part in triple):
            raise _refuse(
                RefusalCode.INCOMPLETE_RESOLUTION_DESCRIPTOR,
                "the resolution carries no complete descriptor projection, so the "
                "policy body digest cannot be re-verified on this side",
            )

        # 4. Re-verify the body digest with Policy Authority's OWN canonicalization.
        #    Reimplementing it here would create a second authority semantics whose
        #    drift would surface as a false failure on a valid artifact.
        recomputed = framed_body_digest(
            adapter_id=triple[0], policy_type=triple[1], projection=triple[2]
        )
        if recomputed != resolution.record.policy_body_digest:
            raise _refuse(
                RefusalCode.BODY_DIGEST_MISMATCH,
                "the recomputed framed body digest does not match the issuance "
                "record; the artifact and its record disagree",
            )

        # 5. A historical answer describes the past and never implies current
        #    validity, so compiling one must be asked for explicitly.
        if resolution.historical and not allow_historical:
            raise _refuse(
                RefusalCode.HISTORICAL_RESOLUTION_NOT_REQUESTED,
                "the resolution is historical; it describes the past and does not "
                "imply current validity",
            )

        pack = pack_builder(resolution.policy)
        if not isinstance(pack, PolicyPack) or pack.schema_version != SCHEMA_VERSION_V2:
            raise _refuse(
                RefusalCode.BUILDER_RETURNED_UNUSABLE_PACK,
                f"the pack builder must return a {SCHEMA_VERSION_V2} PolicyPack",
            )
        if pack.authoritative_source is not None:
            raise _refuse(
                RefusalCode.AUTHORED_SOURCE_REFUSED,
                "the builder supplied an authoritative source; on the authoritative "
                "path the reference is derived from the resolution, never authored",
            )

        source = _derive_source_ref(resolution)
        bound = pack.model_copy(update={"authoritative_source": source})

        # The compiler's own carriage checks run here too, so a derived reference
        # that is somehow malformed is refused by this root rather than downstream.
        diagnostics = check_authoritative_source(bound, required=True)
        if diagnostics:
            raise _refuse(
                RefusalCode.BODY_DIGEST_MISMATCH
                if any("DIGEST" in d.code for d in diagnostics)
                else RefusalCode.INCOMPLETE_RESOLUTION_DESCRIPTOR,
                "; ".join(d.message for d in diagnostics),
            )

        return AuthoritativeCompilationDraft(
            pack=bound,
            pack_digest=compute_pack_digest(bound),
            authoritative_source=source,
            resolution=resolution,
        )

    def draft_from_coordinate(
        self,
        *,
        coordinate: Any,
        as_of: datetime,
        registry: Any,
        signature_verifier: Any,
        adapters: Any,
        pack_builder: Optional[PolicyPackBuilder],
        approval_verifier: Any = None,
        historical_resolution: Any = None,
        allow_historical: bool = False,
        expected_reference_tenant_id: str = "",
        resolver: Optional[Callable[..., Any]] = None,
    ) -> AuthoritativeCompilationDraft:
        """Resolve a coordinate under injected trust, then derive the draft.

        Trust arrives already constructed: this package builds no registry, no key
        and no verifier. ``resolver`` exists so the flow can be exercised offline
        against a hand-assembled resolution; it defaults to Policy Authority's own
        ``resolve_policy`` and is never a place to substitute a different authority
        in production.
        """
        resolve = resolver or resolve_policy
        kwargs = dict(
            reference=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=as_of,
            registry=registry,
            signature_verifier=signature_verifier,
            adapters=adapters,
            approval_verifier=approval_verifier,
        )
        if historical_resolution is not None:
            kwargs["historical_resolution"] = historical_resolution
        resolution = resolve(**kwargs)
        return self.draft_from_resolution(
            resolution,
            requested_coordinate=coordinate,
            pack_builder=pack_builder,
            allow_historical=allow_historical,
        )


__all__ = [
    "AuthoritativePolicyCompilationService",
    "PolicyPackBuilder",
]

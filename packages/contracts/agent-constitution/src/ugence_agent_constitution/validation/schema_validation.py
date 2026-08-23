"""Schema-layer validation: can this build read the payload at all?

Runs before any semantic rule, and refuses to hand a half-understood payload to
the semantic layer. Three gates, in order:

1. The payload is a mapping. Anything else is INVALID.
2. It declares a schema version, and this build recognizes that version *for the
   kind being asked about*. An unrecognized version is INDETERMINATE — the shape
   is unknown, so nothing further can honestly be said about it. A retired version
   is INVALID, because a shape this build deliberately dropped is known-wrong
   rather than unknown.
3. It parses into the frozen model for that kind, with unknown fields refused.

Gate 2 has one named special case. A payload declaring the *manifest* schema, when
the caller asked for a *constitution*, is reported as
:data:`~.codes.DRAFT_IS_NOT_A_CONSTITUTION` rather than as a generic wrong-kind
mismatch. The confusion it names — treating a draft as if ratification had
happened — is the specific thing the two-type split exists to prevent, and a
caller reading a generic type error may well just fix the type annotation.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Tuple

from pydantic import ValidationError

from ..compatibility import SchemaCompatibility, schema_compatibility
from ..models.common import ArtifactKind
from ..models.constitution import AgentConstitution
from ..models.contract import DeveloperImplementationContract
from ..models.manifest import AgentRoleManifest
from ..models.subject import ConformanceSubject
from ..version import AGENT_ROLE_MANIFEST_V1, SUPPORTED_SCHEMA_VERSIONS
from . import codes
from .outcomes import ValidationFinding, indeterminate, invalid

#: The one mapping from artifact kind to the frozen model that implements it.
MODEL_FOR_KIND = {
    ArtifactKind.AGENT_ROLE_MANIFEST: AgentRoleManifest,
    ArtifactKind.AGENT_CONSTITUTION: AgentConstitution,
    ArtifactKind.DEVELOPER_IMPLEMENTATION_CONTRACT: DeveloperImplementationContract,
    ArtifactKind.CONFORMANCE_SUBJECT: ConformanceSubject,
}


def _kind_declaring(declared: str) -> Optional[ArtifactKind]:
    """Return the artifact kind whose supported schema set contains ``declared``."""
    for candidate in ArtifactKind:
        if declared in SUPPORTED_SCHEMA_VERSIONS.get(candidate.value, ()):
            return candidate
    return None


def _error_path(error: Mapping[str, Any]) -> str:
    loc = error.get("loc") or ()
    return ".".join(str(part) for part in loc) or "<root>"


def validate_schema(
    payload: Any, kind: ArtifactKind
) -> Tuple[Optional[Any], List[ValidationFinding]]:
    """Parse ``payload`` as ``kind``.

    Returns ``(artifact, findings)``. ``artifact`` is ``None`` whenever the payload
    could not be understood well enough to construct — the semantic layer is then
    skipped entirely rather than run against a guess.
    """
    findings: List[ValidationFinding] = []

    if not isinstance(payload, Mapping):
        findings.append(
            invalid(
                codes.PAYLOAD_NOT_A_MAPPING,
                "<root>",
                f"expected a mapping payload, got {type(payload).__name__}",
            )
        )
        return None, findings

    declared = payload.get("schema_version")
    if not isinstance(declared, str) or not declared.strip():
        findings.append(
            invalid(
                codes.SCHEMA_VERSION_MISSING,
                "schema_version",
                "payload declares no schema version; the shape it claims to be is "
                "not inferable from its fields and will not be guessed",
            )
        )
        return None, findings

    compatibility = schema_compatibility(kind, declared)
    if compatibility is SchemaCompatibility.RETIRED:
        findings.append(
            invalid(
                codes.SCHEMA_VERSION_RETIRED,
                "schema_version",
                f"schema version {declared!r} was retired by this build",
            )
        )
        return None, findings
    if compatibility is SchemaCompatibility.UNRECOGNIZED:
        if (
            kind is ArtifactKind.AGENT_CONSTITUTION
            and declared == AGENT_ROLE_MANIFEST_V1
        ):
            findings.append(
                invalid(
                    codes.DRAFT_IS_NOT_A_CONSTITUTION,
                    "schema_version",
                    "payload is an agent role manifest: a draft, which carries no "
                    "authority and has not been ratified. A draft is never readable "
                    "as a constitution; ratification produces a separate artifact.",
                )
            )
            return None, findings
        other = _kind_declaring(declared)
        if other is not None:
            findings.append(
                invalid(
                    codes.SCHEMA_VERSION_WRONG_KIND,
                    "schema_version",
                    f"schema version {declared!r} is the {other.value} shape, not "
                    f"{kind.value}; a known shape read as the wrong kind is wrong, "
                    "not merely unrecognized",
                )
            )
            return None, findings
        findings.append(
            indeterminate(
                codes.SCHEMA_VERSION_UNRECOGNIZED,
                "schema_version",
                f"schema version {declared!r} is not recognized for {kind.value}; "
                "this build cannot decide whether the payload is well-formed",
            )
        )
        return None, findings

    model = MODEL_FOR_KIND[ArtifactKind(kind)]
    try:
        artifact = model.model_validate(dict(payload))
    except ValidationError as exc:
        for error in exc.errors():
            findings.append(
                invalid(
                    codes.SCHEMA_STRUCTURE_INVALID,
                    _error_path(error),
                    f"{error.get('type', 'invalid')}: {error.get('msg', '')}",
                )
            )
        return None, findings

    return artifact, findings


__all__ = ["MODEL_FOR_KIND", "validate_schema"]

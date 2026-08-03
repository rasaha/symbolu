"""Provenance, secret, determinism, and schema validation.

* Every substantive object must cite provenance; an object without provenance is
  ``PROPOSED_ONLY`` and surfaced as ``REVIEW_REQUIRED`` (never silently admitted).
* Runtime secrets embedded in a pack are a hard error.
* Non-deterministic values in policy logic (floats/NaN) are a hard error.
* Unsupported schema versions are fatal.
"""

from __future__ import annotations

import math
import re
from typing import List

from ..models.common import (
    SUPPORTED_SCHEMA_VERSIONS,
    ObjectType,
    PolicyObject,
)
from ..models.policy_pack import PolicyPack
from ..serialization import canonical_json
from .errors import Severity, ValidationDiagnostic

#: Object types that do not themselves require provenance (structural/derived).
_PROVENANCE_EXEMPT = frozenset(
    {
        ObjectType.SOURCE_DOCUMENT,
        ObjectType.HUMAN_APPROVAL_RECORD,
        ObjectType.APPROVAL_STEP,
        ObjectType.TEST_SCENARIO,
        ObjectType.REPLAY_CASE,
    }
)

#: Field names that suggest a secret value (an object field named like this must
#: not carry a value).
_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|api[_-]?key|access[_-]?key|private[_-]?key|bearer[_-]?token|"
    r"client[_-]?secret)s?$",
    re.IGNORECASE,
)
#: Secret-shaped VALUE markers. A pack should carry non-secret handles, never these.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+ey[A-Za-z0-9._-]{10,}"),
    re.compile(r"\b(password|secret|api[_-]?key|token)\s*[:=]\s*\S+", re.IGNORECASE),
)
#: Fields that legitimately name a *handle* — exempt from the key-name check, but
#: still scanned for secret-shaped values.
_HANDLE_FIELDS = frozenset({"credential_handle", "signature_reference"})


def _diag(code, severity, message, object_id="", remediation="") -> ValidationDiagnostic:
    return ValidationDiagnostic(
        code=code, severity=severity, message=message,
        object_id=object_id, suggested_remediation=remediation,
    )


def check_schema_version(pack: PolicyPack) -> List[ValidationDiagnostic]:
    if pack.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return [
            _diag(
                "UNSUPPORTED_SCHEMA_VERSION",
                Severity.FATAL,
                f"schema version '{pack.schema_version}' is not supported "
                f"(supported: {', '.join(SUPPORTED_SCHEMA_VERSIONS)})",
                object_id=pack.pack_id,
                remediation="migrate the pack to a supported schema version",
            )
        ]
    return []


def check_provenance(pack: PolicyPack) -> List[ValidationDiagnostic]:
    known_sources = {d.object_id for d in pack.source_documents}
    out: List[ValidationDiagnostic] = []
    for obj in pack.all_objects():
        if obj.object_type in _PROVENANCE_EXEMPT:
            continue
        if not obj.provenance_refs:
            out.append(
                _diag(
                    "MISSING_PROVENANCE",
                    Severity.REVIEW_REQUIRED,
                    f"object '{obj.object_id}' ({obj.object_type.value}) has no "
                    "provenance; it is PROPOSED_ONLY and excluded from synthesis "
                    "until a reviewer approves the gap",
                    object_id=obj.object_id,
                    remediation="cite a SourceDocument/ProvenanceReference or record a reviewed gap",
                )
            )
            continue
        for ref in obj.provenance_refs:
            if known_sources and ref not in known_sources:
                out.append(
                    _diag(
                        "DANGLING_PROVENANCE_REFERENCE",
                        Severity.ERROR,
                        f"object '{obj.object_id}' cites unknown source '{ref}'",
                        object_id=obj.object_id,
                        remediation="register the source as a SourceDocument",
                    )
                )
    return out


def _scan_secrets(obj: PolicyObject) -> List[ValidationDiagnostic]:
    out: List[ValidationDiagnostic] = []
    data = obj.model_dump(mode="python")
    for key, value in data.items():
        if isinstance(value, str) and value and key not in _HANDLE_FIELDS:
            if _SECRET_KEY_PATTERN.search(key):
                out.append(
                    _diag(
                        "EMBEDDED_SECRET",
                        Severity.ERROR,
                        f"object '{obj.object_id}' field '{key}' is named like a secret",
                        object_id=obj.object_id,
                        remediation="store a non-secret handle; never embed secrets in a pack",
                    )
                )
        if isinstance(value, str) and any(p.search(value) for p in _SECRET_VALUE_PATTERNS):
            out.append(
                _diag(
                    "EMBEDDED_SECRET",
                    Severity.ERROR,
                    f"object '{obj.object_id}' field '{key}' embeds a secret-shaped value",
                    object_id=obj.object_id,
                    remediation="store a non-secret handle; never embed secrets in a pack",
                )
            )
    return out


def check_secrets(pack: PolicyPack) -> List[ValidationDiagnostic]:
    out: List[ValidationDiagnostic] = []
    for obj in pack.all_objects():
        out.extend(_scan_secrets(obj))
    return out


def check_determinism(pack: PolicyPack) -> List[ValidationDiagnostic]:
    """Reject non-deterministic values (floats, NaN, inf) in policy logic.

    Policy amounts are integer minor units; floating-point values invite
    non-reproducible comparisons and are refused.
    """
    out: List[ValidationDiagnostic] = []

    def scan(value, obj_id):
        if isinstance(value, float):
            note = "NaN/inf" if (math.isnan(value) or math.isinf(value)) else "float"
            out.append(
                _diag(
                    "NON_DETERMINISTIC_VALUE",
                    Severity.ERROR,
                    f"object '{obj_id}' contains a {note} value in policy logic",
                    object_id=obj_id,
                    remediation="use integer minor units or an exact string, not a float",
                )
            )
        elif isinstance(value, dict):
            for v in value.values():
                scan(v, obj_id)
        elif isinstance(value, (list, tuple)):
            for v in value:
                scan(v, obj_id)

    for obj in pack.all_objects():
        scan(obj.model_dump(mode="python"), obj.object_id)
    # Guard against non-canonicalizable content (defensive; canonical_json must
    # never raise for a well-typed pack).
    try:
        canonical_json.dumps(list(pack.all_objects()))
    except TypeError as exc:  # pragma: no cover - defensive
        out.append(
            _diag(
                "NON_DETERMINISTIC_VALUE",
                Severity.ERROR,
                f"pack contains non-serializable content: {exc}",
                object_id=pack.pack_id,
            )
        )
    return out


def check_all(pack: PolicyPack) -> List[ValidationDiagnostic]:
    out: List[ValidationDiagnostic] = []
    out.extend(check_schema_version(pack))
    out.extend(check_provenance(pack))
    out.extend(check_secrets(pack))
    out.extend(check_determinism(pack))
    return out

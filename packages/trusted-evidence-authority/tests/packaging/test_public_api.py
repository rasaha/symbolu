"""The documented public API agrees with the actual package surface.

Rebuilds the public-API description from the imported
``ugence_trusted_evidence_authority.api`` module and asserts it equals the
committed ``public_api.json``. Catches an accidental export addition or removal,
an enum-value drift, a dataclass-field change, a field **reordering**, or a
changed pinned constant that the machine-readable snapshot does not reflect.

The same builder is used by the distribution verifier against the *installed*
wheel, so the source tree, the manifest, the wheel and an isolated installed
runtime are all held to one description.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_trusted_evidence_authority as pkg
from ugence_trusted_evidence_authority import api

_PKG_ROOT = pathlib.Path(pkg.__file__).resolve().parent
# tests/packaging/ -> tests/ -> packages/trusted-evidence-authority/
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PUBLIC_API_JSON = _DIST_ROOT / "public_api.json"


def _kind(obj) -> str:
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return "enum"
        if issubclass(obj, Exception):
            return "exception"
        if dataclasses.is_dataclass(obj):
            return "dataclass"
        return "class"
    if callable(obj):
        return "function"
    return "constant"


def _constant_value(obj):
    """A JSON-representable, order-preserving rendering of a pinned constant."""

    if isinstance(obj, str):
        return obj
    if isinstance(obj, (tuple, list)):
        return [getattr(v, "value", v) for v in obj]
    if isinstance(obj, frozenset):
        return sorted(getattr(v, "value", v) for v in obj)
    if hasattr(obj, "items"):  # the lifecycle transition mapping
        return {
            getattr(k, "value", k): sorted(getattr(v, "value", v) for v in value)
            for k, value in obj.items()
        }
    return repr(obj)


def actual_surface(module=api, version=None) -> dict:
    symbols: dict = {}
    for name in sorted(module.__all__):
        if name == "__version__":
            continue
        obj = getattr(module, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            entry["values"] = [m.value for m in obj]
        elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        elif entry["kind"] == "constant":
            entry["value"] = _constant_value(obj)
        symbols[name] = entry
    return {
        "distribution": "ugence-trusted-evidence-authority",
        "namespace": "ugence_trusted_evidence_authority",
        "package_version": version or pkg.__version__,
        "curated_api_module": "ugence_trusted_evidence_authority.api",
        "symbols": symbols,
    }


def test_documented_public_api_matches_actual():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    documented.pop("note", None)
    actual = actual_surface()
    for key in ("distribution", "namespace", "package_version", "curated_api_module"):
        assert documented[key] == actual[key], key
    assert documented["symbols"] == actual["symbols"]


def test_curated_api_names_match_module_all():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    expected = {n for n in api.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_top_level_reexports_match_the_curated_api():
    """The package root and ``api`` export the same names (plus ``api`` itself)."""

    assert set(pkg.__all__) - {"api"} == set(api.__all__)
    for name in api.__all__:
        if name == "__version__":
            continue
        assert getattr(pkg, name) is getattr(api, name), name


def test_all_is_explicit_and_free_of_duplicates():
    for module in (pkg, api):
        assert isinstance(module.__all__, list)
        assert len(set(module.__all__)) == len(module.__all__)


def test_no_private_name_is_exported():
    for name in api.__all__:
        assert name == "__version__" or not name.startswith("_"), name


def test_py_typed_marker_present():
    assert (_PKG_ROOT / "py.typed").is_file(), "PEP 561 py.typed marker missing"


def test_the_manifest_records_the_package_version():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    assert documented["package_version"] == pkg.__version__ == "0.2.0"


def test_pinned_constants_are_snapshotted_with_their_values():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    constants = {
        name: entry
        for name, entry in documented["symbols"].items()
        if entry["kind"] == "constant"
    }
    assert set(constants) == {
        # -- TEV-1 (frozen) -------------------------------------------------
        "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
        "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
        "EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN",
        "EVIDENCE_TRUST_STAGE_ORDER",
        "RECEIPT_REPORTABLE_TRUST_STAGES",
        "EVIDENCE_LIFECYCLE_TRANSITIONS",
        "TRUSTED_EVIDENCE_REFUSAL_REASONS",
        # -- TEV-2 ------------------------------------------------------------
        "TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS",
        "TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS",
        "TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1",
        "TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1",
        "TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN",
        "TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN",
        "SIGNED_INPUT_LENGTH_PREFIX_BYTES",
        "ED25519_SEED_SIZE",
        "ED25519_PUBLIC_KEY_SIZE",
        "ED25519_SIGNATURE_SIZE",
        "TRUST_ANCHOR_RECORD_DIGEST_DOMAIN",
        "SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1",
        "SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1",
        "SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN",
        "SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN",
        "TRUSTED_EVIDENCE_PROTOCOL_V1_ID",
        "TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION",
        "TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN",
        "RECEIPT_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    }
    for entry in constants.values():
        assert "value" in entry


def test_the_two_tev1_digest_domains_are_snapshotted_and_unchanged():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    identity_domain = documented["symbols"]["EVIDENCE_IDENTITY_DIGEST_DOMAIN"]["value"]
    receipt_domain = documented["symbols"][
        "EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN"
    ]["value"]
    assert identity_domain != receipt_domain
    assert identity_domain == api.EVIDENCE_IDENTITY_DIGEST_DOMAIN
    assert receipt_domain == api.EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
    # Byte-for-byte what TEV-1 merged. Changing either would change every
    # existing digest, including the four pinned vectors.
    assert identity_domain == (
        "ugence.trusted-evidence-authority/evidence-identity/v1"
    )
    assert receipt_domain == (
        "ugence.trusted-evidence-authority/"
        "evidence-verification-receipt-payload/v1"
    )


def test_every_digest_and_signing_domain_is_distinct():
    """§26.6 — a signature or digest valid in one domain verifies in no other."""

    domains = [
        api.EVIDENCE_IDENTITY_DIGEST_DOMAIN,
        api.EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
        api.TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
        api.SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
        api.SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
        api.TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
        api.TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
        api.TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    ]
    assert len(set(domains)) == len(domains)
    for domain in domains:
        assert domain.startswith("ugence.trusted-evidence-authority/"), domain
        assert domain.endswith("/v1"), domain

    # No benchmark domain is minted: BR-1/BR-2 own that byte space.
    for name in api.__all__:
        assert "BENCHMARK" not in name.upper(), name


#: The 29 curated symbols TEV-1 merged. Every one must still be exported, with
#: the same kind, the same fields in the same order and the same enum members in
#: the same order — asserted by the manifest comparison above and pinned here by
#: name so a removal is caught even if the manifest were regenerated wholesale.
TEV1_CURATED_SYMBOLS = [
    "TrustedEvidenceContractError",
    "TrustedEvidenceCanonicalizationError",
    "TrustedEvidenceLifecycleError",
    "ApplicabilityDeclaration",
    "DeclaredVerificationOutcome",
    "EvidenceLifecycleState",
    "EvidenceStructuralStatus",
    "EvidenceTrustStage",
    "TrustedEvidenceRefusalReason",
    "ApplicabilityCoordinate",
    "EvidenceSchemaRef",
    "EvidenceObservation",
    "EvidenceScopeBinding",
    "EvidenceClaimBinding",
    "EvidenceProvenanceChain",
    "CanonicalEvidenceIdentity",
    "EvidenceVerificationRequest",
    "EvidenceVerificationReceiptPayload",
    "canonical_bytes",
    "canonical_digest",
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    "TRUSTED_EVIDENCE_CANONICALIZATION_VERSION",
    "EVIDENCE_IDENTITY_DIGEST_DOMAIN",
    "EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN",
    "EVIDENCE_TRUST_STAGE_ORDER",
    "RECEIPT_REPORTABLE_TRUST_STAGES",
    "EVIDENCE_LIFECYCLE_TRANSITIONS",
    "TRUSTED_EVIDENCE_REFUSAL_REASONS",
]


def test_all_twenty_nine_tev1_symbols_remain_exported():
    """Backward compatibility, pinned by name rather than by count."""

    assert len(TEV1_CURATED_SYMBOLS) == 29
    exported = set(api.__all__)
    missing = [n for n in TEV1_CURATED_SYMBOLS if n not in exported]
    assert missing == [], missing
    # And they remain importable from the package root, not only from ``api``.
    for name in TEV1_CURATED_SYMBOLS:
        assert getattr(pkg, name) is getattr(api, name), name


def test_the_curated_surface_size_is_pinned():
    """A symbol added or removed without updating the manifest fails here."""

    exported = [n for n in api.__all__ if n != "__version__"]
    assert len(exported) == 87
    tev2_only = set(exported) - set(TEV1_CURATED_SYMBOLS)
    assert len(tev2_only) == 58


def test_enum_member_order_is_snapshotted_not_just_the_member_set():
    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    values = documented["symbols"]["TrustedEvidenceRefusalReason"]["values"]
    assert values == [m.value for m in api.TrustedEvidenceRefusalReason]
    assert values[0] == "TRUSTED_EVIDENCE_MISSING"
    # TEV-1's nineteen keep their exact ordinal positions; TEV-2 appended.
    assert values[18] == "TRUSTED_EVIDENCE_INDETERMINATE"
    assert values[19] == "TRUSTED_EVIDENCE_ENVELOPE_MALFORMED"
    assert values[-1] == "TRUSTED_EVIDENCE_RECEIPT_EXPIRED"
    assert len(values) == 40


def test_every_tev1_dataclass_keeps_its_exact_field_order():
    """A reordered field changes canonical bytes and therefore every digest."""

    documented = json.loads(_PUBLIC_API_JSON.read_text(encoding="utf-8"))
    expected = {
        "EvidenceSchemaRef": ["schema_id", "schema_version"],
        "ApplicabilityCoordinate": ["declaration", "value"],
        "EvidenceObservation": [
            "producer_id", "collected_at", "observed_from", "observed_to",
            "issuer_id",
        ],
        "EvidenceScopeBinding": [
            "tenant_id", "assessment_context_ref", "assessment_context_digest",
            "subject_ref", "assessment_purpose_ref", "usage_scope_ref",
            "assessed_system_applicability", "assessed_system_binding_ref",
            "assessed_system_binding_digest",
        ],
        "EvidenceClaimBinding": [
            "applicability", "claim_ref", "metric_ref", "unit",
            "measurement_semantics_ref",
        ],
        "EvidenceProvenanceChain": ["chain_ref", "custody_refs"],
        "CanonicalEvidenceIdentity": [
            "evidence_id", "evidence_type", "schema", "content_digest",
            "observation", "scope", "claim", "provenance", "lifecycle_state",
            "geography", "domain", "intended_outcome", "valid_from", "valid_to",
        ],
        "EvidenceVerificationRequest": [
            "evidence", "expected_content_digest", "expected_tenant_id",
            "expected_assessment_context_ref",
            "expected_assessment_context_digest", "expected_subject_ref",
            "expected_assessment_purpose_ref", "expected_usage_scope_ref",
            "as_of", "requested_trust_stages",
            "expected_assessed_system_binding_ref",
            "expected_assessed_system_binding_digest",
        ],
        "EvidenceVerificationReceiptPayload": [
            "receipt_id", "schema", "source_evidence_identity_digest",
            "evidence_content_digest", "verification_request_digest", "scope",
            "verified_at", "verifier_authority_id", "verifier_key_id",
            "verification_protocol_id", "verification_protocol_version",
            "declared_outcome", "declared_cleared_stages",
            "declared_unattempted_stages", "declared_refusal_reasons",
            "evidence_valid_from", "evidence_valid_to", "receipt_valid_from",
            "receipt_valid_to",
        ],
    }
    for name, fields in expected.items():
        assert documented["symbols"][name]["fields"] == fields, name
        assert [
            f.name for f in dataclasses.fields(getattr(api, name))
        ] == fields, name


def test_every_tev1_enum_keeps_its_exact_member_order():
    expected = {
        "ApplicabilityDeclaration": ["APPLICABLE", "NOT_APPLICABLE"],
        "DeclaredVerificationOutcome": [
            "DECLARED_ADMITTED", "DECLARED_REFUSED", "DECLARED_INDETERMINATE",
        ],
        "EvidenceLifecycleState": [
            "PRODUCED", "SUBMITTED", "RETAINED", "EXPIRED", "REVOKED",
        ],
        "EvidenceStructuralStatus": ["STRUCTURAL_UNVERIFIED"],
        "EvidenceTrustStage": [
            "STRUCTURALLY_CONSTRUCTIBLE", "CRYPTOGRAPHICALLY_AUTHENTIC",
            "PROVENANCE_VERIFIED", "CONTEXT_SYSTEM_BOUND", "CURRENTLY_VALID",
            "POLICY_SUFFICIENT",
        ],
    }
    for name, members in expected.items():
        assert [m.value for m in getattr(api, name)] == members, name

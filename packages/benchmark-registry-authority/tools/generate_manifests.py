#!/usr/bin/env python3
"""Regenerate the four committed machine-readable manifests from the live surface.

Run:
    PYTHONPATH=packages/benchmark-registry-authority/src:\
packages/benchmark-registry/src:packages/benchmark-registry-authority/tests \
        python packages/benchmark-registry-authority/tools/generate_manifests.py

Everything a manifest can state is **derived from the live package** — the
sealed contract-type registry, ``api.__all__``, the actual dataclass fields, the
actual derived properties, the actual constructor gates. Only genuinely
editorial facts (which transition a payload represents, which later milestone
owns the corresponding authority-issued result) are carried as literals here,
and ``tests/packaging/test_inventories.py`` re-derives all of it and compares,
so a committed manifest can never drift from the surface it describes.

This generator is developer tooling. It is **not** part of the distribution: it
lives outside ``src/`` and is excluded from both the wheel and the sdist.
"""

from __future__ import annotations

import dataclasses
import json
import typing
import pathlib
from enum import EnumMeta

PKG = pathlib.Path(__file__).resolve().parent.parent

import _builders as fixtures  # noqa: E402
from ugence_benchmark_registry_authority import api  # noqa: E402
from ugence_benchmark_registry_authority.contracts.canonical import (  # noqa: E402
    _contract_type_registry_snapshot,
    canonical_bytes,
    canonical_digest,
)

DISTRIBUTION = "ugence-benchmark-registry-authority"
NAMESPACE = "ugence_benchmark_registry_authority"

# --------------------------------------------------------------------------- #
# Editorial metadata: the facts a manifest cannot read off the live surface.
# --------------------------------------------------------------------------- #
TRANSITION_METADATA = {
    "BenchmarkSubmissionRecordPayload": {
        "transition_represented": "initial -> SUBMITTED",
        "required_predecessor_state": None,
        "required_predecessor_declared_outcome": None,
    },
    "BenchmarkAdmissionDecisionPayload": {
        "transition_represented": (
            "SUBMITTED -> ADMITTED (declared_outcome=ADMITTED); "
            "SUBMITTED -> REJECTED (declared_outcome=REJECTED)"
        ),
        "required_predecessor_state": "SUBMITTED",
        "required_predecessor_declared_outcome": None,
    },
    "BenchmarkPostAdmissionRejectionEventPayload": {
        "transition_represented": "ADMITTED -> REJECTED",
        "required_predecessor_state": "ADMITTED",
        "required_predecessor_declared_outcome": "ADMITTED",
    },
    "BenchmarkRegistrationEventPayload": {
        "transition_represented": "ADMITTED -> REGISTERED",
        "required_predecessor_state": "ADMITTED",
        "required_predecessor_declared_outcome": "ADMITTED",
    },
    "BenchmarkRevocationEventPayload": {
        "transition_represented": "REGISTERED -> REVOKED",
        "required_predecessor_state": "REGISTERED",
        "required_predecessor_declared_outcome": None,
    },
    "BenchmarkConflictRecordPayload": {
        "transition_represented": (
            "none — outside the linear chain; records a refused attempt and "
            "appends no successor"
        ),
        "required_predecessor_state": None,
        "required_predecessor_declared_outcome": None,
    },
    "BenchmarkRegistrySnapshotAssertion": {
        "transition_represented": (
            "none — a caller's assertion about current state, not a move"
        ),
        "required_predecessor_state": None,
        "required_predecessor_declared_outcome": None,
    },
    "BenchmarkTransitionPlan": {
        "transition_represented": (
            "any transition the closed relation admits, as a plan only — a "
            "plan is not the transition, and BR-2B cannot perform one"
        ),
        "required_predecessor_state": None,
        "required_predecessor_declared_outcome": None,
    },
    "BenchmarkTransitionRefusal": {
        "transition_represented": (
            "none — records a move that would not be admissible against the "
            "nested assertion"
        ),
        "required_predecessor_state": None,
        "required_predecessor_declared_outcome": None,
    },
}

LATER_MILESTONE = {
    "BenchmarkPublisherSubmissionEnvelope": (
        "BR-2C — publisher trust and signature verification. The audited "
        "Ed25519 verifier that could establish publisher authenticity."
    ),
    "BenchmarkApprovalEnvelope": (
        "BR-2C — the approval-verification boundary that could establish "
        "approval authenticity."
    ),
    "BenchmarkRevocationEnvelope": (
        "BR-2C — revocation signature verification under an entitled anchor."
    ),
    "BenchmarkSubmissionRecordPayload": (
        "BR-2D — the authority-issued submission record appended by the "
        "durable registry authority's append-only log."
    ),
    "BenchmarkAdmissionDecisionPayload": (
        "BR-2D — BenchmarkAdmissionDecision, the authority-issued result. "
        "Reserved and undefined until BR-2D."
    ),
    "BenchmarkPostAdmissionRejectionEventPayload": (
        "BR-2D — the authority-issued post-admission rejection event."
    ),
    "BenchmarkRegistrationEventPayload": (
        "BR-2D — BenchmarkRegistrationEvent, the authority-issued result. "
        "Reserved and undefined until BR-2D."
    ),
    "BenchmarkRevocationEventPayload": (
        "BR-2D — the authority-issued revocation event, appended only "
        "after the revoker's signature verifies under an entitled anchor."
    ),
    "BenchmarkConflictRecordPayload": (
        "BR-2D — the authority-issued conflict record produced by the "
        "durable registry authority's compare-and-set slot claim."
    ),
    "BenchmarkResolutionRecordPayload": (
        "BR-2D — BenchmarkResolution, the authority-issued result and "
        "its issuance boundary, after real verification exists. Reserved and "
        "undefined at BR-2A."
    ),
    "BenchmarkHistoricalRecordPayload": (
        "BR-2D — the authority-issued historical record returned by the "
        "read-only inspection API."
    ),
    "BenchmarkExactResolutionRequest": (
        "BR-2D — the trusted exact-resolution API that consumes it."
    ),
    "BenchmarkHistoricalInspectionRequest": (
        "BR-2D — the separately named read-only historical inspection API."
    ),
    "PlatformRegistryScopeExpectation": (
        "BR-2D — the authorization check that consumes it, applied before any "
        "temporal or lifecycle check."
    ),
    "TenantRegistryScopeExpectation": (
        "BR-2D — the cross-tenant non-disclosure check that consumes it."
    ),
    "BenchmarkRegistrySnapshotAssertion": (
        "BR-2D — the durable registry authority that can observe the state "
        "this contract only asserts. BR-2B holds no store and reads none."
    ),
    "BenchmarkTransitionPlan": (
        "BR-2D — the first phase permitted to assert that the planned "
        "transition occurred. A plan says only that it would be admissible."
    ),
    "BenchmarkTransitionRefusal": (
        "BR-2D — the authority-issued refusal appended when the move is "
        "actually attempted against observed rather than asserted state."
    ),
}

ACTOR_PROPERTIES = (
    "publisher_identity",
    "registry_authority_identity",
    "revoker_identity",
    "approval_authority_identity",
    "tenant_id",
)

DIGEST_PROPERTY_SUFFIX = "_digest"


def _root_canonicalizable_classes():
    """The fifteen root-canonicalizable classes, in registry insertion order."""

    return [
        (cls, domain)
        for cls, (domain, root_ok) in _contract_type_registry_snapshot().items()
        if root_ok
    ]


def _nested_source_of_truth(cls):
    """Nested exact contract fields — the objects this class derives from."""

    return sorted(
        f.name
        for f in dataclasses.fields(cls)
        if dataclasses.is_dataclass(f.type)
        or f.name
        in {
            "coordinate",
            "scope",
            "publisher_submission_envelope",
            "approval_envelope",
            "submission_record",
            "admission_decision",
            "registration_event",
            "revocation_envelope",
        }
    )


def _derived_digest_properties(cls):
    return sorted(
        name
        for name in dir(cls)
        if name.endswith(DIGEST_PROPERTY_SUFFIX)
        and isinstance(getattr(cls, name, None), property)
    )


def _caller_supplied_digest_fields(cls):
    """Fields whose name ends in ``_digest`` — a caller-supplied digest.

    Upstream digests are never among these: an upstream digest is always a
    derived property. What legitimately appears here is a digest of something
    **outside** this package's graph, which cannot be recomputed from a nested
    object because the object is not held (the BR-1 identity digest, the
    benchmark content digest, the immutable admitted digest).
    """

    return sorted(
        f.name
        for f in dataclasses.fields(cls)
        if f.name.endswith(DIGEST_PROPERTY_SUFFIX)
    )


def _reachable_actor_identities(cls, instance):
    reachable = []
    for name in ACTOR_PROPERTIES:
        if isinstance(getattr(cls, name, None), property):
            reachable.append(name)
        elif any(f.name == name for f in dataclasses.fields(cls)):
            reachable.append(name)
    for f in dataclasses.fields(cls):
        if f.name.startswith("declared_") and f.name.endswith("_identity"):
            reachable.append(f.name)
    return sorted(set(reachable))


SEPARATION_CHECKS = {
    "BenchmarkApprovalEnvelope": [
        "approval_authority_identity != publisher_submission_envelope."
        "publisher_identity"
    ],
    "BenchmarkSubmissionRecordPayload": [
        "declared_registry_authority_identity != publisher_submission_envelope."
        "publisher_identity"
    ],
    "BenchmarkAdmissionDecisionPayload": [
        "registry_authority_identity != approval_envelope."
        "approval_authority_identity",
        "submission_record.publisher_submission_envelope is byte-identical and "
        "digest-identical to approval_envelope.publisher_submission_envelope",
        "declared_refusal_reason required iff declared_outcome is REJECTED",
    ],
    "BenchmarkPostAdmissionRejectionEventPayload": [
        "admission_decision.declared_outcome must be ADMITTED"
    ],
    "BenchmarkRegistrationEventPayload": [
        "admission_decision.declared_outcome must be ADMITTED"
    ],
    "BenchmarkRevocationEventPayload": [
        "revocation_envelope.revoker_identity != registry_authority_identity",
        "revocation_envelope.coordinate == registration_event.coordinate",
        "revocation_envelope.admitted_digest == registration_event."
        "benchmark_identity_digest",
    ],
    "PlatformRegistryScopeExpectation": ["scope.kind must be PLATFORM_WIDE"],
    "TenantRegistryScopeExpectation": ["scope.kind must be TENANT"],
}

PREV_EVENT_DIGEST_RULE = {
    "BenchmarkSubmissionRecordPayload": "None — the only payload permitted None",
    "BenchmarkAdmissionDecisionPayload": (
        "equals the independently recomputed canonical digest of "
        "submission_record"
    ),
    "BenchmarkPostAdmissionRejectionEventPayload": (
        "equals the independently recomputed canonical digest of "
        "admission_decision"
    ),
    "BenchmarkRegistrationEventPayload": (
        "equals the independently recomputed canonical digest of the ADMITTED "
        "admission_decision"
    ),
    "BenchmarkRevocationEventPayload": (
        "equals the independently recomputed canonical digest of "
        "registration_event"
    ),
    "BenchmarkConflictRecordPayload": (
        "equals the independently recomputed canonical digest of "
        "submission_record"
    ),
}


def build_contract_inventory():
    fixtures_by_name = dict(fixtures.PINNED_VECTOR_BUILDERS)
    rows = []
    for cls, domain in _root_canonicalizable_classes():
        name = cls.__name__
        instance = fixtures_by_name[name]()
        field_names = [f.name for f in dataclasses.fields(cls)]
        prev_rule = PREV_EVENT_DIGEST_RULE.get(name)
        transition = TRANSITION_METADATA.get(name, {})
        rows.append(
            {
                "class_name": name,
                "kind": "public_data_contract",
                "caller_constructible": True,
                "canonicalizable": True,
                "digest_domain": domain,
                "carries_declared_authority_information": any(
                    f.startswith("declared_") for f in field_names
                )
                or name.endswith("Envelope"),
                "permanently_false_trust_properties": sorted(
                    p
                    for p in (
                        list(api.BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES)
                        + [
                            "signature_verified",
                            "admission_established",
                            "authorizes_execution",
                            "active_eligibility_established",
                            "authorization_granted",
                        ]
                    )
                    if isinstance(getattr(cls, p, None), property)
                    and getattr(instance, p) is False
                ),
                "later_milestone_authority_issued_result": LATER_MILESTONE[name],
                "fields": field_names,
                "nested_source_of_truth_contracts": _nested_source_of_truth(cls),
                "derived_digest_properties": _derived_digest_properties(cls),
                "caller_supplied_digest_fields": _caller_supplied_digest_fields(
                    cls
                ),
                "caller_supplied_upstream_digest_fields": [],
                "mechanically_reachable_actor_identities": (
                    _reachable_actor_identities(cls, instance)
                ),
                "equality_and_separation_checks": SEPARATION_CHECKS.get(name, []),
                "carries_declared_recorded_at": (
                    "declared_recorded_at" in field_names
                ),
                "prev_event_digest_rule": (
                    prev_rule
                    if prev_rule is not None
                    else "not applicable — carries no chain position"
                ),
                "transition_represented": transition.get(
                    "transition_represented",
                    "none — not a lifecycle payload",
                ),
                "required_predecessor_state": transition.get(
                    "required_predecessor_state"
                ),
                "required_predecessor_declared_outcome": transition.get(
                    "required_predecessor_declared_outcome"
                ),
                "terminal": bool(getattr(instance, "is_terminal", False)),
            }
        )
    return rows


def classify_non_contract_symbols():
    rows = []
    contract_names = {
        cls.__name__ for cls, _ in _root_canonicalizable_classes()
    }
    for symbol in api.__all__:
        if symbol == "__version__" or symbol in contract_names:
            continue
        value = getattr(api, symbol)
        if isinstance(value, EnumMeta):
            kind = "closed_vocabulary_enum"
        elif isinstance(value, type) and issubclass(value, BaseException):
            kind = "typed_error"
        elif isinstance(value, type) and getattr(
            value, "_is_protocol", False
        ):
            kind = "protocol_port"
        elif isinstance(value, type) and dataclasses.is_dataclass(value):
            kind = "frozen_descriptor"
        elif isinstance(value, type):
            kind = "abstract_type_declaration"
        elif typing.get_origin(value) is not None and typing.get_args(value):
            # A typing alias such as ``Union[Plan, Refusal]``. It is *callable*
            # in CPython, so without this branch it was recorded as a
            # "pure_validation_function" — a Union described as a function.
            # Its members are pinned so widening the alias moves the manifest
            # and fails a gate, rather than only shifting a symbol count.
            kind = "closed_type_alias"
        elif callable(value):
            kind = "pure_validation_function"
        else:
            kind = "pinned_constant"
        row = {
            "symbol": symbol,
            "kind": kind,
            "caller_constructible": kind
            in {"frozen_descriptor", "closed_vocabulary_enum", "typed_error"},
            "canonicalizable": False,
        }
        if kind == "closed_type_alias":
            row["members"] = sorted(
                getattr(arg, "__name__", str(arg))
                for arg in typing.get_args(value)
            )
        rows.append(row)
    return rows


def main() -> int:
    contracts = build_contract_inventory()
    others = classify_non_contract_symbols()

    inventory = {
        "distribution": DISTRIBUTION,
        "namespace": NAMESPACE,
        "package_version": api.__version__,
        "milestone": "BR-2A",
        "note": (
            "Machine-readable public-contract inventory. "
            "'Every type is constructible and canonicalizable' applies to "
            "PUBLIC DATA CONTRACTS ONLY — the fifteen rows under "
            "'public_data_contracts'. It does NOT apply to Protocols, enums, "
            "errors, constants, pure validation functions, frozen descriptors "
            "or abstract type declarations, each of which is listed under "
            "'other_public_symbols' and marked with its own kind and with "
            "canonicalizable=false. "
            "No row anywhere carries a caller-supplied upstream digest field: "
            "every upstream digest in this package is a derived read-only "
            "property recomputed from the exact nested object. The "
            "'caller_supplied_digest_fields' column lists digests of artifacts "
            "OUTSIDE this package's graph (the BR-1 identity digest, the "
            "benchmark content digest, the immutable admitted digest), which "
            "cannot be recomputed here because the objects are not held. "
            "Regenerate with tools/generate_manifests.py; "
            "tests/packaging/test_inventories.py re-derives every column from "
            "the live surface and asserts this file equals it."
        ),
        "public_data_contracts": contracts,
        "other_public_symbols": others,
    }
    (PKG / "public_contract_inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=False) + "\n"
    )

    domains = {
        "distribution": DISTRIBUTION,
        "namespace": NAMESPACE,
        "package_version": api.__version__,
        "canonicalization_version": (
            api.BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION
        ),
        "note": (
            "One domain-separation tag per artifact class this subphase "
            "actually ships, and no tag for an artifact that does not exist. "
            "Nested-admissible-only classes are the exact frozen BR-1 contracts "
            "a BR-2A graph may contain; they own NO BR-2A domain, because BR-2 "
            "never re-digests a BR-1 artifact under a BR-2 domain — a BR-1 "
            "identity must keep exactly one digest, the one BR-1 computes. "
            "Derived from the sealed contract-type registry itself, so it "
            "cannot drift from the boundary the encoder enforces."
        ),
        "root_canonicalizable": {
            cls.__name__: domain for cls, domain in _root_canonicalizable_classes()
        },
        "nested_admissible_only": sorted(
            cls.__name__
            for cls, (_domain, root_ok) in (
                _contract_type_registry_snapshot().items()
            )
            if not root_ok
        ),
    }
    (PKG / "canonical_domain_inventory.json").write_text(
        json.dumps(domains, indent=2) + "\n"
    )

    vectors = {
        "distribution": DISTRIBUTION,
        "namespace": NAMESPACE,
        "package_version": api.__version__,
        "canonicalization_version": (
            api.BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION
        ),
        "note": (
            "One pinned canonical byte vector and digest per shipped artifact "
            "class. 'canonical_bytes' is the exact UTF-8 JSON the encoder "
            "produces for the pinned fixture; 'digest' is its sha-256. Both are "
            "reproducible from the literals in tests/_builders.py, and the "
            "digest is independently recomputable with plain hashlib over the "
            "byte string alone, importing nothing from the package."
        ),
        "vectors": {},
    }
    fixtures_by_name = dict(fixtures.PINNED_VECTOR_BUILDERS)
    for cls, _domain in _root_canonicalizable_classes():
        instance = fixtures_by_name[cls.__name__]()
        raw = canonical_bytes(instance)
        vectors["vectors"][cls.__name__] = {
            "canonical_bytes": raw.decode("utf-8"),
            "digest": canonical_digest(instance),
        }
    (PKG / "pinned_canonical_vectors.json").write_text(
        json.dumps(vectors, indent=2, ensure_ascii=False) + "\n"
    )

    def _describe(symbol):
        value = getattr(api, symbol)
        if isinstance(value, EnumMeta):
            return {
                "kind": "enum",
                "members": [m.value for m in value],
            }
        if isinstance(value, type) and issubclass(value, BaseException):
            return {"kind": "error"}
        if isinstance(value, type) and getattr(value, "_is_protocol", False):
            return {"kind": "protocol"}
        if isinstance(value, type) and dataclasses.is_dataclass(value):
            return {
                "kind": "contract",
                "fields": [f.name for f in dataclasses.fields(value)],
            }
        if isinstance(value, type):
            return {"kind": "type"}
        if callable(value):
            return {"kind": "function"}
        if isinstance(value, (str, int, bool)) or value is None:
            return {"kind": "constant", "value": value}
        if isinstance(value, frozenset):
            return {
                "kind": "constant",
                "value": sorted(getattr(m, "value", m) for m in value),
            }
        if isinstance(value, tuple):
            return {
                "kind": "constant",
                "value": [
                    getattr(m, "value", m.__name__ if isinstance(m, type) else m)
                    for m in value
                ],
            }
        if hasattr(value, "items"):
            return {"kind": "constant", "value": _jsonable(value)}
        if dataclasses.is_dataclass(value):
            return {"kind": "frozen_instance", "type": type(value).__name__}
        return {"kind": "constant", "value": repr(value)}

    def _jsonable(obj):
        if hasattr(obj, "items"):
            return {
                str(getattr(k, "value", k if not isinstance(k, tuple) else
                            "|".join(str(getattr(p, "value", p)) for p in k))):
                _jsonable(v)
                for k, v in obj.items()
            }
        if isinstance(obj, (list, tuple)):
            return [_jsonable(v) for v in obj]
        if isinstance(obj, frozenset):
            return sorted(_jsonable(v) for v in obj)
        if isinstance(obj, type):
            return obj.__name__
        return getattr(obj, "value", obj)

    public_api = {
        "distribution": DISTRIBUTION,
        "namespace": NAMESPACE,
        "package_version": api.__version__,
        "curated_api_module": f"{NAMESPACE}.api",
        "note": (
            "Machine-readable snapshot of the curated public API "
            f"({NAMESPACE}.api.__all__). "
            "__version__ is carried separately as package_version and is NOT a "
            "member of 'symbols', so symbols is exactly one shorter than "
            "api.__all__ — both counts are asserted, and neither is 'corrected' "
            "to match the other. tests/packaging/test_public_api.py asserts this "
            "file equals the actual package surface, and "
            "verify_benchmark_registry_authority_distribution.py asserts the "
            "same for the built wheel, the built sdist and the isolated "
            "installed runtime."
        ),
        "symbols": {
            symbol: _describe(symbol)
            for symbol in sorted(api.__all__)
            if symbol != "__version__"
        },
    }
    (PKG / "public_api.json").write_text(
        json.dumps(public_api, indent=2, ensure_ascii=False) + "\n"
    )

    print(f"public_contract_inventory.json  {len(contracts)} data contracts, "
          f"{len(others)} other symbols")
    print(f"canonical_domain_inventory.json  "
          f"{len(domains['root_canonicalizable'])} domains, "
          f"{len(domains['nested_admissible_only'])} nested-only")
    print(f"pinned_canonical_vectors.json    {len(vectors['vectors'])} vectors")
    print(f"public_api.json                  {len(public_api['symbols'])} symbols "
          f"(api.__all__ = {len(api.__all__)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

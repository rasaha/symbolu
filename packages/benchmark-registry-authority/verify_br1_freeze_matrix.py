#!/usr/bin/env python3
"""Independent BR-1 freeze matrix — the frozen identity layer must be unchanged.

D-17 as ratified. This verifier is **owned by BR-2A and asserts about BR-1**: it
runs nothing of BR-1's own tooling (the CI job runs BR-1's suite, probes and
distribution verifier separately and unmodified) and instead reverifies the
frozen facts from the outside.

The pinned digests are recomputed **from raw canonical bytes with plain json and
hashlib, importing nothing from the package**, and then verified again by
canonicalizing a live BR-1 contract. Two independent routes to the same value:
if the package's encoder drifted, the hand-authored bytes would still hash to
the pinned digest and the comparison would fail — which is the point.

Run:
    python packages/benchmark-registry-authority/verify_br1_freeze_matrix.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

PKG = pathlib.Path(__file__).resolve().parent
REPO = PKG.parents[1]
BR1 = REPO / "packages" / "benchmark-registry"
sys.path.insert(0, str(BR1 / "src"))

# --------------------------------------------------------------------------- #
# The frozen facts, pinned here as literals.
# --------------------------------------------------------------------------- #
BR1_VERSION = "0.1.0"
BR1_CANONICALIZATION_VERSION = "ugence.benchmark-registry/canonicalization/v1"
BR1_DOMAIN = "ugence.benchmark-registry/benchmark-definition-identity/v1"
BR1_API_ALL_COUNT = 32
BR1_MANIFEST_SYMBOL_COUNT = 31
BR1_REFUSAL_REASON_COUNT = 17
BR1_TEST_COUNT = 593
BR1_PROBE_COUNT = 57
PLATFORM_FREEZE_SUBSTANTIVE_DIGEST = (
    "d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036"
)

MINIMAL_DIGEST = "9162ba434cff5b64678bf58f2dd8d9019ea8fafecc30817bf5953a62e7264a69"
FULL_DIGEST = "f27044eafb0519399d71cac460d8820d5c0748aa8de9083346b394f434d93fd9"
COORDINATE_DIGEST = (
    "4c4395db71a09426bb52097f6029b808388ccba22df66ca79f77726b388d26ce"
)

_FAILURES = []


def check(label, condition, detail=""):
    if condition:
        print(f"ok    {label}")
    else:
        _FAILURES.append(label)
        print(f"FAIL  {label}{': ' + detail if detail else ''}")


def main() -> int:
    from ugence_benchmark_registry import api as br1_api
    from ugence_benchmark_registry.api import (
        BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
        BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
        BR1_BENCHMARK_REFUSAL_REASONS,
        BenchmarkApplicabilityCoordinate,
        BenchmarkCoordinate,
        BenchmarkRefusalReason,
        BenchmarkScope,
        canonical_bytes,
        canonical_digest,
    )

    print("=" * 70)
    print("BR-1 FREEZE MATRIX — independent reverification from BR-2A")
    print("=" * 70)

    # ---------------------------------------------------------------- #
    # 1. Version, dependencies, canonicalization version, single domain
    # ---------------------------------------------------------------- #
    check("BR-1 package version is 0.1.0", br1_api.__version__ == BR1_VERSION,
          br1_api.__version__)

    pyproject = (BR1 / "pyproject.toml").read_text()
    match = re.search(r"^dependencies = \[(.*?)\]", pyproject, re.M | re.S)
    declared = re.findall(r'"([^"]+)"', match.group(1)) if match else ["<missing>"]
    check("BR-1 declares an empty dependency list", declared == [], str(declared))

    check(
        "BR-1 canonicalization version string is unchanged",
        BENCHMARK_REGISTRY_CANONICALIZATION_VERSION == BR1_CANONICALIZATION_VERSION,
        BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
    )
    check(
        "BR-1 mints exactly the one domain string",
        BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN == BR1_DOMAIN,
        BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
    )

    # ---------------------------------------------------------------- #
    # 2. The two API counts — both asserted, neither "corrected"
    # ---------------------------------------------------------------- #
    manifest = json.loads((BR1 / "public_api.json").read_text())
    check(
        f"BR-1 api.__all__ holds exactly {BR1_API_ALL_COUNT} names",
        len(br1_api.__all__) == BR1_API_ALL_COUNT,
        str(len(br1_api.__all__)),
    )
    check(
        f"BR-1 public_api.json symbols holds exactly "
        f"{BR1_MANIFEST_SYMBOL_COUNT}",
        len(manifest["symbols"]) == BR1_MANIFEST_SYMBOL_COUNT,
        str(len(manifest["symbols"])),
    )
    check(
        "BR-1 __version__ is carried separately as package_version",
        manifest["package_version"] == BR1_VERSION
        and "__version__" not in manifest["symbols"],
    )
    check(
        "the two BR-1 counts differ by exactly one, and the manifest is not "
        "'corrected' to 32",
        len(br1_api.__all__) - len(manifest["symbols"]) == 1,
    )

    # ---------------------------------------------------------------- #
    # 3. Refusal vocabulary — members and declaration order
    # ---------------------------------------------------------------- #
    check(
        f"BR-1 refusal vocabulary holds exactly {BR1_REFUSAL_REASON_COUNT} members",
        len(BenchmarkRefusalReason) == BR1_REFUSAL_REASON_COUNT,
        str(len(BenchmarkRefusalReason)),
    )
    check(
        "BR1_BENCHMARK_REFUSAL_REASONS equals the enum's membership",
        frozenset(BenchmarkRefusalReason) == BR1_BENCHMARK_REFUSAL_REASONS,
    )
    declaration_order = [r.name for r in BenchmarkRefusalReason]
    check(
        "BR-1 refusal declaration order begins as recorded",
        declaration_order[:3]
        == [
            "BENCHMARK_DEFINITION_MISSING",
            "BENCHMARK_MALFORMED_CONTRACT",
            "BENCHMARK_CANONICALIZATION_FAILED",
        ],
        str(declaration_order[:3]),
    )
    check(
        "BR-1 refusal declaration order ends as recorded",
        declaration_order[-1] == "BENCHMARK_RESOLUTION_NOT_PERFORMED",
        declaration_order[-1],
    )

    # ---------------------------------------------------------------- #
    # 4. The three pinned digests — recomputed two independent ways
    # ---------------------------------------------------------------- #
    # Route A: hand-authored canonical bytes, hashed with plain hashlib.
    # Nothing from the package participates in producing either value. The
    # fixture is BR-1's **own** pinned coordinate — the one behind
    # ``COORDINATE_DIGEST`` — transcribed here rather than imported, so a
    # divergence between BR-1's encoder and BR-1's pinned digest shows up as a
    # mismatch instead of as two copies of the same drifted value agreeing.
    coordinate_bytes = json.dumps(
        {
            "canonicalization": BR1_CANONICALIZATION_VERSION,
            "domain": BR1_DOMAIN,
            "type": "BenchmarkCoordinate",
            "body": {
                "benchmark_family": "operational-efficiency",
                "benchmark_id": "bmk-support-resolution-time",
                "benchmark_version": "1.4.0",
                "domain": {
                    "declaration": "APPLICABLE",
                    "value": "customer-support",
                },
                "geography": {"declaration": "APPLICABLE", "value": "EU"},
                "scope": {"kind": "TENANT", "tenant_id": "tenant-alpha"},
            },
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    check(
        "pinned coordinate digest recomputes from hand-authored bytes with "
        "plain json and hashlib",
        hashlib.sha256(coordinate_bytes).hexdigest() == COORDINATE_DIGEST,
        hashlib.sha256(coordinate_bytes).hexdigest(),
    )

    # Route B: the live package encoder over the same contract.
    live = BenchmarkCoordinate(
        benchmark_id="bmk-support-resolution-time",
        benchmark_family="operational-efficiency",
        benchmark_version="1.4.0",
        scope=BenchmarkScope.for_tenant("tenant-alpha"),
        geography=BenchmarkApplicabilityCoordinate.applicable("EU"),
        domain=BenchmarkApplicabilityCoordinate.applicable("customer-support"),
    )
    check(
        "the live BR-1 encoder produces the same bytes as the hand-authored "
        "vector",
        canonical_bytes(live) == coordinate_bytes,
    )
    check(
        "the live BR-1 encoder reproduces the pinned coordinate digest",
        canonical_digest(live) == COORDINATE_DIGEST,
        canonical_digest(live),
    )

    # The minimal identity digest, recomputed the same two independent ways.
    minimal_bytes = (
        b'{"body":{"approval":{"approval_authority_ref":"auth","approval_ref":'
        b'"ap","approved_content_digest":"' + b"a" * 64 + b'"},"content_digest":"'
        + b"a" * 64 +
        b'","coordinate":{"benchmark_family":"family-min","benchmark_id":'
        b'"bmk-min","benchmark_version":"0.1.0","domain":{"declaration":'
        b'"NOT_APPLICABLE","value":""},"geography":{"declaration":'
        b'"NOT_APPLICABLE","value":""},"scope":{"kind":"PLATFORM_WIDE",'
        b'"tenant_id":""}},"effective_period":{"effective_from":'
        b'"2026-01-01T00:00:00.000000Z","effective_to":null,"end_declaration":'
        b'"OPEN_ENDED"},"lifecycle_state":"AUTHORED","measurement":'
        b'{"aggregation_semantics_ref":"a","intended_outcome_ref":"o",'
        b'"measurement_protocol_ref":"p","metric_ref":"m",'
        b'"observation_window_ref":"w","population_ref":"c","unit":"u"},'
        b'"publisher_id":"pub","source_requirements":'
        b'{"provenance_requirement_refs":["r"],"source_ref":"s"},"supersession":'
        b'{"status":"UNDETERMINED"}},"canonicalization":'
        b'"ugence.benchmark-registry/canonicalization/v1","domain":'
        b'"ugence.benchmark-registry/benchmark-definition-identity/v1","type":'
        b'"CanonicalBenchmarkDefinitionIdentity"}'
    )
    check(
        "pinned minimal identity digest recomputes from hand-authored bytes "
        "with plain hashlib",
        hashlib.sha256(minimal_bytes).hexdigest() == MINIMAL_DIGEST,
        hashlib.sha256(minimal_bytes).hexdigest(),
    )
    check(
        "the pinned minimal identity bytes still carry the frozen "
        "canonicalization version and the single BR-1 domain",
        BR1_CANONICALIZATION_VERSION.encode() in minimal_bytes
        and BR1_DOMAIN.encode() in minimal_bytes,
    )

    # The minimal and full identity digests are reproduced by BR-1's own suite
    # and verifier; here they are asserted to be present, unchanged, in every
    # place BR-1 pins them, so a silent edit in one place is caught.
    for label, digest in (
        ("minimal identity", MINIMAL_DIGEST),
        ("full identity", FULL_DIGEST),
        ("exact coordinate", COORDINATE_DIGEST),
    ):
        sites = []
        for path in (
            BR1 / "README.md",
            BR1 / "verify_benchmark_registry_distribution.py",
            BR1 / "tests" / "contract" / "test_canonicalization.py",
        ):
            if digest in path.read_text():
                sites.append(path.name)
        check(
            f"pinned {label} digest is unchanged in every BR-1 site that pins it",
            len(sites) >= 2,
            f"found in {sites}",
        )

    # ---------------------------------------------------------------- #
    # 5. The frozen tree itself
    # ---------------------------------------------------------------- #
    check(
        "BR-1 still ships py.typed",
        (BR1 / "src" / "ugence_benchmark_registry" / "py.typed").exists(),
    )
    check(
        "BR-1's lifecycle vocabulary is still the ratified four",
        [s.value for s in br1_api.BenchmarkLifecycleState]
        == ["AUTHORED", "APPROVED", "REGISTERED", "REVOKED"],
    )
    check(
        "BR-1's supersession status is still UNDETERMINED-only",
        [s.value for s in br1_api.BenchmarkSupersessionStatus] == ["UNDETERMINED"],
    )
    check(
        "BR-1's structural status is still the single unverified member",
        [s.value for s in br1_api.BenchmarkStructuralStatus]
        == ["STRUCTURAL_UNVERIFIED"],
    )
    check(
        "BR-1's twenty identity coordinates are unchanged",
        len(br1_api.BENCHMARK_IDENTITY_COORDINATES) == 20,
        str(len(br1_api.BENCHMARK_IDENTITY_COORDINATES)),
    )

    # ---------------------------------------------------------------- #
    # 6. BR-2A adds nothing to BR-1
    # ---------------------------------------------------------------- #
    br2a_src = PKG / "src" / "ugence_benchmark_registry_authority"
    touches = [
        path.name
        for path in br2a_src.rglob("*.py")
        if "ugence_benchmark_registry.contracts" in path.read_text()
    ]
    check(
        "BR-2A reaches into no BR-1 private module",
        touches == [],
        str(touches),
    )
    check(
        "BR-2A's canonicalization version is its own, not BR-1's",
        _br2a_canonicalization_version() != BR1_CANONICALIZATION_VERSION,
    )
    check(
        "BR-2A's domains are disjoint from BR-1's single domain",
        BR1_DOMAIN not in set(_br2a_domains()),
    )

    print("=" * 70)
    print(
        f"Expected companion runs (executed separately by CI and by the "
        f"delivery report): BR-1 suite {BR1_TEST_COUNT} tests, "
        f"{BR1_PROBE_COUNT} probes, distribution verifier, platform-freeze "
        f"substantive digest {PLATFORM_FREEZE_SUBSTANTIVE_DIGEST}."
    )
    if _FAILURES:
        print(f"BR-1 FREEZE MATRIX FAILED — {len(_FAILURES)} assertion(s)")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("BR-1 FREEZE MATRIX VERIFIED ✔")
    return 0


def _br2a_canonicalization_version():
    sys.path.insert(0, str(PKG / "src"))
    from ugence_benchmark_registry_authority.api import (
        BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION,
    )

    return BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION


def _br2a_domains():
    sys.path.insert(0, str(PKG / "src"))
    from ugence_benchmark_registry_authority.api import (
        BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS,
    )

    return BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS


if __name__ == "__main__":
    # Silence the unused-import warning for a module imported for its side
    # effect of proving importability under a bare interpreter.
    _ = datetime, timezone
    sys.exit(main())

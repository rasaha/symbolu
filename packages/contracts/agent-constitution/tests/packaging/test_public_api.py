"""The curated public API matches ``public_api.json`` exactly.

A surface that drifts without a reviewed file changing is a surface nobody agreed
to. This test is the reason ``public_api.json`` is worth keeping.
"""

from __future__ import annotations

import json
import pathlib

import ugence_agent_constitution
from ugence_agent_constitution import api, version_info
from ugence_agent_constitution.validation import codes

PKG_ROOT = pathlib.Path(ugence_agent_constitution.__file__).resolve().parent
PUBLIC_API = PKG_ROOT.parents[1] / "public_api.json"

#: Names taken by other packages in the monorepo. AC-0 must not reuse any of them,
#: because two different things under one name is how a boundary stops being read.
RESERVED_ELSEWHERE = {
    "CapabilityRegistry",
    "CapabilityDefinition",
    "CapabilityManifest",
    "CompilationResult",
    "AuthorityRequirement",
    "GovernanceDisposition",
    "resolve_policy",
}


def _snapshot():
    if not PUBLIC_API.is_file():
        return None
    return json.loads(PUBLIC_API.read_text(encoding="utf-8"))


def test_the_snapshot_lists_exactly_the_curated_surface():
    snapshot = _snapshot()
    if snapshot is None:
        return  # installed wheel without the source-tree snapshot
    assert sorted(snapshot["symbols"]) == sorted(api.__all__)


def test_the_snapshot_records_the_distribution_and_namespace():
    snapshot = _snapshot()
    if snapshot is None:
        return
    info = version_info()
    assert snapshot["distribution"] == info.distribution
    assert snapshot["namespace"] == info.canonical_namespace
    assert snapshot["package_version"] == info.distribution_version


def test_every_curated_name_actually_resolves():
    for name in api.__all__:
        assert hasattr(api, name), name
        assert hasattr(ugence_agent_constitution, name), name


def test_the_top_level_namespace_re_exports_the_curated_surface():
    assert set(ugence_agent_constitution.__all__) == set(api.__all__)


def test_no_name_taken_by_another_package_is_reused():
    """Reusing one of these would put two different meanings under one name."""
    assert not (set(api.__all__) & RESERVED_ELSEWHERE)
    assert not (set(dir(ugence_agent_constitution)) & RESERVED_ELSEWHERE)


#: The one exported name containing "registry". It is a *reference* to an entry in
#: a registry this package does not own, resolve, or ship — the opposite of owning
#: one — so the substring scan below excludes it by name rather than by pattern.
REGISTRY_REFERENCE_ONLY = {"CapabilityRegistryEntryRef"}


def test_no_out_of_scope_capability_is_exported():
    """AC-0's non-goals, asserted against the surface rather than only documented."""
    scanned = [n for n in api.__all__ if n not in REGISTRY_REFERENCE_ONLY]
    surface = " ".join(scanned).lower()
    for forbidden in (
        "compile",
        "registry",
        "sign",
        "signature",
        "verdict",
        "finding_for",
        "llm",
        "prompt",
        "bind_runtime",
        "authorize",
    ):
        assert forbidden not in surface, forbidden


def test_the_registry_reference_exception_names_a_reference_and_not_a_registry():
    """The exception above must stay an exception: a reference type with no resolve
    step, no lookup, and no stored entries."""
    from ugence_agent_constitution import CapabilityRegistryEntryRef

    assert set(CapabilityRegistryEntryRef.model_fields) == {
        "registry_namespace",
        "entry_id",
        "entry_version",
        "entry_digest",
    }
    for attribute in dir(CapabilityRegistryEntryRef):
        assert "resolve" not in attribute.lower(), attribute
        assert "lookup" not in attribute.lower(), attribute


def test_version_info_claims_nothing_out_of_scope():
    info = version_info().to_dict()
    for claim in (
        "compiler_implemented",
        "capability_registry_implemented",
        "conformance_findings_implemented",
        "signing_implemented",
        "ui_implemented",
        "llm_assistance_implemented",
        "runtime_binding_implemented",
        "authority_decision_implemented",
        "pilot_validated",
        "production_certified",
    ):
        assert info[claim] is False, claim


def test_the_snapshot_records_the_finding_codes_this_build_can_emit():
    snapshot = _snapshot()
    if snapshot is None:
        return
    assert sorted(snapshot["finding_codes"]) == sorted(codes.ALL_CODES)

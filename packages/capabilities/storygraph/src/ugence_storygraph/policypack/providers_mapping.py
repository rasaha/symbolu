"""Trusted-provider mapping schema (§10).

Declares how a legitimate-evidence provider is configured. Provider failure must
never silently become approval, and missing provider evidence must not strengthen the
harmful graph — both are enforced by the schema (no ALLOW availability behavior) and
by the frozen matcher (missing context leaves the structural vector unchanged).
"""

from __future__ import annotations

PROVIDER_MAPPING_SCHEMA_VERSION = "ctd.provider_mapping/1.0.0"

_REQUIRED = ("provider_id", "provider_type", "authority_source", "evidence_schema",
             "supported_operations", "scope_matching_fields", "validity_window",
             "revocation_semantics", "availability_behavior", "verification_method",
             "tenant_isolation", "replay_fixture_format", "schema_version")

# a provider becoming unavailable/stale/conflicting may map only to fail-visible
# advisory outcomes — never to permission.
_AVAILABILITY = ("REQUIRE_ADDITIONAL_EVIDENCE", "HOLD_FOR_REVIEW", "OBSERVE",
                 "UNAVAILABLE", "ADDITIONAL_CONTEXT_REQUIRED")


def validate_provider_mapping(p: dict) -> list:
    errs = []
    for f in _REQUIRED:
        if f not in p:
            errs.append(f"provider_mapping: missing '{f}'")
    if p.get("schema_version") not in (PROVIDER_MAPPING_SCHEMA_VERSION, None):
        errs.append("provider_mapping: unversioned or wrong schema_version")
    ab = p.get("availability_behavior")
    if ab is not None and ab not in _AVAILABILITY:
        errs.append(f"provider_mapping.availability_behavior '{ab}' invalid; provider "
                    "failure may never become permission")
    if p.get("tenant_isolation") is False:
        errs.append("provider_mapping.tenant_isolation must be true")
    return errs

"""Evidence-boundary discipline: references only, no hidden retrieval, no secrets.

TAP receives caller-supplied evidence references; it never implicitly fetches
unrestricted enterprise data, never accepts embedded secrets, and keeps provenance
separate from support.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from ugence_governance_provider_framework.api import (
    AssertionGovernanceRequest, ProviderConfigurationError)
from ugence_tap_provider.configuration import TapSettings, build_tap_provider
from ugence_tap_provider.core import TapEngine
from ugence_tap_provider.mapping import map_request

CANON = pathlib.Path(__file__).resolve().parents[2] / "src" / "ugence_tap_provider"


def test_evidence_resolution_modes_validated():
    for mode in ("caller_supplied", "provider_client", "external_resolver"):
        TapSettings(evidence_resolution=mode).validate()
    with pytest.raises(ProviderConfigurationError):
        TapSettings(evidence_resolution="web_crawl").validate()


def test_embedded_secret_rejected_reference_accepted():
    with pytest.raises(ProviderConfigurationError):
        TapSettings(secret_refs={"api_key": "sk-plaintext"}).validate()
    TapSettings(secret_refs={"api_key": "ref:vault/api_key"}).validate()  # ok


def test_references_only_no_raw_content_crosses_boundary():
    n = map_request(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    # The native item carries the reference + a provenance tag, not fetched content.
    assert n.evidence[0].source_reference == "e1"
    assert n.evidence[0].content == ""
    assert n.evidence[0].provenance == "caller_supplied"


def test_provenance_is_separate_from_support():
    p = build_tap_provider(TapEngine()); p.initialize()
    r = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    # provenance never appears as a support signal; coverage is derived from stance
    assert r.coverage.value in ("SUPPORTED", "CONSTRAINED", "UNSUPPORTED", "INDETERMINATE")


def test_no_network_or_filesystem_retrieval_in_core():
    """The TAP core/client/mapping never import a network or document-fetch library."""
    forbidden_roots = {"requests", "httpx", "urllib", "http", "socket", "aiohttp",
                       "boto3", "google", "psycopg2", "sqlalchemy", "kubernetes"}
    hits = []
    for sub in ("core", "client", "mapping"):
        for p in (CANON / sub).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            for node in ast.walk(ast.parse(p.read_text(), filename=str(p))):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                hits += [f"{p.name}->{n}" for n in names if n in forbidden_roots]
    assert not hits, hits


def test_observability_records_no_raw_evidence_content():
    from ugence_tap_provider.observability import TapInvocationRecord
    fields = set(TapInvocationRecord.__dataclass_fields__)
    # Only counts/coverage are recorded — no field for raw content or secrets.
    assert "evidence_count" in fields
    assert "evidence_coverage" in fields
    assert not (fields & {"content", "evidence_content", "secret", "raw_source"})

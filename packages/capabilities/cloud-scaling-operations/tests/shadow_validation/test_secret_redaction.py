"""Secret redaction across headers, URLs, records, exceptions, and evidence files."""
from __future__ import annotations

import json
import tempfile

from shadow_validation.redaction import (
    redact_headers, redact_url, redact_record, redact_exception, contains_secret_material,
)
from shadow_validation.evidence import generate_fixture_evidence, scan_for_secret_material
from shadow_mutation_canaries import run_mutation_canaries


def test_headers_fully_redacted():
    r = redact_headers({"Authorization": "Bearer abc.def", "X-Api-Key": "k", "Accept": "json"})
    assert r["Authorization"] == "<redacted>"
    assert r["X-Api-Key"] == "<redacted>"
    assert r["Accept"] == "json"


def test_url_query_and_userinfo_redacted():
    assert "leak" not in redact_url("https://a.local/app?token=leak&x=1")
    assert "pw" not in redact_url("https://user:pw@a.local/app")


def test_record_and_exception_redaction():
    r = redact_record({"argocd_token": "leak", "note": "call Bearer zzz.yyy"})
    blob = json.dumps(r)
    assert "leak" not in blob and "zzz.yyy" not in blob
    assert "leaksig" not in redact_exception(RuntimeError("https://a.local/x?sig=leaksig"))


def test_contains_secret_material_detects_bare_bearer():
    assert contains_secret_material("Authorization: Bearer real.token.here") is True
    assert contains_secret_material("Authorization: Bearer <redacted>") is False


def test_generated_fixture_evidence_has_no_secret_material():
    d = tempfile.mkdtemp(prefix="shadow-redact-")
    generate_fixture_evidence(d, canary_results=run_mutation_canaries())
    assert scan_for_secret_material(d) == []

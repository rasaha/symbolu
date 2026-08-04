"""Structured, redacting logs (P3E §17)."""
import json

from governance_studio_deployment.logging_utils import log_event, sanitize_correlation_id


def test_only_allowlisted_fields_are_emitted(capsys):
    log_event("request", level="info", timestamp="2026-08-04T00:00:00Z", method="GET",
              route="/api/v1/scenarios", status=200, duration_ms=3, correlation_id="abc",
              authorization="Basic secret", password="hunter2", body="payload", query="?x=1")
    line = capsys.readouterr().out.strip()
    record = json.loads(line)
    assert record["event"] == "request"
    assert record["method"] == "GET"
    for banned in ("authorization", "password", "body", "query"):
        assert banned not in record
    assert "Basic secret" not in line and "hunter2" not in line


def test_correlation_id_is_sanitised():
    assert sanitize_correlation_id("../../etc/passwd").isalnum() is False  # dots/slashes stripped except . -
    assert "/" not in sanitize_correlation_id("a/b/c")
    generated = sanitize_correlation_id(None)
    assert len(generated) == 32
    assert sanitize_correlation_id("x" * 200) == "x" * 64  # bounded length


def test_malicious_correlation_id_cannot_inject():
    cleaned = sanitize_correlation_id('evil","level":"critical')
    assert '"' not in cleaned and "," not in cleaned

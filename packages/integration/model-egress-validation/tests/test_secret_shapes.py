from __future__ import annotations

import pytest

from ugence_model_egress_validation import Finding, assert_clean, scan


def test_findings_name_paths_and_shapes_never_values():
    obj = {"ok": "projects/p/secrets/s/versions/3", "nested": {"key": "sk-proj-abcdefghijklmnopqrstuvwxyz0123"},
           "list": ["fine", "AIzaSyA1234567890abcdefghijklmnopqrstu"], "marker": "the-known-marker-value"}
    findings = scan(obj, known_markers=["the-known-marker-value"])
    assert findings == [Finding("$.nested.key", "sk-proj-"), Finding("$.list[1]", "AIza"), Finding("$.marker", "known-marker")]
    assert "abcdefghijklmnop" not in " ".join(str(f) for f in findings)
    with pytest.raises(ValueError, match=r"the report carries a credential shape at: \$.nested.key"):
        assert_clean(obj, what="the report")


def test_a_secret_shaped_key_is_a_finding_too():
    assert scan({"sk-proj-abcdefghijklmnopqrstuvwxyz": "x"})[0].path == "$.<key>"


def test_clean_objects_scan_empty():
    assert scan({"digest": "a" * 64, "rows": [{"status": "OFFLINE_CONFORMANT", "observed": "refusal=model_not_pinned"}]}) == []
    assert_clean("task-123")

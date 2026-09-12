from __future__ import annotations

import pytest

from ugence_model_egress_unit import looks_like_a_credential
from ugence_model_egress_validation import Finding, assert_clean, scan
from synthetic_shapes import KINDS, expected_family, synthetic_credential_shape


def test_findings_name_paths_and_shapes_never_values():
    key_like = synthetic_credential_shape("openai_project_key")        # assembled at runtime; no literal here
    api_like = synthetic_credential_shape("google_api_key")
    obj = {"ok": "projects/p/secrets/s/versions/3", "nested": {"key": key_like},
           "list": ["fine", api_like], "marker": "the-known-marker-value"}
    findings = scan(obj, known_markers=["the-known-marker-value"])
    assert findings == [Finding("$.nested.key", expected_family("openai_project_key")),
                        Finding("$.list[1]", expected_family("google_api_key")),
                        Finding("$.marker", "known-marker")]
    rendered = " ".join(str(f) for f in findings)
    assert key_like not in rendered and api_like not in rendered and key_like[8:24] not in rendered
    with pytest.raises(ValueError, match=r"the report carries a credential shape at: \$.nested.key") as info:
        assert_clean(obj, what="the report")
    assert key_like not in str(info.value)


def test_a_secret_shaped_key_is_a_finding_too():
    assert scan({synthetic_credential_shape("openai_project_key_short"): "x"})[0].path == "$.<key>"


def test_clean_objects_scan_empty():
    assert scan({"digest": "a" * 64, "rows": [{"status": "OFFLINE_CONFORMANT", "observed": "refusal=model_not_pinned"}]}) == []
    assert_clean("task-123")


def test_the_runtime_assembled_shapes_take_the_same_production_detection_path():
    """Requirement 8: the production detector (the unit's looks_like_a_credential, which
    the scanner calls) catches each synthetic value through its real prefix family."""

    for kind in KINDS:
        value = synthetic_credential_shape(kind)
        assert looks_like_a_credential(value), kind
        assert scan({"v": value}) == [Finding("$.v", expected_family(kind))], kind
    for fragment in ("sk", "-", "proj", "AI", "za", "SyA"):
        assert not looks_like_a_credential(fragment) and scan({"v": fragment}) == []

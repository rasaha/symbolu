"""JSON/CSV structured-complexity limit tests."""

from __future__ import annotations

import json

import pytest

from ugence_ai_hiring.errors import ContentExtractionError, StructuredLimitError
from ugence_ai_hiring.normalization.limits import EvidenceLimits
from ugence_ai_hiring.normalization.structured_limits import (
    check_csv_bounded,
    parse_json_bounded,
)


# --- JSON ------------------------------------------------------------------
def test_json_bytes_limit():
    with pytest.raises(StructuredLimitError):
        parse_json_bounded(b'{"a": 1}' * 100, EvidenceLimits(max_json_bytes=10))


def test_json_nesting_depth_limit():
    nested = "{}".join('{"a":' * 0 for _ in range(0))  # placeholder
    payload = b'{"a":' * 10 + b"1" + b"}" * 10
    with pytest.raises(StructuredLimitError):
        parse_json_bounded(payload, EvidenceLimits(max_json_depth=3))


def test_json_field_count_limit():
    obj = {f"k{i}": i for i in range(20)}
    with pytest.raises(StructuredLimitError):
        parse_json_bounded(json.dumps(obj).encode(), EvidenceLimits(max_json_fields=5))


def test_json_array_length_limit():
    payload = json.dumps({"arr": list(range(50))}).encode()
    with pytest.raises(StructuredLimitError):
        parse_json_bounded(payload, EvidenceLimits(max_json_array_length=10))


def test_json_string_length_limit():
    payload = json.dumps({"s": "x" * 100}).encode()
    with pytest.raises(StructuredLimitError):
        parse_json_bounded(payload, EvidenceLimits(max_json_string_length=10))


def test_json_duplicate_keys_rejected():
    with pytest.raises(StructuredLimitError):
        parse_json_bounded(b'{"a": 1, "a": 2}')


def test_json_malformed_raises_content_error():
    with pytest.raises(ContentExtractionError):
        parse_json_bounded(b"{not json")


def test_json_valid_within_limits():
    obj = parse_json_bounded(b'{"answer": "ok", "score": 3}')
    assert obj["answer"] == "ok"


# --- CSV -------------------------------------------------------------------
def test_csv_bytes_limit():
    with pytest.raises(StructuredLimitError):
        check_csv_bounded(b"a,b,c\n1,2,3\n" * 10, EvidenceLimits(max_csv_bytes=10))


def test_csv_row_limit():
    data = ("h1,h2\n" + "\n".join("1,2" for _ in range(50))).encode()
    with pytest.raises(StructuredLimitError):
        check_csv_bounded(data, EvidenceLimits(max_csv_rows=10))


def test_csv_column_limit():
    data = (",".join(f"c{i}" for i in range(20)) + "\n").encode()
    with pytest.raises(StructuredLimitError):
        check_csv_bounded(data, EvidenceLimits(max_csv_columns=5))


def test_csv_cell_length_limit():
    data = ("h\n" + "x" * 100 + "\n").encode()
    with pytest.raises(StructuredLimitError):
        check_csv_bounded(data, EvidenceLimits(max_csv_cell_length=10))


def test_csv_total_cells_limit():
    data = ("a,b,c\n" + "\n".join("1,2,3" for _ in range(20))).encode()
    with pytest.raises(StructuredLimitError):
        check_csv_bounded(data, EvidenceLimits(max_csv_total_cells=10))


def test_csv_valid_within_limits():
    check_csv_bounded(b"name,answer\nx,used a heap\n")  # no raise


def test_structured_limit_failure_leaves_no_evidence(platform):
    from ugence_ai_hiring.normalization.models import EvidenceFormat, RawSubmission
    from ugence_ai_hiring.services import EvidenceIngestionService

    svc = EvidenceIngestionService(
        platform.evidence_repo, platform.provenance_repo, platform.chunk_repo,
        platform.quarantine_repo, platform.lineage_repo, platform.evidence_index_repo,
        platform.audit_service, limits=EvidenceLimits(max_json_fields=1))
    sub = RawSubmission(content=b'{"a":1,"b":2,"c":3}', candidate_id="c1", role_id="r1",
                        assessment_item_id="a1", declared_format=EvidenceFormat.JSON,
                        uploader="svc-ats")
    with pytest.raises(StructuredLimitError):
        svc.ingest(sub)
    from ugence_ai_hiring.index.interfaces import SearchQuery
    assert platform.search_service.search(SearchQuery(candidate_id="c1")) == ()

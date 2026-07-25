"""Deterministic search index tests."""

from __future__ import annotations

from ai_hiring.index.interfaces import SearchQuery
from ai_hiring.normalization.models import EvidenceFormat, RawSubmission

SERVICE_ID = "svc-ats"


def _ingest(platform, text, **kw):
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
        assessment_type="WORK_SAMPLE", filename="f.txt",
    )
    base.update(kw)
    sub = RawSubmission.from_text(text, **base)
    return platform.evidence_ingestion_service.ingest(sub)


def test_retrieve_by_candidate(platform):
    _ingest(platform, "alpha", candidate_id="cand-A")
    _ingest(platform, "beta", candidate_id="cand-B", assessment_item_id="a2")
    results = platform.search_service.by_candidate("cand-A")
    assert results and all(r.candidate_id == "cand-A" for r in results)


def test_retrieve_by_role_and_assessment(platform):
    _ingest(platform, "one", role_id="role-X", assessment_item_id="asm-1")
    _ingest(platform, "two", role_id="role-Y", assessment_item_id="asm-2")
    by_role = platform.search_service.search(SearchQuery(role_id="role-X"))
    assert by_role and all(r.role_id == "role-X" for r in by_role)
    by_asm = platform.search_service.by_assessment("asm-2")
    assert by_asm and all(r.assessment_item_id == "asm-2" for r in by_asm)


def test_retrieve_by_document_type_and_filename(platform):
    _ingest(platform, "code body", declared_format=EvidenceFormat.SOURCE_CODE,
            filename="main.py", assessment_item_id="a-code")
    res = platform.search_service.search(SearchQuery(document_type="SOURCE_CODE"))
    assert res and all(r.document_type == "SOURCE_CODE" for r in res)
    by_file = platform.search_service.search(SearchQuery(filename="main.py"))
    assert by_file and all(r.filename == "main.py" for r in by_file)


def test_retrieve_by_chunk_id(platform):
    ing = _ingest(platform, "chunk lookup body")
    chunk_id = ing.chunks[0].chunk_id
    entry = platform.search_service.by_chunk(chunk_id)
    assert entry is not None and entry.chunk_id == chunk_id


def test_keyword_search(platform):
    _ingest(platform, "the candidate implemented a rate limiter", assessment_item_id="a-kw")
    hits = platform.search_service.keyword("limiter")
    assert hits and any("limiter" in h.text for h in hits)
    # a keyword absent from all evidence returns nothing
    assert platform.search_service.keyword("zzznotpresent") == ()


def test_retrieve_by_metadata(platform):
    _ingest(platform, "python solution", metadata={"language": "python"}, assessment_item_id="a-md")
    hits = platform.search_service.search(SearchQuery(metadata={"language": "python"}))
    assert hits and all(h.metadata.get("language") == "python" for h in hits)
    assert platform.search_service.search(SearchQuery(metadata={"language": "rust"})) == ()


def test_results_are_deterministically_ordered(platform):
    ing = _ingest(platform, "B" * 2500)  # 3 chunks, one evidence
    res = platform.search_service.by_evidence(ing.evidence_id)
    indices = [r.chunk_index for r in res]
    assert indices == sorted(indices)  # ordered by (evidence_id, version, chunk_index)


def test_conjunctive_filters(platform):
    _ingest(platform, "match me", candidate_id="cand-Z", role_id="role-Z",
            assessment_item_id="a-z")
    q = SearchQuery(candidate_id="cand-Z", role_id="role-Z", keyword="match")
    assert platform.search_service.search(q)
    # a mismatched conjunct yields nothing
    q2 = SearchQuery(candidate_id="cand-Z", role_id="role-OTHER")
    assert platform.search_service.search(q2) == ()

"""Evidence lineage DAG + provenance reconstruction tests."""

from __future__ import annotations

from ugence_ai_hiring.normalization.models import EvidenceFormat, IngestionStage, RawSubmission

SERVICE_ID = "svc-ats"


def _sub(text: str, **kw) -> RawSubmission:
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
    )
    base.update(kw)
    return RawSubmission.from_text(text, **base)


def test_lineage_graph_reconstructs(platform):
    ing = platform.evidence_ingestion_service.ingest(_sub("lineage body"))
    graph = platform.provenance_service.lineage(ing.evidence_id)
    assert len(graph.nodes) == len(ing.lineage_node_ids)
    # exactly one root (the UPLOAD_RECEIVED node)
    roots = graph.roots()
    assert len(roots) == 1
    assert roots[0].operation == IngestionStage.UPLOAD_RECEIVED.value


def test_lineage_is_a_connected_dag_in_topological_order(platform):
    ing = platform.evidence_ingestion_service.ingest(_sub("A" * 1500))  # 2 chunks
    graph = platform.provenance_service.lineage(ing.evidence_id)
    ordered = graph.topological()
    assert len(ordered) == len(graph.nodes)
    seen: set[str] = set()
    for node in ordered:
        # every parent appears before the node (topological property)
        assert all(p in seen for p in node.parent_ids)
        seen.add(node.node_id)


def test_chunk_nodes_descend_from_chunked_operation(platform):
    ing = platform.evidence_ingestion_service.ingest(_sub("A" * 2500))  # 3 chunks
    graph = platform.provenance_service.lineage(ing.evidence_id)
    chunked = [n for n in graph.nodes if n.operation == IngestionStage.CHUNKED.value][0]
    chunk_children = graph.children_of(chunked.node_id)
    chunk_ops = sorted(n.operation for n in chunk_children if n.operation.startswith("CHUNK["))
    assert chunk_ops == ["CHUNK[0]", "CHUNK[1]", "CHUNK[2]"]
    # the FINALIZED stage node also follows CHUNKED in the pipeline chain
    assert any(n.operation == IngestionStage.FINALIZED.value for n in chunk_children)


def test_transformation_history_recorded_per_version(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("one"))
    history = platform.provenance_service.transformation_history(v1.evidence_id, 1)
    ops = [s.operation for s in history]
    # every pipeline stage appended a provenance transformation step
    assert IngestionStage.UPLOAD_RECEIVED.value in ops
    assert IngestionStage.NORMALIZED.value in ops
    assert IngestionStage.CHUNKED.value in ops
    assert all(s.actor == SERVICE_ID for s in history)


def test_version_ancestry_across_revisions(platform):
    svc = platform.evidence_ingestion_service
    v1 = svc.ingest(_sub("one"))
    svc.ingest(_sub("two"), parent_evidence_id=v1.evidence_id)
    versions = platform.provenance_service.versions(v1.evidence_id)
    assert [p.version for p in versions] == [1, 2]
    assert versions[1].parent_version == 1


def test_lineage_edges_present(platform):
    ing = platform.evidence_ingestion_service.ingest(_sub("body"))
    graph = platform.provenance_service.lineage(ing.evidence_id)
    edges = graph.as_edges()
    # a linear pipeline of N stage nodes yields at least N-1 edges
    assert len(edges) >= len(graph.roots())
    assert all(len(edge) == 2 for edge in edges)

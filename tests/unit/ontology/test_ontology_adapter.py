"""
Tests for Ontology Signal Adapter (O2)
=======================================

Verifies the ontology encoding and similarity adapter that bridges
backbone capabilities into the framework signal path.
"""

from __future__ import annotations

import pytest

from agentic.agentic_framework.signal_adapters.ontology_adapter import (
    OntologyEncodingResolution,
    OntologySimilarityResolution,
    resolve_ontology_encoding,
    resolve_ontology_similarity,
)


# =========================================================================
# OntologyEncodingResolution contract
# =========================================================================

class TestEncodingResolutionContract:
    """Verify the encoding resolution dataclass contract."""

    def test_frozen(self) -> None:
        res = OntologyEncodingResolution(available=False)
        with pytest.raises(AttributeError):
            res.available = True  # type: ignore[misc]

    def test_unavailable_defaults(self) -> None:
        res = OntologyEncodingResolution(available=False)
        assert res.dimensions == {}
        assert res.content_hash == ""
        assert res.dominant_dimensions == ()
        assert res.word_count == 0

    def test_to_dict_structure(self) -> None:
        res = OntologyEncodingResolution(
            available=True,
            dimensions={"ACTION": 0.5, "MIND": 0.3},
            content_hash="abc123",
            dominant_dimensions=(("ACTION", 0.5), ("MIND", 0.3)),
            word_count=10,
        )
        d = res.to_dict()
        assert d["available"] is True
        assert d["dimensions"]["ACTION"] == 0.5
        assert d["content_hash"] == "abc123"
        assert d["word_count"] == 10
        assert len(d["dominant_dimensions"]) == 2
        assert d["dominant_dimensions"][0]["dimension"] == "ACTION"


# =========================================================================
# OntologySimilarityResolution contract
# =========================================================================

class TestSimilarityResolutionContract:
    """Verify the similarity resolution dataclass contract."""

    def test_frozen(self) -> None:
        res = OntologySimilarityResolution(available=False)
        with pytest.raises(AttributeError):
            res.available = True  # type: ignore[misc]

    def test_unavailable_defaults(self) -> None:
        res = OntologySimilarityResolution(available=False)
        assert res.score == 0.0
        assert res.dimension_similarities == {}
        assert res.dominant_shared == ()
        assert res.divergent == ()
        assert res.explanation == ""

    def test_to_dict_structure(self) -> None:
        res = OntologySimilarityResolution(
            available=True,
            score=0.75,
            method="structural",
            dominant_shared=(("ACTION", 0.6, 0.7),),
            divergent=(("BODY", 0.1, 0.8),),
            explanation="Moderate structural similarity.",
        )
        d = res.to_dict()
        assert d["available"] is True
        assert d["score"] == 0.75
        assert d["method"] == "structural"
        assert d["dominant_shared"][0]["dimension"] == "ACTION"
        assert d["divergent"][0]["dimension"] == "BODY"


# =========================================================================
# resolve_ontology_encoding
# =========================================================================

class TestResolveOntologyEncoding:
    """Verify the encoding resolve function."""

    def test_basic_encoding(self) -> None:
        res = resolve_ontology_encoding("The war divided the nation in 1861")
        assert res.available is True
        assert len(res.dimensions) == 10
        assert all(0.0 <= v <= 1.0 for v in res.dimensions.values())
        assert len(res.content_hash) == 32
        assert res.word_count > 0

    def test_all_ten_dimensions_present(self) -> None:
        res = resolve_ontology_encoding("A simple test sentence")
        expected_dims = {
            "ACTION", "IDENTIFICATION", "BODY", "MIND", "EGO",
            "INTELLECT", "SOUL", "WITNESS", "SINGULARITY", "ABSOLUTE",
        }
        assert set(res.dimensions.keys()) == expected_dims

    def test_dominant_dimensions_ordered(self) -> None:
        res = resolve_ontology_encoding("The king decided to fight the war")
        assert res.available is True
        assert len(res.dominant_dimensions) <= 3
        if len(res.dominant_dimensions) >= 2:
            assert res.dominant_dimensions[0][1] >= res.dominant_dimensions[1][1]

    def test_empty_content(self) -> None:
        res = resolve_ontology_encoding("")
        assert res.available is True
        assert all(v == 0.0 for v in res.dimensions.values())

    def test_whitespace_only(self) -> None:
        res = resolve_ontology_encoding("   ")
        assert res.available is True
        assert all(v == 0.0 for v in res.dimensions.values())

    def test_deterministic(self) -> None:
        text = "The empire rose and fell over centuries"
        res1 = resolve_ontology_encoding(text)
        res2 = resolve_ontology_encoding(text)
        assert res1.dimensions == res2.dimensions
        assert res1.content_hash == res2.content_hash
        assert res1.dominant_dimensions == res2.dominant_dimensions

    def test_different_content_different_hash(self) -> None:
        res1 = resolve_ontology_encoding("First text about war")
        res2 = resolve_ontology_encoding("Second text about peace")
        assert res1.content_hash != res2.content_hash

    def test_to_dict_serializable(self) -> None:
        import json
        res = resolve_ontology_encoding("Test content for serialization")
        d = res.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        deserialized = json.loads(serialized)
        assert deserialized["available"] is True

    def test_source_detail(self) -> None:
        res = resolve_ontology_encoding("test")
        assert "ontology_backbone_10d" in res.source_detail


# =========================================================================
# resolve_ontology_similarity
# =========================================================================

class TestResolveOntologySimilarity:
    """Verify the similarity resolve function."""

    def test_basic_similarity(self) -> None:
        res = resolve_ontology_similarity(
            "The Civil War divided the nation",
            "The family was torn apart by conflict",
        )
        assert res.available is True
        assert 0.0 <= res.score <= 1.0
        assert res.method == "structural"

    def test_identical_content_high_similarity(self) -> None:
        text = "The king ruled the kingdom with absolute power"
        res = resolve_ontology_similarity(text, text)
        assert res.available is True
        assert res.score >= 0.9

    def test_dimension_similarities_complete(self) -> None:
        res = resolve_ontology_similarity("war and peace", "love and hate")
        assert res.available is True
        assert len(res.dimension_similarities) == 10

    def test_dominant_shared_tuples(self) -> None:
        res = resolve_ontology_similarity(
            "The empire was destroyed by internal conflict",
            "The company collapsed from internal divisions",
        )
        assert res.available is True
        for item in res.dominant_shared:
            assert len(item) == 3
            name, s1, s2 = item
            assert isinstance(name, str)
            assert isinstance(s1, float)
            assert isinstance(s2, float)

    def test_divergent_tuples(self) -> None:
        res = resolve_ontology_similarity(
            "The spiritual journey of the soul",
            "The physical structure of the building",
        )
        assert res.available is True
        for item in res.divergent:
            assert len(item) == 3

    def test_cosine_method(self) -> None:
        res = resolve_ontology_similarity(
            "action and movement",
            "stillness and rest",
            method="cosine",
        )
        assert res.available is True
        assert res.method == "cosine"

    def test_euclidean_method(self) -> None:
        res = resolve_ontology_similarity(
            "action and movement",
            "stillness and rest",
            method="euclidean",
        )
        assert res.available is True
        assert res.method == "euclidean"

    def test_deterministic(self) -> None:
        t1, t2 = "The war began", "The conflict started"
        res1 = resolve_ontology_similarity(t1, t2)
        res2 = resolve_ontology_similarity(t1, t2)
        assert res1.score == res2.score
        assert res1.dimension_similarities == res2.dimension_similarities

    def test_explanation_present(self) -> None:
        res = resolve_ontology_similarity("light", "darkness")
        assert res.available is True
        assert isinstance(res.explanation, str)
        assert len(res.explanation) > 0

    def test_to_dict_serializable(self) -> None:
        import json
        res = resolve_ontology_similarity("alpha", "beta")
        d = res.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)

    def test_source_detail(self) -> None:
        res = resolve_ontology_similarity("a", "b")
        assert "ontology_backbone_similarity" in res.source_detail


# =========================================================================
# Fail-closed behavior
# =========================================================================

class TestFailClosed:
    """Verify fail-closed behavior (errors -> unavailable, never raise)."""

    def test_encoding_with_none_graceful(self) -> None:
        # The backbone encoder handles None gracefully (treats as empty).
        # The adapter should never raise regardless.
        res = resolve_ontology_encoding(None)  # type: ignore[arg-type]
        assert isinstance(res, OntologyEncodingResolution)
        # Either available with zero vector, or unavailable — both are acceptable
        assert isinstance(res.available, bool)

    def test_similarity_with_none_graceful(self) -> None:
        res = resolve_ontology_similarity(None, "text")  # type: ignore[arg-type]
        assert isinstance(res, OntologySimilarityResolution)
        assert isinstance(res.available, bool)

    def test_encoding_never_raises(self) -> None:
        """No input should cause resolve_ontology_encoding to raise."""
        for bad_input in [None, 42, [], {}, True, b"bytes"]:
            res = resolve_ontology_encoding(bad_input)  # type: ignore[arg-type]
            assert isinstance(res, OntologyEncodingResolution)

    def test_similarity_never_raises(self) -> None:
        """No input should cause resolve_ontology_similarity to raise."""
        for bad1, bad2 in [(None, None), (42, "text"), ("text", [])]:
            res = resolve_ontology_similarity(bad1, bad2)  # type: ignore[arg-type]
            assert isinstance(res, OntologySimilarityResolution)


# =========================================================================
# Framework integration
# =========================================================================

class TestFrameworkIntegration:
    """Verify the adapter is properly wired into the signal_adapters package."""

    def test_importable_from_package(self) -> None:
        from agentic.agentic_framework.signal_adapters import (
            resolve_ontology_encoding as pkg_encode,
            resolve_ontology_similarity as pkg_sim,
            OntologyEncodingResolution as PkgEncRes,
            OntologySimilarityResolution as PkgSimRes,
        )
        assert pkg_encode is resolve_ontology_encoding
        assert pkg_sim is resolve_ontology_similarity
        assert PkgEncRes is OntologyEncodingResolution
        assert PkgSimRes is OntologySimilarityResolution

    def test_in_package_all(self) -> None:
        from agentic.agentic_framework import signal_adapters
        assert "resolve_ontology_encoding" in signal_adapters.__all__
        assert "resolve_ontology_similarity" in signal_adapters.__all__
        assert "OntologyEncodingResolution" in signal_adapters.__all__
        assert "OntologySimilarityResolution" in signal_adapters.__all__


# =========================================================================
# Canonical ontology source verification
# =========================================================================

class TestCanonicalSourceUsage:
    """Verify the adapter consumes canonical ontology modules."""

    def test_encoding_uses_canonical_encoder(self) -> None:
        """The encoding resolution's content_hash matches direct encoder output."""
        from agentic.ontology.backbone.encoder import encode_10d

        text = "Deterministic encoding test"
        adapter_res = resolve_ontology_encoding(text)
        direct_vec = encode_10d(text)

        assert adapter_res.content_hash == direct_vec.content_hash
        for dim_name, score in adapter_res.dimensions.items():
            # Verify scores match direct encoder output
            from agentic.ontology.backbone.encoder import Dimension
            dim = Dimension[dim_name]
            assert score == direct_vec.get(dim)

    def test_similarity_uses_canonical_similarity(self) -> None:
        """The similarity resolution's score matches direct similarity output."""
        from agentic.ontology.backbone.encoder import encode_10d
        from agentic.ontology.backbone.similarity import compute_similarity

        t1, t2 = "War and conflict", "Peace and harmony"
        adapter_res = resolve_ontology_similarity(t1, t2)
        direct_res = compute_similarity(encode_10d(t1), encode_10d(t2), "structural")

        assert adapter_res.score == direct_res.score

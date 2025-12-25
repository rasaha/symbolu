#!/usr/bin/env python3
"""
Export Ontological Data to RAG Storage
========================================

Exports training data, test samples, and model artifacts to RAG-compatible
formats (vector DB, graph DB, knowledge base).

Usage:
    python -m symbolu.ontological.export_to_rag
    python -m symbolu.ontological.export_to_rag --training-data data/training_drishti_data.json
    python -m symbolu.ontological.export_to_rag --output-dir data/rag --analyze-samples

Outputs:
    data/rag/knowledge_base.json   - Complete knowledge base with patterns and relationships
    data/rag/vector_export.json    - Formatted for Pinecone/Weaviate
    data/rag/graph_export.json     - Formatted for Neo4j
    data/rag/documents.json        - Indexed document analyses
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# Check for PyTorch
try:
    import torch
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu.ontological.rag_storage import (
    OntologicalRAGStorage,
    OntologicalDocument,
    create_rag_schema,
)
from symbolu.ontological.types import LAYER_NAMES


def load_training_data(training_data_path: str) -> Optional[Dict[str, Any]]:
    """Load training data from JSON file."""
    path = Path(training_data_path)
    if not path.exists():
        print(f"Training data not found at: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded training data from: {path}")
    print(f"  - Epochs: {data['config']['epochs']}")
    print(f"  - Best validation accuracy: {data['config']['best_val_acc']:.2%}")
    print(f"  - Test results: {len(data.get('test_results', []))} samples")

    return data


def analyze_sample_texts(engine, texts: List[str]) -> List[Dict[str, Any]]:
    """Analyze a list of texts with the trained engine."""
    results = []
    for text in texts:
        analysis = engine.analyze(text)
        results.append({
            "text": text,
            **analysis,
        })
    return results


def export_training_data_to_rag(
    training_data: Dict[str, Any],
    storage: OntologicalRAGStorage,
    output_dir: str,
) -> None:
    """Export training data artifacts to RAG storage."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Index test results as documents
    test_results = training_data.get("test_results", [])
    for i, result in enumerate(test_results):
        doc = OntologicalDocument(
            doc_id=f"test_{i:04d}",
            text=result["text"],
            dominant_layer=result["dominant_layer"],
            confidence=result["confidence"],
            certainty_level=result["certainty_level"],
            ontological_vector=[],  # Not saved in training data
            bhava_vector=[],
            full_vector=[],
            coherence=result["coherence"],
            uncertainty=0.0,
            strongest_relationships=result["strongest_relationships"],
            reasoning_score=0.0,
            creativity_score=0.0,
            relationship_matrix=[],
            metadata={
                "source": "training_test",
                "epoch": training_data["config"]["epochs"],
            },
        )
        storage.documents[doc.doc_id] = doc

    print(f"Indexed {len(test_results)} test results as documents")

    # 2. Store learned Drishti deviations as metadata
    final_drishti = training_data.get("final_drishti", {})
    drishti_file = output_path / "learned_drishti.json"
    with open(drishti_file, "w", encoding="utf-8") as f:
        json.dump({
            "description": "Learned deviations from initial Vedic Drishti patterns",
            "learned_aspect_matrix": final_drishti.get("learned_aspect_matrix", []),
            "learned_drishti_patterns": final_drishti.get("learned_drishti_patterns", []),
            "significant_deviations": final_drishti.get("significant_deviations", []),
            "total_deviations": final_drishti.get("total_deviations", 0),
            "training_config": training_data["config"],
        }, f, indent=2)
    print(f"Saved learned Drishti patterns to: {drishti_file}")

    # 3. Store relationship statistics
    rel_stats = training_data.get("final_relationship_stats", {})
    rel_file = output_path / "relationship_stats.json"
    with open(rel_file, "w", encoding="utf-8") as f:
        json.dump({
            "description": "Final relationship statistics from training",
            "avg_coherence": rel_stats.get("avg_coherence", 0),
            "pattern_distribution": rel_stats.get("pattern_distribution", {}),
            "pattern_avg_strength": rel_stats.get("pattern_avg_strength", {}),
            "strongest_relationships": rel_stats.get("strongest_relationships", []),
        }, f, indent=2)
    print(f"Saved relationship statistics to: {rel_file}")

    # 4. Store training history
    history_file = output_path / "training_history.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump({
            "description": "Per-epoch training metrics",
            "history": training_data.get("history", []),
        }, f, indent=2)
    print(f"Saved training history to: {history_file}")


def export_with_model(
    model_path: str,
    sample_texts: List[str],
    storage: OntologicalRAGStorage,
    output_dir: str,
) -> None:
    """Load trained model and analyze sample texts for RAG export."""
    if not PYTORCH_AVAILABLE:
        print("PyTorch not available. Skipping model-based export.")
        return

    from symbolu.ontological.unified_engine import UnifiedOntologicalEngineV2

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load model
    model_file = Path(model_path)
    if not model_file.exists():
        print(f"Model not found at: {model_file}")
        print("Run training first: python -m symbolu.ontological.train_v2")
        return

    print(f"Loading model from: {model_file}")
    engine = UnifiedOntologicalEngineV2()
    engine.load_state_dict(torch.load(model_file, map_location="cpu"))
    engine.eval()

    # Analyze sample texts
    print(f"\nAnalyzing {len(sample_texts)} sample texts...")
    for i, text in enumerate(sample_texts):
        analysis = engine.analyze(text)

        doc = OntologicalDocument.from_analysis(
            doc_id=f"sample_{i:04d}",
            text=text,
            analysis=analysis,
            metadata={"source": "sample_export"},
        )
        storage.index_document(
            doc_id=doc.doc_id,
            text=text,
            analysis=analysis,
            metadata={"source": "sample_export"},
        )

        print(f"  [{i+1}/{len(sample_texts)}] {text[:50]}...")
        print(f"    → {analysis['dominant_layer']} ({analysis['confidence']:.1%})")

    print(f"\nIndexed {len(sample_texts)} documents to storage")


def run_full_export(
    training_data_path: str = "data/training_drishti_data.json",
    model_path: str = "checkpoints/unified_v2_best.pt",
    output_dir: str = "data/rag",
    analyze_samples: bool = False,
) -> Dict[str, Any]:
    """Run complete RAG export pipeline."""

    print("=" * 70)
    print("   ONTOLOGICAL DATA → RAG EXPORT")
    print("=" * 70)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Initialize storage
    storage = OntologicalRAGStorage()

    # 1. Export RAG schema
    print("\n1. CREATING RAG SCHEMA")
    print("-" * 70)
    schema = create_rag_schema()
    schema_file = output_path / "schema.json"
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Schema saved to: {schema_file}")
    print(f"  - Vector dimension: {schema['vector_index']['dimension']}D")
    print(f"  - Metadata fields: {len(schema['metadata_fields'])}")

    # 2. Load and export training data if available
    print("\n2. LOADING TRAINING DATA")
    print("-" * 70)
    training_data = load_training_data(training_data_path)
    if training_data:
        export_training_data_to_rag(training_data, storage, output_dir)

    # 3. Analyze sample texts with trained model
    if analyze_samples:
        print("\n3. ANALYZING SAMPLE TEXTS")
        print("-" * 70)

        sample_texts = [
            "What is the nature of consciousness?",
            "Implement a binary search algorithm in Python",
            "The melody dances through shadows of forgotten dreams",
            "If A implies B and B implies C, then A implies C",
            "AI systems must be designed with fairness and transparency",
            "The quantum field collapses upon observation",
            "Calculate the derivative of x squared plus 3x",
            "Beauty lies in the harmony of opposing forces",
            "The recursive function calls itself until base case",
            "Ethical considerations must guide technological progress",
            "I think, therefore I am",
            "The universe tends toward entropy",
        ]

        export_with_model(model_path, sample_texts, storage, output_dir)

    # 4. Export to various formats
    print("\n4. EXPORTING TO RAG FORMATS")
    print("-" * 70)

    # Knowledge base (complete)
    kb_file = output_path / "knowledge_base.json"
    storage.export_knowledge_base(str(kb_file))

    # Vector DB format (Pinecone/Weaviate)
    vector_data = storage.export_for_vector_db()
    vector_file = output_path / "vector_export.json"
    with open(vector_file, "w", encoding="utf-8") as f:
        json.dump(vector_data, f, indent=2)
    print(f"Vector DB export saved to: {vector_file}")
    print(f"  - Vectors: {len(vector_data['vectors'])}")
    print(f"  - Dimension: {vector_data['dimension']}D")

    # Graph DB format (Neo4j)
    graph_data = storage.export_for_graph_db()
    graph_file = output_path / "graph_export.json"
    with open(graph_file, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)
    print(f"Graph DB export saved to: {graph_file}")
    print(f"  - Nodes: {len(graph_data['nodes'])}")
    print(f"  - Edges: {len(graph_data['edges'])}")

    # Summary
    print("\n" + "=" * 70)
    print("   EXPORT COMPLETE")
    print("=" * 70)

    files_created = list(output_path.glob("*.json"))
    print(f"\nFiles created in {output_dir}:")
    for f in sorted(files_created):
        size = f.stat().st_size / 1024
        print(f"  - {f.name} ({size:.1f} KB)")

    print("\nRAG Integration:")
    print("  • Vector DB: Use vector_export.json with Pinecone/Weaviate")
    print("  • Graph DB: Use graph_export.json with Neo4j")
    print("  • Full KB: Use knowledge_base.json for complete data")

    return {
        "output_dir": str(output_dir),
        "files_created": [str(f) for f in files_created],
        "documents_indexed": len(storage.documents),
        "relationships": len(storage.relationships),
        "patterns": len(storage.patterns),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export ontological data to RAG storage")
    parser.add_argument(
        "--training-data",
        default="data/training_drishti_data.json",
        help="Path to training data JSON file",
    )
    parser.add_argument(
        "--model",
        default="checkpoints/unified_v2_best.pt",
        help="Path to trained model checkpoint",
    )
    parser.add_argument(
        "--output-dir",
        default="data/rag",
        help="Output directory for RAG exports",
    )
    parser.add_argument(
        "--analyze-samples",
        action="store_true",
        help="Analyze sample texts with trained model",
    )

    args = parser.parse_args()

    result = run_full_export(
        training_data_path=args.training_data,
        model_path=args.model,
        output_dir=args.output_dir,
        analyze_samples=args.analyze_samples,
    )

    print(f"\nExport summary:")
    print(f"  Documents indexed: {result['documents_indexed']}")
    print(f"  Relationships: {result['relationships']}")
    print(f"  Drishti patterns: {result['patterns']}")

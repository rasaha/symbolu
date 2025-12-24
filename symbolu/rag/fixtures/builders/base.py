"""
Base Corpus Builder
===================

Abstract base class and types for corpus document generation.
"""

import json
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class DocumentSpec:
    """
    Specification for a single document in a corpus.

    Attributes:
        doc_id: Unique document identifier
        corpus_id: Parent corpus identifier
        title: Document title
        content: Full text content
        metadata: Extended metadata for retrieval/filtering
    """
    doc_id: str
    corpus_id: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Auto-calculate token count (rough estimate: ~4 chars per token)
        if "token_count" not in self.metadata:
            self.metadata["token_count"] = len(self.content) // 4

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    def to_text(self) -> str:
        """Format as plain text document with metadata header."""
        lines = [
            f"# {self.title}",
            "",
            f"Document ID: {self.doc_id}",
            f"Corpus: {self.corpus_id}",
            f"Domain: {self.metadata.get('domain', 'unknown')}",
            f"Tags: {', '.join(self.metadata.get('tags', []))}",
            f"Difficulty: {self.metadata.get('difficulty', 'intermediate')}",
            "",
            "---",
            "",
            self.content
        ]
        return "\n".join(lines)

    def generate_chunks(self, chunk_size: int = 300, overlap: int = 50) -> List[Dict[str, Any]]:
        """
        Generate chunk specifications for this document.

        Args:
            chunk_size: Target characters per chunk
            overlap: Character overlap between chunks

        Returns:
            List of chunk dictionaries
        """
        chunks = []
        text = self.content
        idx = 0
        chunk_num = 0

        while idx < len(text):
            end = idx + chunk_size
            chunk_text = text[idx:end]

            # Generate deterministic chunk ID
            chunk_hash = hashlib.md5(
                f"{self.doc_id}:{chunk_num}:{chunk_text[:50]}".encode()
            ).hexdigest()[:8]

            chunks.append({
                "chunk_id": f"{self.doc_id}_c{chunk_num}_{chunk_hash}",
                "text": chunk_text,
                "doc_id": self.doc_id,
                "chunk_index": chunk_num,
                "embedding_ready": True
            })

            chunk_num += 1
            idx = end - overlap if end < len(text) else end

        return chunks


class CorpusBuilder(ABC):
    """
    Abstract base class for corpus builders.

    Subclasses must implement:
    - corpus_id: The corpus identifier
    - build_documents(): Generate all documents
    """

    @property
    @abstractmethod
    def corpus_id(self) -> str:
        """Return the corpus identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return corpus description."""
        pass

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return primary domain."""
        pass

    @abstractmethod
    def build_documents(self) -> List[DocumentSpec]:
        """Generate all documents for this corpus."""
        pass

    def build_manifest(self) -> Dict[str, Any]:
        """Generate corpus manifest."""
        docs = self.build_documents()
        return {
            "corpus_id": self.corpus_id,
            "description": self.description,
            "domain": self.domain,
            "document_count": len(docs),
            "documents": [d.doc_id for d in docs],
            "metadata": {
                "generated": True,
                "version": "1.0",
                "source": f"{self.__class__.__name__}"
            }
        }

    def write_to_directory(self, base_path: Path) -> int:
        """
        Write all documents to a directory.

        Args:
            base_path: Base directory for corpus files

        Returns:
            Number of documents written
        """
        corpus_dir = base_path / self.corpus_id
        corpus_dir.mkdir(parents=True, exist_ok=True)

        docs = self.build_documents()

        for doc in docs:
            # Write as .txt file
            file_path = corpus_dir / f"{doc.doc_id}.txt"
            file_path.write_text(doc.to_text(), encoding="utf-8")

        # Write manifest
        manifest_path = corpus_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(self.build_manifest(), indent=2),
            encoding="utf-8"
        )

        return len(docs)

    def write_json_corpus(self, output_path: Path) -> int:
        """
        Write corpus as single JSON file with full structure.

        Args:
            output_path: Path to output JSON file

        Returns:
            Number of documents written
        """
        docs = self.build_documents()

        corpus_data = {
            "corpus_id": self.corpus_id,
            "description": self.description,
            "domain": self.domain,
            "document_count": len(docs),
            "documents": []
        }

        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["chunks"] = doc.generate_chunks()
            corpus_data["documents"].append(doc_data)

        output_path.write_text(
            json.dumps(corpus_data, indent=2),
            encoding="utf-8"
        )

        return len(docs)

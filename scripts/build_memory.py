#!/usr/bin/env python3
"""
Symbol-U Episodic Memory Builder
================================

Offline script to populate the Episodic Memory Store with WikiText-103.
This runs SEPARATELY from training - it does not touch the GPU training loop.

The embeddings are generated using a frozen sentence-transformers model
(all-MiniLM-L6-v2), completely separate from the Sovereign Model's weights.

Usage:
------
    # Build from WikiText-103 validation split (smaller, for testing)
    python scripts/build_memory.py --split validation

    # Build from WikiText-103 train split (full corpus)
    python scripts/build_memory.py --split train --limit 100000

    # Custom persistence path
    python scripts/build_memory.py --output ./data/my_memory

Dependencies:
-------------
- datasets (HuggingFace)
- sentence-transformers
- chromadb
- tqdm

Version: 1.0.0
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Iterator

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_wikitext103(split: str = "validation", limit: int = None):
    """
    Load WikiText-103 dataset from HuggingFace.

    Args:
        split: Dataset split ("train", "validation", or "test")
        limit: Maximum number of examples to load (None for all)

    Returns:
        HuggingFace Dataset object
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError(
            "datasets is required. Install with: pip install datasets"
        )

    logger.info(f"Loading WikiText-103 ({split} split)...")
    dataset = load_dataset("wikitext", "wikitext-103-v1", split=split)

    if limit is not None:
        dataset = dataset.select(range(min(limit, len(dataset))))
        logger.info(f"Limited to {len(dataset)} examples")

    logger.info(f"Loaded {len(dataset)} examples from WikiText-103 {split}")
    return dataset


class TextChunker:
    """
    Text chunker using sentence-transformers tokenizer.

    Ensures chunks fit within the embedding model's window
    without truncation artifacts.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        """
        Initialize the chunker.

        Args:
            model_name: Sentence-transformers model (for tokenizer)
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_name = model_name

        # Load tokenizer from sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )

        logger.info(f"Loading tokenizer from {model_name}...")
        self._model = SentenceTransformer(model_name)
        self._tokenizer = self._model.tokenizer

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []

        # Tokenize the full text
        tokens = self._tokenizer.encode(text, add_special_tokens=False)

        if len(tokens) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        # Create overlapping chunks
        chunks = []
        start = 0
        stride = self.chunk_size - self.chunk_overlap

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]

            # Decode back to text
            chunk_text = self._tokenizer.decode(chunk_tokens, skip_special_tokens=True)
            chunk_text = chunk_text.strip()

            if chunk_text:
                chunks.append(chunk_text)

            start += stride

            # Prevent infinite loop on edge cases
            if start >= len(tokens):
                break

        return chunks

    def chunk_documents(self, texts: List[str]) -> Iterator[str]:
        """
        Chunk multiple documents.

        Args:
            texts: List of document texts

        Yields:
            Individual text chunks
        """
        for text in texts:
            for chunk in self.chunk_text(text):
                yield chunk


def build_episodic_memory(
    output_path: str = "./data/episodic_memory",
    split: str = "validation",
    limit: int = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    batch_size: int = 100,
) -> int:
    """
    Build the episodic memory from WikiText-103.

    Args:
        output_path: Path for ChromaDB persistence
        split: WikiText-103 split to use
        limit: Maximum number of source documents
        chunk_size: Chunk size in tokens
        chunk_overlap: Overlap between chunks
        batch_size: Batch size for embedding/insertion

    Returns:
        Total number of chunks indexed
    """
    from symbolu.rag.episodic_store import EpisodicMemoryStore

    try:
        from tqdm import tqdm
    except ImportError:
        # Fallback if tqdm not installed
        def tqdm(iterable, **kwargs):
            return iterable

    # Load dataset
    dataset = load_wikitext103(split=split, limit=limit)

    # Initialize chunker
    chunker = TextChunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    # Chunk all documents
    logger.info("Chunking documents...")
    all_chunks = []
    for example in tqdm(dataset, desc="Chunking"):
        text = example.get("text", "")
        if text and text.strip():
            chunks = chunker.chunk_text(text)
            all_chunks.extend(chunks)

    logger.info(f"Created {len(all_chunks)} chunks from {len(dataset)} documents")

    if not all_chunks:
        logger.warning("No chunks created - dataset may be empty")
        return 0

    # Initialize memory store
    logger.info(f"Initializing EpisodicMemoryStore at {output_path}...")
    memory = EpisodicMemoryStore(persistence_path=output_path)

    # Check if we're adding to existing or starting fresh
    existing_count = memory.count()
    if existing_count > 0:
        logger.info(f"Found {existing_count} existing chunks in memory")
        response = input(f"Clear existing memory? (y/N): ").strip().lower()
        if response == "y":
            memory.clear()
            logger.info("Memory cleared")

    # Insert chunks in batches with progress bar
    logger.info("Indexing chunks into episodic memory...")
    source = f"WikiText-103-{split}"

    total_added = 0
    for i in tqdm(range(0, len(all_chunks), batch_size), desc="Indexing"):
        batch = all_chunks[i:i + batch_size]
        metadata = [{"chunk_index": i + j, "split": split} for j in range(len(batch))]
        added = memory.add_memories(
            texts=batch,
            sources=[source],
            metadata=metadata,
            batch_size=batch_size,
        )
        total_added += added

    logger.info(f"Indexing complete! Total chunks in memory: {memory.count()}")

    # Print stats
    stats = memory.get_stats()
    logger.info(f"Memory stats: {stats}")

    return total_added


def main():
    parser = argparse.ArgumentParser(
        description="Build Episodic Memory from WikiText-103",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with validation split
  python scripts/build_memory.py --split validation

  # Full build with train split (limited)
  python scripts/build_memory.py --split train --limit 50000

  # Custom output path
  python scripts/build_memory.py --output ./my_memory --split validation
        """,
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./data/episodic_memory",
        help="Output path for ChromaDB persistence (default: ./data/episodic_memory)",
    )

    parser.add_argument(
        "--split", "-s",
        type=str,
        default="validation",
        choices=["train", "validation", "test"],
        help="WikiText-103 split to use (default: validation)",
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Maximum number of source documents to process (default: all)",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Chunk size in tokens (default: 500)",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Overlap between chunks in tokens (default: 50)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for embedding/insertion (default: 100)",
    )

    args = parser.parse_args()

    try:
        total = build_episodic_memory(
            output_path=args.output,
            split=args.split,
            limit=args.limit,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            batch_size=args.batch_size,
        )
        logger.info(f"Successfully indexed {total} chunks")
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"Build failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

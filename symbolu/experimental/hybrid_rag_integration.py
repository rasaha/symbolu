#!/usr/bin/env python3
"""
Hybrid RAG Integration: Token + State-Delta Fusion
===================================================

This module bridges traditional token-based RAG with State-Delta retrieval,
providing a unified interface that leverages both paradigms.

Architecture:
------------
                    Query
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
   Traditional RAG           State-Delta RAG
   (Token/Chunk)             (Meaning/Trajectory)
          │                       │
          ▼                       ▼
   Lexical Match            Semantic Match
   - Keywords               - Topic similarity
   - Exact phrases          - Ontology pattern
   - Surface similarity     - Entropy alignment
          │                       │
          └───────────┬───────────┘
                      ▼
               ┌──────────────┐
               │ Fusion Layer │
               │  (weighted)  │
               └──────────────┘
                      │
                      ▼
              CandidateEntry[]
              (Unified Output)

Why Hybrid?
-----------
- Token RAG: Fast, good for exact matches, keyword recall
- State-Delta: Slower, but captures MEANING structure

Example:
  Query: "How do proteins fold?"

  Token RAG returns:
    "Protein folding is the process..."  (keyword match)

  State-Delta returns:
    "Hydrophobic cores form first because..."  (same meaning position)

  Hybrid merges both, capturing keyword relevance AND semantic depth.

Usage:
------
    from symbolu.experimental import HybridRAGEngine

    engine = HybridRAGEngine()

    # Index documents (builds both token and state indices)
    engine.index_corpus("biology", "data/biology/", domain="biology")

    # Query (fuses both retrieval methods)
    results = engine.query(
        query_text="How do proteins fold?",
        query_state=cognitive_state,  # From StateProjector
        expected_transition="QUESTIONING->FACTUAL",
        top_k=5,
    )
"""

import torch
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

# Traditional RAG imports
from ..rag.utils.types import CandidateEntry, ScoredChunk
from ..rag.stitching.pipeline import (
    index_corpus as token_index_corpus,
    run_rag as token_run_rag,
)
from ..rag.vectorstore.memory_store import get_global_store

# State-Delta RAG imports
from .state_retrieval import (
    StateTrajectory,
    RetrievalResult,
    StateTrajectoryIndex,
)
from .cognitive_state import StateProjector, CognitiveStateProjectorLite

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class FusionMode(Enum):
    """How to combine Token and State-Delta results."""
    TOKEN_ONLY = "token_only"          # Traditional RAG only
    STATE_ONLY = "state_only"          # State-Delta RAG only
    WEIGHTED_AVERAGE = "weighted_avg"  # Weighted combination
    RECIPROCAL_RANK = "rrf"            # Reciprocal Rank Fusion
    RERANKING = "rerank"               # Use State-Delta to rerank Token results


@dataclass
class HybridRAGConfig:
    """Configuration for Hybrid RAG Engine."""

    # Fusion mode
    mode: FusionMode = FusionMode.WEIGHTED_AVERAGE

    # Weights for weighted average fusion
    token_weight: float = 0.4  # Weight for traditional RAG
    state_weight: float = 0.6  # Weight for State-Delta RAG

    # State-Delta retrieval weights
    topic_weight: float = 0.4
    ontology_weight: float = 0.4
    entropy_weight: float = 0.2

    # RRF parameter (for reciprocal rank fusion)
    rrf_k: int = 60

    # Top-k for each retrieval method before fusion
    token_top_k: int = 10
    state_top_k: int = 10

    # Final output size
    output_top_k: int = 5

    # Score normalization
    normalize_scores: bool = True

    # Minimum score threshold
    min_score: float = 0.0

    def validate(self):
        """Validate configuration."""
        if self.mode == FusionMode.WEIGHTED_AVERAGE:
            total = self.token_weight + self.state_weight
            if abs(total - 1.0) > 0.01:
                raise ValueError(f"Weights must sum to 1.0, got {total}")


# =============================================================================
# HYBRID RAG ENGINE
# =============================================================================

class HybridRAGEngine:
    """
    Unified RAG engine combining token-based and state-delta retrieval.

    This engine provides a single interface for:
    1. Indexing documents (creates both token chunks and state trajectories)
    2. Querying (fuses results from both retrieval methods)
    3. Explanation (shows why each result was retrieved)
    """

    def __init__(
        self,
        config: Optional[HybridRAGConfig] = None,
        state_projector: Optional[Union[StateProjector, CognitiveStateProjectorLite]] = None,
        state_dim: int = 124,
        hidden_dim: int = 768,
    ):
        """
        Initialize Hybrid RAG Engine.

        Args:
            config: Hybrid RAG configuration
            state_projector: Pre-initialized state projector (creates one if None)
            state_dim: Dimension of cognitive states
            hidden_dim: Dimension of hidden states (for projector)
        """
        self.config = config or HybridRAGConfig()
        self.config.validate()

        self.state_dim = state_dim
        self.hidden_dim = hidden_dim

        # Token-based store (uses global singleton)
        self.token_store = get_global_store()

        # State-Delta index
        self.state_index = StateTrajectoryIndex(state_dim=state_dim)

        # State projector (for converting text to states)
        self.state_projector = state_projector

        # Corpus tracking
        self.indexed_corpora: Dict[str, Dict[str, Any]] = {}

        # Source text cache (trajectory_id -> original text)
        # Needed because StateTrajectory doesn't store full text
        self.source_text_cache: Dict[str, str] = {}

    def index_corpus(
        self,
        corpus_id: str,
        source_path: str,
        domain: str = "",
        chunk_size: int = 300,
        state_window: int = 16,  # Tokens per state
    ) -> Dict[str, int]:
        """
        Index a corpus for both token and state-delta retrieval.

        Args:
            corpus_id: Unique identifier for this corpus
            source_path: Path to documents
            domain: Domain label (biology, coding, etc.)
            chunk_size: Token chunk size
            state_window: Tokens per cognitive state

        Returns:
            Dict with 'token_chunks' and 'state_trajectories' counts
        """
        # Step 1: Token-based indexing
        token_count = token_index_corpus(
            corpus_id=corpus_id,
            source_path=source_path,
            store=self.token_store,
            chunk_size=chunk_size,
        )

        logger.info(f"Indexed {token_count} token chunks for corpus '{corpus_id}'")

        # Step 2: State-Delta indexing (if projector available)
        state_count = 0
        if self.state_projector is not None:
            state_count = self._index_states(
                corpus_id=corpus_id,
                source_path=source_path,
                domain=domain,
                state_window=state_window,
            )
            logger.info(f"Indexed {state_count} state trajectories for corpus '{corpus_id}'")
        else:
            logger.warning("No state projector - skipping State-Delta indexing")

        # Track corpus
        self.indexed_corpora[corpus_id] = {
            'source_path': source_path,
            'domain': domain,
            'token_chunks': token_count,
            'state_trajectories': state_count,
        }

        return {
            'token_chunks': token_count,
            'state_trajectories': state_count,
        }

    def _index_states(
        self,
        corpus_id: str,
        source_path: str,
        domain: str,
        state_window: int,
    ) -> int:
        """Index documents as state trajectories."""
        from ..rag.ingestion.loader import load_documents

        documents = load_documents(source_path)
        count = 0

        for i, doc in enumerate(documents):
            trajectory_id = f"{corpus_id}_{i}"

            # Store source text for later retrieval
            self.source_text_cache[trajectory_id] = doc.text

            # Convert text to states (simplified - in practice, use tokenizer)
            states = self._text_to_states(doc.text, state_window)

            if len(states) > 0:
                self.state_index.add_trajectory(
                    trajectory_id=trajectory_id,
                    states=states,
                    source=doc.metadata.get('source', ''),
                    domain=domain,
                )
                count += 1

        return count

    def _text_to_states(self, text: str, window: int) -> List[torch.Tensor]:
        """
        Convert text to cognitive states.

        In production, this would:
        1. Tokenize text
        2. Embed tokens
        3. Run through transformer
        4. Project hidden states to cognitive states

        For now, we create synthetic states for demonstration.
        """
        if self.state_projector is None:
            return []

        # Simplified: create states from text segments
        # In production, use actual model inference
        words = text.split()
        states = []

        for i in range(0, len(words), window):
            segment = ' '.join(words[i:i + window])
            if segment:
                # Create synthetic hidden state from segment
                hidden = self._text_to_hidden(segment)
                state = self._project_state(hidden)
                states.append(state)

        return states

    def _text_to_hidden(self, text: str) -> torch.Tensor:
        """Convert text segment to synthetic hidden state."""
        # Deterministic hash-based embedding (matches RAG encoder approach)
        import hashlib
        hash_bytes = hashlib.md5(text.encode()).digest()
        hidden = torch.zeros(self.hidden_dim)

        for i, byte in enumerate(hash_bytes):
            idx = i * (self.hidden_dim // 16)
            if idx < self.hidden_dim:
                hidden[idx] = (byte / 255.0) * 2 - 1

        return hidden.unsqueeze(0)  # [1, hidden_dim]

    def _project_state(self, hidden: torch.Tensor) -> torch.Tensor:
        """Project hidden state to cognitive state."""
        with torch.no_grad():
            if isinstance(self.state_projector, CognitiveStateProjectorLite):
                output = self.state_projector(hidden)
                # Combine into state vector
                topic = output['topic'].squeeze(0)
                ontology = output['ontology'].squeeze(0)
                entropy = output['entropy'].unsqueeze(-1) if output['entropy'].dim() == 0 else output['entropy']
                return torch.cat([
                    torch.zeros(44),  # Phoneme placeholder
                    topic,
                    ontology,
                    torch.tensor([0.9, entropy.item(), 0.8, 0.1]),  # dynamics
                ])
            else:
                output = self.state_projector(hidden)
                return output.squeeze(0)

    def query(
        self,
        query_text: str,
        query_state: Optional[torch.Tensor] = None,
        corpus_id: Optional[str] = None,
        expected_transition: Optional[str] = None,
        domain_filter: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[CandidateEntry]:
        """
        Query with hybrid token + state-delta retrieval.

        Args:
            query_text: Query string
            query_state: Pre-computed query cognitive state (computes if None)
            corpus_id: Corpus to search (all if None)
            expected_transition: e.g., "QUESTIONING->FACTUAL"
            domain_filter: Filter by domain
            top_k: Number of results (uses config default if None)

        Returns:
            List of CandidateEntry objects with fused scores
        """
        top_k = top_k or self.config.output_top_k

        # Compute query state if needed
        if query_state is None and self.state_projector is not None:
            hidden = self._text_to_hidden(query_text)
            query_state = self._project_state(hidden)

        # Get results from both methods
        if self.config.mode == FusionMode.TOKEN_ONLY:
            return self._token_retrieval(query_text, corpus_id, top_k)

        elif self.config.mode == FusionMode.STATE_ONLY:
            if query_state is None:
                raise ValueError("STATE_ONLY mode requires query_state")
            return self._state_retrieval(
                query_state, expected_transition, domain_filter, top_k
            )

        else:
            # Hybrid modes
            token_results = self._token_retrieval(
                query_text, corpus_id, self.config.token_top_k
            )
            state_results = []
            if query_state is not None:
                state_results = self._state_retrieval(
                    query_state, expected_transition, domain_filter,
                    self.config.state_top_k
                )

            # Fuse results
            return self._fuse_results(token_results, state_results, top_k)

    def _token_retrieval(
        self,
        query_text: str,
        corpus_id: Optional[str],
        top_k: int,
    ) -> List[CandidateEntry]:
        """Traditional token-based retrieval."""
        if corpus_id:
            return token_run_rag(
                query=query_text,
                corpus_id=corpus_id,
                store=self.token_store,
                top_k=top_k,
            )
        else:
            # Search all corpora
            all_results = []
            for cid in self.indexed_corpora:
                results = token_run_rag(
                    query=query_text,
                    corpus_id=cid,
                    store=self.token_store,
                    top_k=top_k,
                )
                all_results.extend(results)

            # Sort by score and take top_k
            all_results.sort(key=lambda x: x.score, reverse=True)
            return all_results[:top_k]

    def _state_retrieval(
        self,
        query_state: torch.Tensor,
        expected_transition: Optional[str],
        domain_filter: Optional[str],
        top_k: int,
    ) -> List[CandidateEntry]:
        """State-Delta retrieval converted to CandidateEntry format."""
        results = self.state_index.retrieve(
            query_state=query_state,
            expected_transition=expected_transition,
            domain_filter=domain_filter,
            k=top_k,
            topic_weight=self.config.topic_weight,
            ontology_weight=self.config.ontology_weight,
            entropy_weight=self.config.entropy_weight,
        )

        # Convert to CandidateEntry
        candidates = []
        for result in results:
            # Get source text from cache
            text = self.source_text_cache.get(
                result.trajectory_id,
                f"[Trajectory {result.trajectory_id}]"
            )

            candidates.append(CandidateEntry(
                text=text[:500],  # Truncate for display
                score=result.total_score,
                source=result.trajectory.source or result.trajectory_id,
                metadata={
                    'retrieval_type': 'state_delta',
                    'topic_score': result.topic_score,
                    'ontology_score': result.ontology_score,
                    'entropy_score': result.entropy_score,
                    'domain': result.trajectory.domain,
                    'matched_positions': result.matched_positions,
                    'ontology_pattern': result.trajectory.ontology_pattern,
                }
            ))

        return candidates

    def _fuse_results(
        self,
        token_results: List[CandidateEntry],
        state_results: List[CandidateEntry],
        top_k: int,
    ) -> List[CandidateEntry]:
        """Fuse token and state-delta results."""
        if self.config.mode == FusionMode.WEIGHTED_AVERAGE:
            return self._weighted_average_fusion(token_results, state_results, top_k)
        elif self.config.mode == FusionMode.RECIPROCAL_RANK:
            return self._rrf_fusion(token_results, state_results, top_k)
        elif self.config.mode == FusionMode.RERANKING:
            return self._reranking_fusion(token_results, state_results, top_k)
        else:
            return token_results[:top_k]

    def _weighted_average_fusion(
        self,
        token_results: List[CandidateEntry],
        state_results: List[CandidateEntry],
        top_k: int,
    ) -> List[CandidateEntry]:
        """Combine results using weighted average of scores."""
        # Normalize scores if needed
        if self.config.normalize_scores:
            token_results = self._normalize_scores(token_results)
            state_results = self._normalize_scores(state_results)

        # Build text -> scores mapping
        combined: Dict[str, Dict[str, Any]] = {}

        for entry in token_results:
            key = entry.text[:100]  # Use truncated text as key
            combined[key] = {
                'entry': entry,
                'token_score': entry.score,
                'state_score': 0.0,
            }

        for entry in state_results:
            key = entry.text[:100]
            if key in combined:
                combined[key]['state_score'] = entry.score
            else:
                combined[key] = {
                    'entry': entry,
                    'token_score': 0.0,
                    'state_score': entry.score,
                }

        # Compute weighted scores
        results = []
        for key, data in combined.items():
            fused_score = (
                self.config.token_weight * data['token_score'] +
                self.config.state_weight * data['state_score']
            )

            if fused_score >= self.config.min_score:
                entry = data['entry']
                # Update metadata
                entry.metadata['fusion_type'] = 'weighted_average'
                entry.metadata['token_score'] = data['token_score']
                entry.metadata['state_score'] = data['state_score']
                entry.score = fused_score
                results.append(entry)

        # Sort and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _rrf_fusion(
        self,
        token_results: List[CandidateEntry],
        state_results: List[CandidateEntry],
        top_k: int,
    ) -> List[CandidateEntry]:
        """Reciprocal Rank Fusion for combining ranked lists."""
        k = self.config.rrf_k

        # Build text -> RRF score mapping
        rrf_scores: Dict[str, float] = {}
        entries: Dict[str, CandidateEntry] = {}

        # Token RRF
        for rank, entry in enumerate(token_results):
            key = entry.text[:100]
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            entries[key] = entry

        # State RRF
        for rank, entry in enumerate(state_results):
            key = entry.text[:100]
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
            if key not in entries:
                entries[key] = entry

        # Build results
        results = []
        for key, rrf_score in rrf_scores.items():
            entry = entries[key]
            entry.score = rrf_score
            entry.metadata['fusion_type'] = 'reciprocal_rank'
            results.append(entry)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _reranking_fusion(
        self,
        token_results: List[CandidateEntry],
        state_results: List[CandidateEntry],
        top_k: int,
    ) -> List[CandidateEntry]:
        """Use State-Delta scores to rerank Token results."""
        # Build state score lookup
        state_scores: Dict[str, float] = {}
        for entry in state_results:
            key = entry.text[:100]
            state_scores[key] = entry.score

        # Rerank token results
        for entry in token_results:
            key = entry.text[:100]
            state_score = state_scores.get(key, 0.0)

            # Boost score based on state similarity
            entry.score = (
                self.config.token_weight * entry.score +
                self.config.state_weight * state_score
            )
            entry.metadata['fusion_type'] = 'reranking'
            entry.metadata['state_boost'] = state_score

        token_results.sort(key=lambda x: x.score, reverse=True)
        return token_results[:top_k]

    def _normalize_scores(
        self,
        entries: List[CandidateEntry],
    ) -> List[CandidateEntry]:
        """Normalize scores to [0, 1] range."""
        if not entries:
            return entries

        scores = [e.score for e in entries]
        min_score = min(scores)
        max_score = max(scores)

        if max_score - min_score < 1e-9:
            for e in entries:
                e.score = 1.0
        else:
            for e in entries:
                e.score = (e.score - min_score) / (max_score - min_score)

        return entries

    def explain_result(self, entry: CandidateEntry) -> str:
        """Generate explanation for why a result was retrieved."""
        fusion_type = entry.metadata.get('fusion_type', 'unknown')
        retrieval_type = entry.metadata.get('retrieval_type', 'token')

        lines = [f"Result: {entry.text[:80]}..."]
        lines.append(f"Score: {entry.score:.4f}")
        lines.append(f"Source: {entry.source}")

        if fusion_type != 'unknown':
            lines.append(f"\nFusion: {fusion_type}")

        if 'token_score' in entry.metadata:
            lines.append(f"  Token Score: {entry.metadata['token_score']:.4f}")
        if 'state_score' in entry.metadata:
            lines.append(f"  State Score: {entry.metadata['state_score']:.4f}")

        if retrieval_type == 'state_delta':
            lines.append(f"\nState-Delta Matching:")
            lines.append(f"  Topic: {entry.metadata.get('topic_score', 0):.4f}")
            lines.append(f"  Ontology: {entry.metadata.get('ontology_score', 0):.4f}")
            lines.append(f"  Entropy: {entry.metadata.get('entropy_score', 0):.4f}")
            if entry.metadata.get('ontology_pattern'):
                pattern = entry.metadata['ontology_pattern'][:5]
                lines.append(f"  Pattern: {pattern}")

        return '\n'.join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'corpora': list(self.indexed_corpora.keys()),
            'total_token_chunks': sum(
                c['token_chunks'] for c in self.indexed_corpora.values()
            ),
            'total_state_trajectories': sum(
                c['state_trajectories'] for c in self.indexed_corpora.values()
            ),
            'fusion_mode': self.config.mode.value,
            'has_state_projector': self.state_projector is not None,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_hybrid_engine(
    mode: str = "weighted_avg",
    token_weight: float = 0.4,
    state_weight: float = 0.6,
    hidden_dim: int = 768,
) -> HybridRAGEngine:
    """
    Create a configured Hybrid RAG Engine.

    Args:
        mode: Fusion mode ("token_only", "state_only", "weighted_avg", "rrf", "rerank")
        token_weight: Weight for token-based retrieval
        state_weight: Weight for state-delta retrieval
        hidden_dim: Hidden dimension for state projector

    Returns:
        Configured HybridRAGEngine
    """
    config = HybridRAGConfig(
        mode=FusionMode(mode),
        token_weight=token_weight,
        state_weight=state_weight,
    )

    # Create lightweight projector
    projector = CognitiveStateProjectorLite(d_model=hidden_dim)

    return HybridRAGEngine(config=config, state_projector=projector)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("Hybrid RAG Integration Demo")
    print("=" * 50)

    # Create engine
    engine = create_hybrid_engine(
        mode="weighted_avg",
        token_weight=0.4,
        state_weight=0.6,
    )

    print(f"Engine created with mode: {engine.config.mode.value}")
    print(f"Has state projector: {engine.state_projector is not None}")

    # Demo query (would need indexed corpus)
    print("\nTo use:")
    print("  engine.index_corpus('my_docs', 'path/to/docs/', domain='general')")
    print("  results = engine.query('How does X work?')")
    print("  for r in results:")
    print("    print(engine.explain_result(r))")

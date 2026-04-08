#!/usr/bin/env python3
"""
State Trajectory Retrieval: Meaning-Based Knowledge Retrieval
==============================================================

This module implements retrieval based on cognitive state trajectories,
not token embeddings. This is fundamentally different from traditional RAG.

Key Insight:
-----------
Traditional RAG: "Find text chunks with similar WORDS"
State-Delta Retrieval: "Find knowledge with similar MEANING STRUCTURE"

Example:
  Query: "How do proteins fold?"

  Token RAG might retrieve:
    "Protein folding is the process by which proteins fold..."
    (keyword match, low information)

  State-Delta Retrieval retrieves:
    "Hydrophobic residues cluster in the core while..."
    (same ontological position: FACTUAL + biology + answering pattern)

Architecture:
------------
1. Documents are stored as STATE TRAJECTORIES, not token chunks
2. Each position has a CognitiveState with:
   - topic_embedding[64]: Domain/subject
   - ontology_probs[12]: Bhava state distribution
   - dynamics[4]: coherence, entropy, confidence, momentum
3. Retrieval matches by:
   - Topic similarity (what domain)
   - Ontology trajectory (how understanding evolves)
   - Entropy alignment (uncertainty reduction pattern)

Usage:
------
    from symbolu_extensions.experimental import StateTrajectoryIndex

    # Create index
    index = StateTrajectoryIndex()

    # Add documents as state trajectories
    index.add_trajectory("doc_1", states_list)

    # Retrieve by meaning position
    results = index.retrieve(
        query_state,
        expected_transition="QUESTIONING->FACTUAL",
        k=5
    )
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict
import json
import os
from pathlib import Path

from .cognitive_state import CognitiveState, StateDelta


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class StateTrajectory:
    """
    A sequence of cognitive states representing understanding evolution.

    This is what we store instead of text chunks.
    Each document becomes a trajectory of meaning states.
    """

    trajectory_id: str
    states: List[torch.Tensor]  # List of [state_dim] tensors

    # Metadata
    source: str = ""  # Original document/source
    domain: str = ""  # Primary domain (biology, coding, etc.)

    # Precomputed features for fast retrieval
    mean_topic: Optional[torch.Tensor] = None  # [topic_dim]
    ontology_pattern: Optional[List[int]] = None  # Sequence of dominant Bhava
    entropy_trajectory: Optional[List[float]] = None  # How entropy evolves

    # Token alignment (for debugging/inspection)
    token_positions: Optional[List[int]] = None  # Original token positions

    def __post_init__(self):
        """Precompute features if not provided."""
        if len(self.states) > 0 and self.mean_topic is None:
            self._compute_features()

    def _compute_features(self):
        """Compute retrieval features from states."""
        if len(self.states) == 0:
            return

        # Stack states
        states_tensor = torch.stack(self.states)  # [T, state_dim]

        # Extract components (assuming standard layout: phoneme[44] + topic[64] + onto[12] + dynamics[4])
        topic_start = 44
        topic_end = 44 + 64
        onto_start = 44 + 64
        onto_end = 44 + 64 + 12
        dynamics_start = 44 + 64 + 12

        # Mean topic embedding
        self.mean_topic = states_tensor[:, topic_start:topic_end].mean(dim=0)

        # Ontology pattern (sequence of dominant Bhava states)
        onto_probs = states_tensor[:, onto_start:onto_end]  # [T, 12]
        self.ontology_pattern = onto_probs.argmax(dim=-1).tolist()

        # Entropy trajectory (from dynamics)
        entropy_idx = dynamics_start + 1  # coherence[0], entropy[1], ...
        self.entropy_trajectory = states_tensor[:, entropy_idx].tolist()

    def get_transition_pattern(self, window: int = 3) -> List[Tuple[int, int]]:
        """
        Get ontology transitions as (from_state, to_state) pairs.

        Args:
            window: Look at transitions within this window

        Returns:
            List of (from_bhava, to_bhava) transitions
        """
        if self.ontology_pattern is None:
            return []

        transitions = []
        for i in range(len(self.ontology_pattern) - 1):
            transitions.append((self.ontology_pattern[i], self.ontology_pattern[i + 1]))

        return transitions

    @property
    def length(self) -> int:
        return len(self.states)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            'trajectory_id': self.trajectory_id,
            'states': [s.tolist() for s in self.states],
            'source': self.source,
            'domain': self.domain,
            'mean_topic': self.mean_topic.tolist() if self.mean_topic is not None else None,
            'ontology_pattern': self.ontology_pattern,
            'entropy_trajectory': self.entropy_trajectory,
            'token_positions': self.token_positions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateTrajectory':
        """Deserialize from storage."""
        states = [torch.tensor(s) for s in data['states']]
        traj = cls(
            trajectory_id=data['trajectory_id'],
            states=states,
            source=data.get('source', ''),
            domain=data.get('domain', ''),
            token_positions=data.get('token_positions'),
        )
        if data.get('mean_topic') is not None:
            traj.mean_topic = torch.tensor(data['mean_topic'])
        traj.ontology_pattern = data.get('ontology_pattern')
        traj.entropy_trajectory = data.get('entropy_trajectory')
        return traj


@dataclass
class RetrievalResult:
    """Result from trajectory retrieval."""

    trajectory_id: str
    trajectory: StateTrajectory

    # Matching scores
    topic_score: float = 0.0
    ontology_score: float = 0.0
    entropy_score: float = 0.0
    total_score: float = 0.0

    # Matched positions (which states in trajectory matched)
    matched_positions: List[int] = field(default_factory=list)

    # The specific states that matched
    matched_states: List[torch.Tensor] = field(default_factory=list)


# =============================================================================
# PATTERN MATCHING
# =============================================================================

class OntologyPatternMatcher:
    """
    Matches ontology transition patterns.

    This finds trajectories with similar "shapes" of understanding evolution.
    E.g., QUESTIONING -> FACTUAL -> ANALYTICAL is a common "explaining" pattern.
    """

    # Common ontology transition patterns
    PATTERNS = {
        'explaining': [8, 0, 1],      # QUESTIONING -> FACTUAL -> ANALYTICAL
        'instructing': [8, 0, 5],     # QUESTIONING -> FACTUAL -> INSTRUCTIVE
        'analyzing': [0, 1, 2],       # FACTUAL -> ANALYTICAL -> EVALUATIVE
        'storytelling': [3, 3, 0],    # NARRATIVE -> NARRATIVE -> FACTUAL
        'arguing': [4, 0, 4],         # ARGUMENTATIVE -> FACTUAL -> ARGUMENTATIVE
        'speculating': [8, 7, 6],     # QUESTIONING -> SPECULATIVE -> CERTAIN
    }

    def __init__(self):
        # Build pattern index: transition -> list of pattern names
        self.transition_index: Dict[Tuple[int, int], List[str]] = defaultdict(list)

        for name, pattern in self.PATTERNS.items():
            for i in range(len(pattern) - 1):
                transition = (pattern[i], pattern[i + 1])
                self.transition_index[transition].append(name)

    def parse_transition_string(self, transition_str: str) -> List[Tuple[int, int]]:
        """
        Parse transition string like "QUESTIONING->FACTUAL" to indices.

        Args:
            transition_str: e.g., "QUESTIONING->FACTUAL->ANALYTICAL"

        Returns:
            List of (from_idx, to_idx) tuples
        """
        from .ontology_mapper import BHAVA_TO_IDX

        parts = transition_str.upper().replace(' ', '').split('->')
        transitions = []

        for i in range(len(parts) - 1):
            from_bhava = parts[i]
            to_bhava = parts[i + 1]

            if from_bhava in BHAVA_TO_IDX and to_bhava in BHAVA_TO_IDX:
                transitions.append((BHAVA_TO_IDX[from_bhava], BHAVA_TO_IDX[to_bhava]))

        return transitions

    def match_pattern(
        self,
        trajectory_pattern: List[int],
        target_transitions: List[Tuple[int, int]],
    ) -> Tuple[float, List[int]]:
        """
        Find how well a trajectory matches target transitions.

        Args:
            trajectory_pattern: List of Bhava indices from trajectory
            target_transitions: List of (from, to) transitions to find

        Returns:
            (match_score, matched_positions)
        """
        if len(trajectory_pattern) < 2 or len(target_transitions) == 0:
            return 0.0, []

        matched_positions = []
        matches_found = 0

        # Extract transitions from trajectory
        traj_transitions = []
        for i in range(len(trajectory_pattern) - 1):
            traj_transitions.append((trajectory_pattern[i], trajectory_pattern[i + 1]))

        # Find matching transitions
        for target in target_transitions:
            for i, traj_trans in enumerate(traj_transitions):
                if traj_trans == target:
                    matches_found += 1
                    matched_positions.append(i)
                    break  # Only count first match

        score = matches_found / len(target_transitions) if target_transitions else 0.0
        return score, matched_positions

    def find_similar_patterns(
        self,
        trajectory_pattern: List[int],
        min_overlap: int = 2,
    ) -> List[str]:
        """
        Find named patterns similar to this trajectory.

        Args:
            trajectory_pattern: List of Bhava indices
            min_overlap: Minimum transition overlap to consider similar

        Returns:
            List of pattern names that match
        """
        pattern_scores = defaultdict(int)

        for i in range(len(trajectory_pattern) - 1):
            transition = (trajectory_pattern[i], trajectory_pattern[i + 1])
            for pattern_name in self.transition_index[transition]:
                pattern_scores[pattern_name] += 1

        return [name for name, score in pattern_scores.items() if score >= min_overlap]


# =============================================================================
# STATE TRAJECTORY INDEX
# =============================================================================

class StateTrajectoryIndex:
    """
    Index for storing and retrieving cognitive state trajectories.

    This is the core of State-Delta Retrieval. Unlike vector databases
    that store token embeddings, this indexes by MEANING STRUCTURE.

    Retrieval happens by:
    1. Topic similarity (what domain)
    2. Ontology trajectory (how understanding evolves)
    3. Entropy alignment (uncertainty reduction pattern)

    Example:
        index = StateTrajectoryIndex()

        # Add documents
        for doc in documents:
            states = perception_model(doc.tokens)
            index.add_trajectory(doc.id, states, domain=doc.domain)

        # Query
        query_state = perception_model(query_tokens)[-1]
        results = index.retrieve(
            query_state,
            expected_transition="QUESTIONING->FACTUAL",
            k=5
        )
    """

    def __init__(
        self,
        topic_dim: int = 64,
        num_ontology: int = 12,
        state_dim: int = 124,
        use_faiss: bool = False,
    ):
        self.topic_dim = topic_dim
        self.num_ontology = num_ontology
        self.state_dim = state_dim
        self.use_faiss = use_faiss

        # Main storage
        self.trajectories: Dict[str, StateTrajectory] = {}

        # Indices for fast retrieval
        self.topic_vectors: List[torch.Tensor] = []  # [N, topic_dim]
        self.trajectory_ids: List[str] = []

        # Domain index
        self.domain_index: Dict[str, List[str]] = defaultdict(list)

        # Ontology pattern matcher
        self.pattern_matcher = OntologyPatternMatcher()

        # FAISS index (optional, for large-scale retrieval)
        self.faiss_index = None
        if use_faiss:
            self._init_faiss()

    def _init_faiss(self):
        """Initialize FAISS index for topic vectors."""
        try:
            import faiss
            self.faiss_index = faiss.IndexFlatIP(self.topic_dim)  # Inner product
        except ImportError:
            print("FAISS not available, falling back to brute-force search")
            self.use_faiss = False

    def add_trajectory(
        self,
        trajectory_id: str,
        states: Union[List[torch.Tensor], torch.Tensor],
        source: str = "",
        domain: str = "",
        token_positions: Optional[List[int]] = None,
    ) -> StateTrajectory:
        """
        Add a document as a state trajectory.

        Args:
            trajectory_id: Unique identifier
            states: List of state tensors [state_dim] or tensor [T, state_dim]
            source: Original document/source
            domain: Domain label (biology, coding, etc.)
            token_positions: Original token positions for alignment

        Returns:
            Created StateTrajectory object
        """
        # Handle tensor input
        if isinstance(states, torch.Tensor):
            if states.dim() == 2:
                states = [states[i] for i in range(states.size(0))]
            else:
                states = [states]

        # Ensure all states are detached
        states = [s.detach().cpu() if isinstance(s, torch.Tensor) else torch.tensor(s) for s in states]

        # Create trajectory
        trajectory = StateTrajectory(
            trajectory_id=trajectory_id,
            states=states,
            source=source,
            domain=domain,
            token_positions=token_positions,
        )

        # Store
        self.trajectories[trajectory_id] = trajectory
        self.trajectory_ids.append(trajectory_id)

        # Index by topic
        if trajectory.mean_topic is not None:
            self.topic_vectors.append(trajectory.mean_topic)

            if self.use_faiss and self.faiss_index is not None:
                import faiss
                topic_np = trajectory.mean_topic.numpy().reshape(1, -1)
                faiss.normalize_L2(topic_np)
                self.faiss_index.add(topic_np)

        # Index by domain
        if domain:
            self.domain_index[domain].append(trajectory_id)

        return trajectory

    def retrieve(
        self,
        query_state: torch.Tensor,
        expected_transition: Optional[str] = None,
        domain_filter: Optional[str] = None,
        k: int = 5,
        topic_weight: float = 0.4,
        ontology_weight: float = 0.4,
        entropy_weight: float = 0.2,
    ) -> List[RetrievalResult]:
        """
        Retrieve trajectories by meaning position.

        This is NOT keyword search. It's MEANING search.

        Args:
            query_state: [state_dim] current cognitive state
            expected_transition: e.g., "QUESTIONING->FACTUAL"
            domain_filter: Only search in this domain
            k: Number of results
            topic_weight: Weight for topic similarity
            ontology_weight: Weight for ontology pattern match
            entropy_weight: Weight for entropy alignment

        Returns:
            List of RetrievalResult sorted by score
        """
        if len(self.trajectories) == 0:
            return []

        # Ensure query is on CPU
        query_state = query_state.detach().cpu()

        # Extract query components
        topic_start = 44
        topic_end = 44 + self.topic_dim
        onto_start = 44 + self.topic_dim
        onto_end = onto_start + self.num_ontology
        entropy_idx = onto_end + 1

        query_topic = query_state[topic_start:topic_end]
        query_onto = query_state[onto_start:onto_end]
        query_entropy = query_state[entropy_idx].item()
        query_dominant_bhava = query_onto.argmax().item()

        # Parse expected transition
        target_transitions = []
        if expected_transition:
            target_transitions = self.pattern_matcher.parse_transition_string(expected_transition)

        # Get candidate trajectories
        candidates = list(self.trajectory_ids)
        if domain_filter:
            candidates = self.domain_index.get(domain_filter, candidates)

        # Score all candidates
        results = []

        for traj_id in candidates:
            trajectory = self.trajectories[traj_id]

            # 1. Topic similarity (cosine)
            if trajectory.mean_topic is not None:
                topic_sim = F.cosine_similarity(
                    query_topic.unsqueeze(0),
                    trajectory.mean_topic.unsqueeze(0)
                ).item()
            else:
                topic_sim = 0.0

            # 2. Ontology pattern match
            if trajectory.ontology_pattern and target_transitions:
                onto_score, matched_pos = self.pattern_matcher.match_pattern(
                    trajectory.ontology_pattern,
                    target_transitions
                )
            elif trajectory.ontology_pattern:
                # Match by dominant Bhava in trajectory
                bhava_counts = defaultdict(int)
                for bhava in trajectory.ontology_pattern:
                    bhava_counts[bhava] += 1
                if query_dominant_bhava in bhava_counts:
                    onto_score = bhava_counts[query_dominant_bhava] / len(trajectory.ontology_pattern)
                else:
                    onto_score = 0.0
                matched_pos = [i for i, b in enumerate(trajectory.ontology_pattern) if b == query_dominant_bhava]
            else:
                onto_score = 0.0
                matched_pos = []

            # 3. Entropy alignment
            # High query entropy should match trajectories that reduce entropy
            if trajectory.entropy_trajectory and len(trajectory.entropy_trajectory) > 1:
                traj_entropy_change = trajectory.entropy_trajectory[-1] - trajectory.entropy_trajectory[0]
                # If query has high entropy, prefer trajectories that decrease entropy
                if query_entropy > 0.5:
                    entropy_score = max(0, -traj_entropy_change)  # Negative change = good
                else:
                    entropy_score = 1.0 - abs(traj_entropy_change)  # Stable entropy
            else:
                entropy_score = 0.5

            # Combined score
            total_score = (
                topic_weight * topic_sim +
                ontology_weight * onto_score +
                entropy_weight * entropy_score
            )

            # Get matched states
            matched_states = [trajectory.states[i] for i in matched_pos if i < len(trajectory.states)]

            results.append(RetrievalResult(
                trajectory_id=traj_id,
                trajectory=trajectory,
                topic_score=topic_sim,
                ontology_score=onto_score,
                entropy_score=entropy_score,
                total_score=total_score,
                matched_positions=matched_pos,
                matched_states=matched_states,
            ))

        # Sort by total score
        results.sort(key=lambda x: x.total_score, reverse=True)

        return results[:k]

    def retrieve_by_trajectory(
        self,
        query_states: torch.Tensor,
        k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Retrieve using a full trajectory query (not just one state).

        This finds trajectories with similar "shape" of understanding.

        Args:
            query_states: [T, state_dim] sequence of states
            k: Number of results

        Returns:
            List of RetrievalResult
        """
        # Create temporary trajectory for query
        query_states = query_states.detach().cpu()
        query_traj = StateTrajectory(
            trajectory_id="_query_",
            states=[query_states[i] for i in range(query_states.size(0))],
        )

        # Match by pattern similarity
        results = []

        for traj_id, trajectory in self.trajectories.items():
            if trajectory.ontology_pattern is None or query_traj.ontology_pattern is None:
                continue

            # Compare ontology patterns using edit distance
            pattern_sim = self._pattern_similarity(
                query_traj.ontology_pattern,
                trajectory.ontology_pattern
            )

            # Compare topic drift
            if query_traj.mean_topic is not None and trajectory.mean_topic is not None:
                topic_sim = F.cosine_similarity(
                    query_traj.mean_topic.unsqueeze(0),
                    trajectory.mean_topic.unsqueeze(0)
                ).item()
            else:
                topic_sim = 0.0

            # Compare entropy trajectories
            if query_traj.entropy_trajectory and trajectory.entropy_trajectory:
                entropy_sim = self._trajectory_similarity(
                    query_traj.entropy_trajectory,
                    trajectory.entropy_trajectory
                )
            else:
                entropy_sim = 0.5

            total_score = 0.4 * pattern_sim + 0.4 * topic_sim + 0.2 * entropy_sim

            results.append(RetrievalResult(
                trajectory_id=traj_id,
                trajectory=trajectory,
                topic_score=topic_sim,
                ontology_score=pattern_sim,
                entropy_score=entropy_sim,
                total_score=total_score,
            ))

        results.sort(key=lambda x: x.total_score, reverse=True)
        return results[:k]

    def _pattern_similarity(self, pattern1: List[int], pattern2: List[int]) -> float:
        """Compute similarity between two ontology patterns."""
        if not pattern1 or not pattern2:
            return 0.0

        # Use longest common subsequence ratio
        m, n = len(pattern1), len(pattern2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if pattern1[i - 1] == pattern2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_length = dp[m][n]
        return 2.0 * lcs_length / (m + n)

    def _trajectory_similarity(self, traj1: List[float], traj2: List[float]) -> float:
        """Compute similarity between two numeric trajectories."""
        # Resample to same length
        min_len = min(len(traj1), len(traj2))
        if min_len == 0:
            return 0.5

        t1 = torch.tensor(traj1[:min_len])
        t2 = torch.tensor(traj2[:min_len])

        # Correlation
        t1_centered = t1 - t1.mean()
        t2_centered = t2 - t2.mean()

        if t1_centered.std() > 0 and t2_centered.std() > 0:
            corr = (t1_centered * t2_centered).mean() / (t1_centered.std() * t2_centered.std())
            return (corr.item() + 1) / 2  # Map [-1, 1] to [0, 1]
        else:
            return 0.5

    def save(self, path: str):
        """Save index to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save trajectories
        trajectories_data = {
            tid: traj.to_dict() for tid, traj in self.trajectories.items()
        }
        with open(path / "trajectories.json", "w") as f:
            json.dump(trajectories_data, f)

        # Save metadata
        metadata = {
            'topic_dim': self.topic_dim,
            'num_ontology': self.num_ontology,
            'state_dim': self.state_dim,
            'trajectory_ids': self.trajectory_ids,
            'domain_index': dict(self.domain_index),
        }
        with open(path / "metadata.json", "w") as f:
            json.dump(metadata, f)

    @classmethod
    def load(cls, path: str) -> 'StateTrajectoryIndex':
        """Load index from disk."""
        path = Path(path)

        # Load metadata
        with open(path / "metadata.json", "r") as f:
            metadata = json.load(f)

        index = cls(
            topic_dim=metadata['topic_dim'],
            num_ontology=metadata['num_ontology'],
            state_dim=metadata['state_dim'],
        )

        # Load trajectories
        with open(path / "trajectories.json", "r") as f:
            trajectories_data = json.load(f)

        for tid, data in trajectories_data.items():
            traj = StateTrajectory.from_dict(data)
            index.trajectories[tid] = traj
            index.trajectory_ids.append(tid)

            if traj.mean_topic is not None:
                index.topic_vectors.append(traj.mean_topic)

            if traj.domain:
                index.domain_index[traj.domain].append(tid)

        return index

    def __len__(self) -> int:
        return len(self.trajectories)

    def stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            'num_trajectories': len(self.trajectories),
            'num_domains': len(self.domain_index),
            'domains': list(self.domain_index.keys()),
            'total_states': sum(t.length for t in self.trajectories.values()),
            'avg_trajectory_length': (
                sum(t.length for t in self.trajectories.values()) / len(self.trajectories)
                if self.trajectories else 0
            ),
        }


# =============================================================================
# STATE-GUIDED GENERATION
# =============================================================================

class StateGuidedRetriever(nn.Module):
    """
    Retrieval-augmented generation using state trajectories.

    Instead of concatenating retrieved text chunks to prompts,
    this uses retrieved STATE TRAJECTORIES to guide generation.

    The key insight: Retrieved trajectories show HOW understanding
    should evolve, not just WHAT information to include.
    """

    def __init__(
        self,
        index: StateTrajectoryIndex,
        state_dim: int = 124,
        hidden_dim: int = 256,
        num_retrieved: int = 3,
    ):
        super().__init__()
        self.index = index
        self.state_dim = state_dim
        self.num_retrieved = num_retrieved

        # Fusion network: combine query state with retrieved patterns
        self.fusion = nn.Sequential(
            nn.Linear(state_dim * (num_retrieved + 1), hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, state_dim),
        )

        # Trajectory pattern encoder
        self.pattern_encoder = nn.LSTM(
            input_size=state_dim,
            hidden_size=hidden_dim,
            num_layers=1,
            batch_first=True,
        )

        # Delta modifier based on retrieved patterns
        self.delta_modifier = nn.Linear(hidden_dim, state_dim)

    def forward(
        self,
        query_state: torch.Tensor,
        expected_transition: Optional[str] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Retrieve and fuse relevant state patterns.

        Args:
            query_state: [B, state_dim] or [state_dim]
            expected_transition: Optional transition pattern to match

        Returns:
            Dict with:
                augmented_state: [B, state_dim] state with retrieved knowledge
                delta_guidance: [B, state_dim] suggested delta based on patterns
                retrieval_scores: [B, num_retrieved] retrieval confidence
        """
        single_query = query_state.dim() == 1
        if single_query:
            query_state = query_state.unsqueeze(0)

        B = query_state.size(0)
        device = query_state.device

        augmented_states = []
        delta_guidances = []
        all_scores = []

        for b in range(B):
            # Retrieve
            results = self.index.retrieve(
                query_state[b],
                expected_transition=expected_transition,
                k=self.num_retrieved,
            )

            # Get retrieved states
            retrieved_states = []
            scores = []

            for result in results:
                if result.matched_states:
                    # Use the first matched state
                    retrieved_states.append(result.matched_states[0].to(device))
                elif result.trajectory.states:
                    # Use the last state of trajectory
                    retrieved_states.append(result.trajectory.states[-1].to(device))
                scores.append(result.total_score)

            # Pad if needed
            while len(retrieved_states) < self.num_retrieved:
                retrieved_states.append(torch.zeros(self.state_dim, device=device))
                scores.append(0.0)

            retrieved_states = retrieved_states[:self.num_retrieved]
            scores = scores[:self.num_retrieved]

            # Fuse query with retrieved states
            combined = torch.cat([query_state[b]] + retrieved_states)
            augmented = self.fusion(combined)
            augmented_states.append(augmented)

            # Encode trajectory patterns for delta guidance
            if results and results[0].trajectory.states:
                traj_states = torch.stack([
                    s.to(device) for s in results[0].trajectory.states[:10]
                ])  # Max 10 states
                _, (h_n, _) = self.pattern_encoder(traj_states.unsqueeze(0))
                delta_guidance = self.delta_modifier(h_n.squeeze(0))
            else:
                delta_guidance = torch.zeros(self.state_dim, device=device)

            delta_guidances.append(delta_guidance)
            all_scores.append(torch.tensor(scores, device=device))

        augmented_states = torch.stack(augmented_states)
        delta_guidances = torch.stack(delta_guidances)
        all_scores = torch.stack(all_scores)

        if single_query:
            augmented_states = augmented_states.squeeze(0)
            delta_guidances = delta_guidances.squeeze(0)
            all_scores = all_scores.squeeze(0)

        return {
            'augmented_state': augmented_states,
            'delta_guidance': delta_guidances,
            'retrieval_scores': all_scores,
        }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_usage():
    """Demonstrate state trajectory retrieval."""

    print("State Trajectory Retrieval Demo")
    print("=" * 60)

    # Create index
    index = StateTrajectoryIndex()

    # Create some example trajectories
    state_dim = 124

    # Biology document trajectory
    bio_states = []
    for t in range(20):
        state = torch.zeros(state_dim)
        # Topic: biology (high in first topic dim)
        state[44] = 0.9  # topic dim 0 = biology
        # Ontology: starts FACTUAL, moves to ANALYTICAL
        onto_start = 44 + 64
        if t < 10:
            state[onto_start + 0] = 0.8  # FACTUAL
            state[onto_start + 1] = 0.2  # ANALYTICAL
        else:
            state[onto_start + 0] = 0.3  # FACTUAL
            state[onto_start + 1] = 0.7  # ANALYTICAL
        # Entropy: decreasing (explaining)
        state[onto_start + 12 + 1] = 0.7 - t * 0.02  # entropy
        bio_states.append(state)

    index.add_trajectory(
        "bio_doc_1",
        bio_states,
        source="Molecular Biology Textbook",
        domain="biology",
    )

    # Coding document trajectory
    code_states = []
    for t in range(15):
        state = torch.zeros(state_dim)
        # Topic: coding
        state[45] = 0.85  # topic dim 1 = coding
        # Ontology: INSTRUCTIVE throughout
        onto_start = 44 + 64
        state[onto_start + 5] = 0.75  # INSTRUCTIVE
        state[onto_start + 0] = 0.25  # FACTUAL
        # Entropy: stable low
        state[onto_start + 12 + 1] = 0.3
        code_states.append(state)

    index.add_trajectory(
        "code_doc_1",
        code_states,
        source="Python Tutorial",
        domain="coding",
    )

    print(f"Index stats: {index.stats()}")

    # Query: biology question
    query_state = torch.zeros(state_dim)
    query_state[44] = 0.85  # biology topic
    onto_start = 44 + 64
    query_state[onto_start + 8] = 0.75  # QUESTIONING
    query_state[onto_start + 12 + 1] = 0.65  # high entropy

    print("\nQuery: Biology question (QUESTIONING, high entropy)")

    # Retrieve
    results = index.retrieve(
        query_state,
        expected_transition="QUESTIONING->FACTUAL",
        k=3,
    )

    print(f"\nRetrieved {len(results)} results:")
    for i, result in enumerate(results):
        print(f"\n  {i+1}. {result.trajectory_id}")
        print(f"     Source: {result.trajectory.source}")
        print(f"     Domain: {result.trajectory.domain}")
        print(f"     Topic score: {result.topic_score:.3f}")
        print(f"     Ontology score: {result.ontology_score:.3f}")
        print(f"     Entropy score: {result.entropy_score:.3f}")
        print(f"     Total score: {result.total_score:.3f}")

    # Test save/load
    print("\n" + "=" * 60)
    print("Testing save/load...")

    index.save("/tmp/test_index")
    loaded_index = StateTrajectoryIndex.load("/tmp/test_index")
    print(f"Loaded index stats: {loaded_index.stats()}")

    print("\nState-Delta Retrieval demo complete!")


if __name__ == "__main__":
    example_usage()

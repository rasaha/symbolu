"""
CTM+ (Coherence-Tier Memory Plus) Controller.

This is the main implementation of the CTM+ algorithm, integrating:
1. Phase Integrator: Learns access patterns via streaming accumulator
2. USE Coherence: Computes pairwise phase correlation for locality
3. BCVF Gate: Bidirectional verification for promotion/demotion
4. SCC Optimizer: Self-tunes parameters based on global coherence

CTM+ is NOT a new memory chip - it's controller intelligence that makes
existing DRAM+NAND behave smarter.
"""

import math
import random
from typing import Tuple, List, Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # For forward references
from collections import deque
from .base import BaseController
from ..core.state import GlobalState, PageState, Tier, OpType
from ..core.config import SimulatorConfig, CTMPlusConfig


class PhaseIntegrator:
    """
    Streaming pattern accumulator for learning access patterns.

    Implements:
        x_t = f(e_t)                           # Embed event
        φ_t = π·sin(w_φ^T x_t)                 # Extract phase
        a_t = σ(w_a^T x_t)                     # Extract amplitude
        k_t = a_t · e^{-jφ_t}                  # Complex phasor
        M_t = γ·M_{t-1} + (1-γ)·(k_t ⊙ v_t)   # EMA accumulator
    """

    def __init__(self, config: CTMPlusConfig):
        self.config = config.phase
        self.dim = self.config.embedding_dim

        # Projection weights (randomly initialized, could be learned)
        random.seed(42)  # Reproducibility
        self._w_phase = [random.gauss(0, 0.1) for _ in range(self.dim)]
        self._w_amp = [random.gauss(0, 0.1) for _ in range(self.dim)]
        self._w_value = [[random.gauss(0, 0.1) for _ in range(self.dim)] for _ in range(self.dim)]

        # Streaming accumulator (complex-valued)
        self._accumulator = [complex(0, 0) for _ in range(self.dim)]

        # Recent events for context
        self._recent_pages: deque = deque(maxlen=16)

    def embed_event(self, page_id: int, op_type: OpType, delta_t: int) -> List[float]:
        """
        Embed a memory event into a feature vector.

        Simple embedding: hash-based + temporal features.
        """
        embedding = [0.0] * self.dim

        # Page ID features (hash to spread across dimensions)
        for i in range(min(8, self.dim)):
            embedding[i] = math.sin(page_id * (i + 1) * 0.1)

        # Operation type one-hot
        if self.dim > 8:
            embedding[8 + int(op_type)] = 1.0

        # Temporal feature (log-scaled delta)
        if self.dim > 12:
            embedding[12] = math.log1p(delta_t) / 20.0

        # Context: recent page co-occurrence
        for i, recent_page in enumerate(self._recent_pages):
            if self.dim > 16 + i:
                # Similarity to recent pages
                embedding[16 + i] = 1.0 if recent_page == page_id else 0.1

        return embedding

    def update(self, page_id: int, op_type: OpType, delta_t: int) -> Tuple[float, float]:
        """
        Update phase integrator and return (phase, amplitude) for this event.

        Returns:
            Tuple of (phase, amplitude) for the current event
        """
        # Embed event
        x = self.embed_event(page_id, op_type, delta_t)

        # Compute phase: φ = π·sin(w_φ^T x)
        dot_phase = sum(w * xi for w, xi in zip(self._w_phase, x))
        phase = self.config.phase_scale * math.sin(dot_phase)

        # Compute amplitude: a = σ(w_a^T x)
        dot_amp = sum(w * xi for w, xi in zip(self._w_amp, x))
        amplitude = 1.0 / (1.0 + math.exp(-dot_amp))  # Sigmoid

        # Compute value vector: v = W_v x
        v = [sum(row[j] * x[j] for j in range(self.dim)) for row in self._w_value]

        # Compute complex phasor: k = a·e^{-jφ}
        k = amplitude * complex(math.cos(-phase), math.sin(-phase))

        # Update accumulator: M = γ·M + (1-γ)·(k ⊙ v)
        gamma = self.config.decay_gamma
        for i in range(self.dim):
            self._accumulator[i] = (
                gamma * self._accumulator[i] + (1 - gamma) * k * v[i]
            )

        # Update recent pages
        self._recent_pages.append(page_id)

        return (phase, amplitude)

    def get_context_phase(self) -> float:
        """Get current context phase from accumulator."""
        # Extract phase from mean of accumulator
        total = sum(self._accumulator)
        if abs(total) < 1e-10:
            return 0.0
        return math.atan2(total.imag, total.real)


class CoherenceComputer:
    """
    Computes coherence scores using fast and slow paths.

    Fast path (O(1) per access):
        C_fast = α·c + β·(1-δ) + γ·cos(φ - φ̄)

    Slow path (O(|N|×W) background):
        C_{i,j} = (1/W) Σ cos(φ_i - φ_j)
        c_i = σ(η·Σ C_{i,j})
    """

    def __init__(self, config: CTMPlusConfig):
        self.config = config.coherence
        self._access_counter = 0

    def fast_coherence(self, page: PageState, mean_phase: float) -> float:
        """
        Compute fast-path coherence score (O(1)).

        Called on every access.
        """
        return page.compute_fast_coherence(mean_phase, self.config)

    def slow_update(self, state: GlobalState) -> None:
        """
        Compute slow-path coherence scores (O(n × W)).

        Called periodically in background.
        Updates coherence scores for all pages in tier0 and tier1.
        """
        # Get all active pages
        all_pages = list(state.tier0.pages.values()) + list(state.tier1.pages.values())

        if len(all_pages) < 2:
            return

        # Build neighbor map (address-based locality)
        page_ids = sorted([p.page_id for p in all_pages])
        page_map = {p.page_id: p for p in all_pages}

        for page in all_pages:
            # Find neighbors (nearby page IDs)
            idx = page_ids.index(page.page_id) if page.page_id in page_ids else -1
            if idx < 0:
                continue

            neighbors = []
            for offset in range(-self.config.neighborhood_size // 2,
                               self.config.neighborhood_size // 2 + 1):
                neighbor_idx = idx + offset
                if 0 <= neighbor_idx < len(page_ids) and neighbor_idx != idx:
                    neighbors.append(page_map[page_ids[neighbor_idx]])

            if not neighbors:
                continue

            # Compute pairwise correlation
            total_corr = 0.0
            for neighbor in neighbors:
                corr = self._pairwise_correlation(page, neighbor)
                total_corr += corr

            # Update coherence via sigmoid
            raw_score = self.config.eta * total_corr
            page.coherence = 1.0 / (1.0 + math.exp(-raw_score))

    def _pairwise_correlation(self, page_i: PageState, page_j: PageState) -> float:
        """
        Compute pairwise phase correlation over history.

        C_{i,j} = (1/W) Σ cos(φ_i - φ_j)
        """
        hist_i = list(page_i.phase_history)
        hist_j = list(page_j.phase_history)

        if not hist_i or not hist_j:
            # No history, use current phase
            return math.cos(page_i.phase - page_j.phase)

        # Align histories
        min_len = min(len(hist_i), len(hist_j), self.config.window_size)
        if min_len == 0:
            return 0.0

        total = 0.0
        for k in range(min_len):
            phi_i = hist_i[-(k + 1)] if k < len(hist_i) else hist_i[0]
            phi_j = hist_j[-(k + 1)] if k < len(hist_j) else hist_j[0]
            total += math.cos(phi_i - phi_j)

        return total / min_len


class BCVFGate:
    """
    BCVF (Bidirectional Coherence Verification Framework) decision gate.

    Computes action weights via Lagrangian:
        L(i,A) = λ_f(1-s_f)² + λ_b(1-s_b)² + λ_c(s_f-s_b)²
        w(i,A) = e^{-β·L(i,A)}

    Only approves actions where w > threshold.
    """

    def __init__(self, config: CTMPlusConfig):
        self.config = config.bcvf
        self._rejections = 0
        self._approvals = 0

    def should_promote(
        self,
        page: PageState,
        state: GlobalState,
        predicted_hit_improvement: float = 0.1,
    ) -> Tuple[bool, float]:
        """
        Decide whether to promote a page from tier1 to tier0.

        Args:
            page: Page to potentially promote
            state: Global state
            predicted_hit_improvement: Expected hit rate improvement

        Returns:
            Tuple of (should_promote, weight)
        """
        # Forward score: immediate performance benefit
        s_f = self._forward_score_promote(page, predicted_hit_improvement)

        # Backward score: long-term health
        s_b = self._backward_score(page)

        # Compute BCVF Lagrangian
        L = (
            self.config.lambda_f * (1 - s_f) ** 2
            + self.config.lambda_b * (1 - s_b) ** 2
            + self.config.lambda_c * (s_f - s_b) ** 2
        )

        # Compute weight
        w = math.exp(-self.config.beta * L)

        # Decision
        approved = w > self.config.threshold

        if approved:
            self._approvals += 1
        else:
            self._rejections += 1

        return (approved, w)

    def should_demote(
        self,
        page: PageState,
        state: GlobalState,
    ) -> Tuple[bool, float]:
        """
        Decide whether to demote a page from tier0 to tier1.

        Returns:
            Tuple of (should_demote, weight)
        """
        # Forward score: how much does keeping this page help?
        # Low score = not helping much = OK to demote
        s_f = self._forward_score_demote(page)

        # Backward score: long-term health of demotion
        s_b = self._backward_score_demote(page)

        # BCVF Lagrangian
        L = (
            self.config.lambda_f * (1 - s_f) ** 2
            + self.config.lambda_b * (1 - s_b) ** 2
            + self.config.lambda_c * (s_f - s_b) ** 2
        )

        w = math.exp(-self.config.beta * L)

        approved = w > self.config.threshold

        if approved:
            self._approvals += 1
        else:
            self._rejections += 1

        return (approved, w)

    def _forward_score_promote(self, page: PageState, hit_improvement: float) -> float:
        """Forward score for promotion: will this reduce latency?"""
        # Combine predicted hit improvement with page amplitude
        score = (
            self.config.alpha_latency * min(1.0, hit_improvement * 2)
            + self.config.alpha_miss * page.amplitude
        )
        return 1.0 / (1.0 + math.exp(-score * 4))  # Sigmoid

    def _forward_score_demote(self, page: PageState) -> float:
        """Forward score for demotion: how much will we lose?"""
        # Higher amplitude = more to lose = lower demotion score
        return 1.0 - page.amplitude

    def _backward_score(self, page: PageState) -> float:
        """Backward score: long-term health."""
        score = (
            self.config.beta_heat * (1 - page.heat)
            + self.config.beta_coherence * page.coherence
            + self.config.beta_uncertainty * (1 - page.uncertainty)
            + self.config.beta_drift * (1 - page.drift)
        )
        return 1.0 / (1.0 + math.exp(-score * 4))

    def _backward_score_demote(self, page: PageState) -> float:
        """Backward score for demotion: is it safe to demote?"""
        # High heat = lots of writes = risky to demote to NAND
        # Low coherence = unstable = maybe OK to demote
        score = (
            self.config.beta_heat * (1 - page.heat)  # Low heat = safe
            + self.config.beta_coherence * (1 - page.coherence)  # Low coherence = OK to demote
            + self.config.beta_uncertainty * page.uncertainty  # High uncertainty = OK to demote
        )
        return 1.0 / (1.0 + math.exp(-score * 4))

    @property
    def rejection_rate(self) -> float:
        total = self._rejections + self._approvals
        if total == 0:
            return 0.0
        return self._rejections / total


class SCCOptimizer:
    """
    SCC (Semantic Coherence Controller) for self-tuning parameters.

    Computes global coherence and adjusts BCVF parameters:
        C_tier = α·c̄ + β·R̄ + γ·(1-ū) + δ·P̄
        θ_{t+1} = θ_t + ρ·∇_θ C_global
    """

    def __init__(self, config: CTMPlusConfig):
        self.config = config.scc

        # Tunable parameters (will be adjusted)
        self.threshold = config.bcvf.threshold
        self.beta = config.bcvf.beta

        # History for gradient estimation
        self._coherence_history: deque = deque(maxlen=10)
        self._threshold_history: deque = deque(maxlen=10)

    def compute_tier_coherence(self, state: GlobalState) -> float:
        """Compute per-tier coherence score."""
        tier0_pages = list(state.tier0.pages.values())

        if not tier0_pages:
            return 0.0

        # Mean coherence
        c_bar = sum(p.coherence for p in tier0_pages) / len(tier0_pages)

        # Hit rate (reuse)
        r_bar = state.tier0.hit_rate

        # Mean certainty (1 - uncertainty)
        u_bar = sum(1 - p.uncertainty for p in tier0_pages) / len(tier0_pages)

        # Predictability (inverse of phase variance)
        if len(tier0_pages) > 1:
            phases = [p.phase for p in tier0_pages]
            mean_phase = sum(phases) / len(phases)
            variance = sum((p - mean_phase) ** 2 for p in phases) / len(phases)
            p_bar = 1.0 / (1.0 + variance)
        else:
            p_bar = 0.5

        return (
            self.config.alpha * c_bar
            + self.config.beta * r_bar
            + self.config.gamma * u_bar
            + self.config.delta * p_bar
        )

    def update(self, state: GlobalState, bcvf: BCVFGate) -> None:
        """
        Update tunable parameters based on coherence gradient.

        Called periodically (every SCC update interval).
        """
        current_coherence = self.compute_tier_coherence(state)
        self._coherence_history.append(current_coherence)
        self._threshold_history.append(self.threshold)

        if len(self._coherence_history) < 3:
            return

        # Estimate gradient via finite differences
        c_prev = self._coherence_history[-2]
        c_curr = self._coherence_history[-1]
        t_prev = self._threshold_history[-2]
        t_curr = self._threshold_history[-1]

        # Simple gradient approximation
        if abs(t_curr - t_prev) > 1e-6:
            grad = (c_curr - c_prev) / (t_curr - t_prev + 1e-6)
        else:
            grad = 0.0

        # Update threshold to maximize coherence
        self.threshold = max(0.3, min(0.9, self.threshold + self.config.learning_rate * grad))

        # Also adjust temperature based on rejection rate
        if bcvf.rejection_rate > 0.5:
            # Too many rejections, lower temperature (sharper decisions)
            self.beta = min(5.0, self.beta * 1.01)
        elif bcvf.rejection_rate < 0.1:
            # Too few rejections, raise temperature (more exploration)
            self.beta = max(1.0, self.beta * 0.99)


class NeighborTracker:
    """
    Tracks co-occurrence patterns to identify correlated pages.

    Maintains a sliding window of recent accesses and builds a
    neighbor map: page_id -> list of frequently co-accessed pages.

    This enables CTM+ to exploit structure that LRU cannot see.
    """

    def __init__(self, window_size: int = 16, top_k: int = 8, min_count: int = 3):
        self.window_size = window_size
        self.top_k = top_k
        self.min_count = min_count

        # Recent access window
        self._recent: deque = deque(maxlen=window_size)

        # Co-occurrence counts: (page_a, page_b) -> count
        self._cooccurrence: Dict[Tuple[int, int], int] = {}

        # Cached neighbor lists: page_id -> [neighbor_ids]
        self._neighbors: Dict[int, List[int]] = {}

        # Update interval (rebuild neighbors every N accesses)
        self._access_count = 0
        self._rebuild_interval = 1000

    def record_access(self, page_id: int) -> None:
        """Record an access and update co-occurrence."""
        # Update co-occurrence with recent pages
        for recent_page in self._recent:
            if recent_page != page_id:
                key = (min(page_id, recent_page), max(page_id, recent_page))
                self._cooccurrence[key] = self._cooccurrence.get(key, 0) + 1

        self._recent.append(page_id)
        self._access_count += 1

        # Periodically rebuild neighbor lists
        if self._access_count % self._rebuild_interval == 0:
            self._rebuild_neighbors()

    def get_neighbors(self, page_id: int) -> List[int]:
        """Get top-K neighbors for a page."""
        return self._neighbors.get(page_id, [])

    def _rebuild_neighbors(self) -> None:
        """Rebuild neighbor lists from co-occurrence data."""
        # Group by page
        page_counts: Dict[int, List[Tuple[int, int]]] = {}

        for (a, b), count in self._cooccurrence.items():
            if count >= self.min_count:
                if a not in page_counts:
                    page_counts[a] = []
                if b not in page_counts:
                    page_counts[b] = []
                page_counts[a].append((b, count))
                page_counts[b].append((a, count))

        # Build top-K neighbor lists
        self._neighbors = {}
        for page_id, neighbors in page_counts.items():
            # Sort by count descending, take top K
            neighbors.sort(key=lambda x: x[1], reverse=True)
            self._neighbors[page_id] = [n[0] for n in neighbors[:self.top_k]]

    def get_neighbor_hotness(self, page_id: int, state: 'GlobalState') -> float:
        """
        Compute how "hot" a page's neighbors are.

        Returns a score [0, 1] based on how many neighbors are in tier0.
        """
        neighbors = self.get_neighbors(page_id)
        if not neighbors:
            return 0.0

        in_tier0 = sum(1 for n in neighbors if state.tier0.contains(n))
        return in_tier0 / len(neighbors)


class ShadowTier:
    """
    Ghost cache that tracks recently evicted/bypassed pages.

    This is the key to matching ARC's "regret tracking" capability.
    When we see a "shadow hit" (miss that was recently evicted),
    we know we made a wrong decision and should correct it.

    Equivalent to ARC's B1/B2 ghost lists.
    """

    def __init__(self, max_size: int = 2000):
        self.max_size = max_size
        self._pages: deque = deque()
        self._lookup: set = set()

        # Stats for feedback loop
        self.shadow_hits = 0
        self.total_checks = 0

    def add(self, page_id: int) -> None:
        """Add a page to the shadow tier (was evicted/bypassed)."""
        if page_id in self._lookup:
            return

        if len(self._pages) >= self.max_size:
            removed = self._pages.popleft()
            self._lookup.discard(removed)

        self._pages.append(page_id)
        self._lookup.add(page_id)

    def contains(self, page_id: int) -> bool:
        """Check if page is in shadow tier (was recently evicted)."""
        self.total_checks += 1
        hit = page_id in self._lookup
        if hit:
            self.shadow_hits += 1
        return hit

    def remove(self, page_id: int) -> None:
        """Remove page from shadow tier (being re-admitted)."""
        self._lookup.discard(page_id)

    @property
    def shadow_hit_rate(self) -> float:
        """Rate of shadow hits (indicates eviction regret)."""
        return self.shadow_hits / self.total_checks if self.total_checks > 0 else 0.0


class TransitionTracker:
    """
    Enhanced Markov transition model with:
    - Recency-weighted transitions (ChatGPT suggestion)
    - 2-gram support for better pattern capture (Gemini suggestion)

    This is the key differentiator from ARC - we can predict
    what's coming next, not just what was recently accessed.
    """

    def __init__(self, top_m: int = 8, decay_tau: int = 500):
        self.top_m = top_m
        self.decay_tau = decay_tau  # Decay horizon in accesses

        # 1st-order transitions: current_page -> {next_page: score}
        self._transitions: Dict[int, Dict[int, float]] = {}

        # 2nd-order transitions: (prev, current) -> {next_page: score}
        # Key is (prev ^ current) for efficiency
        self._transitions_2gram: Dict[int, Dict[int, float]] = {}

        # Access history
        self._last_page: Optional[int] = None
        self._prev_page: Optional[int] = None  # For 2-gram

        # Last access time for recency weighting
        self._last_transition_time: Dict[Tuple[int, int], int] = {}
        self._access_count = 0

        # Stats
        self._total_transitions = 0

    def record_access(self, page_id: int) -> None:
        """Record a transition with recency-weighted scoring."""
        self._access_count += 1

        if self._last_page is not None and self._last_page != page_id:
            # === 1st-order transition ===
            self._update_transition(
                self._transitions,
                self._last_page,
                page_id,
                (self._last_page, page_id)
            )

            # === 2nd-order transition (2-gram) ===
            if self._prev_page is not None:
                # Key: hash of (prev, last) pair
                bigram_key = (self._prev_page << 16) ^ self._last_page
                self._update_transition(
                    self._transitions_2gram,
                    bigram_key,
                    page_id,
                    (bigram_key, page_id)
                )

            self._total_transitions += 1

        # Update history
        self._prev_page = self._last_page
        self._last_page = page_id

    def _update_transition(
        self,
        trans_dict: Dict[int, Dict[int, float]],
        key: int,
        next_page: int,
        time_key: Tuple[int, int]
    ) -> None:
        """Update a transition with recency weighting."""
        if key not in trans_dict:
            trans_dict[key] = {}

        trans = trans_dict[key]

        # Compute recency-weighted increment
        # weight = exp(-Δt / τ) where Δt is time since last this transition
        last_time = self._last_transition_time.get(time_key, 0)
        delta_t = self._access_count - last_time
        weight = math.exp(-delta_t / self.decay_tau) if delta_t > 0 else 1.0

        # Update score with recency weight (more recent = higher weight)
        trans[next_page] = trans.get(next_page, 0.0) * 0.95 + (1.0 + weight)

        # Record transition time
        self._last_transition_time[time_key] = self._access_count

        # Prune to top-M
        if len(trans) > self.top_m * 2:
            sorted_trans = sorted(trans.items(), key=lambda x: x[1], reverse=True)
            trans_dict[key] = dict(sorted_trans[:self.top_m])

    def get_next_probability(self, current_page: int, next_page: int) -> float:
        """Get P(next_page | current_page)."""
        if current_page not in self._transitions:
            return 0.0

        trans = self._transitions[current_page]
        total = sum(trans.values())
        if total == 0:
            return 0.0

        return trans.get(next_page, 0.0) / total

    def get_top_predictions(self, current_page: int, k: int = 3) -> List[Tuple[int, float]]:
        """
        Get top-K most likely next pages using both 1-gram and 2-gram.

        2-gram is preferred when available (more context = better prediction).
        """
        predictions = {}

        # Try 2-gram first (if we have prev_page context)
        if self._prev_page is not None:
            bigram_key = (self._prev_page << 16) ^ current_page
            if bigram_key in self._transitions_2gram:
                trans = self._transitions_2gram[bigram_key]
                total = sum(trans.values())
                if total > 0:
                    for page, score in trans.items():
                        # 2-gram predictions get higher weight
                        predictions[page] = predictions.get(page, 0) + 1.5 * (score / total)

        # Add 1-gram predictions
        if current_page in self._transitions:
            trans = self._transitions[current_page]
            total = sum(trans.values())
            if total > 0:
                for page, score in trans.items():
                    predictions[page] = predictions.get(page, 0) + (score / total)

        if not predictions:
            return []

        # Normalize and return top-K
        total = sum(predictions.values())
        sorted_pred = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        return [(page, score / total) for page, score in sorted_pred[:k]]

    def get_reuse_score(self, page_id: int) -> float:
        """
        Estimate how likely this page is to be accessed soon.

        Looks at all pages that transition TO this page.
        """
        score = 0.0
        for src, trans in self._transitions.items():
            if page_id in trans:
                total = sum(trans.values())
                if total > 0:
                    score += trans[page_id] / total
        return min(1.0, score)


class AdmissionController:
    """
    Enhanced admission controller with scan-pressure adaptation.

    Features:
    - Probabilistic admission based on reuse/cluster scores
    - Scan detection and penalty
    - Dynamic adaptation via scan_pressure (ChatGPT suggestion)
    - loosen_constraints() for shadow hit feedback (Gemini suggestion)
    """

    def __init__(
        self,
        base_admit_prob: float = 0.8,
        reuse_weight: float = 0.4,
        cluster_weight: float = 0.3,
        stream_penalty: float = 0.3,
    ):
        self.base_admit_prob = base_admit_prob
        self.reuse_weight = reuse_weight
        self.cluster_weight = cluster_weight
        self.stream_penalty = stream_penalty

        # Track sequential access patterns (scan detection)
        self._last_pages: deque = deque(maxlen=8)
        self._sequential_count = 0

        # Scan pressure: adapts admission based on workload phase (ChatGPT suggestion)
        self._scan_pressure: float = 0.0  # [0, 1]
        self._unique_pages_window: set = set()
        self._reuse_count = 0
        self._window_accesses = 0

        # Stats
        self.admits = 0
        self.bypasses = 0

    def should_admit(
        self,
        page_id: int,
        reuse_score: float,
        cluster_score: float,
        access_count: int,
    ) -> bool:
        """
        Decide whether to admit page to fast tier.

        Uses scan-pressure to adapt to workload phases.
        """
        # Update scan pressure tracking
        self._window_accesses += 1
        if page_id in self._unique_pages_window:
            self._reuse_count += 1
        self._unique_pages_window.add(page_id)

        # Update scan_pressure every 100 accesses
        if self._window_accesses >= 100:
            unique_rate = len(self._unique_pages_window) / self._window_accesses
            reuse_rate = self._reuse_count / self._window_accesses

            # High unique rate = scanning, low reuse = scanning
            if unique_rate > 0.8:
                self._scan_pressure = min(1.0, self._scan_pressure + 0.1)
            elif reuse_rate > 0.3:
                self._scan_pressure = max(0.0, self._scan_pressure - 0.1)

            # Reset window
            self._unique_pages_window.clear()
            self._reuse_count = 0
            self._window_accesses = 0

        # Detect sequential scan (cache-unfriendly)
        is_sequential = False
        if self._last_pages:
            last = self._last_pages[-1]
            if abs(page_id - last) <= 2:
                self._sequential_count += 1
                if self._sequential_count > 4:
                    is_sequential = True
            else:
                self._sequential_count = 0

        self._last_pages.append(page_id)

        # Compute admission probability with scan-pressure modulation
        stream_score = 1.0 if is_sequential else 0.0

        raw_score = (
            self.reuse_weight * reuse_score
            + self.cluster_weight * cluster_score
            - self.stream_penalty * stream_score
        )

        # Sigmoid to get probability
        p_admit = 1.0 / (1.0 + math.exp(-4.0 * (raw_score - 0.3)))

        # Modulate by scan pressure (high pressure = more conservative)
        p_admit *= (1.0 - 0.5 * self._scan_pressure)

        # Boost for pages with history
        if access_count > 1:
            p_admit = min(1.0, p_admit + 0.2)

        # Make decision
        admit = random.random() < p_admit

        if admit:
            self.admits += 1
        else:
            self.bypasses += 1

        return admit

    def loosen_constraints(self) -> None:
        """
        Called when shadow hit detected - we were too strict.

        Reduces stream_penalty to admit more pages (Gemini suggestion).
        """
        self.stream_penalty = max(0.1, self.stream_penalty - 0.05)
        self._scan_pressure = max(0.0, self._scan_pressure - 0.1)

    def tighten_constraints(self) -> None:
        """Called when pollution detected - we were too loose."""
        self.stream_penalty = min(0.5, self.stream_penalty + 0.02)

    @property
    def bypass_rate(self) -> float:
        """Fraction of accesses that bypassed cache."""
        total = self.admits + self.bypasses
        return self.bypasses / total if total > 0 else 0.0

    @property
    def scan_pressure(self) -> float:
        """Current scan pressure level."""
        return self._scan_pressure


class PrefetchEngine:
    """
    Dynamic budgeted prefetch engine.

    Features:
    - Adaptive budget based on prefetch_hit_rate (Gemini suggestion)
    - Burst prefetch for confident predictions (ChatGPT suggestion)
    """

    def __init__(
        self,
        initial_budget: int = 15,  # Initial prefetches per 1000 accesses
        min_probability: float = 0.25,  # Min P(next) to trigger prefetch
        max_distance: int = 64,
    ):
        self.budget_per_1k = initial_budget
        self.min_budget = 5
        self.max_budget = 50
        self.min_probability = min_probability
        self.max_distance = max_distance

        # Budget tracking
        self._prefetches_this_epoch = 0
        self._epoch_accesses = 0

        # Stats
        self.total_prefetches = 0
        self.prefetch_hits = 0
        self.prefetch_misses = 0
        self._pending_prefetches: set = set()

        # For adaptive budgeting
        self._epoch_hits = 0
        self._epoch_prefetches = 0

    def should_prefetch(self, probability: float) -> bool:
        """Check if we should prefetch given the probability and budget."""
        # Check budget
        budget_remaining = self.budget_per_1k - self._prefetches_this_epoch
        if budget_remaining <= 0:
            return False

        # Check probability threshold
        if probability < self.min_probability:
            return False

        return True

    def get_burst_size(self, confidence: float) -> int:
        """
        Get number of pages to prefetch based on confidence (ChatGPT suggestion).

        High confidence = prefetch more (burst), low = prefetch 1.
        """
        return min(4, max(1, int(confidence * 6)))

    def record_prefetch(self, page_id: int) -> None:
        """Record that we prefetched a page."""
        self._prefetches_this_epoch += 1
        self._epoch_prefetches += 1
        self.total_prefetches += 1
        self._pending_prefetches.add(page_id)

    def record_access(self, page_id: int) -> None:
        """Record an access with dynamic budget adjustment (Gemini suggestion)."""
        self._epoch_accesses += 1

        # Check if this was a prefetched page
        if page_id in self._pending_prefetches:
            self.prefetch_hits += 1
            self._epoch_hits += 1
            self._pending_prefetches.discard(page_id)

        # End of epoch: adjust budget based on hit rate
        if self._epoch_accesses >= 1000:
            # Count remaining pending prefetches as misses
            self.prefetch_misses += len(self._pending_prefetches)

            # Dynamic budget adjustment (Gemini suggestion)
            if self._epoch_prefetches > 0:
                epoch_hit_rate = self._epoch_hits / self._epoch_prefetches
                if epoch_hit_rate > 0.5:
                    # Predictions are good - increase budget
                    self.budget_per_1k = min(self.max_budget, self.budget_per_1k + 5)
                elif epoch_hit_rate < 0.1:
                    # Predictions are bad - decrease budget
                    self.budget_per_1k = max(self.min_budget, self.budget_per_1k - 5)

            # Reset epoch
            self._pending_prefetches.clear()
            self._prefetches_this_epoch = 0
            self._epoch_accesses = 0
            self._epoch_hits = 0
            self._epoch_prefetches = 0

    @property
    def prefetch_hit_rate(self) -> float:
        """Fraction of prefetches that were actually used."""
        total = self.prefetch_hits + self.prefetch_misses
        return self.prefetch_hits / total if total > 0 else 0.0


class CTMPlusController(BaseController):
    """
    CTM+ Controller: Full implementation of Coherence-Tier Memory Plus.

    Integrates all components:
    - Phase Integrator for pattern learning
    - Coherence Computer for fast/slow coherence
    - BCVF Gate for bidirectional verification
    - SCC Optimizer for self-tuning
    - NeighborTracker for correlated page detection
    - TransitionTracker for Markov predictions (NEW)
    - AdmissionController for probabilistic admission (NEW)
    - PrefetchEngine for budgeted prefetch (NEW)
    """

    def __init__(
        self,
        config: SimulatorConfig,
        ctm_config: Optional[CTMPlusConfig] = None,
    ):
        super().__init__(config)
        self.ctm_config = ctm_config or CTMPlusConfig.default()

        # Initialize components
        self._phase_integrator = PhaseIntegrator(self.ctm_config)
        self._coherence = CoherenceComputer(self.ctm_config)
        self._bcvf = BCVFGate(self.ctm_config)
        self._scc = SCCOptimizer(self.ctm_config)
        self._neighbor_tracker = NeighborTracker()

        # NEW: Predictive components (the key to beating ARC)
        self._transition_tracker = TransitionTracker(top_m=8, decay_tau=500)
        self._admission_controller = AdmissionController()
        self._prefetch_engine = PrefetchEngine(initial_budget=15, min_probability=0.25)

        # NEW v2: Shadow tier for regret tracking (like ARC's B1/B2)
        self._shadow_tier = ShadowTier(max_size=2048)

        # Stats
        self._promotions = 0
        self._demotions = 0
        self._bcvf_rejections = 0
        self._access_counter = 0
        self._last_access_time: Dict[int, int] = {}
        self._neighbor_boosts = 0
        self._prefetch_promotions = 0
        self._shadow_hit_promotions = 0

        # Epoch tracking
        self._epoch_promotions = 0
        self._epoch_demotions = 0

    @property
    def name(self) -> str:
        return "CTM+"

    def reset(self) -> None:
        self._phase_integrator = PhaseIntegrator(self.ctm_config)
        self._coherence = CoherenceComputer(self.ctm_config)
        self._bcvf = BCVFGate(self.ctm_config)
        self._scc = SCCOptimizer(self.ctm_config)
        self._neighbor_tracker = NeighborTracker()
        self._transition_tracker = TransitionTracker(top_m=8, decay_tau=500)
        self._admission_controller = AdmissionController()
        self._prefetch_engine = PrefetchEngine(initial_budget=15, min_probability=0.25)
        self._shadow_tier = ShadowTier(max_size=2048)
        self._promotions = 0
        self._demotions = 0
        self._bcvf_rejections = 0
        self._access_counter = 0
        self._last_access_time = {}
        self._neighbor_boosts = 0
        self._prefetch_promotions = 0
        self._epoch_promotions = 0
        self._epoch_demotions = 0
        self._shadow_hit_promotions = 0

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
    ) -> Tuple[Tier, int, bool, bool]:
        self._access_counter += 1

        # === NEW: Track transitions for Markov predictions ===
        self._transition_tracker.record_access(page_id)
        self._prefetch_engine.record_access(page_id)

        # Track co-occurrence for neighbor learning
        self._neighbor_tracker.record_access(page_id)

        # Compute delta_t
        delta_t = self._access_counter - self._last_access_time.get(page_id, 0)
        self._last_access_time[page_id] = self._access_counter

        # Update phase integrator
        phase, amplitude = self._phase_integrator.update(page_id, op_type, delta_t)

        # Get or create page
        page = state.get_or_create_page(page_id)

        # Update page state
        page.phase = phase
        page.amplitude = max(page.amplitude, amplitude)
        page.update_on_access(state.current_time, op_type)

        # Boost coherence of neighbors
        neighbors = self._neighbor_tracker.get_neighbors(page_id)
        for neighbor_id in neighbors:
            neighbor = state.all_pages.get(neighbor_id)
            if neighbor:
                neighbor.coherence = min(1.0, neighbor.coherence + 0.02)
                self._neighbor_boosts += 1

        # Compute coherence scores
        mean_phase = state.global_mean_phase
        fast_coh = self._coherence.fast_coherence(page, mean_phase)
        neighbor_hotness = self._neighbor_tracker.get_neighbor_hotness(page_id, state)

        # === NEW: Get reuse prediction from transition model ===
        reuse_score = self._transition_tracker.get_reuse_score(page_id)

        promoted = False
        demoted = False

        # Case 1: Page in tier0 (fast tier hit)
        if state.tier0.contains(page_id):
            state.tier0.touch(page_id)
            state.tier0.record_hit()

            # === NEW: Predictive prefetch after tier0 hit ===
            self._do_predictive_prefetch(state, page_id)

            latency = self._compute_latency(Tier.TIER0, False, False)
            return (Tier.TIER0, latency, False, False)

        # Case 2: Page in tier1 (slow tier hit - consider promotion)
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)

            # === NEW v2: Check if this is a regret case (page was recently demoted) ===
            is_shadow_hit = self._shadow_tier.contains(page_id)
            if is_shadow_hit:
                # REGRET: We evicted this page but it came back. Force promote!
                self._shadow_tier.remove(page_id)
                self._shadow_hit_promotions += 1
                self._admission_controller.loosen_constraints()
                should_promote = True
            else:
                # Check promotion eligibility
                can_promote = (
                    self._epoch_promotions < self.ctm_config.max_promotions_per_epoch
                    and state.current_time - page.last_demotion_time > self.ctm_config.promotion_cooldown
                )

                if can_promote:
                    # Use transition-based reuse score in promotion decision
                    combined_score = 0.5 * reuse_score + 0.3 * fast_coh + 0.2 * neighbor_hotness
                    should_promote, weight = self._bcvf.should_promote(
                        page, state, predicted_hit_improvement=combined_score * 0.4
                    )
                    if not should_promote:
                        self._bcvf_rejections += 1
                else:
                    should_promote = False

            if should_promote:
                state.tier1.remove(page_id)
                evicted = state.tier0.add(page)
                promoted = True
                self._promotions += 1
                self._epoch_promotions += 1
                page.last_promotion_time = state.current_time

                if evicted is not None:
                    demoted = self._handle_eviction(state, evicted)

                # Prefetch after promotion
                self._do_predictive_prefetch(state, page_id)

            latency = self._compute_latency(Tier.TIER1, promoted, demoted)
            return (Tier.TIER1, latency, promoted, demoted)

        # Case 3: Miss - add to system
        # === NEW v2: Check shadow tier first (regret detection) ===
        is_shadow_hit = self._shadow_tier.contains(page_id)
        if is_shadow_hit:
            # Shadow hit! We evicted/bypassed this page but it came back.
            # This means we were too strict - loosen admission constraints.
            self._admission_controller.loosen_constraints()
            self._shadow_tier.remove(page_id)
            self._shadow_hit_promotions += 1
            # Force admission to tier0 (bypass the admission controller)
            should_admit = True
        else:
            # Normal admission decision
            access_count = page.access_count
            cluster_score = neighbor_hotness
            should_admit = self._admission_controller.should_admit(
                page_id=page_id,
                reuse_score=reuse_score,
                cluster_score=cluster_score,
                access_count=access_count,
            )

        if should_admit and not state.tier0.is_full:
            # Admit directly to tier0
            state.tier0.add(page)
            promoted = True
            self._promotions += 1
            self._epoch_promotions += 1
        elif should_admit:
            # Admit with eviction
            evicted = state.tier0.add(page)
            promoted = True
            self._promotions += 1
            self._epoch_promotions += 1

            if evicted is not None:
                demoted = self._handle_eviction(state, evicted)
        else:
            # Bypass: add to tier1 (scan resistance)
            # Note: We don't add bypassed pages to shadow tier - only evicted pages
            # Shadow tier tracks "regret" for pages that WERE in tier0 and got evicted
            state.tier1.add(page)

        latency = self._compute_latency(Tier.NONE, promoted, demoted)
        return (Tier.NONE, latency, promoted, demoted)

    def _do_predictive_prefetch(self, state: GlobalState, current_page: int) -> None:
        """
        Prefetch predicted next page(s) based on transition model.

        This is CTM+'s key differentiator from ARC.
        Uses burst prefetch for high-confidence predictions (ChatGPT suggestion).
        """
        # Get top predictions - get more candidates for burst
        predictions = self._transition_tracker.get_top_predictions(current_page, k=4)

        if not predictions:
            return

        # === NEW v2: Burst prefetch based on confidence ===
        top_confidence = predictions[0][1] if predictions else 0.0
        burst_size = self._prefetch_engine.get_burst_size(top_confidence)
        prefetched_count = 0

        for next_page, probability in predictions:
            if prefetched_count >= burst_size:
                break

            # Check if we should prefetch
            if not self._prefetch_engine.should_prefetch(probability):
                continue

            # Check if page exists and is in tier1
            page = state.all_pages.get(next_page)
            if page is None:
                continue

            if state.tier1.contains(next_page):
                # Prefetch: promote from tier1 to tier0
                state.tier1.remove(next_page)
                evicted = state.tier0.add(page)
                self._prefetch_promotions += 1
                self._prefetch_engine.record_prefetch(next_page)
                prefetched_count += 1

                if evicted is not None:
                    # Put evicted page in tier1 and track in shadow tier
                    state.tier1.add(evicted)
                    self._shadow_tier.add(evicted.page_id)

    def _handle_eviction(self, state: GlobalState, evicted: PageState) -> bool:
        """Handle evicted page with BCVF verification and neighbor protection."""
        # Check if evicted page has hot neighbors (cluster protection)
        neighbor_hotness = self._neighbor_tracker.get_neighbor_hotness(evicted.page_id, state)

        # If page has many hot neighbors, protect it (don't demote)
        if neighbor_hotness > 0.6:
            # Keep in tier0 - its cluster is still hot
            state.tier0.add(evicted)
            self._bcvf_rejections += 1
            return False

        should_demote, _ = self._bcvf.should_demote(evicted, state)

        if should_demote:
            state.tier1.add(evicted)
            evicted.last_demotion_time = state.current_time
            self._demotions += 1
            self._epoch_demotions += 1
            # === NEW v2: Track evicted pages in shadow tier for regret detection ===
            self._shadow_tier.add(evicted.page_id)
            return True
        else:
            # BCVF rejected demotion - put back in tier0 (LRU position)
            state.tier0.add(evicted)
            self._bcvf_rejections += 1
            return False

    def on_epoch(self, state: GlobalState, epoch: int) -> None:
        """End of epoch processing."""
        # Reset epoch counters
        self._epoch_promotions = 0
        self._epoch_demotions = 0

        # Apply decay to pages not recently accessed
        # This updates amplitude, uncertainty, drift based on time since last access
        for page in list(state.tier0.pages.values()) + list(state.tier1.pages.values()):
            page.decay(state.current_time, decay_rate=0.001)

        # Slow-path coherence update - now every epoch instead of every 10
        self._coherence.slow_update(state)

        # SCC parameter tuning
        self._scc.update(state, self._bcvf)

        # Update BCVF with SCC-tuned parameters
        self._bcvf.config = type(self._bcvf.config)(
            threshold=self._scc.threshold,
            beta=self._scc.beta,
            lambda_f=self._bcvf.config.lambda_f,
            lambda_b=self._bcvf.config.lambda_b,
            lambda_c=self._bcvf.config.lambda_c,
            alpha_latency=self._bcvf.config.alpha_latency,
            alpha_miss=self._bcvf.config.alpha_miss,
            beta_heat=self._bcvf.config.beta_heat,
            beta_coherence=self._bcvf.config.beta_coherence,
            beta_uncertainty=self._bcvf.config.beta_uncertainty,
            beta_drift=self._bcvf.config.beta_drift,
        )

    def get_stats(self) -> dict:
        return {
            "promotions": self._promotions,
            "demotions": self._demotions,
            "bcvf_rejections": self._bcvf_rejections,
            "bcvf_rejection_rate": self._bcvf.rejection_rate,
            "scc_threshold": self._scc.threshold,
            "scc_beta": self._scc.beta,
            "tier_coherence": self._scc.compute_tier_coherence,
            "neighbor_boosts": self._neighbor_boosts,
            "tracked_neighbors": len(self._neighbor_tracker._neighbors),
            # Predictive component stats
            "prefetch_promotions": self._prefetch_promotions,
            "prefetch_hit_rate": self._prefetch_engine.prefetch_hit_rate,
            "total_prefetches": self._prefetch_engine.total_prefetches,
            "prefetch_budget": self._prefetch_engine.budget_per_1k,
            "admission_bypass_rate": self._admission_controller.bypass_rate,
            "scan_pressure": self._admission_controller.scan_pressure,
            "transition_count": self._transition_tracker._total_transitions,
            # NEW v2: Shadow tier stats
            "shadow_hit_promotions": self._shadow_hit_promotions,
            "shadow_hit_rate": self._shadow_tier.shadow_hit_rate,
            "shadow_tier_size": len(self._shadow_tier._pages),
        }

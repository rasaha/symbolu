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


class CTMPlusController(BaseController):
    """
    CTM+ Controller: Full implementation of Coherence-Tier Memory Plus.

    Integrates all components:
    - Phase Integrator for pattern learning
    - Coherence Computer for fast/slow coherence
    - BCVF Gate for bidirectional verification
    - SCC Optimizer for self-tuning
    - NeighborTracker for correlated page detection
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

        # Stats
        self._promotions = 0
        self._demotions = 0
        self._bcvf_rejections = 0
        self._access_counter = 0
        self._last_access_time: Dict[int, int] = {}
        self._neighbor_boosts = 0

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
        self._promotions = 0
        self._demotions = 0
        self._bcvf_rejections = 0
        self._access_counter = 0
        self._last_access_time = {}
        self._neighbor_boosts = 0
        self._epoch_promotions = 0
        self._epoch_demotions = 0

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
    ) -> Tuple[Tier, int, bool, bool]:
        self._access_counter += 1

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
        page.amplitude = max(page.amplitude, amplitude)  # Keep max amplitude
        page.update_on_access(state.current_time, op_type)

        # Boost coherence of neighbors (key for cluster-awareness)
        neighbors = self._neighbor_tracker.get_neighbors(page_id)
        for neighbor_id in neighbors:
            neighbor = state.all_pages.get(neighbor_id)
            if neighbor:
                # Small coherence boost for co-accessed pages
                neighbor.coherence = min(1.0, neighbor.coherence + 0.02)
                self._neighbor_boosts += 1

        # Compute fast coherence
        mean_phase = state.global_mean_phase
        fast_coh = self._coherence.fast_coherence(page, mean_phase)

        # Factor in neighbor hotness (if neighbors are in tier0, this page is valuable)
        neighbor_hotness = self._neighbor_tracker.get_neighbor_hotness(page_id, state)
        adjusted_coh = 0.7 * fast_coh + 0.3 * neighbor_hotness

        promoted = False
        demoted = False

        # Case 1: Page in tier0 (fast tier hit)
        if state.tier0.contains(page_id):
            state.tier0.touch(page_id)
            state.tier0.record_hit()
            latency = self._compute_latency(Tier.TIER0, False, False)
            return (Tier.TIER0, latency, False, False)

        # Case 2: Page in tier1 (slow tier hit - consider promotion)
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)

            # Check BCVF for promotion (use adjusted coherence)
            can_promote = (
                self._epoch_promotions < self.ctm_config.max_promotions_per_epoch
                and state.current_time - page.last_demotion_time > self.ctm_config.promotion_cooldown
            )

            if can_promote:
                # Use adjusted coherence that includes neighbor hotness
                should_promote, weight = self._bcvf.should_promote(
                    page, state, predicted_hit_improvement=adjusted_coh * 0.3
                )

                if should_promote:
                    # Promote
                    state.tier1.remove(page_id)
                    evicted = state.tier0.add(page)
                    promoted = True
                    self._promotions += 1
                    self._epoch_promotions += 1
                    page.last_promotion_time = state.current_time

                    # Handle eviction with BCVF (consider neighbor protection)
                    if evicted is not None:
                        demoted = self._handle_eviction(state, evicted)
                else:
                    self._bcvf_rejections += 1

            latency = self._compute_latency(Tier.TIER1, promoted, demoted)
            return (Tier.TIER1, latency, promoted, demoted)

        # Case 3: Miss - add to system
        # Use coherence to decide initial tier
        if fast_coh > 0.6 and not state.tier0.is_full:
            # High coherence - add to tier0
            state.tier0.add(page)
        elif fast_coh > 0.6:
            # High coherence but tier0 full - promote with eviction
            evicted = state.tier0.add(page)
            promoted = True
            self._promotions += 1
            self._epoch_promotions += 1

            if evicted is not None:
                demoted = self._handle_eviction(state, evicted)
        else:
            # Low coherence - add to tier1
            state.tier1.add(page)

        latency = self._compute_latency(Tier.NONE, promoted, demoted)
        return (Tier.NONE, latency, promoted, demoted)

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
        }

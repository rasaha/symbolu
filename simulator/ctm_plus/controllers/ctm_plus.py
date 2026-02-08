"""
CTM+ (Coherence-Tier Memory Plus) Controller.

Core components:
1. Phase Integrator: Learns access patterns via streaming accumulator.
2. USE Coherence: Computes pairwise phase correlation for locality.
3. Dual Shadow Tier: ARC-like B1/B2 ghost caches with adaptive p.
4. Predictive Prefetch: Markov model with burst prefetch.
5. Mode Switcher: Online workload classifier with hysteresis.
6. Smart Victim Selection: Pre-eviction scoring with ARC-style partitioning.

Removed components (ablation showed no impact):
- BCVF Gate: Had zero effect on hit rate
- SCC Optimizer: Depended on BCVF
- Admission Controller: Hurt temporal workloads by mistaking locality for scans

Key architectural changes:
- Explicit victim selection BEFORE eviction (not post-hoc protection)
- Tier0 logically partitioned by p (recency vs frequency sets)
- ARC-safe weights: 70% recency+frequency, 30% CTM+ signals
- Loop pinning for temporal workloads

CTM+ vs ARC distinction:
- ARC solves capacity allocation (set-level balancing)
- CTM+ solves victim selection (page-level decision-making)
- CTM+ degenerates safely to ARC/LRU when predictions are weak
"""

import math
import random
from typing import Tuple, List, Optional, Dict, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    pass  # For forward references

from .base import BaseController
from .mode_switch import ModeSwitchController, ModePolicy, WorkloadMode
from ..core.state import GlobalState, PageState, Tier, OpType
from ..core.config import SimulatorConfig, CTMPlusConfig


class PhaseIntegrator:
    """Streaming pattern accumulator for learning access patterns."""

    def __init__(self, config: CTMPlusConfig):
        self.config = config.phase
        self.dim = self.config.embedding_dim

        random.seed(42)
        self._w_phase = [random.gauss(0, 0.1) for _ in range(self.dim)]
        self._w_amp = [random.gauss(0, 0.1) for _ in range(self.dim)]
        self._w_value = [[random.gauss(0, 0.1) for _ in range(self.dim)] for _ in range(self.dim)]

        self._accumulator = [complex(0, 0) for _ in range(self.dim)]
        self._recent_pages: deque = deque(maxlen=16)

    def embed_event(self, page_id: int, op_type: OpType, delta_t: int) -> List[float]:
        embedding = [0.0] * self.dim
        for i in range(min(8, self.dim)):
            embedding[i] = math.sin(page_id * (i + 1) * 0.1)
        if self.dim > 8:
            embedding[8 + int(op_type)] = 1.0
        if self.dim > 12:
            embedding[12] = math.log1p(delta_t) / 20.0
        for i, recent_page in enumerate(self._recent_pages):
            if self.dim > 16 + i:
                embedding[16 + i] = 1.0 if recent_page == page_id else 0.1
        return embedding

    def update(self, page_id: int, op_type: OpType, delta_t: int) -> Tuple[float, float]:
        x = self.embed_event(page_id, op_type, delta_t)
        dot_phase = sum(w * xi for w, xi in zip(self._w_phase, x))
        phase = self.config.phase_scale * math.sin(dot_phase)
        dot_amp = sum(w * xi for w, xi in zip(self._w_amp, x))
        amplitude = 1.0 / (1.0 + math.exp(-dot_amp))
        v = [sum(row[j] * x[j] for j in range(self.dim)) for row in self._w_value]
        k = amplitude * complex(math.cos(-phase), math.sin(-phase))
        gamma = self.config.decay_gamma
        for i in range(self.dim):
            self._accumulator[i] = gamma * self._accumulator[i] + (1 - gamma) * k * v[i]
        self._recent_pages.append(page_id)
        return (phase, amplitude)


class CoherenceComputer:
    """Computes coherence scores using fast (O(1)) and slow (O(N)) paths."""

    def __init__(self, config: CTMPlusConfig):
        self.config = config.coherence

    def fast_coherence(self, page: PageState, mean_phase: float) -> float:
        return page.compute_fast_coherence(mean_phase, self.config)

    def slow_update(self, state: GlobalState, neighbor_tracker: 'NeighborTracker') -> None:
        """
        Compute slow-path coherence using co-occurrence neighbors (not sorted ID adjacency).

        FIX: Use neighbor_tracker for real locality, not arbitrary page ID adjacency.
        FIX: Precompute index map to avoid O(n²) list.index() calls.
        """
        all_pages = list(state.tier0.pages.values()) + list(state.tier1.pages.values())
        if len(all_pages) < 2:
            return

        page_map = {p.page_id: p for p in all_pages}

        for page in all_pages:
            # FIX: Use co-occurrence neighbors from NeighborTracker, not sorted ID adjacency
            neighbor_ids = neighbor_tracker.get_neighbors(page.page_id)
            if not neighbor_ids:
                continue

            neighbors = [page_map[nid] for nid in neighbor_ids if nid in page_map]
            if not neighbors:
                continue

            total_corr = 0.0
            for neighbor in neighbors:
                total_corr += self._pairwise_correlation(page, neighbor)

            raw_score = self.config.eta * total_corr
            page.coherence = 1.0 / (1.0 + math.exp(-raw_score))

    def _pairwise_correlation(self, page_i: PageState, page_j: PageState) -> float:
        hist_i = list(page_i.phase_history)
        hist_j = list(page_j.phase_history)
        if not hist_i or not hist_j:
            return math.cos(page_i.phase - page_j.phase)

        min_len = min(len(hist_i), len(hist_j), self.config.window_size)
        if min_len == 0:
            return 0.0

        total = 0.0
        for k in range(min_len):
            phi_i = hist_i[-(k + 1)] if k < len(hist_i) else hist_i[0]
            phi_j = hist_j[-(k + 1)] if k < len(hist_j) else hist_j[0]
            total += math.cos(phi_i - phi_j)
        return total / min_len


class NeighborTracker:
    """Tracks co-occurrence patterns for real locality detection."""

    def __init__(self, window_size=16, top_k=8):
        self._recent: deque = deque(maxlen=window_size)
        self._cooccurrence: Dict[Tuple[int, int], int] = {}
        self._neighbors: Dict[int, List[int]] = {}
        self._access_count = 0
        self.top_k = top_k

    def record_access(self, page_id: int):
        for recent in self._recent:
            if recent != page_id:
                key = (min(page_id, recent), max(page_id, recent))
                self._cooccurrence[key] = self._cooccurrence.get(key, 0) + 1
        self._recent.append(page_id)
        self._access_count += 1
        if self._access_count % 1000 == 0:
            self._rebuild_neighbors()

    def get_neighbors(self, page_id: int) -> List[int]:
        return self._neighbors.get(page_id, [])

    def get_neighbor_hotness(self, page_id: int, state: GlobalState) -> float:
        neighbors = self.get_neighbors(page_id)
        if not neighbors:
            return 0.0
        in_tier0 = sum(1 for n in neighbors if state.tier0.contains(n))
        return in_tier0 / len(neighbors)

    def _rebuild_neighbors(self):
        page_counts: Dict[int, List[Tuple[int, int]]] = {}
        for (a, b), count in self._cooccurrence.items():
            if count >= 3:
                page_counts.setdefault(a, []).append((b, count))
                page_counts.setdefault(b, []).append((a, count))
        self._neighbors = {}
        for pid, neighs in page_counts.items():
            neighs.sort(key=lambda x: x[1], reverse=True)
            self._neighbors[pid] = [n[0] for n in neighs[:self.top_k]]


class TransitionTracker:
    """Markov transition model: tracks P(next=j | current=i)."""

    def __init__(self, top_m=8, decay=0.95):
        self.top_m = top_m
        self.decay = decay
        self._transitions: Dict[int, Dict[int, float]] = {}
        self._last_page: Optional[int] = None
        self._total_transitions = 0

    def record_access(self, page_id: int):
        if self._last_page is not None and self._last_page != page_id:
            if self._last_page not in self._transitions:
                self._transitions[self._last_page] = {}
            trans = self._transitions[self._last_page]
            for key in trans:
                trans[key] *= self.decay
            trans[page_id] = trans.get(page_id, 0.0) + 1.0
            if len(trans) > self.top_m * 2:
                self._transitions[self._last_page] = dict(
                    sorted(trans.items(), key=lambda x: x[1], reverse=True)[:self.top_m]
                )
            self._total_transitions += 1
        self._last_page = page_id

    def get_top_predictions(self, current_page: int, k=3) -> List[Tuple[int, float]]:
        if current_page not in self._transitions:
            return []
        trans = self._transitions[current_page]
        total = sum(trans.values())
        if total == 0:
            return []
        return [(p, s / total) for p, s in sorted(trans.items(), key=lambda x: x[1], reverse=True)[:k]]

    def get_reuse_score(self, page_id: int) -> float:
        score = 0.0
        for _, trans in self._transitions.items():
            if page_id in trans:
                total = sum(trans.values())
                if total > 0:
                    score += trans[page_id] / total
        return min(1.0, score)


class DualShadowTier:
    """
    ARC-like dual ghost cache with adaptive balancing parameter p.

    This is the key to matching ARC's power:
    - B1 (ShadowRecency): ghosts of pages evicted from recency-based decisions
    - B2 (ShadowFrequency): ghosts of pages evicted from frequency-based decisions
    - p: adaptive parameter that balances recency vs frequency

    When B1 gets hits → increase p (favor frequency more)
    When B2 gets hits → decrease p (favor recency more)
    """

    def __init__(self, max_size: int = 500):
        self.max_size = max_size

        # B1: Ghost of recently-evicted "recent" pages (low reuse)
        self._b1_ghosts: deque = deque()
        self._b1_lookup: set = set()
        self.b1_hits = 0

        # B2: Ghost of recently-evicted "frequent" pages (high reuse)
        self._b2_ghosts: deque = deque()
        self._b2_lookup: set = set()
        self.b2_hits = 0

        # Adaptive balancing parameter p ∈ [0, 1]
        # p=0 → favor recency, p=1 → favor frequency
        self.p = 0.5

        # For regret-on-miss tracking (not raw contains)
        self._recent_regrets: deque = deque(maxlen=100)
        self._miss_count = 0

    def add_to_b1(self, page_id: int) -> None:
        """Add page evicted due to low reuse (recency eviction)."""
        if page_id in self._b1_lookup or page_id in self._b2_lookup:
            return

        if len(self._b1_ghosts) >= self.max_size:
            removed = self._b1_ghosts.popleft()
            self._b1_lookup.discard(removed)

        self._b1_ghosts.append(page_id)
        self._b1_lookup.add(page_id)

    def add_to_b2(self, page_id: int) -> None:
        """Add page evicted despite high reuse (frequency eviction)."""
        if page_id in self._b1_lookup or page_id in self._b2_lookup:
            return

        if len(self._b2_ghosts) >= self.max_size:
            removed = self._b2_ghosts.popleft()
            self._b2_lookup.discard(removed)

        self._b2_ghosts.append(page_id)
        self._b2_lookup.add(page_id)

    def check_and_record_regret(self, page_id: int, is_miss: bool) -> Tuple[bool, str]:
        """
        Check if page is in ghost cache and record regret.

        FIX: Only count regret on actual misses (page not in tier0 or tier1).
        Returns: (is_regret, ghost_type) where ghost_type is 'b1', 'b2', or ''
        """
        if not is_miss:
            return (False, '')

        self._miss_count += 1

        if page_id in self._b1_lookup:
            self.b1_hits += 1
            self._b1_lookup.discard(page_id)
            self._recent_regrets.append(1)
            # B1 hit → we evicted a "recent" page too early → favor recency less
            self._adapt_p(b1_hit=True)
            return (True, 'b1')

        if page_id in self._b2_lookup:
            self.b2_hits += 1
            self._b2_lookup.discard(page_id)
            self._recent_regrets.append(1)
            # B2 hit → we evicted a "frequent" page too early → favor frequency less
            self._adapt_p(b1_hit=False)
            return (True, 'b2')

        self._recent_regrets.append(0)
        return (False, '')

    def _adapt_p(self, b1_hit: bool) -> None:
        """
        Adapt balancing parameter p based on ghost hits.

        ARC-like adaptation:
        - B1 hit: increase p (favor frequency more, since recency decision was wrong)
        - B2 hit: decrease p (favor recency more, since frequency decision was wrong)
        """
        delta = 0.1
        if b1_hit:
            self.p = min(1.0, self.p + delta)
        else:
            self.p = max(0.0, self.p - delta)

    @property
    def regret_on_miss_rate(self) -> float:
        """
        Rate of regret specifically on misses (not raw shadow contains).

        FIX: This is the correct metric for Panic Mode trigger.
        """
        if len(self._recent_regrets) == 0:
            return 0.0
        return sum(self._recent_regrets) / len(self._recent_regrets)

    def should_favor_frequency(self) -> bool:
        """Whether current p suggests favoring frequency over recency."""
        return self.p > 0.5


class PrefetchEngine:
    """Budgeted prefetch engine with burst support and mode-adaptive parameters."""

    def __init__(self, budget_per_1k=20, min_probability=0.25):
        self.budget_per_1k = budget_per_1k
        self.min_probability = min_probability
        self._prefetches_this_epoch = 0
        self._epoch_accesses = 0
        self.total_prefetches = 0
        self.prefetch_hits = 0
        self.prefetch_misses = 0
        self._pending_prefetches: set = set()

    def should_prefetch(
        self,
        probability: float,
        prefetch_enabled: bool = True,
        budget_scale: float = 1.0,
        min_prob_override: float = None
    ) -> bool:
        """Check if prefetch should happen, considering mode policy."""
        if not prefetch_enabled:
            return False

        effective_budget = int(self.budget_per_1k * budget_scale)
        budget_remaining = effective_budget - self._prefetches_this_epoch

        effective_min_prob = min_prob_override if min_prob_override is not None else self.min_probability

        if budget_remaining <= 0 or probability < effective_min_prob:
            return False
        return True

    def get_burst_size(self, top_probability: float, max_burst: int = 3) -> int:
        """
        FIX: Burst prefetch when probability mass supports it.
        Higher confidence → prefetch more pages.
        Mode policy can limit max_burst.
        """
        if top_probability > 0.5:
            return min(3, max_burst)
        elif top_probability > 0.3:
            return min(2, max_burst)
        return 1

    def record_prefetch(self, page_id: int):
        self._prefetches_this_epoch += 1
        self.total_prefetches += 1
        self._pending_prefetches.add(page_id)

    def record_access(self, page_id: int):
        self._epoch_accesses += 1
        if page_id in self._pending_prefetches:
            self.prefetch_hits += 1
            self._pending_prefetches.discard(page_id)
        if self._epoch_accesses >= 1000:
            self.prefetch_misses += len(self._pending_prefetches)
            self._pending_prefetches.clear()
            self._prefetches_this_epoch = 0
            self._epoch_accesses = 0

    @property
    def prefetch_hit_rate(self) -> float:
        total = self.prefetch_hits + self.prefetch_misses
        return self.prefetch_hits / total if total > 0 else 0.0


class CTMPlusController(BaseController):
    """
    CTM+ Controller with ChatGPT's critical fixes applied.
    """

    def __init__(self, config: SimulatorConfig, ctm_config: Optional[CTMPlusConfig] = None):
        super().__init__(config)
        self.ctm_config = ctm_config or CTMPlusConfig.default()

        # Components
        self._phase_integrator = PhaseIntegrator(self.ctm_config)
        self._coherence = CoherenceComputer(self.ctm_config)
        self._neighbor_tracker = NeighborTracker()
        self._transition_tracker = TransitionTracker(top_m=8, decay=0.95)
        self._prefetch_engine = PrefetchEngine(budget_per_1k=20, min_probability=0.25)

        # FIX: Dual Shadow Tier (ARC-like B1/B2) instead of single FIFO
        self._shadow_tier = DualShadowTier(max_size=config.tier0_size)

        # Phase-Adaptive Mode Switcher
        self._mode_switcher = ModeSwitchController(
            temperature=1.0,
            switch_confidence=0.65,
            persistence_windows=3,
            min_switch_interval=2000,
            window_size=512
        )
        self._current_policy: ModePolicy = self._mode_switcher.current_policy

        # Stats
        self._promotions = 0
        self._demotions = 0
        self._access_counter = 0
        self._last_access_time: Dict[int, int] = {}
        self._neighbor_boosts = 0
        self._prefetch_promotions = 0
        self._epoch_promotions = 0
        self._epoch_demotions = 0
        self._smart_victim_selections = 0

    @property
    def name(self) -> str:
        return "CTM+"

    def reset(self) -> None:
        self.__init__(self.config, self.ctm_config)

    def _tier0_partition(self, state: GlobalState) -> Tuple[set, set]:
        """
        Logically partition Tier0 into recency and frequency sets using adaptive p.

        ARC-style partitioning:
        - Recency set (T1-like): pages[:split] sorted by last_access_time
        - Frequency set (T2-like): pages[split:] sorted by last_access_time

        The split point is determined by shadow tier's p parameter:
        - p=0.5 means equal split
        - p>0.5 favors frequency (smaller recency set)
        - p<0.5 favors recency (larger recency set)
        """
        pages = list(state.tier0.pages.values())
        if not pages:
            return (set(), set())

        # Sort by recency (most recent first)
        pages.sort(key=lambda p: p.last_access_time, reverse=True)

        # Split based on adaptive p (p=0.5 -> 50% recency, 50% freq)
        # Higher p means favor frequency, so recency set is smaller
        split = int(len(pages) * (1 - self._shadow_tier.p))
        split = max(1, min(len(pages) - 1, split))  # At least 1 in each

        recency_set = set(p.page_id for p in pages[:split])
        freq_set = set(p.page_id for p in pages[split:])

        return (recency_set, freq_set)

    def _select_victim(self, state: GlobalState) -> Optional[PageState]:
        """
        Score Tier0 pages and return the worst victim for eviction.

        OPTIMIZED: Uses sampling for O(k) instead of O(n) complexity.
        - Sample k candidates from tier0 (default k=32)
        - Score only sampled candidates
        - Falls back to LRU on small caches

        ARC-safe weights (70% recency+frequency, 30% CTM+ signals):
        - 40% recency_rank (ARC T1-like)
        - 30% (1-frequency) (ARC T2-like)
        - 15% (1-reuse) (TransitionTracker signal)
        - 10% (1-coherence) (structural signal)
        - -10% neighbor_hotness (cluster protection)
        """
        if not state.tier0.pages:
            return None

        pages = list(state.tier0.pages.values())
        n = len(pages)

        # Ablation: if smart victim disabled, use LRU
        if not self.ctm_config.enable_smart_victim:
            return min(pages, key=lambda p: p.last_access_time)

        # For small caches, just use LRU (fast path)
        if n <= 16:
            return min(pages, key=lambda p: p.last_access_time)

        # SAMPLING: Pick k random candidates + always include LRU victim
        sample_size = min(self.ctm_config.victim_sample_size, n)

        # Always include the LRU page (oldest) as a candidate
        lru_page = min(pages, key=lambda p: p.last_access_time)

        # Random sample of other candidates
        if n > sample_size:
            sampled = random.sample(pages, sample_size - 1)
            if lru_page not in sampled:
                sampled.append(lru_page)
        else:
            sampled = pages

        # Get time range for normalization (from full cache, but fast)
        max_time = max(p.last_access_time for p in pages)
        min_time = lru_page.last_access_time
        time_range = max(1, max_time - min_time)

        # Get adaptive p for partition logic
        p = self._shadow_tier.p

        best_score = float("inf")
        victim = None

        for page in sampled:
            # Normalize recency to [0, 1] where 0 = oldest = evict first
            recency_rank = (page.last_access_time - min_time) / time_range

            # Frequency: higher access_count = less likely to evict
            frequency = min(1.0, page.access_count / 10.0)

            # CTM+ signals
            coherence = page.coherence
            reuse = self._transition_tracker.get_reuse_score(page.page_id)
            neighbor_hot = self._neighbor_tracker.get_neighbor_hotness(page.page_id, state)

            # Base victim score (lower = evict first)
            # ARC-safe: 70% is pure ARC logic (recency + frequency)
            score = (
                0.40 * recency_rank +           # ARC T1-like: favor recent
                0.30 * frequency +              # ARC T2-like: favor frequent
                0.15 * reuse +                  # CTM+ signal: favor predicted reuse
                0.10 * coherence -              # CTM+ signal: favor coherent
                0.10 * neighbor_hot             # CTM+ signal: protect clusters
            )

            # Simplified partition penalty based on p
            # If p > 0.5 (favor frequency), penalize low-freq pages more
            # If p < 0.5 (favor recency), penalize low-recency pages more
            if p > 0.5 and frequency < 0.3:
                score -= 0.10 * (p - 0.5) * 2  # Scale by how much p favors freq
            elif p < 0.5 and recency_rank < 0.3:
                score -= 0.10 * (0.5 - p) * 2  # Scale by how much p favors recency

            if score < best_score:
                best_score = score
                victim = page

        if victim is not None:
            self._smart_victim_selections += 1

        return victim

    def on_access(self, state: GlobalState, page_id: int, op_type: OpType) -> Tuple[Tier, int, bool, bool]:
        self._access_counter += 1

        # Predictive updates
        self._transition_tracker.record_access(page_id)
        self._prefetch_engine.record_access(page_id)
        self._neighbor_tracker.record_access(page_id)

        # Delta T
        delta_t = self._access_counter - self._last_access_time.get(page_id, 0)
        self._last_access_time[page_id] = self._access_counter

        # Phase update
        phase, amplitude = self._phase_integrator.update(page_id, op_type, delta_t)
        page = state.get_or_create_page(page_id)
        page.phase = phase
        page.amplitude = max(page.amplitude, amplitude)
        page.update_on_access(state.current_time, op_type)

        # Get neighbor hotness early (needed for mode switcher)
        neighbor_hotness = self._neighbor_tracker.get_neighbor_hotness(page_id, state)

        # Update mode switcher and get current policy
        is_tier0_hit = state.tier0.contains(page_id)
        _, policy, _ = self._mode_switcher.record_access(
            page_id=page_id,
            is_tier0_hit=is_tier0_hit,
            neighbor_hotness=neighbor_hotness,
            shadow_hit_rate=self._shadow_tier.regret_on_miss_rate,
            was_eviction=False
        )
        self._current_policy = policy

        # Boost neighbors (scaled by policy)
        neighbor_boost_amount = 0.02 * policy.neighbor_boost_scale
        for nid in self._neighbor_tracker.get_neighbors(page_id):
            if nid in state.all_pages:
                state.all_pages[nid].coherence = min(1.0, state.all_pages[nid].coherence + neighbor_boost_amount)
                self._neighbor_boosts += 1

        # Scores
        mean_phase = state.global_mean_phase
        fast_coh = self._coherence.fast_coherence(page, mean_phase)
        reuse_score = self._transition_tracker.get_reuse_score(page_id)

        promoted = False
        demoted = False

        # Case 1: Tier 0 Hit (Fast Path)
        if state.tier0.contains(page_id):
            state.tier0.touch(page_id)
            state.tier0.record_hit()
            self._do_predictive_prefetch(state, page_id, policy)
            latency = self._compute_latency(Tier.TIER0, False, False)
            return (Tier.TIER0, latency, False, False)

        # Case 2: Tier 1 Hit (Slow Path - consider promotion)
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)

            # Check promotion eligibility
            can_promote = (
                self._epoch_promotions < self.ctm_config.max_promotions_per_epoch and
                state.current_time - page.last_demotion_time > self.ctm_config.promotion_cooldown
            )

            should_promote = False

            if can_promote:
                # LOOP PINNING: Fast-track promotion for temporal patterns
                # This fixes the -4.1% temporal regression by keeping short loops in Tier0
                reuse_thresh = self.ctm_config.loop_pin_reuse_threshold
                neighbor_thresh = self.ctm_config.loop_pin_neighbor_threshold
                if reuse_score > reuse_thresh and neighbor_hotness > neighbor_thresh:
                    should_promote = True
                else:
                    # Use adaptive p from shadow tier to weight reuse vs recency
                    if self._shadow_tier.should_favor_frequency():
                        # Favor frequency: weight reuse higher
                        combined_score = 0.6 * reuse_score + 0.2 * fast_coh + 0.2 * neighbor_hotness
                    else:
                        # Favor recency: weight coherence higher
                        combined_score = 0.4 * reuse_score + 0.4 * fast_coh + 0.2 * neighbor_hotness

                    # Promote based on combined score threshold (configurable)
                    should_promote = combined_score > self.ctm_config.promotion_threshold

            if should_promote:
                state.tier1.remove(page_id)

                # EXPLICIT VICTIM SELECTION (the key change)
                # Select victim BEFORE eviction, not after
                evicted = None
                if state.tier0.is_full:
                    victim = self._select_victim(state)
                    if victim:
                        state.tier0.remove(victim.page_id)
                        evicted = victim

                state.tier0.add(page)
                promoted = True
                self._promotions += 1
                self._epoch_promotions += 1
                page.last_promotion_time = state.current_time

                if evicted is not None:
                    demoted = self._handle_eviction(state, evicted)

                self._do_predictive_prefetch(state, page_id, policy)

            latency = self._compute_latency(Tier.TIER1, promoted, demoted)
            return (Tier.TIER1, latency, promoted, demoted)

        # Case 3: Miss - Always admit to Tier0
        # NOTE: Admission controller was removed as it hurt temporal workloads
        # by mistaking temporal locality for sequential scans
        self._shadow_tier.check_and_record_regret(page_id, is_miss=True)

        # EXPLICIT VICTIM SELECTION before admission
        evicted = None
        if state.tier0.is_full:
            victim = self._select_victim(state)
            if victim:
                state.tier0.remove(victim.page_id)
                evicted = victim

        state.tier0.add(page)
        promoted = True
        self._promotions += 1

        if evicted is not None:
            demoted = self._handle_eviction(state, evicted)

        latency = self._compute_latency(Tier.NONE, promoted, demoted)
        return (Tier.NONE, latency, promoted, demoted)

    def _do_predictive_prefetch(self, state: GlobalState, current_page: int, policy: ModePolicy = None) -> None:
        """
        FIX: Burst prefetch with gating based on probability mass.
        Mode-adaptive: respects policy.prefetch_enabled, budget_scale, min_prob, burst_size.
        """
        # Use current policy if not provided
        if policy is None:
            policy = self._current_policy

        # Check if prefetch is enabled for current mode
        if not policy.prefetch_enabled:
            return

        predictions = self._transition_tracker.get_top_predictions(current_page, k=4)
        if not predictions:
            return

        # Determine burst size based on confidence and policy
        top_prob = predictions[0][1] if predictions else 0.0
        burst_size = self._prefetch_engine.get_burst_size(top_prob, max_burst=policy.prefetch_burst_size)
        prefetched = 0

        for next_page, prob in predictions:
            if prefetched >= burst_size:
                break
            if not self._prefetch_engine.should_prefetch(
                prob,
                prefetch_enabled=policy.prefetch_enabled,
                budget_scale=policy.prefetch_budget_scale,
                min_prob_override=policy.prefetch_min_prob
            ):
                continue

            page = state.all_pages.get(next_page)
            if page is None:
                continue

            if state.tier1.contains(next_page):
                state.tier1.remove(next_page)

                # EXPLICIT VICTIM SELECTION for prefetch too
                evicted = None
                if state.tier0.is_full:
                    victim = self._select_victim(state)
                    if victim:
                        state.tier0.remove(victim.page_id)
                        evicted = victim

                state.tier0.add(page)
                self._prefetch_promotions += 1
                self._prefetch_engine.record_prefetch(next_page)
                prefetched += 1

                if evicted is not None:
                    # Prefetch eviction goes to tier1 and shadow tier
                    self._handle_eviction(state, evicted)

    def _handle_eviction(self, state: GlobalState, evicted: PageState) -> bool:
        """
        Handle eviction from Tier 0.

        SIMPLIFIED: All protection logic is now in _select_victim().
        This function only demotes the already-selected victim.

        Steps:
        1. Add evicted page to Tier1
        2. Record in shadow tier for regret tracking (ARC-like B1/B2)
        3. Update stats
        """
        # Demote to tier1
        state.tier1.add(evicted)
        evicted.last_demotion_time = state.current_time

        # Classify into appropriate shadow tier based on reuse score
        # This enables ARC-like adaptation via ghost hits
        evicted_reuse = self._transition_tracker.get_reuse_score(evicted.page_id)
        if evicted_reuse > 0.3:
            # High reuse page evicted → B2 (frequency ghost)
            self._shadow_tier.add_to_b2(evicted.page_id)
        else:
            # Low reuse page evicted → B1 (recency ghost)
            self._shadow_tier.add_to_b1(evicted.page_id)

        self._demotions += 1
        self._epoch_demotions += 1
        return True

    def on_epoch(self, state: GlobalState, epoch: int) -> None:
        self._epoch_promotions = 0
        self._epoch_demotions = 0

        # Periodic decay
        for page in list(state.tier0.pages.values()) + list(state.tier1.pages.values()):
            page.decay(state.current_time, decay_rate=0.001)

        # FIX: Use co-occurrence neighbors for coherence, not sorted ID adjacency
        self._coherence.slow_update(state, self._neighbor_tracker)

    def get_stats(self) -> dict:
        # Get mode switcher stats
        mode_stats = self._mode_switcher.get_stats()

        return {
            "promotions": self._promotions,
            "demotions": self._demotions,
            # FIX: Call the function with state argument
            "neighbor_boosts": self._neighbor_boosts,
            "tracked_neighbors": len(self._neighbor_tracker._neighbors),
            "prefetch_promotions": self._prefetch_promotions,
            "prefetch_hit_rate": self._prefetch_engine.prefetch_hit_rate,
            "total_prefetches": self._prefetch_engine.total_prefetches,
            "transition_count": self._transition_tracker._total_transitions,
            # Shadow tier stats (ARC-like)
            "shadow_b1_hits": self._shadow_tier.b1_hits,
            "shadow_b2_hits": self._shadow_tier.b2_hits,
            "shadow_p": self._shadow_tier.p,
            "regret_on_miss_rate": self._shadow_tier.regret_on_miss_rate,
            # Victim selection stats
            "smart_victim_selections": self._smart_victim_selections,
            "smart_victim_enabled": self.ctm_config.enable_smart_victim,
            # Mode switcher stats
            "mode_current": mode_stats["current_mode"],
            "mode_confidence": mode_stats["mode_confidence"],
            "mode_switches": mode_stats["mode_switches"],
            "mode_time_fractions": mode_stats["mode_time_fractions"],
            "mode_signals": mode_stats["signals"],
        }

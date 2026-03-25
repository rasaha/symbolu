"""
CTM+ (Coherence-Tier Memory Plus) Controller.

Core components:
1. Phase Integrator: Learns access patterns via streaming accumulator.
2. USE Coherence: Computes pairwise phase correlation for locality.
3. Dual Shadow Tier: ARC-like B1/B2 ghost caches with adaptive p.
4. Predictive Prefetch: Markov model with burst prefetch.
5. Mode Switcher: Online workload classifier with hysteresis.
6. Smart Victim Selection: Pre-eviction scoring with ARC-style partitioning.

Gap closure components (state-of-the-art techniques):
7.  IRR Tracker (LIRS): Inter-Reference Recency for scan-resistant eviction.
8.  RefaultTracker (TMO/MGLRU): PID-controlled refault feedback loop.
9.  AdaptiveWeightLearner (CACHEUS/LeCaR): Hedge-algorithm online weight learning.
10. Size-aware eviction (LHD): Hits-per-byte metric for variable-size objects.
11. Lazy promotion (SIEVE): Visited-bit deferred scoring, O(1) per-access overhead.
12. ExternalHintManager (CXL CMM-H): Application hint API for page hotness.
"""

import math
import random
from typing import Tuple, List, Optional, Dict, TYPE_CHECKING
from collections import deque

if TYPE_CHECKING:
    pass  # For forward references

from .base import BaseController
from .mode_switch import ModeSwitchController, ModePolicy, WorkloadMode
from ..core.state import GlobalState, PageState, Tier, OpType, PageHint
from ..core.config import (
    SimulatorConfig, CTMPlusConfig, TenantConfig, TenantPriority, MultiTenancyConfig,
    NUMAConfig, CostTieringConfig,
)


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


class FrequencySketch:
    """
    Top Gap 1: 4-bit Count-Min Sketch for O(1) frequency estimation (W-TinyLFU).

    Tracks approximate access frequency for a population much larger than
    the cache (10x default). Periodically halves all counters to age out
    stale frequencies, preventing long-dead pages from dominating.

    Used by AdmissionController to gate cache admission: new pages must
    beat the eviction victim's frequency to be admitted.
    """

    def __init__(self, capacity: int, depth: int = 4):
        self.width = self._next_power_of_2(max(64, capacity))
        self.depth = depth
        self.table = [[0] * self.width for _ in range(depth)]
        self.size = 0
        self.reset_threshold = capacity * 10
        self._seeds = [0x9E3779B9, 0x517CC1B7, 0x6C62272E, 0x2E1B2138]

    @staticmethod
    def _next_power_of_2(n: int) -> int:
        n -= 1
        n |= n >> 1
        n |= n >> 2
        n |= n >> 4
        n |= n >> 8
        n |= n >> 16
        return n + 1

    def _hash(self, key: int, seed_idx: int) -> int:
        h = key * self._seeds[seed_idx]
        h ^= h >> 16
        return h & (self.width - 1)

    def increment(self, key: int) -> int:
        """Increment frequency for key. Returns estimated frequency."""
        self.size += 1
        if self.size >= self.reset_threshold:
            self._reset()

        min_count = 15  # 4-bit max
        for i in range(self.depth):
            idx = self._hash(key, i)
            self.table[i][idx] = min(15, self.table[i][idx] + 1)
            min_count = min(min_count, self.table[i][idx])
        return min_count

    def estimate(self, key: int) -> int:
        """Estimate frequency for key. O(1)."""
        min_count = 15
        for i in range(self.depth):
            idx = self._hash(key, i)
            min_count = min(min_count, self.table[i][idx])
        return min_count

    def _reset(self):
        """Halve all counters (doorkeeper reset). Ages out stale frequencies."""
        for i in range(self.depth):
            for j in range(self.width):
                self.table[i][j] >>= 1
        self.size >>= 1


class AdmissionController:
    """
    Top Gap 1: S3-FIFO-inspired admission control with frequency gating.

    Prevents one-hit-wonders from polluting the cache:
    - Small queue (10%): New pages enter here on first access
    - Main queue (90%): Pages promoted from small on second access
    - Ghost queue: Tracks recently evicted page IDs for regret detection

    Combined with FrequencySketch for TinyLFU-style admission gating:
    on miss, the new page must have frequency >= victim's frequency to
    be admitted. Otherwise the miss is bypassed (page goes to tier1 only).

    NOTE: The previous admission controller was removed because it confused
    temporal locality with scans. This version is different:
    - Uses frequency sketch (not heuristic thresholds)
    - S3-FIFO naturally handles temporal patterns (ghost queue promotion)
    - Scan resistance via small-queue filter (one-hit-wonders never enter main)
    """

    def __init__(self, config: CTMPlusConfig, tier0_size: int):
        self._config = config.admission
        self._tier0_size = tier0_size

        # Frequency sketch tracks 10x more pages than cache can hold
        sketch_cap = tier0_size * self._config.sketch_capacity_multiplier
        self._sketch = FrequencySketch(sketch_cap, self._config.sketch_depth)

        # S3-FIFO queue tracking (metadata only — actual pages live in tier0/tier1)
        small_cap = max(1, int(tier0_size * self._config.small_queue_ratio))
        ghost_cap = max(1, int(tier0_size * self._config.ghost_queue_ratio))
        self._small: deque = deque()  # page_ids in small queue
        self._small_set: set = set()
        self._small_capacity = small_cap
        self._main_set: set = set()  # page_ids in main queue
        self._ghost: deque = deque()  # page_ids evicted from small
        self._ghost_set: set = set()
        self._ghost_capacity = ghost_cap

        # Stats
        self.admissions = 0
        self.rejections = 0
        self.ghost_hits = 0
        self.small_promotions = 0

    def record_access(self, page_id: int) -> None:
        """Record every access in the frequency sketch."""
        if not self._config.enabled:
            return
        self._sketch.increment(page_id)

        # Mark visited in small queue (for S3-FIFO promotion)
        # We don't need a visited bit since we track in sets

    def should_admit(self, page_id: int, victim_id: Optional[int]) -> bool:
        """
        Decide if a new page should be admitted to tier0 on a miss.

        Returns True if the page should be admitted, False if it should
        be bypassed (goes to tier1 only).
        """
        if not self._config.enabled:
            return True  # Always admit when disabled

        # Ghost hit: page was evicted from small queue but came back → admit to main
        if page_id in self._ghost_set:
            self._ghost_set.discard(page_id)
            # Remove from ghost deque (O(n) but ghost is small)
            try:
                self._ghost.remove(page_id)
            except ValueError:
                pass
            self._main_set.add(page_id)
            self.ghost_hits += 1
            self.admissions += 1
            return True

        # Already in main queue → always re-admit
        if page_id in self._main_set:
            self.admissions += 1
            return True

        # Frequency gate: new page must beat victim's frequency
        if self._config.frequency_gate and victim_id is not None:
            new_freq = self._sketch.estimate(page_id)
            victim_freq = self._sketch.estimate(victim_id)
            if new_freq < victim_freq:
                self.rejections += 1
                return False

        # Add to small queue
        self._add_to_small(page_id)
        self.admissions += 1
        return True

    def _add_to_small(self, page_id: int) -> None:
        """Add page to small queue, evicting oldest if full."""
        if page_id in self._small_set:
            return

        while len(self._small) >= self._small_capacity:
            evicted_id = self._small.popleft()
            self._small_set.discard(evicted_id)

            # Check if page was accessed while in small (frequency > 1)
            freq = self._sketch.estimate(evicted_id)
            if freq > 1:
                # Promoted to main (proved it's not a one-hit-wonder)
                self._main_set.add(evicted_id)
                self.small_promotions += 1
            else:
                # One-hit-wonder → evict to ghost
                self._add_to_ghost(evicted_id)

        self._small.append(page_id)
        self._small_set.add(page_id)

    def _add_to_ghost(self, page_id: int) -> None:
        """Add to ghost queue (ID only, no data)."""
        if len(self._ghost) >= self._ghost_capacity:
            removed = self._ghost.popleft()
            self._ghost_set.discard(removed)
        self._ghost.append(page_id)
        self._ghost_set.add(page_id)

    def on_eviction(self, page_id: int) -> None:
        """Called when a page is evicted from tier0."""
        self._small_set.discard(page_id)
        self._main_set.discard(page_id)
        # Don't add to ghost here — ghost only tracks small-queue evictions

    def get_frequency(self, page_id: int) -> int:
        """Get estimated frequency for a page."""
        return self._sketch.estimate(page_id)


class IRRTracker:
    """
    Gap 1: Inter-Reference Recency tracker (LIRS-inspired).

    Tracks the number of unique pages accessed between two consecutive
    accesses to the same page. IRR is a better predictor than raw recency
    for scan-heavy workloads: a page accessed recently but with huge IRR
    is actually cold.
    """

    def __init__(self, config: CTMPlusConfig):
        self._config = config.irr
        self._access_counter = 0  # Monotonic counter of all accesses
        self._unique_since_last: Dict[int, set] = {}  # page_id -> set of unique pages since last access
        self._last_access_position: Dict[int, int] = {}  # page_id -> access counter at last access
        self._recent_unique: set = set()  # Unique pages in current window
        self._recent_unique_by_pos: Dict[int, set] = {}  # position -> cumulative unique set

    def record_access(self, page_id: int, page: PageState) -> float:
        """Record access and return updated IRR for this page.

        IRR = number of distinct pages accessed between two consecutive
        accesses to the same page. This is the true LIRS metric.
        """
        if not self._config.enabled:
            return page.irr

        self._access_counter += 1

        if page_id in self._last_access_position:
            # Count unique pages seen since this page's last access
            last_pos = self._last_access_position[page_id]
            if page_id in self._unique_since_last:
                raw_irr = len(self._unique_since_last[page_id])
            else:
                raw_irr = self._access_counter - last_pos  # fallback

            # EMA smoothing to handle bursty patterns
            alpha = self._config.irr_ema_alpha
            if page.irr == float('inf'):
                page.irr = min(raw_irr, self._config.max_irr)
            else:
                page.irr = alpha * raw_irr + (1 - alpha) * page.irr
            page.irr = min(page.irr, self._config.max_irr)

        # Reset unique tracking for this page (start counting again)
        self._unique_since_last[page_id] = set()

        # Add this page to all other pages' unique-since-last sets
        for pid in self._last_access_position:
            if pid != page_id and pid in self._unique_since_last:
                self._unique_since_last[pid].add(page_id)

        self._last_access_position[page_id] = self._access_counter

        # Periodic cleanup: remove stale entries for pages not seen recently
        if self._access_counter % 5000 == 0:
            cutoff = self._access_counter - 10000
            stale = [pid for pid, pos in self._last_access_position.items() if pos < cutoff]
            for pid in stale:
                self._last_access_position.pop(pid, None)
                self._unique_since_last.pop(pid, None)

        return page.irr

    def get_normalized_irr(self, page: PageState, cache_size: int) -> float:
        """Normalize IRR to [0, 1] where 1 = coldest (highest IRR)."""
        if page.irr == float('inf'):
            return 1.0
        return min(1.0, page.irr / max(cache_size, 1))


class RefaultTracker:
    """
    Gap 3: Refault/pressure-based control (TMO/MGLRU-inspired).

    Tracks whether evicted pages are immediately re-fetched (refaults).
    Uses a PID controller to adjust eviction aggressiveness based on
    measured refault rate vs target.

    Key insight from TMO: measure actual performance impact (refault rate)
    rather than relying on heuristic thresholds.
    """

    def __init__(self, config: CTMPlusConfig):
        self._config = config.refault
        self._refault_window: deque = deque(maxlen=config.refault.refault_window)
        self._evicted_recently: Dict[int, int] = {}  # page_id -> eviction_time
        self._eviction_time_limit = config.refault.refault_window * 2

        # PID state
        self._integral = 0.0
        self._prev_error = 0.0
        self._pressure_adjustment = 0.0  # Output: [-1, 1] adjustment to eviction

        # Stats
        self.total_refaults = 0
        self.total_evictions_tracked = 0

    def record_eviction(self, page_id: int, time: int) -> None:
        """Record that a page was evicted."""
        if not self._config.enabled:
            return
        self._evicted_recently[page_id] = time
        self.total_evictions_tracked += 1

        # Prune old entries
        if len(self._evicted_recently) > self._eviction_time_limit:
            cutoff = time - self._eviction_time_limit
            self._evicted_recently = {
                pid: t for pid, t in self._evicted_recently.items() if t > cutoff
            }

    def check_refault(self, page_id: int) -> bool:
        """Check if accessing this page constitutes a refault (evicted then re-fetched)."""
        if not self._config.enabled:
            return False

        is_refault = page_id in self._evicted_recently
        if is_refault:
            self.total_refaults += 1
            del self._evicted_recently[page_id]

        self._refault_window.append(1 if is_refault else 0)
        return is_refault

    def update_pid(self) -> float:
        """Run PID controller and return pressure adjustment."""
        if not self._config.enabled or len(self._refault_window) < 10:
            return 0.0

        current_rate = sum(self._refault_window) / len(self._refault_window)
        error = current_rate - self._config.target_refault_rate

        # PID terms
        p_term = self._config.kp * error
        self._integral += error
        self._integral = max(-5.0, min(5.0, self._integral))  # Anti-windup
        i_term = self._config.ki * self._integral
        d_term = self._config.kd * (error - self._prev_error)
        self._prev_error = error

        self._pressure_adjustment = max(-1.0, min(1.0, p_term + i_term + d_term))
        return self._pressure_adjustment

    @property
    def refault_rate(self) -> float:
        if not self._refault_window:
            return 0.0
        return sum(self._refault_window) / len(self._refault_window)

    @property
    def pressure(self) -> float:
        """Current pressure adjustment [-1, 1]. Positive = too many refaults."""
        return self._pressure_adjustment


class AdaptiveWeightLearner:
    """
    Gap 4: Online weight learning via Hedge algorithm (CACHEUS/LeCaR-inspired).

    Replaces fixed victim scoring weights (40/30/15/10/-10) with learnable
    weights updated from hit/miss outcomes. Uses multiplicative weights
    (Hedge/EXP3) with theoretical regret guarantees.

    Each "expert" is a scoring dimension:
    0: recency, 1: frequency, 2: reuse, 3: coherence, 4: neighbor_hotness
    """

    def __init__(self, config: CTMPlusConfig):
        self._config = config.adaptive_weights
        n = self._config.num_experts

        # Initialize weights uniformly (will be normalized to sum to 1)
        self._log_weights = [0.0] * n  # Log-space for numerical stability
        self._weights = [1.0 / n] * n  # Probability distribution

        # Track eviction records: list of (features, outcome) pairs
        # Features are recorded at eviction time; outcome is filled in later
        # when we know if it was a refault or not.
        self._pending_evictions: Dict[int, List[float]] = {}  # page_id -> features
        self._completed_records: deque = deque(maxlen=config.adaptive_weights.update_interval)
        self._eviction_count = 0

        # Stats
        self.weight_updates = 0

    def get_weights(self) -> List[float]:
        """Return current scoring weights scaled to sum to ~1.0."""
        if not self._config.enabled:
            return [0.40, 0.30, 0.15, 0.10, 0.10]
        # Scale weights so they sum to 1.05 (matching original total magnitude)
        total = sum(abs(w) for w in self._weights)
        if total == 0:
            return [0.20] * 5
        scale = 1.05 / total
        return [w * scale for w in self._weights]

    def record_eviction(self, page_id: int, features: List[float]) -> None:
        """Record feature vector of evicted page. Outcome determined later."""
        if not self._config.enabled:
            return
        self._pending_evictions[page_id] = features
        self._eviction_count += 1

        # Limit pending to prevent unbounded growth
        if len(self._pending_evictions) > self._config.update_interval * 4:
            # Assume old pending evictions were good (no refault observed)
            oldest = list(self._pending_evictions.keys())[:len(self._pending_evictions) // 2]
            for pid in oldest:
                feats = self._pending_evictions.pop(pid)
                self._completed_records.append((feats, 0.0))

    def record_refault(self, page_id: int) -> None:
        """Record that an evicted page was refaulted (bad eviction)."""
        if not self._config.enabled:
            return
        if page_id in self._pending_evictions:
            features = self._pending_evictions.pop(page_id)
            self._completed_records.append((features, 1.0))
        # If not in pending, the eviction was too old to track — ignore

    def record_no_refault(self, page_id: int) -> None:
        """Record that a pending eviction expired without refault (good eviction)."""
        if not self._config.enabled:
            return
        if page_id in self._pending_evictions:
            features = self._pending_evictions.pop(page_id)
            self._completed_records.append((features, 0.0))

    def maybe_update(self) -> None:
        """Flush old pending evictions as good outcomes and trigger weight update."""
        if not self._config.enabled:
            return

        # Flush pending evictions older than update_interval as "no refault" (good)
        # If a page hasn't been refaulted by now, the eviction was probably fine
        if len(self._pending_evictions) > self._config.update_interval // 2:
            flush_count = len(self._pending_evictions) // 2
            oldest = list(self._pending_evictions.keys())[:flush_count]
            for pid in oldest:
                feats = self._pending_evictions.pop(pid)
                self._completed_records.append((feats, 0.0))

        if len(self._completed_records) >= self._config.update_interval:
            self._update_weights()

    def _update_weights(self) -> None:
        """Hedge algorithm weight update from paired (features, outcome) records."""
        if not self._completed_records:
            return

        n = self._config.num_experts
        eta = self._config.learning_rate

        # Expert indices: 0=recency, 1=frequency, 2=reuse, 3=coherence, 4=neighbor_hot
        # Expert 4 (neighbor_hot) is SUBTRACTED in scoring, so its sign is inverted.
        # For loss computation: high neighbor_hot + refault means the expert's
        # protection signal was correct but we evicted anyway → penalize.
        sign = [1.0, 1.0, 1.0, 1.0, -1.0]  # Sign of each expert in score formula

        expert_losses = [0.0] * n
        count = len(self._completed_records)

        for features, outcome in self._completed_records:
            for j in range(min(n, len(features))):
                if sign[j] > 0:
                    # Positive expert: low feature → evict. Refault means we were wrong.
                    expert_losses[j] += outcome * (1.0 - features[j])
                else:
                    # Negative expert (neighbor_hot): high feature → protect.
                    # Refault of protected page = expert correctly warned us.
                    # Refault of unprotected page = expert failed to warn.
                    expert_losses[j] += outcome * features[j]

        if count > 0:
            expert_losses = [l / count for l in expert_losses]

        # Multiplicative weight update (Hedge)
        for j in range(n):
            self._log_weights[j] -= eta * expert_losses[j]

        # Normalize to probability distribution
        max_lw = max(self._log_weights)
        exp_weights = [math.exp(lw - max_lw) for lw in self._log_weights]
        total = sum(exp_weights)
        self._weights = [max(self._config.min_weight, ew / total) for ew in exp_weights]

        # Re-normalize after flooring
        total = sum(self._weights)
        self._weights = [w / total for w in self._weights]

        self.weight_updates += 1
        self._completed_records.clear()


class ExternalHintManager:
    """
    Gap 6: External hint API (CXL CMM-H Host Hints inspired).

    Provides an interface for applications to signal page hotness or access
    patterns to the controller. Hints influence victim scoring and prefetch.
    """

    def __init__(self, config: CTMPlusConfig):
        self._config = config.external_hints
        self._hints: Dict[int, Tuple[PageHint, float]] = {}  # page_id -> (hint, priority)
        self._willneed_queue: deque = deque(maxlen=64)  # Pages to prefetch

    def set_hint(self, page_id: int, hint: PageHint, priority: float = 0.5) -> None:
        """Set a hint for a page. Called by application/external system."""
        if not self._config.enabled:
            return
        self._hints[page_id] = (hint, max(0.0, min(1.0, priority)))
        if hint == PageHint.WILLNEED:
            self._willneed_queue.append(page_id)

    def clear_hint(self, page_id: int) -> None:
        """Clear hint for a page."""
        self._hints.pop(page_id, None)

    def get_hint(self, page_id: int) -> Tuple[PageHint, float]:
        """Get hint for a page."""
        return self._hints.get(page_id, (PageHint.NONE, 0.0))

    def get_score_adjustment(self, page_id: int) -> float:
        """
        Get victim score adjustment based on hint.

        Positive = harder to evict, Negative = easier to evict.
        """
        if not self._config.enabled:
            return 0.0

        hint, priority = self.get_hint(page_id)
        if hint == PageHint.HOT:
            return self._config.hot_boost * priority
        elif hint == PageHint.COLD:
            return -self._config.cold_penalty * priority
        elif hint == PageHint.PINNED:
            return 10.0  # Effectively unevictable
        elif hint == PageHint.DONTNEED:
            return -self._config.dontneed_evict_priority * priority
        return 0.0

    def is_pinned(self, page_id: int) -> bool:
        """Check if page is pinned (cannot be evicted)."""
        if not self._config.enabled or not self._config.pin_protection:
            return False
        hint, _ = self.get_hint(page_id)
        return hint == PageHint.PINNED

    def pop_willneed_pages(self) -> List[int]:
        """Get and clear pending WILLNEED prefetch requests."""
        if not self._config.enabled or not self._config.willneed_prefetch:
            return []
        pages = list(self._willneed_queue)
        self._willneed_queue.clear()
        return pages

    def apply_to_page(self, page: PageState) -> None:
        """Apply hint metadata to a PageState object."""
        hint, priority = self.get_hint(page.page_id)
        page.hint = hint
        page.hint_priority = priority


class TenantManager:
    """
    Multi-tenancy and QoS isolation manager (CacheLib/DAMON-inspired).

    Provides:
    - Per-tenant tier0 quota enforcement (min/max share)
    - Priority-weighted victim scoring (low-priority tenants evicted first)
    - Noisy neighbor protection (hard cap on per-tenant tier0 usage)
    - Per-tenant metrics (hit rate, occupancy, promotions/demotions)

    Design principles:
    - Zero overhead when disabled (all methods short-circuit)
    - O(1) per-access overhead when enabled (dict lookups only)
    - Quota enforcement is soft on min, hard on max
    """

    def __init__(self, config: MultiTenancyConfig, tier0_capacity: int):
        self._config = config
        self._tier0_capacity = tier0_capacity

        # Registered tenants: tenant_id -> TenantConfig
        self._tenants: Dict[str, TenantConfig] = {}

        # Always register the default tenant
        self._tenants[config.default_tenant_id] = TenantConfig(
            tenant_id=config.default_tenant_id,
            priority=TenantPriority.NORMAL,
        )

        # Per-tenant metrics
        self._tenant_accesses: Dict[str, int] = {}
        self._tenant_hits: Dict[str, int] = {}
        self._tenant_promotions: Dict[str, int] = {}
        self._tenant_demotions: Dict[str, int] = {}
        self._tenant_evictions: Dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def register_tenant(self, config: TenantConfig) -> None:
        """Register a tenant with QoS parameters."""
        self._tenants[config.tenant_id] = config

    def unregister_tenant(self, tenant_id: str) -> None:
        """Unregister a tenant. Its pages become default tenant."""
        self._tenants.pop(tenant_id, None)

    def get_tenant_config(self, tenant_id: str) -> TenantConfig:
        """Get config for a tenant, falling back to default."""
        return self._tenants.get(tenant_id, self._tenants[self._config.default_tenant_id])

    def assign_page_tenant(self, page: PageState, tenant_id: Optional[str] = None) -> None:
        """Assign a page to a tenant."""
        if not self._config.enabled:
            return
        page.tenant_id = tenant_id if tenant_id is not None else self._config.default_tenant_id

    def record_access(self, tenant_id: str, is_hit: bool) -> None:
        """Record an access for per-tenant metrics."""
        if not self._config.enabled:
            return
        self._tenant_accesses[tenant_id] = self._tenant_accesses.get(tenant_id, 0) + 1
        if is_hit:
            self._tenant_hits[tenant_id] = self._tenant_hits.get(tenant_id, 0) + 1

    def record_promotion(self, tenant_id: str) -> None:
        if not self._config.enabled:
            return
        self._tenant_promotions[tenant_id] = self._tenant_promotions.get(tenant_id, 0) + 1

    def record_demotion(self, tenant_id: str) -> None:
        if not self._config.enabled:
            return
        self._tenant_demotions[tenant_id] = self._tenant_demotions.get(tenant_id, 0) + 1

    def record_eviction(self, tenant_id: str) -> None:
        if not self._config.enabled:
            return
        self._tenant_evictions[tenant_id] = self._tenant_evictions.get(tenant_id, 0) + 1

    def get_tenant_tier0_share(self, tenant_id: str, state: GlobalState) -> float:
        """Get current tier0 share for a tenant as fraction [0, 1]."""
        count = state.tier0.get_tenant_page_count(tenant_id)
        if self._tier0_capacity == 0:
            return 0.0
        return count / self._tier0_capacity

    def is_over_quota(self, tenant_id: str, state: GlobalState) -> bool:
        """Check if tenant exceeds its max tier0 share."""
        tc = self.get_tenant_config(tenant_id)
        return self.get_tenant_tier0_share(tenant_id, state) > tc.max_tier0_share

    def is_under_quota(self, tenant_id: str, state: GlobalState) -> bool:
        """Check if tenant is below its guaranteed min tier0 share."""
        tc = self.get_tenant_config(tenant_id)
        if tc.min_tier0_share == 0.0:
            return False
        return self.get_tenant_tier0_share(tenant_id, state) < tc.min_tier0_share

    def should_admit(self, tenant_id: str, state: GlobalState) -> bool:
        """
        Check if a tenant's page should be admitted to tier0.

        Returns False if the tenant is already at its hard max cap,
        UNLESS no other tenant has slack (prevents deadlock).
        """
        if not self._config.enabled:
            return True

        tc = self.get_tenant_config(tenant_id)
        current_share = self.get_tenant_tier0_share(tenant_id, state)

        # Under hard cap → always allow
        if current_share < tc.max_tier0_share:
            return True

        # At or over cap → only allow if tier0 is not full (no eviction needed)
        if not state.tier0.is_full:
            return True

        # Over cap and tier0 full → check if we can evict from another tenant
        # to make room. This prevents starvation when all tenants are at cap.
        for other_tid, other_tc in self._tenants.items():
            if other_tid == tenant_id:
                continue
            other_share = self.get_tenant_tier0_share(other_tid, state)
            if other_share > other_tc.min_tier0_share and other_tc.priority < tc.priority:
                return True  # Can evict from lower-priority tenant

        return False

    def get_victim_score_adjustment(self, page: PageState, state: GlobalState) -> float:
        """
        Compute QoS-based victim score adjustment for a page.

        Returns a value added to the victim score:
        - Positive = harder to evict (protect high-priority, under-quota tenants)
        - Negative = easier to evict (penalize low-priority, over-quota tenants)
        """
        if not self._config.enabled:
            return 0.0

        tc = self.get_tenant_config(page.tenant_id)
        adjustment = 0.0

        # Priority-based protection: higher priority → harder to evict
        # BACKGROUND=0, LOW=1, NORMAL=2, HIGH=3, CRITICAL=4
        # Normalized: (priority - NORMAL) / CRITICAL gives [-0.5, 0, 0.25, 0.5]
        priority_delta = (int(tc.priority) - int(TenantPriority.NORMAL)) / int(TenantPriority.CRITICAL)
        adjustment += self._config.priority_weight_scale * priority_delta

        # Over-quota penalty: tenants exceeding max share get evicted first
        current_share = self.get_tenant_tier0_share(page.tenant_id, state)
        if tc.max_tier0_share < 1.0 and current_share > tc.max_tier0_share:
            overshoot = (current_share - tc.max_tier0_share) / max(0.01, 1.0 - tc.max_tier0_share)
            adjustment -= self._config.over_quota_penalty * min(1.0, overshoot)

        # Under-quota protection: tenants below min share are protected
        if tc.min_tier0_share > 0.0 and current_share < tc.min_tier0_share:
            undershoot = (tc.min_tier0_share - current_share) / max(0.01, tc.min_tier0_share)
            adjustment += self._config.under_quota_boost * min(1.0, undershoot)

        return adjustment

    def get_preferred_victim_tenant(self, state: GlobalState) -> Optional[str]:
        """
        Get the tenant ID that should preferentially have pages evicted.

        Returns the over-quota tenant with the lowest priority, or None.
        Used as a hint for victim selection to bias sampling.
        """
        if not self._config.enabled:
            return None

        best_victim_tenant = None
        best_score = float('inf')  # Lower = more evictable

        for tid, tc in self._tenants.items():
            share = self.get_tenant_tier0_share(tid, state)
            if share <= 0:
                continue
            # Score: lower priority + higher over-quota = more evictable
            score = int(tc.priority) - (max(0, share - tc.max_tier0_share) * 10)
            if score < best_score:
                best_score = score
                best_victim_tenant = tid

        return best_victim_tenant

    def get_stats(self) -> Dict:
        """Get per-tenant metrics."""
        tenant_stats = {}
        for tid in self._tenants:
            accesses = self._tenant_accesses.get(tid, 0)
            hits = self._tenant_hits.get(tid, 0)
            tenant_stats[tid] = {
                "priority": self._tenants[tid].priority.name,
                "min_share": self._tenants[tid].min_tier0_share,
                "max_share": self._tenants[tid].max_tier0_share,
                "accesses": accesses,
                "hits": hits,
                "hit_rate": hits / accesses if accesses > 0 else 0.0,
                "promotions": self._tenant_promotions.get(tid, 0),
                "demotions": self._tenant_demotions.get(tid, 0),
                "evictions": self._tenant_evictions.get(tid, 0),
            }
        return tenant_stats


class CostModel:
    """
    Cost-aware tiering model (CacheLib / CXL CMM-H inspired).

    Computes cost-benefit ratios for promotion decisions and cost-adjusted
    victim scores for eviction. Answers: "Is keeping this page in expensive
    tier0 (DRAM) worth the cost vs. cheap tier1 (NAND)?"

    Key formulas:
        benefit(page) = expected_hits * latency_saved_per_hit
        cost(page)    = tier0_cost - tier1_cost + write_amp_penalty
        value(page)   = benefit / cost  (higher = more worth keeping in tier0)

    Zero overhead when disabled.
    """

    def __init__(self, config: CostTieringConfig, sim_config: SimulatorConfig):
        self._config = config
        self._sim_config = sim_config

        # Precompute latency benefit of tier0 vs tier1 (nanoseconds saved per hit)
        self._latency_benefit = sim_config.tier1_latency_ns - sim_config.tier0_latency_ns

        # Precompute cost differential
        self._tier_cost_delta = config.tier0_cost_per_page - config.tier1_cost_per_page
        self._movement_cost = config.promotion_cost + config.demotion_cost

        # Stats
        self._promotions_gated = 0
        self._promotions_allowed = 0
        self._cost_influenced = 0

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def compute_page_value(self, page: PageState, current_time: int) -> float:
        """
        Compute the cost-benefit value of keeping a page in tier0.

        Returns a normalized value in [0, ~1+] where:
        - > 1.0 = page is clearly worth keeping in tier0
        - ~0.5  = borderline
        - < 0.2 = page is wasting expensive DRAM

        Uses access_count and time-in-tier to estimate future hit rate,
        then compares latency benefit vs. tier cost differential.
        """
        if not self._config.enabled:
            return 0.5  # Neutral

        # Estimate hit rate: accesses / time_in_tier (avoid div by zero)
        time_in_tier = max(1, current_time - max(page.last_promotion_time, 1))
        hit_rate = page.access_count / time_in_tier

        # Expected future benefit over horizon
        expected_hits = hit_rate * self._config.benefit_horizon_accesses
        benefit = expected_hits * self._latency_benefit

        # Cost of keeping in tier0 for the horizon
        cost = (
            self._tier_cost_delta * self._config.benefit_horizon_accesses
            + self._movement_cost
        )

        # Write amplification: write-heavy pages are expensive in NAND.
        # Keeping them in DRAM avoids NAND wear → they get bonus value.
        if page.write_count > 0 and page.access_count > 0:
            write_ratio = page.write_count / page.access_count
            # Write-heavy pages get a value boost (cheaper to keep in DRAM)
            benefit += (
                write_ratio * self._config.write_amp_weight
                * self._config.benefit_horizon_accesses
            )

        # Normalize: value = benefit / cost, clamped to reasonable range
        if cost <= 0:
            return 1.0
        value = benefit / cost
        return max(0.0, min(2.0, value))

    def should_promote(self, page: PageState, current_time: int) -> bool:
        """
        Cost-benefit gate for promotion decisions.

        Returns True if the page's expected value in tier0 justifies
        the cost of promotion. Always returns True when disabled.
        """
        if not self._config.enabled:
            return True

        value = self.compute_page_value(page, current_time)
        if value >= self._config.min_cost_benefit_ratio:
            self._promotions_allowed += 1
            return True
        else:
            self._promotions_gated += 1
            return False

    def get_victim_score_adjustment(self, page: PageState, current_time: int) -> float:
        """
        Cost-based victim score adjustment.

        Low-value pages (not worth tier0 cost) get a negative adjustment
        → easier to evict. High-value pages get a positive adjustment
        → harder to evict.

        Returns positive = protect, negative = easier to evict.
        """
        if not self._config.enabled:
            return 0.0

        value = self.compute_page_value(page, current_time)

        # Center around 0.5 (neutral value), scale by weight
        # value > 0.5 → protect, value < 0.5 → penalize
        adjustment = self._config.cost_eviction_weight * (value - 0.5)
        if adjustment != 0.0:
            self._cost_influenced += 1
        return adjustment

    def get_stats(self) -> Dict:
        """Get cost model metrics."""
        total = self._promotions_allowed + self._promotions_gated
        return {
            "promotions_allowed": self._promotions_allowed,
            "promotions_gated": self._promotions_gated,
            "gate_rate": self._promotions_gated / total if total > 0 else 0.0,
            "cost_influenced_evictions": self._cost_influenced,
            "tier0_cost": self._config.tier0_cost_per_page,
            "tier1_cost": self._config.tier1_cost_per_page,
            "latency_benefit_ns": self._latency_benefit,
        }


class NUMAManager:
    """
    NUMA-aware memory placement manager (Linux DAMON / CXL-inspired).

    Models a multi-socket system where cross-node memory accesses incur
    additional latency. Provides:

    - Node affinity tracking: Each page tracks which NUMA node accesses it
      most frequently and sets a preferred_node accordingly.
    - Locality-aware latency: Access latency includes a distance penalty
      when the requester's node differs from the page's placement node.
    - NUMA-aware victim scoring: Pages placed on a remote node (relative to
      their preferred accessor) are penalized → evicted first.
    - Migration decisions: When a page's accessor node doesn't match its
      current placement node, it may be migrated closer.

    Zero overhead when disabled (all methods short-circuit).
    """

    def __init__(self, config: NUMAConfig):
        self._config = config
        self._distance_matrix = config.get_distance_matrix()

        # Per-node metrics
        self._node_accesses: Dict[int, int] = {}
        self._node_local_hits: Dict[int, int] = {}
        self._node_remote_hits: Dict[int, int] = {}
        self._migrations: int = 0

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def get_distance(self, src_node: int, dst_node: int) -> float:
        """Get distance between two NUMA nodes. 0.0 = local, 1.0 = max remote."""
        if not self._config.enabled or src_node == dst_node:
            return 0.0
        n = self._config.num_nodes
        if 0 <= src_node < n and 0 <= dst_node < n:
            return self._distance_matrix[src_node][dst_node]
        return 1.0

    def compute_latency_penalty(self, accessor_node: int, page_node: int) -> int:
        """
        Compute extra latency (ns) for cross-node access.

        Returns 0 for local access, remote_penalty_ns * distance for remote.
        """
        if not self._config.enabled:
            return 0
        dist = self.get_distance(accessor_node, page_node)
        return int(self._config.remote_penalty_ns * dist)

    def record_access(self, page: PageState, accessor_node: int) -> None:
        """
        Record an access to a page from a specific NUMA node.

        Updates the page's per-node access counts and preferred_node.
        """
        if not self._config.enabled:
            return

        page.last_accessor_node = accessor_node

        # Update per-node access count
        page.node_access_counts[accessor_node] = page.node_access_counts.get(accessor_node, 0) + 1

        # Update preferred node (node with most accesses)
        if page.node_access_counts.get(accessor_node, 0) >= page.node_access_counts.get(page.preferred_node, 0):
            page.preferred_node = accessor_node

        # Per-node metrics
        self._node_accesses[accessor_node] = self._node_accesses.get(accessor_node, 0) + 1
        if accessor_node == page.numa_node:
            self._node_local_hits[accessor_node] = self._node_local_hits.get(accessor_node, 0) + 1
        else:
            self._node_remote_hits[accessor_node] = self._node_remote_hits.get(accessor_node, 0) + 1

    def assign_node(self, page: PageState, accessor_node: int) -> None:
        """Assign a new page to the accessor's NUMA node (initial placement)."""
        if not self._config.enabled:
            return
        page.numa_node = accessor_node
        page.preferred_node = accessor_node
        page.last_accessor_node = accessor_node

    def should_migrate(self, page: PageState, current_time: int) -> bool:
        """
        Decide whether a page should be migrated to its preferred node.

        Conditions:
        1. Page's current node != preferred node
        2. Affinity is strong enough (preferred node has > threshold of accesses)
        3. Cooldown has elapsed since last migration
        """
        if not self._config.enabled:
            return False

        if page.numa_node == page.preferred_node:
            return False

        if current_time - page.last_migration_time < self._config.migration_cooldown:
            return False

        # Compute affinity score: fraction of accesses from preferred node
        total = sum(page.node_access_counts.values())
        if total == 0:
            return False
        preferred_count = page.node_access_counts.get(page.preferred_node, 0)
        affinity = preferred_count / total

        return affinity >= self._config.migration_threshold

    def migrate_page(self, page: PageState, target_node: int, current_time: int) -> None:
        """
        Migrate a page to a different NUMA node.

        Updates the page's numa_node and records the migration time.
        Note: The caller is responsible for updating TierState.numa_occupancy.
        """
        if not self._config.enabled:
            return
        page.numa_node = target_node
        page.last_migration_time = current_time
        self._migrations += 1

    def get_victim_score_adjustment(self, page: PageState, accessor_node: int) -> float:
        """
        Compute NUMA-based victim score adjustment.

        - Pages local to their preferred accessor get a boost (harder to evict)
        - Pages remote from their preferred accessor get a penalty (easier to evict)

        Returns positive = protect, negative = easier to evict.
        """
        if not self._config.enabled:
            return 0.0

        dist_from_preferred = self.get_distance(page.numa_node, page.preferred_node)

        if dist_from_preferred == 0.0:
            # Page is on its preferred node → protect it
            return self._config.local_preference_weight
        else:
            # Page is remote from its preferred accessor → easier to evict
            return -self._config.remote_eviction_penalty * dist_from_preferred

    def get_stats(self) -> Dict:
        """Get NUMA-related metrics."""
        per_node = {}
        for nid in range(self._config.num_nodes):
            accesses = self._node_accesses.get(nid, 0)
            local = self._node_local_hits.get(nid, 0)
            remote = self._node_remote_hits.get(nid, 0)
            per_node[nid] = {
                "accesses": accesses,
                "local_hits": local,
                "remote_hits": remote,
                "local_rate": local / accesses if accesses > 0 else 0.0,
            }
        return {
            "migrations": self._migrations,
            "per_node": per_node,
        }


class CTMPlusController(BaseController):
    """
    CTM+ Controller with all state-of-the-art gap closures implemented.

    Gap closures:
    - IRR Tracking (LIRS): Scan-resistant inter-reference recency
    - Refault/Pressure Control (TMO/MGLRU): PID-based eviction feedback
    - Adaptive Weight Learning (CACHEUS/LeCaR): Hedge-algorithm online weights
    - Size-Aware Eviction (LHD): Hits-per-byte for variable-size objects
    - Lazy Promotion (SIEVE): Visited-bit deferred scoring
    - External Hint API (CXL CMM-H): Application-provided page hints
    - Multi-Tenancy & QoS Isolation: Per-tenant quotas and priority-weighted eviction
    - NUMA-Aware Placement: Locality-aware latency, victim scoring, and migration
    """

    def __init__(self, config: SimulatorConfig, ctm_config: Optional[CTMPlusConfig] = None):
        super().__init__(config)
        self.ctm_config = ctm_config or CTMPlusConfig.default()

        # Core components
        self._phase_integrator = PhaseIntegrator(self.ctm_config)
        self._coherence = CoherenceComputer(self.ctm_config)
        self._neighbor_tracker = NeighborTracker()
        self._transition_tracker = TransitionTracker(top_m=8, decay=0.95)
        self._prefetch_engine = PrefetchEngine(budget_per_1k=20, min_probability=0.25)
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

        # === Gap closure components ===
        self._admission = AdmissionController(self.ctm_config, config.tier0_size)
        self._irr_tracker = IRRTracker(self.ctm_config)
        self._refault_tracker = RefaultTracker(self.ctm_config)
        self._weight_learner = AdaptiveWeightLearner(self.ctm_config)
        self._hint_manager = ExternalHintManager(self.ctm_config)
        self._tenant_manager = TenantManager(self.ctm_config.multi_tenancy, config.tier0_size)
        self._numa_manager = NUMAManager(self.ctm_config.numa)
        self._cost_model = CostModel(self.ctm_config.cost_tiering, config)

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
        self._sieve_evictions = 0
        self._irr_influenced = 0
        self._hint_influenced = 0
        self._refault_promotions = 0
        self._numa_influenced = 0
        self._cost_influenced = 0
        self._page_sizes: Dict[int, int] = {}  # External size overrides

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

        Integrates all gap closures:
        - SIEVE scan (Gap 5): Try visited-bit eviction first for O(1) amortized
        - IRR (Gap 1): Use inter-reference recency instead of raw recency for scans
        - Adaptive weights (Gap 4): Learned weights via Hedge algorithm
        - Size-aware (Gap 2): Hits-per-byte for variable-size objects
        - Hints (Gap 6): Application hints influence scoring
        - Pressure (Gap 3): PID adjustment from refault rate
        """
        if not state.tier0.pages:
            return None

        pages = list(state.tier0.pages.values())
        n = len(pages)

        # Ablation: if smart victim disabled, use LRU
        if not self.ctm_config.enable_smart_victim:
            return min(pages, key=lambda p: p.last_access_time)

        # === Gap 5: SIEVE-style lazy eviction (try first for low overhead) ===
        if self.ctm_config.lazy_promotion.enabled and n > 16:
            sieve_victim = self._sieve_scan(state)
            if sieve_victim is not None:
                self._sieve_evictions += 1
                return sieve_victim

        # For small caches, just use LRU (fast path)
        if n <= 16:
            return min(pages, key=lambda p: p.last_access_time)

        # SAMPLING: Pick k random candidates + always include LRU victim
        sample_size = min(self.ctm_config.victim_sample_size, n)
        lru_page = min(pages, key=lambda p: p.last_access_time)

        if n > sample_size:
            sampled = random.sample(pages, sample_size - 1)
            if lru_page not in sampled:
                sampled.append(lru_page)
        else:
            sampled = pages

        # Get time range for normalization
        max_time = max(p.last_access_time for p in pages)
        min_time = lru_page.last_access_time
        time_range = max(1, max_time - min_time)

        # Get adaptive p for partition logic
        p_val = self._shadow_tier.p

        # === Gap 4: Get learned weights (or fixed fallback) ===
        weights = self._weight_learner.get_weights()

        # === Gap 3: Get pressure adjustment from PID controller ===
        pressure = self._refault_tracker.pressure if self.ctm_config.refault.enabled else 0.0

        best_score = float("inf")
        victim = None

        for page in sampled:
            # === Gap 6: Skip pinned pages ===
            if self._hint_manager.is_pinned(page.page_id):
                continue

            # Normalize recency to [0, 1] where 0 = oldest = evict first
            recency_rank = (page.last_access_time - min_time) / time_range

            # Frequency: higher access_count = less likely to evict
            frequency = min(1.0, page.access_count / 10.0)

            # CTM+ signals
            coherence = page.coherence
            reuse = self._transition_tracker.get_reuse_score(page.page_id)
            neighbor_hot = self._neighbor_tracker.get_neighbor_hotness(page.page_id, state)

            # === Gap 1: IRR-adjusted recency ===
            # If IRR is high, the page is cold despite recent access (scan pattern)
            if self.ctm_config.irr.enabled:
                irr_cold = self._irr_tracker.get_normalized_irr(page, state.tier0.capacity)
                # Blend recency with IRR: high IRR reduces effective recency
                effective_recency = recency_rank * (1.0 - self.ctm_config.irr.irr_weight * irr_cold)
                self._irr_influenced += 1
            else:
                effective_recency = recency_rank

            # Base victim score with adaptive weights (lower = evict first)
            score = (
                weights[0] * effective_recency +  # Recency (IRR-adjusted)
                weights[1] * frequency +           # Frequency
                weights[2] * reuse +               # Predicted reuse
                weights[3] * coherence -           # Structural coherence
                weights[4] * neighbor_hot          # Cluster protection
            )

            # === Gap 2: Size-aware adjustment (LHD hits-per-byte) ===
            # LHD: hit_density = expected_hits / size. Larger pages must justify
            # their space with proportionally more value. Smaller pages get a bonus.
            if self.ctm_config.size_aware.enabled:
                size_ratio = page.size_bytes / self.ctm_config.size_aware.default_page_size
                if size_ratio != 1.0:
                    # Divide score by size ratio: large pages penalized, small pages boosted
                    score /= (1.0 + self.ctm_config.size_aware.size_weight * (size_ratio - 1.0))

            # === Gap 6: Hint-based score adjustment ===
            hint_adj = self._hint_manager.get_score_adjustment(page.page_id)
            if hint_adj != 0.0:
                score += hint_adj
                self._hint_influenced += 1

            # === Gap 3: Pressure-based adjustment ===
            # When pressure is high (too many refaults), be more conservative
            # (raise scores to keep more pages). When low, be more aggressive.
            if pressure > 0.1:
                score += 0.05 * pressure  # Protect more pages when refault rate is high
            elif pressure < -0.1:
                score += 0.05 * pressure  # Evict more aggressively when rate is low

            # === Multi-tenancy: QoS-based victim score adjustment ===
            tenant_adj = self._tenant_manager.get_victim_score_adjustment(page, state)
            if tenant_adj != 0.0:
                score += tenant_adj

            # === NUMA: Locality-based victim score adjustment ===
            # Pages remote from their preferred accessor are easier to evict
            numa_adj = self._numa_manager.get_victim_score_adjustment(page, page.preferred_node)
            if numa_adj != 0.0:
                score += numa_adj
                self._numa_influenced += 1

            # === Cost-aware: Low-value pages easier to evict ===
            cost_adj = self._cost_model.get_victim_score_adjustment(page, state.current_time)
            if cost_adj != 0.0:
                score += cost_adj
                self._cost_influenced += 1

            # Partition penalty based on adaptive p
            if p_val > 0.5 and frequency < 0.3:
                score -= 0.10 * (p_val - 0.5) * 2
            elif p_val < 0.5 and recency_rank < 0.3:
                score -= 0.10 * (0.5 - p_val) * 2

            if score < best_score:
                best_score = score
                victim = page

        if victim is not None:
            self._smart_victim_selections += 1

            # === Gap 4: Record features for weight learning ===
            if self.ctm_config.adaptive_weights.enabled:
                recency_rank = (victim.last_access_time - min_time) / time_range
                frequency = min(1.0, victim.access_count / 10.0)
                reuse = self._transition_tracker.get_reuse_score(victim.page_id)
                coherence = victim.coherence
                neighbor_hot = self._neighbor_tracker.get_neighbor_hotness(victim.page_id, state)
                self._weight_learner.record_eviction(victim.page_id, [
                    recency_rank, frequency, reuse, coherence, neighbor_hot
                ])

        return victim

    def _sieve_scan(self, state: GlobalState) -> Optional[PageState]:
        """
        Gap 5: SIEVE-style lazy eviction scan.

        Scan from LRU end: if visited=True, clear it and skip (retain in place).
        If visited=False, evict. This gives new pages a chance to prove themselves.

        Key insight from SIEVE: retained objects stay in original position (no reinsertion),
        naturally preserving age ordering.
        """
        scan_limit = self.ctm_config.lazy_promotion.sieve_scan_limit
        access_order = state.tier0.access_order
        scanned = 0

        for page_id in list(access_order):
            if scanned >= scan_limit:
                break

            page = state.tier0.pages.get(page_id)
            if page is None:
                continue

            # Skip pinned pages
            if self._hint_manager.is_pinned(page_id):
                continue

            scanned += 1

            if page.visited:
                # Clear visited bit, give second chance (lazy promotion)
                page.visited = False
            else:
                # Not visited since last scan → evict
                return page

        return None  # All scanned pages were visited; fall back to full scoring

    # === Gap 6: Public hint API ===
    def set_page_hint(self, page_id: int, hint: PageHint, priority: float = 0.5) -> None:
        """External API: Set application hint for a page."""
        self._hint_manager.set_hint(page_id, hint, priority)

    def clear_page_hint(self, page_id: int) -> None:
        """External API: Clear hint for a page."""
        self._hint_manager.clear_hint(page_id)

    def set_page_size(self, page_id: int, size_bytes: int) -> None:
        """External API: Set variable size for a page (for size-aware eviction)."""
        # Will be applied when page is next accessed/created
        self._page_sizes[page_id] = size_bytes

    # === Multi-tenancy public API ===
    def register_tenant(self, config: TenantConfig) -> None:
        """External API: Register a tenant with QoS parameters."""
        self._tenant_manager.register_tenant(config)

    def unregister_tenant(self, tenant_id: str) -> None:
        """External API: Unregister a tenant."""
        self._tenant_manager.unregister_tenant(tenant_id)

    def get_tenant_stats(self) -> Dict:
        """External API: Get per-tenant metrics."""
        return self._tenant_manager.get_stats()

    # === Cost-aware tiering public API ===
    def get_cost_stats(self) -> Dict:
        """External API: Get cost model metrics."""
        return self._cost_model.get_stats()

    # === NUMA public API ===
    def get_numa_stats(self) -> Dict:
        """External API: Get NUMA-related metrics."""
        return self._numa_manager.get_stats()

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
        tenant_id: Optional[str] = None,
        numa_node: Optional[int] = None,
    ) -> Tuple[Tier, int, bool, bool]:
        self._access_counter += 1

        # Resolve NUMA node: use provided value or default to 0
        accessor_node = numa_node if numa_node is not None else 0

        # Predictive updates
        self._transition_tracker.record_access(page_id)
        self._prefetch_engine.record_access(page_id)
        self._neighbor_tracker.record_access(page_id)

        # Top Gap 1: Record access in frequency sketch
        self._admission.record_access(page_id)

        # Delta T
        delta_t = self._access_counter - self._last_access_time.get(page_id, 0)
        self._last_access_time[page_id] = self._access_counter

        # Phase update
        phase, amplitude = self._phase_integrator.update(page_id, op_type, delta_t)
        page = state.get_or_create_page(page_id)
        page.phase = phase
        page.amplitude = max(page.amplitude, amplitude)

        # === Multi-tenancy: Assign tenant to page ===
        if tenant_id is not None:
            self._tenant_manager.assign_page_tenant(page, tenant_id)

        # === NUMA: Record access and track node affinity ===
        self._numa_manager.record_access(page, accessor_node)
        page.update_on_access(state.current_time, op_type)

        # === Gap 1: IRR tracking ===
        self._irr_tracker.record_access(page_id, page)

        # === Gap 2: Apply variable page size if set ===
        if hasattr(self, '_page_sizes') and page_id in self._page_sizes:
            page.size_bytes = self._page_sizes[page_id]

        # === Gap 6: Apply external hints ===
        self._hint_manager.apply_to_page(page)

        # === Gap 3: Check refault on tier1 hits and true misses ===
        # In CTM+, evicted pages go to tier1 (demotion, not discard).
        # A "refault" = a recently-demoted page is accessed in tier1,
        # meaning it should have stayed in tier0. Also check true misses
        # (page not in either tier) for pages evicted from tier1 too.
        is_tier1_hit = state.tier1.contains(page_id) and not state.tier0.contains(page_id)
        is_true_miss = not state.tier0.contains(page_id) and not state.tier1.contains(page_id)
        should_check_refault = is_tier1_hit or is_true_miss
        is_refault = self._refault_tracker.check_refault(page_id) if should_check_refault else False
        if is_refault and self.ctm_config.adaptive_weights.enabled:
            self._weight_learner.record_refault(page_id)

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
            self._tenant_manager.record_access(page.tenant_id, is_hit=True)

            # === NUMA: Migrate page closer to accessor if beneficial ===
            if self._numa_manager.should_migrate(page, state.current_time):
                old_node = page.numa_node
                target_node = page.preferred_node
                state.tier0.numa_occupancy[old_node] = max(0, state.tier0.numa_occupancy.get(old_node, 0) - 1)
                self._numa_manager.migrate_page(page, target_node, state.current_time)
                state.tier0.numa_occupancy[target_node] = state.tier0.numa_occupancy.get(target_node, 0) + 1

            self._do_predictive_prefetch(state, page_id, policy, accessor_node=accessor_node)
            latency = self._compute_latency(Tier.TIER0, False, False)
            # === NUMA: Add cross-node latency penalty ===
            latency += self._numa_manager.compute_latency_penalty(accessor_node, page.numa_node)
            return (Tier.TIER0, latency, False, False)

        # Case 2: Tier 1 Hit (Slow Path - consider promotion)
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)
            self._tenant_manager.record_access(page.tenant_id, is_hit=False)

            # Check shadow tier regret: page in B1/B2 means we demoted it too early
            self._shadow_tier.check_and_record_regret(page_id, is_miss=True)

            # Check promotion eligibility (includes tenant quota + cost-benefit gate)
            tenant_can_admit = self._tenant_manager.should_admit(page.tenant_id, state)
            cost_allows = self._cost_model.should_promote(page, state.current_time)
            can_promote = (
                self._epoch_promotions < self.ctm_config.max_promotions_per_epoch and
                state.current_time - page.last_demotion_time > self.ctm_config.promotion_cooldown and
                tenant_can_admit and
                cost_allows
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

                # === NUMA: Place promoted page on accessor's node ===
                self._numa_manager.assign_node(page, accessor_node)

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
                self._tenant_manager.record_promotion(page.tenant_id)
                page.last_promotion_time = state.current_time

                if evicted is not None:
                    demoted = self._handle_eviction(state, evicted)

                self._do_predictive_prefetch(state, page_id, policy, accessor_node=accessor_node)

            latency = self._compute_latency(Tier.TIER1, promoted, demoted)
            # === NUMA: Add cross-node latency penalty ===
            latency += self._numa_manager.compute_latency_penalty(accessor_node, page.numa_node)
            return (Tier.TIER1, latency, promoted, demoted)

        # Case 3: Miss
        self._tenant_manager.record_access(page.tenant_id, is_hit=False)
        self._shadow_tier.check_and_record_regret(page_id, is_miss=True)

        # === Gap 3: Refault-boosted admission ===
        if is_refault:
            self._refault_promotions += 1

        # === Top Gap 1: Admission control (TinyLFU + S3-FIFO) ===
        # Select victim first so we can compare frequencies
        victim = None
        if state.tier0.is_full:
            victim = self._select_victim(state)

        # Gate admission: new page must beat victim's frequency (unless refault)
        # Also gate by tenant quota (multi-tenancy)
        admit = True
        if not is_refault:  # Refaulted pages always re-admitted
            admit = self._admission.should_admit(
                page_id, victim.page_id if victim else None
            )
            # Multi-tenancy: check tenant quota
            if admit and not self._tenant_manager.should_admit(page.tenant_id, state):
                admit = False
            # Cost-aware: check cost-benefit ratio for new pages
            if admit and not self._cost_model.should_promote(page, state.current_time):
                admit = False

        if admit:
            # === NUMA: Place new page on accessor's node ===
            self._numa_manager.assign_node(page, accessor_node)

            evicted = None
            if victim and state.tier0.is_full:
                state.tier0.remove(victim.page_id)
                evicted = victim
                self._admission.on_eviction(victim.page_id)

            state.tier0.add(page)
            promoted = True
            self._promotions += 1
            self._tenant_manager.record_promotion(page.tenant_id)

            if evicted is not None:
                demoted = self._handle_eviction(state, evicted)
        else:
            # Admission rejected: page goes to tier1 only (bypass tier0)
            self._numa_manager.assign_node(page, accessor_node)
            state.tier1.add(page)
            promoted = False

        # === Gap 6: Process WILLNEED prefetch hints ===
        willneed_pages = self._hint_manager.pop_willneed_pages()
        for wn_page_id in willneed_pages:
            if wn_page_id != page_id and state.tier1.contains(wn_page_id):
                self._do_hint_prefetch(state, wn_page_id, accessor_node=accessor_node)

        latency = self._compute_latency(Tier.NONE, promoted, demoted)
        # === NUMA: No extra penalty on miss (already at tier1 latency) ===
        return (Tier.NONE, latency, promoted, demoted)

    def _do_predictive_prefetch(
        self, state: GlobalState, current_page: int,
        policy: ModePolicy = None, accessor_node: int = 0,
    ) -> None:
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

                # NUMA: Place prefetched page on accessor's node
                self._numa_manager.assign_node(page, accessor_node)
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

        Integrates:
        - Gap 3: Record eviction for refault tracking
        - Gap 4: Record non-refault outcome for weight learning
        - Gap 5: Clear visited bit on eviction (SIEVE)
        - Multi-tenancy: Record per-tenant demotion/eviction
        """
        # Demote to tier1
        state.tier1.add(evicted)
        evicted.last_demotion_time = state.current_time
        evicted.visited = False  # Gap 5: Reset visited bit

        # Multi-tenancy: record tenant eviction
        self._tenant_manager.record_demotion(evicted.tenant_id)
        self._tenant_manager.record_eviction(evicted.tenant_id)

        # === Gap 3: Record eviction for refault tracking ===
        self._refault_tracker.record_eviction(evicted.page_id, state.current_time)

        # Top Gap 1: Notify admission controller of eviction
        self._admission.on_eviction(evicted.page_id)

        # Gap 4: Outcome will be determined later — if page is refaulted,
        # record_refault() is called in on_access. If not, pending evictions
        # expire via timeout in record_eviction().

        # Classify into appropriate shadow tier based on reuse score
        evicted_reuse = self._transition_tracker.get_reuse_score(evicted.page_id)
        if evicted_reuse > 0.3:
            self._shadow_tier.add_to_b2(evicted.page_id)
        else:
            self._shadow_tier.add_to_b1(evicted.page_id)

        self._demotions += 1
        self._epoch_demotions += 1
        return True

    def _do_hint_prefetch(self, state: GlobalState, page_id: int, accessor_node: int = 0) -> None:
        """Gap 6: Prefetch a page due to WILLNEED hint."""
        page = state.all_pages.get(page_id)
        if page is None or not state.tier1.contains(page_id):
            return

        state.tier1.remove(page_id)
        evicted = None
        if state.tier0.is_full:
            victim = self._select_victim(state)
            if victim:
                state.tier0.remove(victim.page_id)
                evicted = victim

        # NUMA: Place prefetched page on accessor's node
        self._numa_manager.assign_node(page, accessor_node)
        state.tier0.add(page)
        self._prefetch_promotions += 1
        self._prefetch_engine.record_prefetch(page_id)

        if evicted is not None:
            self._handle_eviction(state, evicted)

    def on_epoch(self, state: GlobalState, epoch: int) -> None:
        self._epoch_promotions = 0
        self._epoch_demotions = 0

        # Periodic decay
        for page in list(state.tier0.pages.values()) + list(state.tier1.pages.values()):
            page.decay(state.current_time, decay_rate=0.001)

        # Use co-occurrence neighbors for coherence
        self._coherence.slow_update(state, self._neighbor_tracker)

        # === Gap 3: Run PID controller for pressure-based eviction adjustment ===
        self._refault_tracker.update_pid()

        # === Gap 4: Flush old pending evictions and check for weight update ===
        self._weight_learner.maybe_update()

    def get_stats(self) -> dict:
        mode_stats = self._mode_switcher.get_stats()

        stats = {
            "promotions": self._promotions,
            "demotions": self._demotions,
            "neighbor_boosts": self._neighbor_boosts,
            "tracked_neighbors": len(self._neighbor_tracker._neighbors),
            "prefetch_promotions": self._prefetch_promotions,
            "prefetch_hit_rate": self._prefetch_engine.prefetch_hit_rate,
            "total_prefetches": self._prefetch_engine.total_prefetches,
            "transition_count": self._transition_tracker._total_transitions,
            # Shadow tier stats
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
            # === Gap closure stats ===
            # Top Gap 1: Admission control
            "admission_enabled": self.ctm_config.admission.enabled,
            "admission_admissions": self._admission.admissions,
            "admission_rejections": self._admission.rejections,
            "admission_ghost_hits": self._admission.ghost_hits,
            "admission_small_promotions": self._admission.small_promotions,
            # Gap 1: IRR Tracking
            "irr_enabled": self.ctm_config.irr.enabled,
            "irr_influenced_decisions": self._irr_influenced,
            # Gap 2: Size-aware eviction
            "size_aware_enabled": self.ctm_config.size_aware.enabled,
            # Gap 3: Refault/pressure control
            "refault_enabled": self.ctm_config.refault.enabled,
            "refault_rate": self._refault_tracker.refault_rate,
            "refault_pressure": self._refault_tracker.pressure,
            "refault_total": self._refault_tracker.total_refaults,
            "refault_promotions": self._refault_promotions,
            # Gap 4: Adaptive weight learning
            "adaptive_weights_enabled": self.ctm_config.adaptive_weights.enabled,
            "learned_weights": self._weight_learner.get_weights(),
            "weight_updates": self._weight_learner.weight_updates,
            # Gap 5: SIEVE lazy promotion
            "sieve_enabled": self.ctm_config.lazy_promotion.enabled,
            "sieve_evictions": self._sieve_evictions,
            # Gap 6: External hints
            "hints_enabled": self.ctm_config.external_hints.enabled,
            "hint_influenced_decisions": self._hint_influenced,
            "active_hints": len(self._hint_manager._hints),
            # Multi-tenancy & QoS isolation
            "multi_tenancy_enabled": self.ctm_config.multi_tenancy.enabled,
            "tenant_stats": self._tenant_manager.get_stats() if self.ctm_config.multi_tenancy.enabled else {},
            # NUMA-aware placement
            "numa_enabled": self.ctm_config.numa.enabled,
            "numa_influenced_decisions": self._numa_influenced,
            "numa_stats": self._numa_manager.get_stats() if self.ctm_config.numa.enabled else {},
            # Cost-aware tiering
            "cost_tiering_enabled": self.ctm_config.cost_tiering.enabled,
            "cost_influenced_decisions": self._cost_influenced,
            "cost_stats": self._cost_model.get_stats() if self.ctm_config.cost_tiering.enabled else {},
        }
        return stats

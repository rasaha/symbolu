"""
Phase-Adaptive CTM Mode Switcher.

This module implements online workload classification and policy multiplexing
for CTM+. It detects workload phases and switches between operating regimes
to optimize for different access patterns.

Modes:
- SCAN: Streaming scans that pollute cache
- LOOP: Temporal repeating cycles
- HOTSET: Stable hot working set
- CLUSTER: Correlated page clusters
- MIXED: Unknown/default

Key design principles:
- Uses cheap online signals (EMAs, rolling hashes)
- Hysteresis + confidence to prevent thrashing
- Changes parameters, not algorithms
"""

import math
from enum import Enum, auto
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from collections import deque


class WorkloadMode(Enum):
    """Discrete workload modes that CTM+ can operate in."""
    SCAN = auto()      # Streaming/sequential scan
    LOOP = auto()      # Temporal repeating pattern
    HOTSET = auto()    # Stable hot working set
    CLUSTER = auto()   # Correlated page clusters
    MIXED = auto()     # Unknown/default


@dataclass
class ModePolicy:
    """
    Per-mode parameter configuration.

    These knobs adjust CTM+ behavior without changing the algorithm.
    """
    # Admission controller
    admission_threshold_scale: float = 1.0  # Multiplier for admission probability
    scan_penalty: float = 0.3               # Penalty for sequential access
    bypass_boost: float = 0.0               # Extra bypass probability

    # Prefetch engine
    prefetch_enabled: bool = True
    prefetch_budget_scale: float = 1.0      # Multiplier for prefetch budget
    prefetch_min_prob: float = 0.25         # Min probability to trigger prefetch
    prefetch_burst_size: int = 2            # Max pages per prefetch burst

    # Shadow tier / regret
    regret_threshold: float = 0.15          # Threshold for panic mode
    force_promote_on_regret: bool = True    # Force tier0 on ghost hit

    # BCVF gate
    bcvf_threshold_scale: float = 1.0       # Multiplier for promote threshold
    bcvf_demote_strictness: float = 1.0     # Higher = harder to demote

    # Neighbor/cluster
    neighbor_boost_scale: float = 1.0       # Scale for neighbor coherence boost
    neighbor_protection: float = 0.6        # Min neighbor_hotness to protect

    # Eviction priority weights
    evict_heat_weight: float = 0.5          # Weight for heat in eviction
    evict_reuse_weight: float = 0.5         # Weight for reuse in eviction


# Pre-defined policies for each mode
MODE_POLICIES: Dict[WorkloadMode, ModePolicy] = {
    WorkloadMode.SCAN: ModePolicy(
        # Goal: resist admissions, avoid prefetch, protect hotset
        admission_threshold_scale=0.5,   # Tighter admission
        scan_penalty=0.5,                # Increase scan penalty
        bypass_boost=0.3,                # More bypasses to tier1
        prefetch_enabled=False,          # Prefetch OFF
        prefetch_budget_scale=0.0,
        regret_threshold=0.25,           # Don't panic easily
        force_promote_on_regret=False,
        bcvf_threshold_scale=1.3,        # Harder to promote
        bcvf_demote_strictness=0.7,      # Easier to demote (evict polluters)
        neighbor_boost_scale=0.5,
        neighbor_protection=0.7,         # Protect hot pages more
        evict_heat_weight=0.3,
        evict_reuse_weight=0.7,          # Favor keeping high-reuse
    ),

    WorkloadMode.LOOP: ModePolicy(
        # Goal: stop temporal regression, embrace the loop
        admission_threshold_scale=1.5,   # More open admission
        scan_penalty=0.1,                # Reduce scan penalty (loops look sequential)
        bypass_boost=-0.2,               # Fewer bypasses
        prefetch_enabled=True,           # Prefetch ON
        prefetch_budget_scale=1.5,
        prefetch_min_prob=0.2,           # Lower threshold
        prefetch_burst_size=2,
        regret_threshold=0.08,           # Aggressive regret detection
        force_promote_on_regret=True,    # Ghost hit => immediate promote
        bcvf_threshold_scale=0.8,        # Easier to promote
        bcvf_demote_strictness=1.0,
        neighbor_boost_scale=1.0,
        neighbor_protection=0.5,
        evict_heat_weight=0.5,
        evict_reuse_weight=0.5,
    ),

    WorkloadMode.HOTSET: ModePolicy(
        # Goal: lock hot pages, reduce churn
        admission_threshold_scale=1.0,   # Moderate admission
        scan_penalty=0.3,
        bypass_boost=0.0,
        prefetch_enabled=True,
        prefetch_budget_scale=0.5,       # Minimal prefetch
        prefetch_min_prob=0.35,
        prefetch_burst_size=1,
        regret_threshold=0.12,
        force_promote_on_regret=True,
        bcvf_threshold_scale=0.9,
        bcvf_demote_strictness=1.4,      # Harder to demote (protect hot pages)
        neighbor_boost_scale=1.2,
        neighbor_protection=0.5,
        evict_heat_weight=0.7,           # Prioritize keeping high-heat
        evict_reuse_weight=0.3,
    ),

    WorkloadMode.CLUSTER: ModePolicy(
        # Goal: keep correlated sets together
        admission_threshold_scale=1.0,
        scan_penalty=0.3,
        bypass_boost=0.0,
        prefetch_enabled=True,           # Prefetch neighbors
        prefetch_budget_scale=1.3,
        prefetch_min_prob=0.2,
        prefetch_burst_size=3,           # Burst prefetch for clusters
        regret_threshold=0.12,
        force_promote_on_regret=True,
        bcvf_threshold_scale=1.0,
        bcvf_demote_strictness=1.0,
        neighbor_boost_scale=1.5,        # Strong neighbor boost
        neighbor_protection=0.5,         # Cluster-aware eviction
        evict_heat_weight=0.4,
        evict_reuse_weight=0.6,
    ),

    WorkloadMode.MIXED: ModePolicy(
        # Goal: safe default, balanced behavior
        admission_threshold_scale=1.0,
        scan_penalty=0.3,
        bypass_boost=0.0,
        prefetch_enabled=True,
        prefetch_budget_scale=1.0,
        prefetch_min_prob=0.25,
        prefetch_burst_size=2,
        regret_threshold=0.15,
        force_promote_on_regret=True,
        bcvf_threshold_scale=1.0,
        bcvf_demote_strictness=1.0,
        neighbor_boost_scale=1.0,
        neighbor_protection=0.6,
        evict_heat_weight=0.5,
        evict_reuse_weight=0.5,
    ),
}


class WorkloadSignals:
    """
    Computes online workload signals for mode classification.

    All signals are computed incrementally over a sliding window
    using exponential moving averages (EMAs) for efficiency.
    """

    def __init__(self, window_size: int = 1024, ema_alpha: float = 0.02):
        self.window_size = window_size
        self.ema_alpha = ema_alpha

        # Recent access history
        self._recent_pages: deque = deque(maxlen=window_size)
        self._unique_in_window: set = set()

        # For loop detection: rolling hash of recent k pages
        self._loop_k = 16
        self._recent_hashes: deque = deque(maxlen=64)
        self._hash_counts: Dict[int, int] = {}

        # EMA signals
        self._seq_run_ema = 0.0          # Sequentiality
        self._unique_ratio_ema = 0.5     # Unique pages ratio
        self._loop_rate_ema = 0.0        # Loop detection rate
        self._hot_concentration_ema = 0.0 # Hot page concentration
        self._tier0_turnover_ema = 0.0   # Eviction rate
        self._neighbor_hit_ratio_ema = 0.0 # Neighbor locality
        self._reuse_delay_ema = 500.0    # Avg reuse distance

        # Page tracking
        self._last_seen: Dict[int, int] = {}
        self._access_count = 0
        self._hit_counts: Dict[int, int] = {}
        self._window_evictions = 0

        # For hot concentration
        self._window_hits = 0
        self._top_m = 100  # Top M pages for concentration

    def record_access(
        self,
        page_id: int,
        is_tier0_hit: bool,
        neighbor_hotness: float,
        was_eviction: bool = False
    ) -> None:
        """Record an access and update all signals."""
        self._access_count += 1
        alpha = self.ema_alpha

        # === Sequentiality score ===
        if self._recent_pages:
            last_page = self._recent_pages[-1]
            is_sequential = abs(page_id - last_page) <= 2
            self._seq_run_ema = alpha * (1.0 if is_sequential else 0.0) + (1 - alpha) * self._seq_run_ema

        # === Unique ratio ===
        # Remove old pages from unique set
        if len(self._recent_pages) >= self.window_size:
            old_page = self._recent_pages[0]
            # Only remove if it's not elsewhere in window (approximate)
            if self._recent_pages.count(old_page) <= 1:
                self._unique_in_window.discard(old_page)

        self._recent_pages.append(page_id)
        self._unique_in_window.add(page_id)

        current_unique_ratio = len(self._unique_in_window) / min(len(self._recent_pages), self.window_size)
        self._unique_ratio_ema = alpha * current_unique_ratio + (1 - alpha) * self._unique_ratio_ema

        # === Reuse delay ===
        if page_id in self._last_seen:
            delay = self._access_count - self._last_seen[page_id]
            self._reuse_delay_ema = alpha * delay + (1 - alpha) * self._reuse_delay_ema
        self._last_seen[page_id] = self._access_count

        # === Loop detection via rolling hash ===
        if len(self._recent_pages) >= self._loop_k:
            # Compute hash of last k pages
            recent_k = list(self._recent_pages)[-self._loop_k:]
            h = self._compute_hash(recent_k)

            # Check if we've seen this pattern recently
            loop_hit = h in self._hash_counts and self._hash_counts[h] > 0
            self._loop_rate_ema = alpha * (1.0 if loop_hit else 0.0) + (1 - alpha) * self._loop_rate_ema

            # Update hash counts (decay old ones)
            if len(self._recent_hashes) >= 64:
                old_hash = self._recent_hashes[0]
                if old_hash in self._hash_counts:
                    self._hash_counts[old_hash] = max(0, self._hash_counts[old_hash] - 1)

            self._recent_hashes.append(h)
            self._hash_counts[h] = self._hash_counts.get(h, 0) + 1

        # === Hot concentration ===
        if is_tier0_hit:
            self._window_hits += 1
            self._hit_counts[page_id] = self._hit_counts.get(page_id, 0) + 1

            # Compute concentration periodically
            if self._access_count % 100 == 0 and self._window_hits > 0:
                # Get top M pages by hits
                sorted_hits = sorted(self._hit_counts.values(), reverse=True)
                top_m_hits = sum(sorted_hits[:self._top_m])
                concentration = top_m_hits / self._window_hits
                self._hot_concentration_ema = alpha * 10 * concentration + (1 - alpha * 10) * self._hot_concentration_ema

        # === Tier0 turnover ===
        if was_eviction:
            self._window_evictions += 1

        if self._access_count % 100 == 0:
            turnover = self._window_evictions / 100.0
            self._tier0_turnover_ema = alpha * 5 * turnover + (1 - alpha * 5) * self._tier0_turnover_ema
            self._window_evictions = 0

        # === Neighbor hit ratio ===
        self._neighbor_hit_ratio_ema = alpha * neighbor_hotness + (1 - alpha) * self._neighbor_hit_ratio_ema

        # Periodic cleanup of hit counts
        if self._access_count % 10000 == 0:
            # Decay hit counts
            self._hit_counts = {k: v // 2 for k, v in self._hit_counts.items() if v > 1}
            self._window_hits = self._window_hits // 2

    def _compute_hash(self, pages: List[int]) -> int:
        """Compute a simple rolling hash for loop detection."""
        h = 0
        for i, p in enumerate(pages):
            h ^= (p * (i + 1) * 31) & 0xFFFFFFFF
        return h

    @property
    def seq_run(self) -> float:
        """Sequentiality score [0, 1]."""
        return self._seq_run_ema

    @property
    def unique_ratio(self) -> float:
        """Unique pages ratio [0, 1]."""
        return self._unique_ratio_ema

    @property
    def loop_rate(self) -> float:
        """Loop detection rate [0, 1]."""
        return self._loop_rate_ema

    @property
    def hot_concentration(self) -> float:
        """Hot page concentration [0, 1]."""
        return self._hot_concentration_ema

    @property
    def tier0_turnover(self) -> float:
        """Tier0 eviction rate (normalized)."""
        return self._tier0_turnover_ema

    @property
    def neighbor_hit_ratio(self) -> float:
        """Average neighbor hotness [0, 1]."""
        return self._neighbor_hit_ratio_ema

    @property
    def reuse_delay(self) -> float:
        """Average reuse delay in accesses."""
        return self._reuse_delay_ema


class ModeSwitchController:
    """
    Online workload classifier with hysteresis.

    Uses softmax over mode logits from signals, then applies
    hysteresis rules to prevent thrashing between modes.
    """

    def __init__(
        self,
        temperature: float = 1.0,
        switch_confidence: float = 0.65,
        persistence_windows: int = 3,
        min_switch_interval: int = 2000,
        window_size: int = 512
    ):
        self.temperature = temperature
        self.switch_confidence = switch_confidence
        self.persistence_windows = persistence_windows
        self.min_switch_interval = min_switch_interval
        self.window_size = window_size

        # State
        self._current_mode = WorkloadMode.MIXED
        self._mode_confidence = 0.5
        self._last_switch_time = 0
        self._access_count = 0

        # For hysteresis: track consecutive windows suggesting a mode
        self._suggested_mode_counts: Dict[WorkloadMode, int] = {m: 0 for m in WorkloadMode}
        self._window_accesses = 0

        # Signals
        self.signals = WorkloadSignals(window_size=window_size)

        # Telemetry
        self._mode_time: Dict[WorkloadMode, int] = {m: 0 for m in WorkloadMode}
        self._mode_switches = 0

    def record_access(
        self,
        page_id: int,
        is_tier0_hit: bool,
        neighbor_hotness: float,
        shadow_hit_rate: float,
        was_eviction: bool = False
    ) -> Tuple[WorkloadMode, ModePolicy, float]:
        """
        Record an access and return current (mode, policy, confidence).

        May trigger a mode switch if conditions are met.
        """
        self._access_count += 1
        self._window_accesses += 1

        # Update signals
        self.signals.record_access(page_id, is_tier0_hit, neighbor_hotness, was_eviction)

        # Track time in current mode
        self._mode_time[self._current_mode] += 1

        # Check for mode switch at window boundaries
        if self._window_accesses >= self.window_size:
            self._window_accesses = 0
            self._maybe_switch_mode(shadow_hit_rate)

        return (self._current_mode, self.current_policy, self._mode_confidence)

    def _maybe_switch_mode(self, shadow_hit_rate: float) -> None:
        """Evaluate mode switch with hysteresis."""
        # Compute mode probabilities
        probs = self._compute_mode_probs(shadow_hit_rate)

        # Find suggested mode (highest probability)
        suggested_mode = max(probs, key=probs.get)
        suggested_prob = probs[suggested_mode]

        # Update persistence counts
        for mode in WorkloadMode:
            if mode == suggested_mode:
                self._suggested_mode_counts[mode] += 1
            else:
                self._suggested_mode_counts[mode] = max(0, self._suggested_mode_counts[mode] - 1)

        # Check hysteresis conditions for switch
        time_since_switch = self._access_count - self._last_switch_time

        can_switch = (
            suggested_mode != self._current_mode and
            suggested_prob > self.switch_confidence and
            self._suggested_mode_counts[suggested_mode] >= self.persistence_windows and
            time_since_switch >= self.min_switch_interval
        )

        if can_switch:
            self._current_mode = suggested_mode
            self._mode_confidence = suggested_prob
            self._last_switch_time = self._access_count
            self._mode_switches += 1
            # Reset persistence counts
            self._suggested_mode_counts = {m: 0 for m in WorkloadMode}
        else:
            # Update confidence for current mode
            self._mode_confidence = probs[self._current_mode]

    def _compute_mode_probs(self, shadow_hit_rate: float) -> Dict[WorkloadMode, float]:
        """Compute softmax probabilities for each mode."""
        s = self.signals

        # Compute logits for each mode based on signals
        logits = {
            WorkloadMode.SCAN: (
                +2.0 * s.seq_run +
                +1.5 * s.unique_ratio +
                -1.0 * shadow_hit_rate +
                -0.5 * s.hot_concentration
            ),
            WorkloadMode.LOOP: (
                +2.5 * s.loop_rate +
                +1.0 * shadow_hit_rate +
                -0.5 * s.unique_ratio +
                +0.5 * (1.0 - s.tier0_turnover)
            ),
            WorkloadMode.HOTSET: (
                +2.0 * s.hot_concentration +
                -1.0 * s.tier0_turnover +
                -0.5 * s.unique_ratio +
                -0.5 * s.seq_run
            ),
            WorkloadMode.CLUSTER: (
                +2.0 * s.neighbor_hit_ratio +
                +1.0 * s.hot_concentration +
                -0.5 * s.unique_ratio +
                +0.5 * (1.0 - s.seq_run)
            ),
            WorkloadMode.MIXED: 0.0  # Baseline
        }

        # Apply temperature and compute softmax
        max_logit = max(logits.values())
        exp_logits = {m: math.exp((l - max_logit) / self.temperature) for m, l in logits.items()}
        total = sum(exp_logits.values())

        return {m: e / total for m, e in exp_logits.items()}

    @property
    def current_mode(self) -> WorkloadMode:
        """Current operating mode."""
        return self._current_mode

    @property
    def current_policy(self) -> ModePolicy:
        """Current mode's policy configuration."""
        return MODE_POLICIES[self._current_mode]

    @property
    def confidence(self) -> float:
        """Confidence in current mode classification."""
        return self._mode_confidence

    def get_stats(self) -> dict:
        """Get mode switching statistics."""
        total_time = sum(self._mode_time.values())
        return {
            "current_mode": self._current_mode.name,
            "mode_confidence": self._mode_confidence,
            "mode_switches": self._mode_switches,
            "mode_time_fractions": {
                m.name: t / max(total_time, 1) for m, t in self._mode_time.items()
            },
            "signals": {
                "seq_run": self.signals.seq_run,
                "unique_ratio": self.signals.unique_ratio,
                "loop_rate": self.signals.loop_rate,
                "hot_concentration": self.signals.hot_concentration,
                "tier0_turnover": self.signals.tier0_turnover,
                "neighbor_hit_ratio": self.signals.neighbor_hit_ratio,
            }
        }

"""
State management for CTM+ simulator.

Implements the 6-dimensional page state vector:
    s_i = [φ_i, a_i, c_i, h_i, u_i, δ_i]

Where:
    φ (phase):       Relational signature [0, 2π]
    a (amplitude):   Importance weight [0, 1]
    c (coherence):   Stability measure [0, 1]
    h (heat):        Write pressure [0, 1]
    u (uncertainty): Entropy proxy [0, 1]
    δ (drift):       Expected decay rate [0, 1]
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Deque
from collections import deque
from enum import IntEnum, Enum
import math


class Tier(IntEnum):
    """Memory tier identifiers."""

    TIER0 = 0       # Fast tier (DRAM/HBM, uncompressed)
    COMPRESSED = 2  # Compressed DRAM tier (zswap/zram-style)
    POOL = 3        # CXL 3.0 shared memory pool
    TIER1 = 1       # Slow tier (NAND/DDR)
    NONE = -1       # Not in any tier


class OpType(IntEnum):
    """Memory operation types."""

    READ = 0
    WRITE = 1
    PREFETCH = 2


class PageHint(Enum):
    """External application hints for page hotness (CXL CMM-H style)."""

    NONE = 0        # No hint
    HOT = 1         # Application expects frequent access
    COLD = 2        # Application expects infrequent access
    PINNED = 3      # Application wants page kept in tier0
    WILLNEED = 4    # Application will access soon (prefetch hint)
    DONTNEED = 5    # Application is done with this page


@dataclass
class PageState:
    """
    6-dimensional state vector for a memory page.

    This is the core CTM+ abstraction: every page carries metadata
    that drives placement decisions.
    """

    page_id: int

    # 6D state vector (all in [0, 1] except phase)
    phase: float = 0.0  # φ: [0, 2π] relational signature
    amplitude: float = 0.5  # a: [0, 1] importance
    coherence: float = 0.5  # c: [0, 1] stability
    heat: float = 0.0  # h: [0, 1] write pressure
    uncertainty: float = 0.5  # u: [0, 1] entropy proxy
    drift: float = 0.1  # δ: [0, 1] expected decay

    # Metadata (not part of state vector)
    tier: Tier = Tier.NONE
    last_access_time: int = 0
    access_count: int = 0
    write_count: int = 0
    last_promotion_time: int = 0
    last_demotion_time: int = 0

    # Phase history for USE correlation
    phase_history: Deque[float] = field(default_factory=lambda: deque(maxlen=64))

    # === Gap 1: IRR Tracking (LIRS) ===
    # Inter-Reference Recency: number of unique pages accessed between
    # two consecutive accesses to this page. High IRR = cold despite recent access.
    irr: float = float('inf')  # Current IRR estimate (inf = never re-accessed)
    prev_access_time: int = 0  # Previous access time (for IRR calculation)

    # === Gap 2: Size-aware eviction (LHD) ===
    # Size in bytes for variable-size objects. Enables hits-per-byte scoring.
    size_bytes: int = 4096  # Default to standard page size

    # === Gap 5: S3-FIFO fast path (replaces SIEVE) ===
    # Visited bit: retained for compatibility (set on access, cleared on eviction).
    # S3-FIFO fast path now handles eviction via frequency-based Small/Main/Ghost queues.
    visited: bool = False

    # === Gap 6: External hint API (CXL CMM-H) ===
    hint: PageHint = PageHint.NONE
    hint_priority: float = 0.0  # Application-provided priority [0, 1]

    # === Multi-tenancy: QoS isolation ===
    tenant_id: str = "default"  # Owning tenant for QoS-aware eviction

    # === Compression tier ===
    compressed_access_count: int = 0  # Accesses while in compression tier
    last_compress_time: int = 0       # Time when page was compressed

    # === Writeback scheduling ===
    dirty: bool = False          # Page has unflushed writes in tier0
    dirty_since: int = 0         # Time when page was first dirtied (0 = clean)

    # === CXL 3.0 shared memory pool ===
    owner_host: int = 0              # Host that owns/originated this page
    pool_resident: bool = False      # True if page is in CXL shared pool
    sharer_hosts: Set[int] = field(default_factory=set)  # Hosts caching this page
    last_pool_access_time: int = 0   # Last time page was accessed via pool
    pool_access_count: int = 0       # Number of accesses while in pool

    # === NUMA-aware placement ===
    numa_node: int = 0           # Current NUMA node where page is placed
    preferred_node: int = 0      # NUMA node of most frequent accessor
    last_accessor_node: int = 0  # NUMA node of most recent accessor
    node_access_counts: Dict[int, int] = field(default_factory=dict)  # per-node access counts
    last_migration_time: int = 0  # Last time page was migrated between nodes

    def update_on_access(
        self,
        time: int,
        op_type: OpType,
        heat_decay: float = 0.99,
        amplitude_boost: float = 0.1,
    ) -> None:
        """
        Update state on memory access.

        Args:
            time: Current simulation time (access count)
            op_type: Type of access (READ, WRITE, PREFETCH)
            heat_decay: Decay factor for heat
            amplitude_boost: Boost to amplitude on access
        """
        # Update access metadata
        self.prev_access_time = self.last_access_time
        self.last_access_time = time
        self.access_count += 1
        self.visited = True  # Legacy visited bit (S3-FIFO fast path uses frequency tracking)

        # Update amplitude (importance increases with access)
        self.amplitude = min(1.0, self.amplitude + amplitude_boost * (1 - self.amplitude))

        # Update heat (write pressure)
        if op_type == OpType.WRITE:
            self.write_count += 1
            self.heat = min(1.0, self.heat + 0.2)  # Writes increase heat
            # Writeback scheduling: mark page dirty on write
            if not self.dirty:
                self.dirty = True
                self.dirty_since = time
        else:
            self.heat *= heat_decay  # Heat decays over time

        # Record phase for history
        self.phase_history.append(self.phase)

    def decay(self, time: int, decay_rate: float = 0.001) -> None:
        """
        Apply time-based decay to state.

        Called periodically to decay amplitude and increase uncertainty
        for pages that haven't been accessed recently.

        Args:
            time: Current simulation time
            decay_rate: Base decay rate per time unit
        """
        time_since_access = time - self.last_access_time
        if time_since_access > 0:
            decay_factor = math.exp(-decay_rate * time_since_access)
            self.amplitude *= decay_factor
            self.uncertainty = min(1.0, self.uncertainty + 0.01 * (1 - decay_factor))
            self.drift = min(1.0, self.drift + 0.005 * (1 - decay_factor))

    def compute_fast_coherence(self, mean_phase: float, config) -> float:
        """
        Compute fast-path coherence score.

        C_fast = α·c + β·(1-δ) + γ·cos(φ - φ̄)

        Args:
            mean_phase: System mean phase φ̄
            config: CoherenceConfig with weights

        Returns:
            Fast coherence score in [0, 1]
        """
        phase_alignment = 0.5 * (1 + math.cos(self.phase - mean_phase))  # Map to [0,1]

        score = (
            config.fast_alpha * self.coherence
            + config.fast_beta * (1 - self.drift)
            + config.fast_gamma * phase_alignment
        )
        return max(0.0, min(1.0, score))

    def to_vector(self) -> tuple:
        """Return state as 6-tuple."""
        return (
            self.phase,
            self.amplitude,
            self.coherence,
            self.heat,
            self.uncertainty,
            self.drift,
        )

    def __repr__(self) -> str:
        return (
            f"PageState(id={self.page_id}, tier={self.tier.name}, "
            f"φ={self.phase:.2f}, a={self.amplitude:.2f}, c={self.coherence:.2f}, "
            f"h={self.heat:.2f}, u={self.uncertainty:.2f}, δ={self.drift:.2f})"
        )


@dataclass
class TierState:
    """
    State of a memory tier (fast or slow).

    Tracks which pages are in the tier and provides LRU-style
    access ordering for eviction decisions.
    """

    tier_id: Tier
    capacity: int
    pages: Dict[int, PageState] = field(default_factory=dict)
    access_order: Deque[int] = field(default_factory=deque)  # LRU order

    # Tier-level metrics
    total_accesses: int = 0
    total_hits: int = 0
    total_promotions: int = 0
    total_demotions: int = 0

    # Per-tenant occupancy tracking: tenant_id -> page count in this tier
    tenant_occupancy: Dict[str, int] = field(default_factory=dict)

    # Per-NUMA-node occupancy tracking: node_id -> page count in this tier
    numa_occupancy: Dict[int, int] = field(default_factory=dict)

    @property
    def size(self) -> int:
        """Current number of pages in tier."""
        return len(self.pages)

    @property
    def is_full(self) -> bool:
        """Whether tier is at capacity."""
        return self.size >= self.capacity

    @property
    def hit_rate(self) -> float:
        """Current hit rate for this tier."""
        if self.total_accesses == 0:
            return 0.0
        return self.total_hits / self.total_accesses

    @property
    def mean_coherence(self) -> float:
        """Mean coherence of pages in tier."""
        if not self.pages:
            return 0.0
        return sum(p.coherence for p in self.pages.values()) / len(self.pages)

    @property
    def mean_phase(self) -> float:
        """Mean phase of pages in tier (circular mean)."""
        if not self.pages:
            return 0.0
        # Circular mean using complex numbers
        sin_sum = sum(math.sin(p.phase) for p in self.pages.values())
        cos_sum = sum(math.cos(p.phase) for p in self.pages.values())
        return math.atan2(sin_sum, cos_sum)

    def contains(self, page_id: int) -> bool:
        """Check if page is in this tier."""
        return page_id in self.pages

    def get(self, page_id: int) -> Optional[PageState]:
        """Get page state if in tier."""
        return self.pages.get(page_id)

    def add(self, page: PageState) -> Optional[PageState]:
        """
        Add page to tier, evicting LRU if necessary.

        Args:
            page: Page to add

        Returns:
            Evicted page if tier was full, None otherwise
        """
        evicted = None

        # Evict LRU if full
        if self.is_full and page.page_id not in self.pages:
            evicted = self._evict_lru()

        # Track tenant/NUMA occupancy change for evicted page
        if evicted is not None:
            tid = evicted.tenant_id
            self.tenant_occupancy[tid] = max(0, self.tenant_occupancy.get(tid, 0) - 1)
            nid = evicted.numa_node
            self.numa_occupancy[nid] = max(0, self.numa_occupancy.get(nid, 0) - 1)

        # Add page (if replacing existing, adjust occupancy)
        if page.page_id in self.pages:
            old_page = self.pages[page.page_id]
            old_tid = old_page.tenant_id
            self.tenant_occupancy[old_tid] = max(0, self.tenant_occupancy.get(old_tid, 0) - 1)
            old_nid = old_page.numa_node
            self.numa_occupancy[old_nid] = max(0, self.numa_occupancy.get(old_nid, 0) - 1)

        self.pages[page.page_id] = page
        page.tier = self.tier_id

        # Track tenant/NUMA occupancy for new page
        self.tenant_occupancy[page.tenant_id] = self.tenant_occupancy.get(page.tenant_id, 0) + 1
        self.numa_occupancy[page.numa_node] = self.numa_occupancy.get(page.numa_node, 0) + 1

        # Update access order
        if page.page_id in self.access_order:
            self.access_order.remove(page.page_id)
        self.access_order.append(page.page_id)

        return evicted

    def remove(self, page_id: int) -> Optional[PageState]:
        """
        Remove page from tier.

        Args:
            page_id: ID of page to remove

        Returns:
            Removed page, or None if not found
        """
        if page_id not in self.pages:
            return None

        page = self.pages.pop(page_id)

        # Clear dirty flag on removal from tier0 (implicit writeback).
        # Dirty pages only make sense in tier0 (DRAM); removal means
        # demotion/eviction requiring writeback.  Ensures INV-8.
        if self.tier_id == Tier.TIER0 and page.dirty:
            page.dirty = False
            page.dirty_since = 0

        page.tier = Tier.NONE

        # Track tenant occupancy
        tid = page.tenant_id
        self.tenant_occupancy[tid] = max(0, self.tenant_occupancy.get(tid, 0) - 1)
        # Track NUMA occupancy
        nid = page.numa_node
        self.numa_occupancy[nid] = max(0, self.numa_occupancy.get(nid, 0) - 1)

        if page_id in self.access_order:
            self.access_order.remove(page_id)

        return page

    def touch(self, page_id: int) -> None:
        """Update access order for page (move to MRU position)."""
        if page_id in self.access_order:
            self.access_order.remove(page_id)
            self.access_order.append(page_id)
        self.total_accesses += 1

    def record_hit(self) -> None:
        """Record a hit on this tier."""
        self.total_hits += 1

    def _evict_lru(self) -> Optional[PageState]:
        """Evict least recently used page.

        Uses remove() to ensure dirty flags and occupancy are updated
        consistently (INV-8 compliance).
        """
        if not self.access_order:
            return None

        lru_page_id = self.access_order[0]  # Peek (remove() will popleft)
        return self.remove(lru_page_id)

    def get_tenant_page_count(self, tenant_id: str) -> int:
        """Get number of pages owned by a tenant in this tier."""
        return self.tenant_occupancy.get(tenant_id, 0)

    def get_numa_node_page_count(self, node_id: int) -> int:
        """Get number of pages placed on a NUMA node in this tier."""
        return self.numa_occupancy.get(node_id, 0)

    def get_lru_candidates(self, n: int) -> list:
        """Get N least recently used pages as eviction candidates."""
        candidates = []
        for page_id in list(self.access_order)[:n]:
            if page_id in self.pages:
                candidates.append(self.pages[page_id])
        return candidates

    def get_mru_candidates(self, n: int) -> list:
        """Get N most recently used pages."""
        candidates = []
        for page_id in list(self.access_order)[-n:]:
            if page_id in self.pages:
                candidates.append(self.pages[page_id])
        return candidates


@dataclass
class GlobalState:
    """
    Global simulator state tracking all pages and tiers.
    """

    tier0: TierState
    tier1: TierState
    tier0c: Optional[TierState] = None  # Compression tier (zswap/zram)
    pool: Optional[TierState] = None    # CXL 3.0 shared memory pool
    all_pages: Dict[int, PageState] = field(default_factory=dict)

    # Global metrics
    current_time: int = 0
    total_accesses: int = 0
    total_promotions: int = 0
    total_demotions: int = 0

    # Phase integrator state (complex-valued accumulator)
    phase_accumulator: complex = 0j

    def get_or_create_page(self, page_id: int) -> PageState:
        """Get existing page or create new one."""
        if page_id not in self.all_pages:
            self.all_pages[page_id] = PageState(page_id=page_id)
        return self.all_pages[page_id]

    def find_page_tier(self, page_id: int) -> Tier:
        """Find which tier a page is in."""
        if self.tier0.contains(page_id):
            return Tier.TIER0
        elif self.tier0c is not None and self.tier0c.contains(page_id):
            return Tier.COMPRESSED
        elif self.pool is not None and self.pool.contains(page_id):
            return Tier.POOL
        elif self.tier1.contains(page_id):
            return Tier.TIER1
        return Tier.NONE

    @property
    def global_mean_phase(self) -> float:
        """Global mean phase across all active pages."""
        active_pages = list(self.tier0.pages.values()) + list(self.tier1.pages.values())
        if self.tier0c is not None:
            active_pages += list(self.tier0c.pages.values())
        if not active_pages:
            return 0.0
        sin_sum = sum(math.sin(p.phase) for p in active_pages)
        cos_sum = sum(math.cos(p.phase) for p in active_pages)
        return math.atan2(sin_sum, cos_sum)

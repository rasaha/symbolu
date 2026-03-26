"""
Formal invariant checker for CTM+ memory controller.

Provides runtime verification of 12 correctness invariants that must hold
after every state transition.  Violations indicate bugs that could cause
data loss, double-frees, or silent corruption in a real memory controller.

ARC has mathematical proofs of its optimality properties.  CTM+ has tests
but (until now) no invariant checking or formal specification.  This module
bridges that gap with runtime assertions derived from the state model.

Usage::

    from ctm_plus.core.invariants import InvariantChecker

    checker = InvariantChecker(state)
    violations = checker.check_all()
    assert not violations, f"Invariant violations: {violations}"

    # Or check specific invariants:
    checker.check_mutual_exclusivity()
    checker.check_capacity()
    checker.check_tier_field_consistency()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .state import GlobalState, TierState, PageState, Tier


@dataclass
class Violation:
    """A single invariant violation."""
    invariant: str        # e.g., "INV-1: mutual exclusivity"
    severity: str         # "CRITICAL", "ERROR", "WARNING"
    page_id: Optional[int]
    message: str

    def __str__(self) -> str:
        pid = f" page={self.page_id}" if self.page_id is not None else ""
        return f"[{self.severity}] {self.invariant}{pid}: {self.message}"


class InvariantChecker:
    """Checks all correctness invariants on a GlobalState snapshot.

    Call ``check_all()`` after every state transition (access, promote,
    demote, evict) to catch violations immediately.  In production, gate
    checks behind a debug flag to avoid overhead.

    Invariants numbered INV-1 through INV-12 matching the formal spec.
    """

    def __init__(self, state: GlobalState):
        self.state = state
        self.violations: List[Violation] = []

    def _add(self, invariant: str, severity: str, page_id: Optional[int], msg: str) -> None:
        self.violations.append(Violation(invariant, severity, page_id, msg))

    def check_all(self) -> List[Violation]:
        """Run all invariant checks and return violations."""
        self.violations = []

        self.check_mutual_exclusivity()          # INV-1
        self.check_tier_field_consistency()       # INV-2
        self.check_capacity()                     # INV-3
        self.check_access_order_consistency()     # INV-4
        self.check_occupancy_tracking()           # INV-5
        self.check_hit_access_monotonicity()      # INV-6
        self.check_timing_monotonicity()          # INV-7
        self.check_dirty_page_consistency()       # INV-8
        self.check_s3fifo_fast_path_semantics()              # INV-9
        self.check_compression_tier_integrity()   # INV-10
        self.check_all_pages_registry()           # INV-11
        self.check_no_orphan_pages()              # INV-12

        return self.violations

    # ── INV-1: Mutual Exclusivity ──

    def check_mutual_exclusivity(self) -> None:
        """A page must be in at most one tier at any time."""
        s = self.state
        tier0_ids = set(s.tier0.pages.keys())
        tier1_ids = set(s.tier1.pages.keys())
        tier0c_ids = set(s.tier0c.pages.keys()) if s.tier0c else set()

        # Check pairwise intersections
        t0_t1 = tier0_ids & tier1_ids
        for pid in t0_t1:
            self._add("INV-1", "CRITICAL", pid,
                       "Page in BOTH tier0 and tier1")

        t0_tc = tier0_ids & tier0c_ids
        for pid in t0_tc:
            self._add("INV-1", "CRITICAL", pid,
                       "Page in BOTH tier0 and tier0c")

        t1_tc = tier1_ids & tier0c_ids
        for pid in t1_tc:
            self._add("INV-1", "CRITICAL", pid,
                       "Page in BOTH tier1 and tier0c")

    # ── INV-2: Tier Field Consistency ──

    def check_tier_field_consistency(self) -> None:
        """page.tier must match the tier the page is actually in."""
        s = self.state

        for pid, page in s.tier0.pages.items():
            if page.tier != Tier.TIER0:
                self._add("INV-2", "CRITICAL", pid,
                           f"Page in tier0.pages but page.tier={page.tier.name}")

        for pid, page in s.tier1.pages.items():
            if page.tier != Tier.TIER1:
                self._add("INV-2", "CRITICAL", pid,
                           f"Page in tier1.pages but page.tier={page.tier.name}")

        if s.tier0c:
            for pid, page in s.tier0c.pages.items():
                if page.tier != Tier.COMPRESSED:
                    self._add("INV-2", "CRITICAL", pid,
                               f"Page in tier0c.pages but page.tier={page.tier.name}")

    # ── INV-3: Capacity ──

    def check_capacity(self) -> None:
        """No tier may exceed its capacity."""
        for tier_name, tier in self._all_tiers():
            if len(tier.pages) > tier.capacity:
                self._add("INV-3", "CRITICAL", None,
                           f"{tier_name} has {len(tier.pages)} pages "
                           f"but capacity is {tier.capacity}")

    # ── INV-4: Access Order Consistency ──

    def check_access_order_consistency(self) -> None:
        """access_order and pages dict must agree on membership."""
        for tier_name, tier in self._all_tiers():
            order_ids = set(tier.access_order)
            pages_ids = set(tier.pages.keys())

            # Pages in order but not in pages dict
            ghost = order_ids - pages_ids
            for pid in ghost:
                self._add("INV-4", "ERROR", pid,
                           f"{tier_name}: page in access_order but not in pages dict")

            # Pages in dict but not in order
            missing = pages_ids - order_ids
            for pid in missing:
                self._add("INV-4", "ERROR", pid,
                           f"{tier_name}: page in pages dict but not in access_order")

            # Duplicates in access order
            if len(tier.access_order) != len(order_ids):
                self._add("INV-4", "ERROR", None,
                           f"{tier_name}: access_order has duplicates "
                           f"(len={len(tier.access_order)}, unique={len(order_ids)})")

    # ── INV-5: Occupancy Tracking ──

    def check_occupancy_tracking(self) -> None:
        """Tenant and NUMA occupancy counters must match actual page counts."""
        for tier_name, tier in self._all_tiers():
            # Tenant occupancy
            actual_tenant: Dict[str, int] = {}
            for page in tier.pages.values():
                actual_tenant[page.tenant_id] = actual_tenant.get(page.tenant_id, 0) + 1

            for tid, expected in tier.tenant_occupancy.items():
                actual = actual_tenant.get(tid, 0)
                if expected != actual:
                    self._add("INV-5", "WARNING", None,
                               f"{tier_name}: tenant '{tid}' occupancy={expected} "
                               f"but actual count={actual}")

            # NUMA occupancy
            actual_numa: Dict[int, int] = {}
            for page in tier.pages.values():
                actual_numa[page.numa_node] = actual_numa.get(page.numa_node, 0) + 1

            for nid, expected in tier.numa_occupancy.items():
                actual = actual_numa.get(nid, 0)
                if expected != actual:
                    self._add("INV-5", "WARNING", None,
                               f"{tier_name}: NUMA node {nid} occupancy={expected} "
                               f"but actual count={actual}")

    # ── INV-6: Hit/Access Monotonicity ──

    def check_hit_access_monotonicity(self) -> None:
        """Hits must not exceed accesses."""
        for tier_name, tier in self._all_tiers():
            if tier.total_hits > tier.total_accesses:
                self._add("INV-6", "ERROR", None,
                           f"{tier_name}: total_hits ({tier.total_hits}) > "
                           f"total_accesses ({tier.total_accesses})")

    # ── INV-7: Timing Monotonicity ──

    def check_timing_monotonicity(self) -> None:
        """Timing fields must be non-negative and monotonically ordered."""
        for pid, page in self.state.all_pages.items():
            if page.last_access_time < 0:
                self._add("INV-7", "ERROR", pid,
                           f"last_access_time={page.last_access_time} is negative")

            if page.access_count < 0:
                self._add("INV-7", "ERROR", pid,
                           f"access_count={page.access_count} is negative")

            if page.write_count < 0:
                self._add("INV-7", "ERROR", pid,
                           f"write_count={page.write_count} is negative")

            if page.write_count > page.access_count:
                self._add("INV-7", "WARNING", pid,
                           f"write_count ({page.write_count}) > "
                           f"access_count ({page.access_count})")

    # ── INV-8: Dirty Page Consistency ──

    def check_dirty_page_consistency(self) -> None:
        """Dirty pages must only exist in tier0, and dirty_since must be set."""
        for pid, page in self.state.all_pages.items():
            if page.dirty:
                if page.tier != Tier.TIER0:
                    self._add("INV-8", "ERROR", pid,
                               f"Page is dirty but in {page.tier.name}, not TIER0")
                if page.dirty_since <= 0:
                    self._add("INV-8", "WARNING", pid,
                               f"Page is dirty but dirty_since={page.dirty_since}")
            else:
                if page.dirty_since > 0:
                    self._add("INV-8", "WARNING", pid,
                               f"Page is clean but dirty_since={page.dirty_since} > 0")

    # ── INV-9: S3-FIFO Fast Path Semantics (replaces SIEVE visited check) ──

    def check_s3fifo_fast_path_semantics(self) -> None:
        """Pages not in tier0 should not have visited=True (legacy stale bit)."""
        for pid, page in self.state.all_pages.items():
            if page.visited and page.tier != Tier.TIER0:
                # A visited page outside tier0 is a stale bit — not harmful
                # but indicates the bit wasn't cleared on demotion.
                self._add("INV-9", "WARNING", pid,
                           f"Page has visited=True but is in {page.tier.name}")

    # ── INV-10: Compression Tier Integrity ──

    def check_compression_tier_integrity(self) -> None:
        """All tier0c pages must have valid compression metadata."""
        if not self.state.tier0c:
            return

        for pid, page in self.state.tier0c.pages.items():
            if page.tier != Tier.COMPRESSED:
                self._add("INV-10", "CRITICAL", pid,
                           f"Page in tier0c but tier={page.tier.name}")

            if page.last_compress_time < 0:
                self._add("INV-10", "ERROR", pid,
                           f"last_compress_time={page.last_compress_time} is negative")

            if page.compressed_access_count < 0:
                self._add("INV-10", "ERROR", pid,
                           f"compressed_access_count={page.compressed_access_count} is negative")

    # ── INV-11: all_pages Registry ──

    def check_all_pages_registry(self) -> None:
        """Every page in a tier must exist in all_pages, with object identity."""
        s = self.state

        for tier_name, tier in self._all_tiers():
            for pid, page in tier.pages.items():
                if pid not in s.all_pages:
                    self._add("INV-11", "CRITICAL", pid,
                               f"Page in {tier_name} but not in all_pages")
                elif s.all_pages[pid] is not page:
                    self._add("INV-11", "CRITICAL", pid,
                               f"Page in {tier_name} is different object "
                               f"from all_pages[{pid}]")

    # ── INV-12: No Orphan Pages ──

    def check_no_orphan_pages(self) -> None:
        """Pages in all_pages that claim a tier must actually be in that tier."""
        s = self.state

        for pid, page in s.all_pages.items():
            if page.tier == Tier.TIER0 and pid not in s.tier0.pages:
                self._add("INV-12", "CRITICAL", pid,
                           "page.tier=TIER0 but page not in tier0.pages")

            elif page.tier == Tier.TIER1 and pid not in s.tier1.pages:
                self._add("INV-12", "CRITICAL", pid,
                           "page.tier=TIER1 but page not in tier1.pages")

            elif page.tier == Tier.COMPRESSED:
                if s.tier0c is None:
                    self._add("INV-12", "CRITICAL", pid,
                               "page.tier=COMPRESSED but tier0c is None")
                elif pid not in s.tier0c.pages:
                    self._add("INV-12", "CRITICAL", pid,
                               "page.tier=COMPRESSED but page not in tier0c.pages")

    # ── Helpers ──

    def _all_tiers(self) -> List[Tuple[str, TierState]]:
        result = [("tier0", self.state.tier0), ("tier1", self.state.tier1)]
        if self.state.tier0c:
            result.append(("tier0c", self.state.tier0c))
        return result


def check_invariants(state: GlobalState) -> List[Violation]:
    """Convenience function: check all invariants and return violations."""
    return InvariantChecker(state).check_all()


def assert_invariants(state: GlobalState, context: str = "") -> None:
    """Assert all invariants hold. Raises AssertionError on violation.

    Args:
        state: The global state to check.
        context: Optional description of when/where the check happens
            (e.g., "after promotion of page 42").
    """
    violations = check_invariants(state)
    if violations:
        critical = [v for v in violations if v.severity == "CRITICAL"]
        errors = [v for v in violations if v.severity == "ERROR"]
        warnings = [v for v in violations if v.severity == "WARNING"]

        msg_parts = []
        if context:
            msg_parts.append(f"Context: {context}")
        msg_parts.append(f"Invariant violations: {len(critical)} CRITICAL, "
                         f"{len(errors)} ERROR, {len(warnings)} WARNING")
        for v in violations:
            msg_parts.append(f"  {v}")

        # Only fail on CRITICAL and ERROR
        if critical or errors:
            raise AssertionError("\n".join(msg_parts))

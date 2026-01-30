"""
Main simulator engine for CTM+ validation.

The Simulator orchestrates trace replay and metrics collection,
enabling fair comparison between different controller algorithms.
"""

from typing import List, Optional, Type
from dataclasses import dataclass
import time

from .core.config import SimulatorConfig
from .core.state import GlobalState, TierState, Tier, OpType
from .core.metrics import SimulationMetrics, MetricsCollector
from .controllers.base import BaseController
from .traces.loader import TraceEvent


@dataclass
class SimulationResult:
    """Complete result of a simulation run."""

    metrics: SimulationMetrics
    elapsed_time_sec: float
    events_per_sec: float
    controller_stats: dict


class Simulator:
    """
    Main simulator for CTM+ validation.

    Usage:
        sim = Simulator(tier0_size=1000, tier1_size=100000)

        # Run with different controllers
        results_lru = sim.run(trace, LRUController(sim.config))
        results_ctm = sim.run(trace, CTMPlusController(sim.config))

        # Compare results
        print_comparison(results_lru.metrics, results_ctm.metrics)
    """

    def __init__(
        self,
        tier0_size: int = 1000,
        tier1_size: int = 100000,
        config: Optional[SimulatorConfig] = None,
    ):
        """
        Initialize simulator.

        Args:
            tier0_size: Number of pages in fast tier
            tier1_size: Number of pages in slow tier
            config: Full configuration (overrides tier sizes if provided)
        """
        if config is not None:
            self.config = config
        else:
            self.config = SimulatorConfig(
                tier0_size=tier0_size,
                tier1_size=tier1_size,
            )

    def run(
        self,
        trace: List[TraceEvent],
        controller: BaseController,
        trace_name: str = "unknown",
        progress_interval: int = 10000,
        verbose: bool = True,
    ) -> SimulationResult:
        """
        Run simulation with given trace and controller.

        Args:
            trace: List of trace events to replay
            controller: Controller to use for tier management
            trace_name: Name of trace (for reporting)
            progress_interval: Print progress every N events
            verbose: Whether to print progress

        Returns:
            SimulationResult with metrics and timing
        """
        # Reset controller
        controller.reset()

        # Initialize state
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=self.config.tier0_size),
            tier1=TierState(tier_id=Tier.TIER1, capacity=self.config.tier1_size),
        )

        # Initialize metrics collector
        metrics = MetricsCollector(
            controller_name=controller.name,
            trace_name=trace_name,
        )

        # Epoch tracking
        epoch_size = getattr(controller, 'ctm_config', None)
        if epoch_size and hasattr(epoch_size, 'epoch_size'):
            epoch_size = epoch_size.epoch_size
        else:
            epoch_size = 1000

        start_time = time.time()

        # Replay trace
        for i, event in enumerate(trace):
            state.current_time = i

            # Process access
            tier, latency_ns, promoted, demoted = controller.on_access(
                state=state,
                page_id=event.page_id,
                op_type=event.op_type,
            )

            # Record metrics
            tier0_hit = (tier == Tier.TIER0)
            tier1_hit = (tier == Tier.TIER1)

            # Get coherence if available
            page = state.all_pages.get(event.page_id)
            coherence = page.coherence if page else None
            phase = page.phase if page else None

            metrics.record_access(
                tier0_hit=tier0_hit,
                tier1_hit=tier1_hit,
                latency_ns=latency_ns,
                coherence=coherence,
                phase=phase,
            )

            if promoted:
                metrics.record_promotion()
            if demoted:
                metrics.record_demotion()

            # End of epoch processing
            if (i + 1) % epoch_size == 0:
                epoch = (i + 1) // epoch_size
                controller.on_epoch(state, epoch)

            # Progress reporting
            if verbose and progress_interval and (i + 1) % progress_interval == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                current_hit_rate = metrics.tier0_hits / (i + 1)
                print(
                    f"  [{controller.name}] {i + 1:,}/{len(trace):,} "
                    f"({100 * (i + 1) / len(trace):.1f}%) "
                    f"| Hit rate: {current_hit_rate:.2%} "
                    f"| {rate:,.0f} events/sec"
                )

        elapsed_time = time.time() - start_time
        events_per_sec = len(trace) / elapsed_time if elapsed_time > 0 else 0

        # Handle BCVF rejections
        controller_stats = controller.get_stats()
        if "bcvf_rejections" in controller_stats:
            # Update metrics collector with BCVF rejections
            for _ in range(controller_stats.get("bcvf_rejections", 0)):
                metrics.record_bcvf_rejection()

        if verbose:
            print(
                f"  [{controller.name}] Complete: {len(trace):,} events "
                f"in {elapsed_time:.2f}s ({events_per_sec:,.0f} events/sec)"
            )

        return SimulationResult(
            metrics=metrics.finalize(),
            elapsed_time_sec=elapsed_time,
            events_per_sec=events_per_sec,
            controller_stats=controller_stats,
        )

    def compare(
        self,
        trace: List[TraceEvent],
        controllers: List[BaseController],
        trace_name: str = "unknown",
        verbose: bool = True,
    ) -> List[SimulationResult]:
        """
        Run simulation with multiple controllers and compare results.

        Args:
            trace: Trace to replay
            controllers: List of controllers to compare
            trace_name: Name of trace
            verbose: Whether to print progress

        Returns:
            List of SimulationResult, one per controller
        """
        results = []

        if verbose:
            print(f"\n{'='*60}")
            print(f"Trace: {trace_name}")
            print(f"Events: {len(trace):,}")
            print(f"Tier-0 size: {self.config.tier0_size:,} pages")
            print(f"Tier-1 size: {self.config.tier1_size:,} pages")
            print(f"{'='*60}\n")

        for controller in controllers:
            if verbose:
                print(f"Running {controller.name}...")

            result = self.run(
                trace=trace,
                controller=controller,
                trace_name=trace_name,
                verbose=verbose,
            )
            results.append(result)

            if verbose:
                print(f"  Hit rate: {result.metrics.hit_rate:.2%}")
                print()

        return results


def run_comparison(
    trace: List[TraceEvent],
    tier0_size: int = 1000,
    tier1_size: int = 100000,
    trace_name: str = "unknown",
    verbose: bool = True,
) -> dict:
    """
    Convenience function to run standard comparison.

    Compares LRU, ARC, and CTM+ on the given trace.

    Args:
        trace: Trace to replay
        tier0_size: Fast tier size
        tier1_size: Slow tier size
        trace_name: Name for reporting
        verbose: Print progress

    Returns:
        Dictionary with results and comparison metrics
    """
    from .controllers.lru import LRUController
    from .controllers.arc import ARCController
    from .controllers.ctm_plus import CTMPlusController

    config = SimulatorConfig(tier0_size=tier0_size, tier1_size=tier1_size)
    sim = Simulator(config=config)

    controllers = [
        LRUController(config),
        ARCController(config),
        CTMPlusController(config),
    ]

    results = sim.compare(trace, controllers, trace_name, verbose)

    # Build comparison
    lru_result = results[0]
    arc_result = results[1]
    ctm_result = results[2]

    comparison = {
        "trace_name": trace_name,
        "num_events": len(trace),
        "tier0_size": tier0_size,
        "tier1_size": tier1_size,
        "results": {
            "LRU": lru_result.metrics.to_dict(),
            "ARC": arc_result.metrics.to_dict(),
            "CTM+": ctm_result.metrics.to_dict(),
        },
        "improvements": {
            "ctm_vs_lru_hit_rate": ctm_result.metrics.hit_rate - lru_result.metrics.hit_rate,
            "ctm_vs_lru_hit_rate_pct": (
                (ctm_result.metrics.hit_rate / lru_result.metrics.hit_rate - 1)
                if lru_result.metrics.hit_rate > 0 else 0
            ),
            "ctm_vs_arc_hit_rate": ctm_result.metrics.hit_rate - arc_result.metrics.hit_rate,
            "ctm_vs_arc_hit_rate_pct": (
                (ctm_result.metrics.hit_rate / arc_result.metrics.hit_rate - 1)
                if arc_result.metrics.hit_rate > 0 else 0
            ),
            "ctm_vs_lru_latency_pct": (
                1 - ctm_result.metrics.avg_latency_ns / lru_result.metrics.avg_latency_ns
                if lru_result.metrics.avg_latency_ns > 0 else 0
            ),
        },
    }

    if verbose:
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"\nHit Rates:")
        print(f"  LRU:   {lru_result.metrics.hit_rate:.2%}")
        print(f"  ARC:   {arc_result.metrics.hit_rate:.2%}")
        print(f"  CTM+:  {ctm_result.metrics.hit_rate:.2%}")
        print(f"\nCTM+ vs LRU: {comparison['improvements']['ctm_vs_lru_hit_rate']:+.2%} "
              f"({comparison['improvements']['ctm_vs_lru_hit_rate_pct']:+.1%} relative)")
        print(f"CTM+ vs ARC: {comparison['improvements']['ctm_vs_arc_hit_rate']:+.2%} "
              f"({comparison['improvements']['ctm_vs_arc_hit_rate_pct']:+.1%} relative)")
        print("="*60)

    return comparison

"""
Standard trace benchmarking for CTM+.

Compares CTM+ against LRU, ARC, and S3-FIFO on industry-standard
trace profiles (MSR Cambridge, Twitter, Meta/CacheLib), producing
publication-ready comparison tables.

Usage:
    from ctm_plus.benchmarks import run_benchmarks
    results = run_benchmarks()

    # Or from CLI:
    python -m ctm_plus.benchmarks [--quick] [--traces msr_src1_0,twitter_kv]
"""

import json
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

from .core.config import SimulatorConfig, CTMPlusConfig, GLCacheConfig
from .core.metrics import SimulationMetrics
from .simulator import Simulator, SimulationResult
from .controllers.lru import LRUController
from .controllers.arc import ARCController
from .controllers.s3fifo import S3FIFOController
from .controllers.ctm_plus import CTMPlusController
from .traces.standard import (
    TraceProfile,
    ALL_PROFILES,
    MSR_PROFILES,
    TWITTER_PROFILES,
    META_PROFILES,
    generate_from_profile,
    load_or_generate,
)


@dataclass
class BenchmarkResult:
    """Result of benchmarking one trace across all controllers."""

    profile: TraceProfile
    results: Dict[str, SimulationResult]  # controller_name -> result
    lru_baseline: SimulationMetrics

    @property
    def controller_names(self) -> List[str]:
        return list(self.results.keys())

    def hit_rate(self, controller: str) -> float:
        return self.results[controller].metrics.hit_rate

    def improvement_vs_lru(self, controller: str) -> float:
        """Absolute hit rate improvement over LRU."""
        return self.hit_rate(controller) - self.lru_baseline.hit_rate

    def relative_improvement_vs_lru(self, controller: str) -> float:
        """Relative hit rate improvement over LRU."""
        base = self.lru_baseline.hit_rate
        if base <= 0:
            return 0.0
        return (self.hit_rate(controller) / base) - 1.0

    def to_dict(self) -> Dict:
        row = {"trace": self.profile.name, "source": self.profile.source}
        for name, result in self.results.items():
            m = result.metrics
            row[f"{name}_hit_rate"] = m.hit_rate
            row[f"{name}_p99_ns"] = m.p99_latency_ns
            row[f"{name}_move_rate"] = m.move_rate
            row[f"{name}_avg_latency_ns"] = m.avg_latency_ns
        return row


@dataclass
class BenchmarkSuite:
    """Complete benchmark results across all traces."""

    results: List[BenchmarkResult]
    config: SimulatorConfig
    elapsed_sec: float

    def summary_table(self) -> str:
        """Generate publication-ready comparison table."""
        controllers = ["LRU", "ARC", "S3-FIFO", "CTM+"]
        available = set()
        for br in self.results:
            available.update(br.controller_names)
        controllers = [c for c in controllers if c in available]

        lines = []
        sep = "-" * (18 + 12 * len(controllers) + 24)

        # Header
        lines.append(sep)
        header = f"{'Trace':<18}"
        for c in controllers:
            header += f" {c:>10}"
        header += f" {'vs LRU':>10}  {'vs ARC':>10}"
        lines.append(header)
        lines.append(sep)

        # Rows grouped by source
        for source_name, profiles in [
            ("MSR Cambridge", MSR_PROFILES),
            ("Twitter", TWITTER_PROFILES),
            ("Meta/CacheLib", META_PROFILES),
        ]:
            source_results = [
                r for r in self.results
                if r.profile.source == profiles[0].source
            ]
            if not source_results:
                continue

            lines.append(f"  [{source_name}]")
            for br in source_results:
                row = f"  {br.profile.name:<16}"
                for c in controllers:
                    if c in br.results:
                        row += f" {br.hit_rate(c):>9.2%}"
                    else:
                        row += f" {'N/A':>10}"

                # CTM+ improvements
                if "CTM+" in br.results:
                    vs_lru = br.improvement_vs_lru("CTM+")
                    row += f"  {vs_lru:>+9.2%}"
                    if "ARC" in br.results:
                        vs_arc = br.hit_rate("CTM+") - br.hit_rate("ARC")
                        row += f"  {vs_arc:>+9.2%}"
                    else:
                        row += f" {'N/A':>10}"
                else:
                    row += f" {'N/A':>10}  {'N/A':>10}"
                lines.append(row)

        lines.append(sep)

        # Averages
        if self.results:
            avg_row = f"  {'AVERAGE':<16}"
            for c in controllers:
                rates = [br.hit_rate(c) for br in self.results if c in br.results]
                if rates:
                    avg_row += f" {sum(rates)/len(rates):>9.2%}"
                else:
                    avg_row += f" {'N/A':>10}"
            if "CTM+" in available:
                vs_lru_vals = [
                    br.improvement_vs_lru("CTM+")
                    for br in self.results if "CTM+" in br.results
                ]
                avg_row += f"  {sum(vs_lru_vals)/len(vs_lru_vals):>+9.2%}" if vs_lru_vals else ""
                if "ARC" in available:
                    vs_arc_vals = [
                        br.hit_rate("CTM+") - br.hit_rate("ARC")
                        for br in self.results
                        if "CTM+" in br.results and "ARC" in br.results
                    ]
                    avg_row += f"  {sum(vs_arc_vals)/len(vs_arc_vals):>+9.2%}" if vs_arc_vals else ""
            lines.append(avg_row)
            lines.append(sep)

        return "\n".join(lines)

    def latency_table(self) -> str:
        """Generate latency comparison table (avg + P99)."""
        controllers = ["LRU", "ARC", "S3-FIFO", "CTM+"]
        available = set()
        for br in self.results:
            available.update(br.controller_names)
        controllers = [c for c in controllers if c in available]

        lines = []
        sep = "-" * (18 + 22 * len(controllers))
        lines.append(f"{'Trace':<18}" + "".join(f" {c+' avg':>10} {c+' P99':>10}" for c in controllers))
        lines.append(sep)

        for br in self.results:
            row = f"  {br.profile.name:<16}"
            for c in controllers:
                if c in br.results:
                    m = br.results[c].metrics
                    row += f" {m.avg_latency_ns:>9,.0f} {m.p99_latency_ns:>9,.0f}"
                else:
                    row += f" {'N/A':>10} {'N/A':>10}"
            lines.append(row)

        lines.append(sep)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Export all results as JSON."""
        data = {
            "config": {
                "tier0_size": self.config.tier0_size,
                "tier1_size": self.config.tier1_size,
            },
            "elapsed_sec": self.elapsed_sec,
            "traces": [br.to_dict() for br in self.results],
        }
        return json.dumps(data, indent=2, default=str)


def run_benchmarks(
    profiles: Optional[List[str]] = None,
    num_events: Optional[int] = None,
    tier0_size: Optional[int] = None,
    trace_dir: Optional[str] = None,
    verbose: bool = True,
    seed: int = 42,
    warmup_fraction: float = 0.0,
    enable_glcache: bool = False,
) -> BenchmarkSuite:
    """
    Run standard trace benchmarks.

    Args:
        profiles: List of profile names to run (None = all 7 standard traces)
        num_events: Override event count per trace (None = profile default)
        tier0_size: Override tier0 size (None = derived from profile)
        trace_dir: Directory with real trace files (None = synthetic only)
        verbose: Print progress
        seed: Random seed
        warmup_fraction: Fraction of events to use as warmup (0.0-0.5).
            During warmup, cache and controller state are built up normally
            but metrics are reset so only steady-state performance is
            measured. Default 0.0 = no warmup (legacy behavior).

    Returns:
        BenchmarkSuite with all results
    """
    # Select profiles
    if profiles is None:
        selected = list(ALL_PROFILES.values())
    else:
        selected = []
        for name in profiles:
            if name not in ALL_PROFILES:
                available = ", ".join(sorted(ALL_PROFILES.keys()))
                raise ValueError(f"Unknown profile: {name}. Available: {available}")
            selected.append(ALL_PROFILES[name])

    if verbose:
        print("=" * 72)
        print("CTM+ STANDARD TRACE BENCHMARK SUITE")
        print("=" * 72)
        mode = "synthetic profiles" if trace_dir is None else f"traces from {trace_dir}"
        print(f"  Mode: {mode}")
        print(f"  Traces: {len(selected)}")
        if num_events:
            print(f"  Events/trace: {num_events:,}")
        if warmup_fraction > 0:
            print(f"  Warmup: {warmup_fraction:.0%} of events")
        print()

    start_time = time.time()
    all_results = []

    for profile in selected:
        # Determine tier0 size
        t0 = tier0_size or max(100, int(profile.num_pages * profile.recommended_tier0_ratio))
        t1 = profile.num_pages * 10  # Large enough to not be the bottleneck

        config = SimulatorConfig(tier0_size=t0, tier1_size=t1)
        sim = Simulator(config=config)

        # Load or generate trace
        n_ev = num_events or profile.num_events
        trace = load_or_generate(profile, trace_dir=trace_dir, num_events=n_ev, seed=seed)

        if verbose:
            print(f"{'─' * 72}")
            print(f"Trace: {profile.name} ({profile.description})")
            print(f"  Pages: {profile.num_pages:,} | Events: {len(trace):,} | "
                  f"Tier0: {t0:,} ({profile.recommended_tier0_ratio:.0%} of WSS)")
            print()

        # Compute warmup events for this trace
        warmup_events = int(len(trace) * warmup_fraction)

        # Create controllers
        controllers = [
            ("LRU", LRUController(config)),
            ("ARC", ARCController(config)),
            ("S3-FIFO", S3FIFOController(config)),
            ("CTM+", CTMPlusController(config)),
        ]

        if enable_glcache:
            gl_ctm_config = CTMPlusConfig(
                glcache=GLCacheConfig(enabled=True),
            )
            controllers.append(
                ("CTM+GL", CTMPlusController(config, gl_ctm_config))
            )

        results = {}
        for ctrl_name, controller in controllers:
            result = sim.run(
                trace=trace,
                controller=controller,
                trace_name=profile.name,
                verbose=verbose,
                warmup_events=warmup_events,
            )
            results[ctrl_name] = result

            if verbose:
                print(f"    {ctrl_name:<10} hit rate: {result.metrics.hit_rate:.2%}  "
                      f"avg: {result.metrics.avg_latency_ns:,.0f}ns  "
                      f"P99: {result.metrics.p99_latency_ns:,.0f}ns")

        if verbose:
            print()

        br = BenchmarkResult(
            profile=profile,
            results=results,
            lru_baseline=results["LRU"].metrics,
        )
        all_results.append(br)

    elapsed = time.time() - start_time

    suite = BenchmarkSuite(
        results=all_results,
        config=config,  # Last config (for reporting)
        elapsed_sec=elapsed,
    )

    if verbose:
        print("\n" + "=" * 72)
        print("HIT RATE COMPARISON")
        print("=" * 72)
        print(suite.summary_table())
        print()
        print("=" * 72)
        print("LATENCY COMPARISON (nanoseconds)")
        print("=" * 72)
        print(suite.latency_table())
        print()
        print(f"Total benchmark time: {elapsed:.1f}s")
        print("=" * 72)

    return suite


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CTM+ Standard Trace Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available trace profiles:
  MSR Cambridge:  msr_src1_0, msr_web_0, msr_proj_0
  Twitter:        twitter_cluster52, twitter_kv
  Meta/CacheLib:  meta_cdn, meta_kv

Examples:
  python -m ctm_plus.benchmarks                    # Run all 7 traces
  python -m ctm_plus.benchmarks --quick             # Quick mode (50k events)
  python -m ctm_plus.benchmarks --traces msr_src1_0,twitter_kv
  python -m ctm_plus.benchmarks --json results.json
  python -m ctm_plus.benchmarks --trace-dir ./traces/  # Use real trace files
""",
    )
    parser.add_argument(
        "--traces",
        type=str,
        default=None,
        help="Comma-separated list of trace profiles to run",
    )
    parser.add_argument(
        "--events",
        type=int,
        default=None,
        help="Events per trace (overrides profile default)",
    )
    parser.add_argument(
        "--tier0",
        type=int,
        default=None,
        help="Override tier0 size for all traces",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick run: 50k events per trace",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=0.0,
        metavar="FRACTION",
        help="Fraction of events to use as warmup (0.0-0.5). "
             "Cache state is built during warmup but metrics are reset "
             "so only steady-state performance is measured. "
             "Example: --warmup 0.1 uses first 10%% as warmup.",
    )
    parser.add_argument(
        "--glcache",
        action="store_true",
        help="Include CTM+ with GL-Cache learned eviction alongside Hedge",
    )
    parser.add_argument(
        "--trace-dir",
        type=str,
        default=None,
        help="Directory containing real trace files",
    )
    parser.add_argument(
        "--json",
        type=str,
        default=None,
        help="Export results to JSON file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available trace profiles and exit",
    )

    args = parser.parse_args()

    if args.list:
        print("Available trace profiles:")
        for name, profile in sorted(ALL_PROFILES.items()):
            print(f"  {name:<22} {profile.description}")
        return 0

    profiles = args.traces.split(",") if args.traces else None
    num_events = 50000 if args.quick else args.events

    suite = run_benchmarks(
        profiles=profiles,
        num_events=num_events,
        tier0_size=args.tier0,
        trace_dir=args.trace_dir,
        verbose=not args.quiet,
        seed=args.seed,
        warmup_fraction=args.warmup,
        enable_glcache=args.glcache,
    )

    if args.json:
        with open(args.json, "w") as f:
            f.write(suite.to_json())
        print(f"\nResults exported to {args.json}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

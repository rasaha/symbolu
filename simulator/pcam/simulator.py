"""
Main PCAM simulator engine.

Orchestrates trace replay, metrics collection, and comparison
between PCAM and baseline controllers.
"""

from typing import List, Dict, Optional, Type, Union
from dataclasses import dataclass
import time

from .core.config import PCAMConfig
from .core.state import AttentionState
from .core.metrics import PCAMMetrics, MetricsCollector
from .traces.format import PCAMTrace, TraceStep
from .baselines.base import BaselineController, ControllerConfig
from .interface import PCAMInterface, SoftwarePCAMInterface


@dataclass
class SimulationResult:
    """Complete result of a simulation run."""
    metrics: PCAMMetrics
    elapsed_time_sec: float
    events_per_sec: float
    controller_name: str
    trace_name: str
    config: Dict

    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"=== Simulation Result: {self.controller_name} on {self.trace_name} ===\n"
            f"Elapsed: {self.elapsed_time_sec:.2f}s ({self.events_per_sec:.0f} events/sec)\n"
            f"\n{self.metrics.summary()}"
        )


class PCAMSimulator:
    """
    Main simulator for PCAM validation.

    Supports two modes:
    1. PCAM mode: Uses PCAMInterface for attention tracking
    2. Baseline mode: Uses BaselineController for comparison

    Usage:
        sim = PCAMSimulator(config)

        # Generate trace
        trace = generate_chat_trace(num_turns=10)

        # Run with PCAM
        pcam_result = sim.run_pcam(trace, "chat_trace")

        # Run with baselines
        lru_result = sim.run_baseline(trace, SinkLRUController(), "chat_trace")
        h2o_result = sim.run_baseline(trace, H2OController(), "chat_trace")

        # Compare
        comparison = sim.compare_results([pcam_result, lru_result, h2o_result])
    """

    def __init__(
        self,
        config: Optional[PCAMConfig] = None,
        verbose: bool = True,
    ):
        self.config = config or PCAMConfig()
        self.verbose = verbose

    def run_pcam(
        self,
        trace: PCAMTrace,
        trace_name: str = "unknown",
        progress_interval: int = 100,
    ) -> SimulationResult:
        """
        Run simulation using PCAM interface.

        Args:
            trace: Trace to replay
            trace_name: Name for reporting
            progress_interval: Print progress every N steps

        Returns:
            SimulationResult with metrics
        """
        # Initialize PCAM interface
        pcam = SoftwarePCAMInterface(
            max_sequences=self.config.max_sequences,
            max_blocks_per_sequence=self.config.max_blocks_per_sequence,
            num_banks=self.config.banks.num_banks,
        )

        # Initialize metrics collector
        collector = MetricsCollector(controller_name="pcam")
        collector.start()

        # Allocate sequences
        for seq_id in trace.sequence_ids:
            pcam.allocate_sequence(seq_id, self.config.max_blocks_per_sequence)

        start_time = time.time()

        # Replay trace
        for i, step in enumerate(trace.steps):
            # ATTEND operation
            candidates, attend_latency, bank_conflicts = pcam.attend(
                query_block_id=step.query_block_id,
                k=self.config.topk.default_k,
                sequence_id=step.sequence_id,
            )

            # Record ATTEND metrics
            candidate_ids = [c[0] for c in candidates]
            collector.record_attend(
                latency_ns=attend_latency,
                candidates=candidate_ids,
                true_top_k=step.true_top_k,
                bank_conflicts=bank_conflicts,
            )

            # UPDATE operations for observed attention
            if step.attention_scores:
                block_ids = list(step.attention_scores.keys())
                weights = list(step.attention_scores.values())

                count, update_latency = pcam.update_batch(
                    sequence_id=step.sequence_id,
                    block_ids=block_ids,
                    weights=weights,
                    query_block_id=step.query_block_id,
                )

                collector.record_update(
                    latency_ns=update_latency,
                    count=count,
                )

            # Record token
            collector.record_token()

            # Apply decay periodically
            if i > 0 and i % self.config.decay_interval_steps == 0:
                pcam.decay(self.config.default_decay_rate)

            # Progress reporting
            if self.verbose and i > 0 and i % progress_interval == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                print(f"  Step {i}/{len(trace.steps)} ({rate:.0f} steps/sec)")

            pcam.step()

        elapsed_time = time.time() - start_time

        # Finalize metrics
        metrics = collector.finalize()

        # Record memory state
        stats = pcam.get_stats()
        collector.record_memory(
            entries=stats.get("total_edges", 0),
            sequences=stats.get("num_sequences", 0),
            edges=stats.get("total_edges", 0),
            budget_pct=1.0,
        )

        return SimulationResult(
            metrics=metrics,
            elapsed_time_sec=elapsed_time,
            events_per_sec=len(trace.steps) / elapsed_time if elapsed_time > 0 else 0,
            controller_name="pcam",
            trace_name=trace_name,
            config={"type": "pcam", "config": str(self.config)},
        )

    def run_baseline(
        self,
        trace: PCAMTrace,
        controller: BaselineController,
        trace_name: str = "unknown",
        progress_interval: int = 100,
    ) -> SimulationResult:
        """
        Run simulation using a baseline controller.

        Args:
            trace: Trace to replay
            controller: Baseline controller to use
            trace_name: Name for reporting
            progress_interval: Print progress every N steps

        Returns:
            SimulationResult with metrics
        """
        # Reset controller
        controller.reset()

        # Initialize metrics collector
        collector = MetricsCollector(controller_name=controller.name)
        collector.start()

        start_time = time.time()

        # Replay trace
        for i, step in enumerate(trace.steps):
            # Get candidates from controller
            candidates = controller.get_candidates(
                query_block=step.query_block_id,
                k=self.config.topk.default_k,
                sequence_id=step.sequence_id,
            )

            # Simulate latency (baseline has no hardware - pure software overhead)
            # Use a fixed overhead to represent hash table lookup
            attend_latency = 500.0  # 500ns software overhead

            # Record metrics
            candidate_ids = [c[0] for c in candidates]
            collector.record_attend(
                latency_ns=attend_latency,
                candidates=candidate_ids,
                true_top_k=step.true_top_k,
                bank_conflicts=0,
            )

            # Record access with actual attention scores
            controller.record_access(
                query_block=step.query_block_id,
                accessed_blocks=step.blocks_accessed,
                attention_scores=step.attention_scores,
                sequence_id=step.sequence_id,
            )

            # Record update latency (software hash table update)
            if step.attention_scores:
                update_latency = 200.0 * len(step.attention_scores)  # 200ns per update
                collector.record_update(
                    latency_ns=update_latency,
                    count=len(step.attention_scores),
                )

            # Record token
            collector.record_token()

            # Step controller
            controller.step()

            # Progress reporting
            if self.verbose and i > 0 and i % progress_interval == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                print(f"  Step {i}/{len(trace.steps)} ({rate:.0f} steps/sec)")

        elapsed_time = time.time() - start_time

        # Finalize metrics
        metrics = collector.finalize()

        # Get controller stats
        ctrl_stats = controller.get_stats()

        # Record hit rate
        if ctrl_stats.get("hits", 0) + ctrl_stats.get("misses", 0) > 0:
            collector.record_hit_rate(
                hits=ctrl_stats.get("hits", 0),
                total=ctrl_stats.get("hits", 0) + ctrl_stats.get("misses", 0),
            )

        return SimulationResult(
            metrics=metrics,
            elapsed_time_sec=elapsed_time,
            events_per_sec=len(trace.steps) / elapsed_time if elapsed_time > 0 else 0,
            controller_name=controller.name,
            trace_name=trace_name,
            config={"type": "baseline", "controller": controller.name},
        )

    def compare_results(
        self,
        results: List[SimulationResult],
    ) -> Dict:
        """
        Compare results from multiple runs.

        Returns comparison metrics and acceptance gate results.
        """
        if not results:
            return {}

        comparison = {
            "results": [],
            "best_throughput": None,
            "best_coverage": None,
            "best_latency": None,
        }

        best_throughput = -1
        best_coverage = -1
        best_latency = float('inf')

        for result in results:
            entry = {
                "controller": result.controller_name,
                "trace": result.trace_name,
                "throughput": result.metrics.throughput.tokens_per_second,
                "coverage": result.metrics.quality.mean_coverage,
                "attend_p50": result.metrics.attend_latency.p50,
                "attend_p99": result.metrics.attend_latency.p99,
                "elapsed_sec": result.elapsed_time_sec,
            }
            comparison["results"].append(entry)

            if entry["throughput"] > best_throughput:
                best_throughput = entry["throughput"]
                comparison["best_throughput"] = result.controller_name

            if entry["coverage"] > best_coverage:
                best_coverage = entry["coverage"]
                comparison["best_coverage"] = result.controller_name

            if entry["attend_p50"] < best_latency:
                best_latency = entry["attend_p50"]
                comparison["best_latency"] = result.controller_name

        # Check acceptance gates if PCAM result exists
        pcam_result = next(
            (r for r in results if r.controller_name == "pcam"),
            None
        )
        baseline_results = [r for r in results if r.controller_name != "pcam"]

        if pcam_result and baseline_results:
            # Find best baseline for comparison
            best_baseline = max(
                baseline_results,
                key=lambda r: r.metrics.throughput.tokens_per_second
            )

            gates = pcam_result.metrics.check_acceptance_gates(
                baseline_metrics=best_baseline.metrics
            )
            comparison["acceptance_gates"] = gates
            comparison["all_gates_passed"] = all(gates.values())

        return comparison

    def run_full_validation(
        self,
        traces: Dict[str, PCAMTrace],
        controllers: List[BaselineController],
    ) -> Dict:
        """
        Run full validation suite.

        Args:
            traces: Dict of trace_name -> trace
            controllers: List of baseline controllers to compare

        Returns:
            Comprehensive validation results
        """
        results = {
            "by_workload": {},
            "summary": {},
            "acceptance_gates": {},
        }

        for trace_name, trace in traces.items():
            if self.verbose:
                print(f"\n=== Running workload: {trace_name} ===")

            workload_results = []

            # Run PCAM
            if self.verbose:
                print(f"  Running PCAM...")
            pcam_result = self.run_pcam(trace, trace_name)
            workload_results.append(pcam_result)

            # Run baselines
            for controller in controllers:
                if self.verbose:
                    print(f"  Running {controller.name}...")
                baseline_result = self.run_baseline(trace, controller, trace_name)
                workload_results.append(baseline_result)

            # Compare
            comparison = self.compare_results(workload_results)
            results["by_workload"][trace_name] = comparison

        # Aggregate acceptance gates across workloads
        all_gates_passed = True
        for trace_name, comparison in results["by_workload"].items():
            gates = comparison.get("acceptance_gates", {})
            for gate_name, passed in gates.items():
                if gate_name not in results["acceptance_gates"]:
                    results["acceptance_gates"][gate_name] = []
                results["acceptance_gates"][gate_name].append({
                    "workload": trace_name,
                    "passed": passed,
                })
                if not passed:
                    all_gates_passed = False

        results["summary"]["all_gates_passed"] = all_gates_passed

        return results


def run_quick_validation(seed: int = 42, verbose: bool = True) -> Dict:
    """
    Run a quick validation to test the framework.

    Args:
        seed: Random seed for reproducibility
        verbose: Print progress

    Returns:
        Validation results
    """
    from .traces.generators import SyntheticTraceGenerator
    from .baselines import SinkLRUController, H2OController, IndustryStyleController

    if verbose:
        print("=== PCAM Quick Validation ===\n")

    # Generate traces
    generator = SyntheticTraceGenerator(seed=seed)

    traces = {
        "chat": generator.generate_chat_trace(num_turns=5, tokens_per_turn=(20, 50)),
        "long_context": generator.generate_long_context_trace(
            context_length=4096, num_queries=50
        ),
        "rag": generator.generate_rag_trace(num_docs=3, query_length=30),
    }

    # Create baselines
    config = ControllerConfig(cache_capacity=128, num_sinks=4, recent_window=32, top_k=32)
    controllers = [
        SinkLRUController(config),
        H2OController(config),
        IndustryStyleController(config),
    ]

    # Run validation
    simulator = PCAMSimulator(verbose=verbose)
    results = simulator.run_full_validation(traces, controllers)

    if verbose:
        print("\n=== Validation Summary ===")
        print(f"All gates passed: {results['summary']['all_gates_passed']}")
        for gate_name, gate_results in results["acceptance_gates"].items():
            passed = sum(1 for r in gate_results if r["passed"])
            total = len(gate_results)
            print(f"  {gate_name}: {passed}/{total} workloads passed")

    return results

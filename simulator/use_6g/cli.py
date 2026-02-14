"""
CLI entry point for USE-6G simulator.

Usage:
    python -m simulator.use_6g [--scenario SCENARIO] [--band BAND] [--elements N]
"""

import argparse
import json
import sys

from .core.config import USE6GConfig, FrequencyBand, FrequencyConfig, AntennaConfig
from .simulator import USE6GSimulator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="USE-6G: Universal Synchronization Engine for 6G Massive MIMO"
    )
    parser.add_argument(
        "--scenario",
        choices=["acquisition", "tracking", "multi_beam", "panel_handover", "all"],
        default="all",
        help="Scenario to run (default: all)",
    )
    parser.add_argument(
        "--band",
        choices=["fr3_upper", "fr2_mmwave", "sub_thz_low", "sub_thz_high"],
        default="sub_thz_low",
        help="Frequency band (default: sub_thz_low, 100-300 GHz)",
    )
    parser.add_argument(
        "--elements-x",
        type=int,
        default=8,
        help="Antenna elements along x-axis (default: 8)",
    )
    parser.add_argument(
        "--elements-y",
        type=int,
        default=8,
        help="Antenna elements along y-axis (default: 8)",
    )
    parser.add_argument(
        "--panels",
        type=int,
        default=2,
        help="Number of antenna panels (default: 2)",
    )
    parser.add_argument(
        "--duration-ms",
        type=float,
        default=100.0,
        help="Simulation duration in milliseconds (default: 100)",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=10,
        help="Number of trials for acquisition scenario (default: 10)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    # Build configuration
    band_map = {
        "fr3_upper": FrequencyBand.FR3_UPPER,
        "fr2_mmwave": FrequencyBand.FR2_MMWAVE,
        "sub_thz_low": FrequencyBand.SUB_THZ_LOW,
        "sub_thz_high": FrequencyBand.SUB_THZ_HIGH,
    }

    config = USE6GConfig(
        frequency=FrequencyConfig(band=band_map[args.band]),
        antenna=AntennaConfig(
            num_elements_x=args.elements_x,
            num_elements_y=args.elements_y,
            num_panels=args.panels,
        ),
        simulation_duration_ms=args.duration_ms,
        random_seed=args.seed,
    )

    sim = USE6GSimulator(config, verbose=not args.quiet)

    if args.scenario == "all":
        results = sim.run_all_scenarios()
        if args.json:
            output = {
                name: result.metrics.to_dict()
                for name, result in results.items()
            }
            print(json.dumps(output, indent=2))
        else:
            for name, result in results.items():
                print()
                print(result.summary())
    else:
        scenario_map = {
            "acquisition": lambda: sim.run_acquisition_scenario(num_trials=args.trials),
            "tracking": lambda: sim.run_beam_tracking_scenario(duration_ms=args.duration_ms),
            "multi_beam": lambda: sim.run_multi_beam_scenario(),
            "panel_handover": lambda: sim.run_panel_handover_scenario(duration_ms=args.duration_ms),
        }
        result = scenario_map[args.scenario]()

        if args.json:
            print(json.dumps(result.metrics.to_dict(), indent=2))
        else:
            print(result.summary())


if __name__ == "__main__":
    main()

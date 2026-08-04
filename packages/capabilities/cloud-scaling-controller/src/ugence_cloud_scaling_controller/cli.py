"""Offline command-line interface: ``ugence-cloud-scaling``.

Subcommands::

    ugence-cloud-scaling evaluate --input observation.json
    ugence-cloud-scaling evaluate --input - --output recommendation.json
    ugence-cloud-scaling demo
    ugence-cloud-scaling version

Contract:
  * Reads JSON (observation object, or ``{"observations": [...]}`` / a JSON array
    for a sequence through one persistent controller).
  * Emits JSON to stdout by default; ``--output`` writes to a file.
  * Diagnostics go to stderr; returns a nonzero exit code on invalid input.
  * Never actuates infrastructure, never requires cloud credentials, needs no
    network access, and generates no nondeterministic timestamps.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

from .api import CloudScalingController
from .contracts import ContractError, ScalingObservation
from .version import __version__

# Deterministic demo fixture: a short fixed sequence that warms the controller and
# then presents a high-load observation. The INPUT is fixed; decision fields are
# reproducible (identity_deviation is pre-existing nondeterminism — see docs).
DEMO_OBSERVATIONS: List[dict] = (
    [
        {
            "metrics": {"cpu": 0.45, "memory": 0.4, "latency_p99": 0.3,
                        "error_rate": 0.02, "queue_depth": 0.25},
            "current_replicas": 4,
            "phase": "normal",
            "correlation_id": "demo-warmup",
        }
    ]
    * 12
    + [
        {
            "metrics": {"cpu": 0.95, "memory": 0.9, "latency_p99": 0.88,
                        "error_rate": 0.25, "queue_depth": 0.82},
            "current_replicas": 4,
            "phase": "peak",
            "correlation_id": "demo-spike",
        }
    ]
)


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _read_input(path: str) -> Any:
    text = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(text)


def _normalize_payload(payload: Any) -> List[dict]:
    """Accept a single observation object, a JSON array, or {"observations": [...]}."""
    if isinstance(payload, dict) and "observations" in payload:
        payload = payload["observations"]
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return payload
    raise ContractError("input must be an object, an array, or {'observations': [...]}")


def _evaluate_sequence(observations: List[dict]) -> List[dict]:
    ctrl = CloudScalingController()
    out: List[dict] = []
    for item in observations:
        rec = ctrl.recommend(ScalingObservation.from_dict(item))
        out.append(rec.to_dict())
    return out


def _emit(results: List[dict], output: Optional[str], single: bool) -> None:
    payload: Any = results[0] if (single and len(results) == 1) else results
    text = json.dumps(payload, sort_keys=True, indent=2)
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        _eprint(f"wrote recommendation(s) to {output}")
    else:
        print(text)


def _cmd_evaluate(args: argparse.Namespace) -> int:
    try:
        payload = _read_input(args.input)
    except FileNotFoundError:
        _eprint(f"error: input file not found: {args.input}")
        return 2
    except json.JSONDecodeError as exc:
        _eprint(f"error: invalid JSON input: {exc}")
        return 2
    try:
        observations = _normalize_payload(payload)
        single = isinstance(payload, dict) and "observations" not in payload
        results = _evaluate_sequence(observations)
    except ContractError as exc:
        _eprint(f"error: invalid observation: {exc}")
        return 2
    _emit(results, args.output, single)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    results = _evaluate_sequence(DEMO_OBSERVATIONS)
    _emit([results[-1]], args.output, single=True)
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    print(json.dumps({"name": "ugence-cloud-scaling-controller",
                      "version": __version__}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ugence-cloud-scaling",
        description="Offline, advisory-only cloud scaling recommendation engine.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("evaluate", help="evaluate observation(s) from JSON")
    p_eval.add_argument("--input", "-i", required=True,
                        help="path to observation JSON, or '-' for stdin")
    p_eval.add_argument("--output", "-o", default=None,
                        help="write recommendation JSON to this file (default: stdout)")
    p_eval.set_defaults(func=_cmd_evaluate)

    p_demo = sub.add_parser("demo", help="run the deterministic demo fixture")
    p_demo.add_argument("--output", "-o", default=None,
                        help="write recommendation JSON to this file (default: stdout)")
    p_demo.set_defaults(func=_cmd_demo)

    p_ver = sub.add_parser("version", help="print the package version as JSON")
    p_ver.set_defaults(func=_cmd_version)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

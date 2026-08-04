"""Read-only shadow-harness CLI.

Every command is non-mutating. There is deliberately NO command that connects to a real
cluster with auto-discovered credentials. A future real command would require explicit
``--kubeconfig / --context / --cluster-id / --namespace / --allowlist / --read-only`` and
is not implemented here — this phase never contacts a remote endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from typing import List, Optional

from .config import ShadowValidationConfig, ShadowConfigError
from .evidence import list_schemas, load_schema, generate_fixture_evidence
from .integrity import scan_harness_source, verify_evidence_dir, reproduce_scenarios

_FIXTURE_BANNER = (
    "FAKE LOCAL SHADOW HARNESS RUN\n"
    "NO REAL CLUSTER ACCESSED\n"
    "NO REAL SHADOW VALIDATION PERFORMED"
)


def _canary_results() -> dict:
    # Lazy import: the canary tooling deliberately imports live executors to attack the
    # boundary; the harness core never does.
    from shadow_mutation_canaries import run_mutation_canaries
    return run_mutation_canaries()


def _cmd_validate_config(a) -> int:
    try:
        if a.input:
            with open(a.input, encoding="utf-8") as f:
                data = json.load(f)
            cfg = ShadowValidationConfig(**data)
        else:
            cfg = ShadowValidationConfig.fixture()
    except (ShadowConfigError, TypeError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"valid": True, "config": cfg.summary()}, sort_keys=True, indent=2))
    return 0


def _cmd_inspect_harness(_a) -> int:
    print(json.dumps({
        "harness": "cloud-scaling-operations read-only shadow validation",
        "phase": "environment-independent harness only",
        "real_environment_observed": False,
        "real_cluster_accessed": False,
        "execution_mode": "SHADOW",
        "allowed_methods": ["GET", "HEAD", "WATCH", "LIST"],
        "blocked_methods": ["POST", "PUT", "PATCH", "DELETE", "DELETECOLLECTION", "CONNECT"],
        "schemas": list_schemas(),
    }, indent=2, sort_keys=True))
    return 0


def _cmd_run_fixture(a) -> int:
    print(_FIXTURE_BANNER, file=sys.stderr)
    out = a.out or tempfile.mkdtemp(prefix="shadow-fixture-")
    aggregate = generate_fixture_evidence(out, canary_results=_canary_results())
    aggregate["_output_dir"] = out
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if aggregate["verdict"].endswith("FIXTURE_OK") else 1


def _cmd_verify_fixture(a) -> int:
    report = verify_evidence_dir(a.dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


def _cmd_mutation_canaries(_a) -> int:
    res = _canary_results()
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["all_blocked"] else 1


def _cmd_evidence_schema(a) -> int:
    if a.name:
        print(json.dumps(load_schema(a.name), indent=2, sort_keys=True))
    else:
        print(json.dumps({"schemas": list_schemas()}, indent=2, sort_keys=True))
    return 0


def _cmd_source_scan(_a) -> int:
    violations = scan_harness_source()
    print(json.dumps({"violations": violations, "clean": not violations},
                     indent=2, sort_keys=True))
    return 0 if not violations else 1


def _cmd_reproduce(_a) -> int:
    print(json.dumps(reproduce_scenarios(), indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ugence-cloud-scaling-operations shadow",
        description="Read-only shadow-validation harness (non-mutating; no real cluster).")
    sub = p.add_subparsers(dest="command", required=True)

    vc = sub.add_parser("validate-config")
    vc.add_argument("--input", "-i", default=None)
    vc.set_defaults(func=_cmd_validate_config)

    sub.add_parser("inspect-harness").set_defaults(func=_cmd_inspect_harness)

    rf = sub.add_parser("run-fixture")
    rf.add_argument("--out", "-o", default=None)
    rf.set_defaults(func=_cmd_run_fixture)

    vf = sub.add_parser("verify-fixture")
    vf.add_argument("--dir", "-d", required=True)
    vf.set_defaults(func=_cmd_verify_fixture)

    sub.add_parser("mutation-canaries").set_defaults(func=_cmd_mutation_canaries)
    sub.add_parser("source-scan").set_defaults(func=_cmd_source_scan)
    sub.add_parser("reproduce-scenarios").set_defaults(func=_cmd_reproduce)

    es = sub.add_parser("evidence-schema")
    es.add_argument("--name", "-n", default=None)
    es.set_defaults(func=_cmd_evidence_schema)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

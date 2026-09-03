"""Command line for the reference pilot: prepare | run | verify | render | replay."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from . import pipeline


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(prog="workflow_fit_reference_pilot", description=pipeline.USAGE_LABEL)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("prepare", help="build the benchmark and pilot manifests from the fixture documents")
    s.add_argument("--fixture", required=True, type=Path); s.add_argument("--out", required=True, type=Path)
    s = sub.add_parser("run", help="execute one synthetic scenario through the ratified runner and write a bundle")
    s.add_argument("--fixture", required=True, type=Path); s.add_argument("--prepared", required=True, type=Path); s.add_argument("--out", required=True, type=Path)
    s.add_argument("--scenario", required=True); s.add_argument("--transport", choices=("unix", "pipe"), default=None)
    for name, help_ in (("verify", "re-validate every artifact of a bundle; fail closed"), ("render", "verify, then print the 4A report"), ("replay", "verify and render without any provider")):
        s = sub.add_parser(name, help=help_); s.add_argument("--bundle", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.command == "prepare":
            m = pipeline.prepare(a.fixture, a.out)
            print(f"prepared manifest_digest={m.manifest_digest} [{pipeline.USAGE_LABEL}]")
        elif a.command == "run":
            r = pipeline.run(a.fixture, a.prepared, a.out, scenario=a.scenario, transport=a.transport)
            print(f"ran scenario={a.scenario} complete={sum(x.complete for x in r.runs)}/{len(r.runs)} [{pipeline.USAGE_LABEL}]")
        elif a.command == "verify":
            pipeline.verify(a.bundle)
            print(f"verified {a.bundle} [{pipeline.USAGE_LABEL}]")
        elif a.command == "render":
            print(pipeline.render_bundle(a.bundle))
        else:
            print(pipeline.replay(a.bundle))
    except Exception as e:  # every refusal is reported by class and detail; nothing is repaired
        print(f"REFUSED {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Assert the worker's DBOS pin exists, is honoured everywhere, and is not quietly widened.

BLOCKING, offline. Opens no socket, installs nothing, needs no container runtime.

**Why this exists.** Until 2026-09-10 nothing pinned DBOS: `dbos>=2.0` is a floor, so every
CI run and every image build resolved it independently and no two were guaranteed to
exercise the same engine. The Model Egress Unit's reconciliation driver depends on durable
resume semantics, and a design may not rest on an unspecified future 2.x
(`SPEC_MODEL_EGRESS_UNIT.md` §3.6).

**The separation this guard defends.** A package declares *compatibility*; a deployment
fixes a *version*. So:

- `dbos>=2.0` stays in both `pyproject.toml` files — that is the library contract, and
  replacing it with a pin would push a deployment concern into a package;
- `constraints.txt` pins `dbos==2.31.1` — that is the build, and it is applied with `-c`
  by CI and by the image alike.

A range such as `>=2.31.1,<2.32` satisfies neither: it is not a contract and it is not a
fixed version. It is refused here for that reason, not on style.

**What it does not prove.** That the deployed image runs this version. The image running
today was built under the unpinned floor and its DBOS version is UNKNOWN until a newly
constrained image is built and inspected — which is blocked on the base-image mirror
(RW-2). This gate reads files. It satisfies no ratified gate identifier of P3E-CTR or
GRW-CTR, and belongs to neither family.

    python deployment/governed-runtime-worker/ci/verify_dbos_constraint.py

Exit codes: 0 the pin holds everywhere; 1 a reference disagrees, the pin moved, or a
declared floor was replaced.
"""

from __future__ import annotations

import os
import re
import sys
from typing import List

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

#: The one place the deployment's version is fixed. Referenced, never duplicated.
CONSTRAINTS = "deployment/governed-runtime-worker/constraints.txt"

#: The version this deployment is exercised at, proven by CI run 86 on 2026-09-10.
PINNED = "dbos==2.31.1"

#: Every file that must apply the constraint, and the reference each must contain.
APPLIED_BY = {
    "deployment/governed-runtime-worker/Dockerfile": "-c /build/worker/constraints.txt",
    ".github/workflows/governed-runtime-worker-ci.yml": f"-c {CONSTRAINTS}",
}

#: Distributions that must keep declaring compatibility rather than a version.
DECLARE_THE_FLOOR = (
    "deployment/governed-runtime-worker/pyproject.toml",
    "packages/integration/durable-execution/pyproject.toml",
)

FLOOR = re.compile(r'"dbos>=2\.0"')
ANY_DBOS_REQUIREMENT = re.compile(r'"dbos[^"]*"')


def _read(relative: str) -> str:
    with open(os.path.join(REPO, relative), "r", encoding="utf-8") as handle:
        return handle.read()


def verify() -> List[str]:
    errors: List[str] = []

    # 1. The constraint exists and pins exactly what it claims to.
    try:
        text = _read(CONSTRAINTS)
    except FileNotFoundError:
        return [f"{CONSTRAINTS} does not exist; the deployment has no DBOS pin"]

    pins = [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")]
    if pins != [PINNED]:
        errors.append(
            f"{CONSTRAINTS} must contain exactly {PINNED!r} and no other constraint; "
            f"found {pins!r}. This file pins DBOS and nothing else — adding entries here "
            f"would imply a transitive reproducibility it does not provide.")
    print(f"ok   {CONSTRAINTS} pins {PINNED}")

    # 2. Every consumer applies it, and by the same path.
    for relative, reference in APPLIED_BY.items():
        body = _read(relative)
        if reference not in body:
            errors.append(f"{relative} does not apply the constraint; expected {reference!r}")
            print(f"FAIL {relative} — missing {reference!r}")
        else:
            print(f"ok   {relative} applies {reference}")

    # 3. The declarations stay compatibility floors, not versions.
    for relative in DECLARE_THE_FLOOR:
        body = _read(relative)
        found = ANY_DBOS_REQUIREMENT.findall(body)
        if not FLOOR.search(body):
            errors.append(
                f"{relative} no longer declares \"dbos>=2.0\"; found {found!r}. A package "
                f"declares compatibility. Pinning here would make a deployment's version "
                f"a library contract, which is what {CONSTRAINTS} exists to avoid.")
            print(f"FAIL {relative} — {found!r}")
        else:
            print(f"ok   {relative} declares the compatibility floor")

    # 4. Where DBOS is importable, it is the pinned version. Absent, this is not a failure:
    #    the gate runs in environments that install nothing.
    try:
        from importlib.metadata import version
        installed = version("dbos")
    except Exception:
        print("--   dbos is not installed here; the resolved version is not checked")
    else:
        expected = PINNED.split("==", 1)[1]
        if installed != expected:
            errors.append(f"the installed dbos is {installed}, not the pinned {expected}")
            print(f"FAIL installed dbos {installed} != pinned {expected}")
        else:
            print(f"ok   installed dbos {installed} matches the pin")

    return errors


def main() -> int:
    print("DBOS deployment constraint")
    errors = verify()
    print()
    if errors:
        print("DBOS CONSTRAINT CONFORMANCE FAILED", file=sys.stderr)
        for error in errors:
            print("  - " + error, file=sys.stderr)
        print(
            "\nA package declares compatibility (dbos>=2.0); a deployment fixes a version\n"
            "(constraints.txt). This gate reads files: it proves neither that an image was\n"
            "built nor which version the deployed worker runs, and satisfies no ratified\n"
            "gate identifier.",
            file=sys.stderr,
        )
        return 1
    print("dbos constraint conformance OK: pinned once, applied by every consumer, and the "
          "compatibility floors are intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

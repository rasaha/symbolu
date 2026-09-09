#!/usr/bin/env python3
"""Report workflows that queue work nothing will ever read, or re-download what they had.

Two defects, both measured on this repository rather than assumed.

**Superseded runs were never cancelled.** Three of ninety-three workflows declared a
``concurrency`` group. A four-commit push to one pull request therefore fanned out four
complete times, and all four kept running: failures kept arriving for commits that had
already been fixed, and the queue executed history while the current head waited behind
it. A superseded run proves nothing about the commit that replaced it.

**Almost nothing was cached.** Five of two hundred and fifty ``actions/setup-python``
steps set ``cache``, across five hundred and thirty separate ``pip install`` invocations.
Every job re-resolved and re-downloaded its dependencies from scratch — for jobs whose
actual test run is two to ten seconds, the install *is* the job. The eleven capability
suites together are about fifty seconds of real pytest against a twelve-minute median
run.

**What is checked, and what is not.** That every workflow declares a concurrency group,
and that every ``setup-python`` step declares a cache. Neither is a claim about speed:
this script cannot measure a runner, and a workflow can satisfy both and still be slow.
It checks that the two cheap mechanisms are present, because their absence is what made
the queue the bottleneck.

**On cancelling.** The standard group cancels in-flight runs for the same ref on pull
requests and never on a branch push, where each commit's run is the evidence that commit
was green. This script does not require that exact expression — a workflow with a real
reason to serialise instead is free to say so, and one does.
"""

from __future__ import annotations

import pathlib
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

#: Workflows exempt from the concurrency requirement, and a stated reason. Empty by
#: intent: an entry here is a decision somebody has to defend, not a place to park a
#: workflow. (``demo-export-publish`` is not exempt — it declares a group and chooses
#: ``cancel-in-progress: false``, which is the mechanism working, not an absence of it.)
EXEMPT_CONCURRENCY: dict[str, str] = {}

#: setup-python steps exempt from the cache requirement, and a stated reason.
EXEMPT_CACHE: dict[str, str] = {}


def _workflows():
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def _steps(document: dict):
    """Yield every step mapping in the document, with the job name it belongs to."""
    for job_name, job in (document.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict):
                yield job_name, step


def missing_concurrency() -> list[str]:
    """Workflows that declare no concurrency group."""
    found = []
    for path in _workflows():
        if path.name in EXEMPT_CONCURRENCY:
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        concurrency = document.get("concurrency")
        group = concurrency.get("group") if isinstance(concurrency, dict) else concurrency
        if not group:
            found.append(path.name)
    return found


def uncached_setup_python() -> list[str]:
    """``actions/setup-python`` steps that set no dependency cache."""
    found = []
    for path in _workflows():
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for index, (job_name, step) in enumerate(_steps(document)):
            if "actions/setup-python" not in str(step.get("uses", "")):
                continue
            location = f"{path.name}:{job_name}"
            if location in EXEMPT_CACHE:
                continue
            with_block = step.get("with") or {}
            if not with_block.get("cache"):
                found.append(location)
    return sorted(set(found))


def main() -> int:
    no_concurrency = missing_concurrency()
    no_cache = uncached_setup_python()
    total = len(_workflows())

    if not no_concurrency and not no_cache:
        print(f"WORKFLOW EFFICIENCY OK — all {total} workflows declare a concurrency "
              "group, and every setup-python step declares a dependency cache")
        return 0

    if no_concurrency:
        print(f"{len(no_concurrency)} of {total} workflows declare no concurrency group; "
              "a superseded run will keep occupying the queue:")
        for name in no_concurrency:
            print(f"  {name}")
    if no_cache:
        print(f"\n{len(no_cache)} setup-python steps declare no dependency cache; each "
              "re-downloads what the last job already had:")
        for location in no_cache:
            print(f"  {location}")
    print("\nAdd the missing declaration, or add an entry to the matching EXEMPT map "
          "with a reason.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

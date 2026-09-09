#!/usr/bin/env python
"""Generate the customer-demo repository content from this repository. One way only.

The demo repository (``rasaha/demo``) carries the three front ends and the studio's
frozen contract, and nothing else. It is **generated, never hand-edited**: this script is
the only thing that writes it, and anything committed to it by hand is lost on the next
export.

**What stays here.** The studio backend, the governed runtime worker, and every package
they compose stay in this repository and are deployed from it; the demo front ends reach
them by ``VITE_API_BASE_URL`` and ``WORKER_URL``. So do the ADRs, the audit records and
the gate files — a governance record must be able to say which tree it describes, and a
second copy destroys that.

**Why the verifiers run first.** Two proofs do not travel with the export.
``apps/authority-plane/scripts/verify-boundary.mjs`` binds the plane's manifest to the
worker's committed contract by hash, and that contract stays here; the studio's
``verify:version`` reads a P3D audit record that stays here too. The exported plane still
*behaves* as ruled — its proxy serves the four approved reads and refuses every write —
but the check that *proves* it cannot write is not in the export. This script therefore
runs those verifiers in **this** repository and refuses to export if any of them fails,
and records the result in ``EXPORT_PROVENANCE.json`` beside the source commit.

    python tools/export_demo.py --out /tmp/demo
    python tools/export_demo.py --out /tmp/demo --skip-verify   # never for a real export

Exit codes: 0 exported; 1 a verifier failed, nothing was written; 2 usage, a missing
source path, or a denied file reaching the output.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["DENY", "EXCLUDE_DIRS", "EXCLUDE_FILES", "SOURCES", "VERIFIERS", "copy_sources", "denied_files",
           "export", "run_verifiers"]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: What the demo repository contains. Everything else stays in this repository.
SOURCES: Tuple[Tuple[str, str], ...] = (
    ("apps/authority-plane", "apps/authority-plane"),
    ("apps/ugence-governance-studio/frontend", "apps/ugence-governance-studio/frontend"),
    ("apps/console", "apps/console"),
    # The frozen contract the studio frontend generates and verifies its client against.
    ("apps/ugence-governance-studio/contracts", "apps/ugence-governance-studio/contracts"),
)

#: Never copied: build output, dependencies, and the suites that need what stays here
#: (the plane's boundary test needs the worker's contract; the studio's e2e needs the
#: backend and two packages).
EXCLUDE_DIRS = frozenset({
    "node_modules", "dist", "dist-ssr", "build", "coverage", ".vite", ".git",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    "tests", "e2e", "test-results", "playwright-report",
})

#: Files that cannot function in the export, excluded so nobody runs one and concludes the
#: boundary is broken. The plane's verifier binds to the worker's contract, which stays
#: here; the test configurations have no suites once ``tests`` and ``e2e`` are dropped.
#: ``package.json`` is copied unchanged — the export rewrites no source file — so its
#: ``verify:boundary`` and ``test`` scripts belong to this repository, and the README
#: says so.
EXCLUDE_FILES = frozenset({
    "apps/authority-plane/scripts/verify-boundary.mjs",
    "apps/authority-plane/vitest.config.ts",
    "apps/ugence-governance-studio/frontend/vitest.config.ts",
    "apps/ugence-governance-studio/frontend/playwright.config.ts",
})

#: A governance record must never reach the export. Checked after the copy, not assumed.
DENY: Tuple[Tuple[str, str], ...] = (
    ("ADR_", "an architecture decision record"),
    ("CONTAINER_GATE", "a container gate record"),
    ("CONTAINER_COMPLETION", "a gate live-state record"),
    ("CONTAINER_RUNTIME_CAPABILITY", "a gate capability record"),
    ("BASE_IMAGE_MIRROR_DECISION", "a base-image ratification record"),
    ("BUILD_CONTEXT_EXCLUSION_DEFECT", "an audit record"),
    ("RAILWAY_HOSTING_DECISION", "an owner ruling record"),
    ("EXTERNAL_DEPLOYMENT_EVIDENCE", "a deployment evidence record"),
    ("AP3_ENTERPRISE_ISSUER_VALIDATION", "a validation record"),
)
DENY_DIRS = ("docs/audits", "docs/architecture")

#: Run in THIS repository, before anything is written. All are stdlib-Node scripts: they
#: need no npm install, and they open no socket.
VERIFIERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("authority-plane verify:boundary",
     ("node", "apps/authority-plane/scripts/verify-boundary.mjs")),
    ("studio verify:openapi",
     ("node", "apps/ugence-governance-studio/frontend/scripts/verify-openapi.mjs")),
    ("studio verify:api-boundary",
     ("node", "apps/ugence-governance-studio/frontend/scripts/verify-api-boundary.mjs")),
    ("studio verify:version",
     ("node", "apps/ugence-governance-studio/frontend/scripts/verify-version.mjs")),
    ("studio verify:tracked-sources",
     ("node", "apps/ugence-governance-studio/frontend/scripts/verify-tracked-sources.mjs")),
)

README = """# Ugence customer demo — generated content

**This repository is generated. Do not edit it by hand.** Every file here is written by
`tools/export_demo.py` in the source repository, and a hand edit is lost on the next
export. Open a change against the source repository instead; `EXPORT_PROVENANCE.json`
names the commit this content came from.

## What is here

The three front ends, and the studio's frozen API contract:

| Path | What it is | What it needs to run |
|---|---|---|
| `apps/ugence-governance-studio/frontend` | the Governance Studio | `VITE_API_BASE_URL` — the studio API, hosted from the source repository |
| `apps/authority-plane` | the Authority Plane, with its own static + read-only proxy front | `WORKER_URL` — the governed runtime worker, on a private network |
| `apps/console` | the control-plane console | `VITE_CONSOLE_API_URL` |

## What is not here, on purpose

The studio backend, the governed runtime worker and the packages they compose stay in the
source repository and are deployed from it. So do the architecture decision records, the
audit records and the container gate records: a governance record has to be able to say
which tree it describes, and a second copy takes that away.

Two proofs therefore do not travel with this export — the authority plane's boundary
verifier, which binds its manifest to the worker's committed contract by hash, and the
studio's version check, which reads an audit record. Both were **run in the source
repository before this content was written**, and `EXPORT_PROVENANCE.json` records the
result. The plane in this repository still behaves as ruled: its proxy serves the four
approved reads and refuses every write.

`npm run verify:boundary` and `npm test` appear in `package.json` because this content is
copied unchanged, but they belong to the source repository: the verifier script and the
test suites are not exported, since neither can run without what stays there. Building and
running works here — `npm ci && npm run build`, then `npm start` for the plane.

## The labels in the interface are deliberate

`PRESENTED_UNPROVEN`, `IN_PROCESS_ISSUER_ONLY`, `REFERENCE_GRADE_SHADOW_ONLY`, "Synthetic
demonstration data", and the plane's standing notice that no write is served before
enterprise issuer validation, are the product stating what it can and cannot prove. They
are not placeholders and must not be removed for a demonstration.
"""


# ---- verification ----------------------------------------------------------------- #

def run_verifiers(repo: str = REPO) -> List[Dict[str, object]]:
    """Every verifier that must hold in THIS repository before an export is written."""
    results: List[Dict[str, object]] = []
    for label, command in VERIFIERS:
        proc = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        ok = proc.returncode == 0
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()
        results.append({
            "verifier": label,
            "command": " ".join(command),
            "passed": ok,
            "exit_code": proc.returncode,
            "output": tail[-1] if tail else "",
        })
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            for line in tail[-6:]:
                print(f"        {line}")
    return results


# ---- the copy --------------------------------------------------------------------- #

def copy_sources(repo: str, out: str) -> int:
    """Copy every SOURCE into ``out``, dropping EXCLUDE_DIRS. Returns the file count."""
    count = 0
    for source, destination in SOURCES:
        src = os.path.join(repo, source)
        if not os.path.isdir(src):
            raise FileNotFoundError(f"source path missing: {source}")
        for root, dirs, files in os.walk(src):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
            relative = os.path.relpath(root, src)
            target = os.path.join(out, destination) if relative == "." else \
                os.path.join(out, destination, relative)
            os.makedirs(target, exist_ok=True)
            for name in sorted(files):
                rel = os.path.relpath(os.path.join(root, name), repo).replace(os.sep, "/")
                if rel in EXCLUDE_FILES:
                    continue
                shutil.copy2(os.path.join(root, name), os.path.join(target, name))
                count += 1
    return count


def denied_files(out: str) -> List[str]:
    """Any governance record that reached the output. Empty is the only acceptable answer."""
    hits: List[str] = []
    for root, _dirs, files in os.walk(out):
        relative_root = os.path.relpath(root, out).replace(os.sep, "/")
        for name in files:
            path = f"{relative_root}/{name}" if relative_root != "." else name
            if any(path.startswith(d) or f"/{d}/" in f"/{path}" for d in DENY_DIRS):
                hits.append(path)
                continue
            if any(name.startswith(prefix) for prefix, _ in DENY):
                hits.append(path)
    return hits


# ---- the export ------------------------------------------------------------------- #

def _commit(repo: str) -> str:
    proc = subprocess.run(("git", "rev-parse", "HEAD"), cwd=repo, capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def export(out: str, repo: str = REPO, skip_verify: bool = False) -> int:
    print(f"exporting from {repo}\n           to {out}\n")
    print("verifying in the source repository:")
    if skip_verify:
        print("  SKIPPED (--skip-verify). This output must not be published.")
        results: List[Dict[str, object]] = []
    else:
        results = run_verifiers(repo)
        if not all(r["passed"] for r in results):
            failed = [str(r["verifier"]) for r in results if not r["passed"]]
            print(f"\nEXPORT REFUSED: {len(failed)} verifier(s) failed: {', '.join(failed)}",
                  file=sys.stderr)
            print("Nothing was written. The export carries no boundary verifier of its own,\n"
                  "so an export from an unverified tree would ship a plane whose proof of\n"
                  "no-write stayed behind.", file=sys.stderr)
            return 1

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    try:
        count = copy_sources(repo, out)
    except FileNotFoundError as exc:
        print(f"EXPORT FAILED: {exc}", file=sys.stderr)
        shutil.rmtree(out, ignore_errors=True)
        return 2

    denied = denied_files(out)
    if denied:
        print(f"EXPORT FAILED: {len(denied)} governance record(s) reached the output:",
              file=sys.stderr)
        for path in denied[:10]:
            print(f"  - {path}", file=sys.stderr)
        shutil.rmtree(out, ignore_errors=True)
        return 2

    provenance = {
        "schema": "ugence.demo-export-provenance.v1",
        "generated_by": "tools/export_demo.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": "rasaha/symbolu",
        "source_commit": _commit(repo),
        "one_way": ("This content is generated. It is never edited in place; a change is "
                    "made in the source repository and re-exported."),
        "exported_paths": [source for source, _ in SOURCES],
        "verifiers_run_in_the_source_repository": results,
        "verifiers_skipped": bool(skip_verify),
        "what_stays_in_the_source_repository": [
            "apps/ugence-governance-studio/backend and the packages it composes",
            "deployment/governed-runtime-worker, including the authority-plane contract "
            "the plane's boundary verifier binds to by hash",
            "docs/architecture (the ADRs) and docs/audits (the audit and gate records)",
        ],
        "files_withheld_because_they_cannot_run_here": sorted(EXCLUDE_FILES),
        "proofs_that_do_not_travel": [
            "apps/authority-plane/scripts/verify-boundary.mjs — the worker's contract stays "
            "in the source repository, so this verifier cannot run here; it ran there, above",
            "the studio's verify:version — reads a P3D audit record that stays there",
        ],
        "maturity_labels": ("PRESENTED_UNPROVEN, IN_PROCESS_ISSUER_ONLY and "
                            "REFERENCE_GRADE_SHADOW_ONLY are shown by the applications on "
                            "purpose and must not be removed for a demonstration."),
        "file_count": count,
    }
    with open(os.path.join(out, "EXPORT_PROVENANCE.json"), "w", encoding="utf-8") as handle:
        json.dump(provenance, handle, indent=2)
        handle.write("\n")
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(README)

    print(f"\nexported {count} files from {len(SOURCES)} paths")
    print(f"wrote    EXPORT_PROVENANCE.json (source commit {provenance['source_commit'][:8]})")
    print("wrote    README.md")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="export_demo.py",
        description="Generate the customer-demo repository content. One way; never hand-edited.")
    parser.add_argument("--out", required=True, help="output directory (replaced if it exists)")
    parser.add_argument("--repo", default=REPO, help="source repository (default: this one)")
    parser.add_argument("--skip-verify", action="store_true",
                        help="skip the source-repository verifiers; the output must not be published")
    args = parser.parse_args(argv)
    return export(os.path.abspath(args.out), repo=args.repo, skip_verify=args.skip_verify)


if __name__ == "__main__":
    raise SystemExit(main())

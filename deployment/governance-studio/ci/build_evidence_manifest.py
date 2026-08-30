"""Build the P3E container evidence manifest from THIS run's output only.

The manifest previously hashed whatever sat in a repository directory. Seven
reference records are committed there — several of them stating
``"result": "NOT_EXECUTED"`` — so a run that never scanned anything still
reported non-null scan hashes, and an incomplete run could look evidenced.

This builder closes that off:

* it reads only ``--evidence-dir``, a fresh run-scoped directory outside the
  checked-out repository (``RUNNER_TEMP``, keyed by run id and attempt), so a
  committed or stale file is not reachable in the first place;
* an artifact is hashed only when its producer step reported ``success`` in this
  run. A producer that failed, was skipped, or never ran yields a null hash, the
  producer's status, and marks the manifest INCOMPLETE — there is no fallback to
  a pre-existing file, even one sitting in the evidence directory;
* every entry records the producing step, and the manifest records the
  repository commit, workflow run id and run attempt.

A manifest is COMPLETE only when every mandatory obligation was produced by this
run. Completeness is a property of the run, not a gate result: this script marks
no gate passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# artifact file -> (manifest key, producing workflow step, mandatory)
ARTIFACTS = {
    "runtime-image-packages.txt": ("runtime_package_inventory", "runtime-package-inventory", True),
    "secret-scan.json": ("secret_scan", "image-layer-secret-scan", True),
    "sbom.image.cdx.json": ("sbom", "image-sbom", True),
    "container-scan.json": ("vuln_report", "container-vulnerability-scan", True),
    "runtime-egress-report.json": ("egress_report", "container-runtime-verification", True),
}
SUCCESS = "success"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build(evidence_dir: str, producers: dict[str, str], commit: str,
          run_id: str, run_attempt: str, image_id: str | None = None,
          dockerfile_sha256: str | None = None) -> dict:
    entries: dict[str, dict] = {}
    incomplete: list[str] = []

    for filename, (key, step, mandatory) in sorted(ARTIFACTS.items(), key=lambda kv: kv[1][0]):
        outcome = producers.get(step, "did-not-run")
        path = os.path.join(evidence_dir, filename)
        present = os.path.isfile(path)

        if outcome == SUCCESS and present:
            entry = {"sha256": _sha256(path), "bytes": os.path.getsize(path),
                     "producer_step": step, "producer_outcome": outcome,
                     "status": "PRESENT"}
        else:
            if outcome != SUCCESS:
                # A file present without a successful producer is NOT evidence:
                # it was pre-populated, left by a failed producer, or stale.
                status = "NOT_PRODUCED_THIS_RUN"
            else:
                status = "PRODUCER_SUCCEEDED_BUT_ARTIFACT_MISSING"
            entry = {"sha256": None, "bytes": None,
                     "producer_step": step, "producer_outcome": outcome,
                     "status": status,
                     "file_present_but_disregarded": bool(present and outcome != SUCCESS)}
            if mandatory:
                incomplete.append(key)
        entries[key] = entry

    return {
        "schema": "p3e-evidence-manifest.v2",
        "run_completeness": "COMPLETE" if not incomplete else "INCOMPLETE",
        "missing_mandatory_evidence": sorted(incomplete),
        "evidence_source": "run-scoped directory outside the repository; committed and "
                           "pre-existing files are unreachable by construction",
        "evidence_dir": evidence_dir,
        "source_commit": commit,
        "workflow_run_id": run_id,
        "workflow_run_attempt": run_attempt,
        "image_id": image_id or None,
        "dockerfile_sha256": dockerfile_sha256 or None,
        "artifacts": entries,
        "gate_note": "Completeness describes this run's evidence only. No container gate is "
                     "marked passed by this manifest.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--producers", required=True,
                    help='JSON object mapping workflow step name -> outcome')
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    ap.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    ap.add_argument("--image-id", default=os.environ.get("IMAGE_ID", ""))
    ap.add_argument("--dockerfile-sha256", default=os.environ.get("DOCKERFILE_SHA256", ""))
    a = ap.parse_args(argv)

    man = build(a.evidence_dir, json.loads(a.producers), a.commit,
                a.run_id, a.run_attempt, a.image_id, a.dockerfile_sha256)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2)
        fh.write("\n")
    print(json.dumps(man, indent=2))
    # An incomplete run is reported, not failed: completeness is the caller's call.
    return 0


if __name__ == "__main__":
    sys.exit(main())

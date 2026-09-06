#!/usr/bin/env python3
"""Measured gate-deletion mutation sweep for the signed-snapshot resolver.

Each gate below is one load-bearing check in ``authority/trust_snapshot.py`` (or
the two shipped directories' ``as_of`` handling), neutralized by a textual
substitution in a copy of the package; the resolver conformance suite runs
against the copy and the result is KILLED (something failed) or SURVIVED. A
survivor is reported and classified, never designed away; a mutation that no
longer applies is an error, never a silent skip.

Run:  python packages/trusted-evidence-authority/scripts/resolver_mutation_sweep.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

PKG = pathlib.Path(__file__).resolve().parents[1]
SRC_REL = pathlib.Path("src") / "ugence_trusted_evidence_authority" / "authority"
SUITE = "tests/authority/test_signed_snapshot_resolver_conformance.py"

#: (id, category, module, description, old, new)
GATES = [
    ("S-01", "instant", "trust_snapshot.py", "as_of exact aware datetime required",
     "        if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:",
     "        if False:"),
    ("S-02", "admission", "trust_snapshot.py", "unadmitted snapshot refuses every resolution",
     "        if self._load_failure is not None or snapshot is None or root is None:",
     "        if snapshot is None or root is None:"),
    ("S-03", "root-lifecycle", "trust_snapshot.py", "publication root usable at as_of",
     "        if root.lifecycle_refusal_at(as_of) is not None:", "        if False:"),
    ("S-04", "window", "trust_snapshot.py", "set published and in force at as_of",
     "        if as_of < manifest.published_at or as_of < manifest.effective_from:", "        if False:"),
    ("S-05", "freshness", "trust_snapshot.py", "signed effective_to bounds freshness",
     "        if as_of >= manifest.effective_to:", "        if False:"),
    ("S-06", "freshness", "trust_snapshot.py", "published_at + max age bounds freshness",
     "        if as_of >= manifest.published_at + self._max_snapshot_age:", "        if False:"),
    ("S-07", "freshness", "trust_snapshot.py", "half-open age boundary (>= not >)",
     "        if as_of >= manifest.published_at + self._max_snapshot_age:",
     "        if as_of > manifest.published_at + self._max_snapshot_age:"),
    ("S-08", "coordinate", "trust_snapshot.py", "exact coordinate lookup, miss refuses",
     "        anchor = self._anchors.get(coordinate)\n        if anchor is None:",
     "        anchor = self._anchors.get(coordinate) or next(iter(self._anchors.values()), None)\n        if anchor is None:"),
    ("S-09", "root", "trust_snapshot.py", "absent root refuses",
     "        if publication_root is None:\n            return refused(", "        if False:\n            return refused("),
    ("S-10", "root", "trust_snapshot.py", "root must hold the publication capability",
     "        if publication_root.capability is not TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION:",
     "        if False:"),
    ("S-11", "root", "trust_snapshot.py", "manifest publisher must be the pinned root",
     "        if manifest.publisher_coordinate != publication_root.coordinate:", "        if False:"),
    ("S-12", "self-authentication", "trust_snapshot.py", "publisher's key inside the set refuses",
     "            if anchor.authority_id == publication_root.authority_id and anchor.key_id == publication_root.key_id:",
     "            if False:"),
    ("S-13", "self-authentication", "trust_snapshot.py", "root public key inside the set refuses",
     "            if anchor.public_key == publication_root.public_key:", "            if False:"),
    ("S-14", "signature", "trust_snapshot.py", "manifest signature must verify",
     "        if verified is not True:", "        if False:"),
    ("S-15", "rollback", "trust_snapshot.py", "version must exceed the last accepted",
     "        if last_accepted_set_version is not None and manifest.trust_anchor_set_version <= last_accepted_set_version:",
     "        if False:"),
    ("S-16", "rollback", "trust_snapshot.py", "equal version is a rollback (<= not <)",
     "        if last_accepted_set_version is not None and manifest.trust_anchor_set_version <= last_accepted_set_version:",
     "        if last_accepted_set_version is not None and manifest.trust_anchor_set_version < last_accepted_set_version:"),
    ("S-17", "document", "trust_snapshot.py", "unavailable document refuses",
     "        if document is None:\n            return refused(", "        if False:\n            return refused("),
    ("S-18", "document", "trust_snapshot.py", "canonical rendering required",
     "    if render_trust_anchor_set_document(snapshot) != document:", "    if False:"),
    ("S-19", "collection", "trust_snapshot.py", "collection digest must match",
     "        if digest != self.manifest.anchor_collection_digest:", "        if False:"),
    ("S-20", "collection", "trust_snapshot.py", "anchor count must match",
     "        if self.manifest.anchor_count != len(self.anchors):", "        if False:"),
    ("S-21", "collection", "trust_snapshot.py", "duplicate coordinate refuses",
     "            if anchor.coordinate in seen:", "            if False:"),
    ("S-22", "collection", "trust_snapshot.py", "canonical record order required",
     "            if previous_key is not None and key < previous_key:", "            if False:"),
    ("S-23", "collection", "trust_snapshot.py", "no publication-capability anchor inside a set",
     "            if anchor.capability is TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION:", "            if False:"),
    ("S-24", "collection", "trust_snapshot.py", "every record names this set and version",
     "            if anchor.trust_anchor_set_version != str(self.manifest.trust_anchor_set_version):", "            if False:"),
    ("S-25", "posture", "trust_snapshot.py", "production authority only after admission",
     "        return self._load_failure is None\n", "        return True\n"),
    ("S-26", "frame", "trust_snapshot.py", "publication domain bound into the signed bytes",
     "            TRUST_ANCHOR_SET_PUBLICATION_SIGNING_DOMAIN.encode(\"utf-8\"),\n            manifest.canonical_bytes(),",
     "            manifest.canonical_bytes(),"),
    ("S-27", "manifest", "trust_snapshot.py", "set version must be a positive int",
     "        if type(self.trust_anchor_set_version) is not int or self.trust_anchor_set_version < 1:", "        if False:"),
    ("S-28", "manifest", "trust_snapshot.py", "validity window strictly ordered",
     "        require_strictly_before(\n            self.effective_from,\n            self.effective_to,",
     "        (lambda *a, **k: None)(\n            self.effective_from,\n            self.effective_to,"),
    ("S-29", "directories", "trust.py", "deny-all keeps refusing with as_of",
     "        return TrustAnchorResolution.refused(\n            coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED\n        )\n\n    def __repr__(self) -> str:\n        return \"DenyAllTrustAnchorDirectory()\"",
     "        return TrustAnchorResolution.refused(\n            coordinate, _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING\n        )\n\n    def __repr__(self) -> str:\n        return \"DenyAllTrustAnchorDirectory()\""),
    ("S-30", "parse", "trust_snapshot.py", "document schema pinned",
     "    if root[\"document_schema\"] != TRUST_ANCHOR_SET_DOCUMENT_SCHEMA_V1:", "    if False:"),
]

#: Survivors that are understood. Each entry is a classification, not an excuse.
#: EQUIVALENT_DEFENSE_IN_DEPTH: another check makes the mutated branch unreachable,
#: so no observable behaviour changes; the gate stays in the source because it
#: states the property at the seam where a reader looks for it.
CLASSIFIED_SURVIVORS: dict = {
    "S-02": "EQUIVALENT_DEFENSE_IN_DEPTH: the constructor sets snapshot=None whenever "
            "load_failure is set, so the remaining `snapshot is None or root is None` "
            "test refuses every unadmitted resolver identically.",
    "S-09": "EQUIVALENT_DEFENSE_IN_DEPTH: the exact-type check on the next line refuses "
            "None with the same PUBLICATION_ROOT_ABSENT failure.",
    "S-30": "EQUIVALENT_DEFENSE_IN_DEPTH: the canonical-rendering check re-renders the "
            "document with the pinned schema constant, so a document naming any other "
            "schema differs from its own re-rendering and is refused as malformed.",
}


def _run_suite(working: pathlib.Path) -> tuple:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", SUITE, "-q", "-x", "-o", "addopts=", "-p", "no:cacheprovider"],
        cwd=str(working), env=env, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, ""
    lines = [l for l in result.stdout.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")]
    if lines:
        return False, lines[0].split(" - ", 1)[0].strip()
    tail = result.stdout.strip().splitlines()
    return False, tail[-1] if tail else "no output"


def main() -> int:
    print(f"gates inventoried: {len(GATES)}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="tea-resolver-mutants-"))
    pristine = work / "pristine"
    working = work / "working"
    ledger = []
    try:
        shutil.copytree(PKG, pristine, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build", "dist", "*.egg-info"))
        shutil.copytree(pristine, working)
        ok, detail = _run_suite(working)
        if not ok:
            print(f"BASELINE FAILED on the pristine tree: {detail}")
            return 1
        killed = survived = 0
        for gate_id, category, module, description, old, new in GATES:
            shutil.rmtree(working)
            shutil.copytree(pristine, working)
            target = working / SRC_REL / module
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(f"ERROR {gate_id}: mutation target appears {text.count(old)} times in {module}")
                return 1
            target.write_text(text.replace(old, new), encoding="utf-8")
            ok, detail = _run_suite(working)
            status = "SURVIVED" if ok else "KILLED"
            if ok:
                survived += 1
            else:
                killed += 1
            ledger.append({"gate": gate_id, "category": category, "module": module,
                           "description": description, "status": status, "first_failure": detail,
                           "classification": CLASSIFIED_SURVIVORS.get(gate_id)})
            print(f"{'ok  ' if not ok else 'SURV'}  {gate_id} {status:8s} {category:20s} {detail[:80]}")
        print(f"TOTALS  inventoried {len(GATES)}  killed {killed}  survived {survived}")
        unclassified = [r["gate"] for r in ledger if r["status"] == "SURVIVED" and not r["classification"]]
        (PKG / "resolver_mutation_ledger.json").write_text(
            json.dumps({"gates_inventoried": len(GATES), "killed": killed, "survived": survived,
                        "ledger": ledger}, indent=2) + "\n", encoding="utf-8")
        if unclassified:
            print(f"UNCLASSIFIED SURVIVORS: {unclassified}")
            return 1
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

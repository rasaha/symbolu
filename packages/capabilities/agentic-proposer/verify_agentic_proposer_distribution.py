#!/usr/bin/env python3
"""Reproducible independent-packaging proof for ``ugence-agentic-proposer`` (S0).

Builds the wheel + sdist, audits wheel contents, installs the wheel into a fresh
virtualenv with NO monorepo path, and proves the S0 skeleton behaves outside the
repository:

  1. build wheel + sdist and record artifact hashes;
  2. audit wheel contents — only ``ugence_agentic_proposer`` source + metadata;
     ``py.typed`` present; NO tests/docs; NO foreign Ugence package bundled;
  3. build the ``ugence-jcs`` dependency wheel from the sibling package into a local
     wheelhouse, clean-install this wheel against it and, with no ``/symbolu`` on
     ``sys.path``: read the
     version, exercise the ratified D4 vocabulary, assert the public surface is
     exactly that vocabulary, and assert that importing the public API loads none
     of the forbidden capability, legacy-framework, network or model-SDK modules —
     the same boundary the source-tree suite proves statically;
  4. report wheel reproducibility honestly.

S0 declares no public-API snapshot and freezes no contract, so there is nothing
here that asserts a frozen API shape.

Run:  python packages/capabilities/agentic-proposer/verify_agentic_proposer_distribution.py
Exit 0 on success; non-zero on the first failed step.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
#: ugence-jcs is a core dependency and is not published to an index, so the clean
#: install resolves it from a locally built wheel. Building it here also proves the
#: declared dependency is satisfiable rather than aspirational.
JCS_PKG = PKG.parents[1] / "jcs"

#: A fixed timestamp so wheel zip entries are deterministic (bit-for-bit builds).
_BUILD_ENV = {**os.environ, "SOURCE_DATE_EPOCH": "1704067200", "PYTHONHASHSEED": "0"}

CLEAN_INSTALL_CHECK = r'''
import sys
import ugence_agentic_proposer as ap

assert ap.__version__ == "0.0.1", ap.__version__
assert "site-packages" in ap.__file__, ap.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

# --- ratified D4 vocabulary ---
assert {m.value for m in ap.TerminalOutcome} == {
    "PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"}
assert {m.value for m in ap.CandidateDisposition} == {
    "RECOMMEND_MATCHED_FOR_APPROVAL", "RECOMMEND_WITHHOLD",
    "REQUEST_EVIDENCE", "ESCALATE_EXCEPTION"}
assert {m.value for m in ap.SemanticAuditorFindingStatus} == {
    "CONSISTENT", "INCONSISTENT", "INDETERMINATE", "CONFLICTING"}

# No outcome or disposition is a reserved authority claim.
reserved = ap.RESERVED_AUTHORITY_VOCABULARY
assert not {m.value for m in ap.TerminalOutcome} & reserved
assert not {m.value for m in ap.CandidateDisposition} & reserved
# INDETERMINATE is reserved in those two positions and ratified only for the auditor.
assert "INDETERMINATE" in reserved
assert ap.SemanticAuditorFindingStatus.INDETERMINATE.value == "INDETERMINATE"

# The public surface is exactly the vocabulary plus the version.
assert set(ap.__all__) == {
    "TerminalOutcome", "CandidateDisposition", "SemanticAuditorFindingStatus",
    "RESERVED_AUTHORITY_VOCABULARY", "__version__"}, ap.__all__

# --- leaf boundary, observed at runtime in a clean interpreter ---
FORBIDDEN = {"agentic", "agent_runtime_migration", "ugence_agent_runtime",
             "ugence_decision_authority", "ugence_actiongate_provider",
             "ugence_action_clearance", "ugence_storygraph",
             "ugence_agent_workforce_composer", "ugence_policy_workflow_compiler",
             "cer_v0_1", "cer_v0_2", "cer_v0_3", "action_gate_ref",
             "control_plane", "cloud_controller",
             "requests", "httpx", "socket", "openai", "anthropic"}
loaded = {m.split(".")[0] for m in sys.modules}
assert not (loaded & FORBIDDEN), sorted(loaded & FORBIDDEN)

print("S0_OK:" + ap.__version__)
'''

FORBIDDEN_WHEEL_SUBSTRINGS = ("agentic_framework", "agent_runtime", "cer_v0_",
                              "action_gate", "control_plane", "cloud_controller",
                              "ugence_jcs", "/tests/", "conftest", "/docs/")


def _run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(outdir: Path) -> tuple[Path, Path]:
    _run([sys.executable, "-m", "build", "--outdir", str(outdir), str(PKG)], env=_BUILD_ENV)
    wheels = list(outdir.glob("*.whl"))
    sdists = list(outdir.glob("*.tar.gz"))
    assert wheels and sdists, "build did not produce wheel + sdist"
    return wheels[0], sdists[0]


def _audit_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert any(n.endswith("ugence_agentic_proposer/py.typed") for n in names), \
        "py.typed missing from wheel"
    assert any(n.endswith("ugence_agentic_proposer/vocabulary.py") for n in names), \
        "vocabulary.py missing from wheel"
    for name in names:
        low = name.lower()
        if not (low.startswith("ugence_agentic_proposer/")
                or low.startswith("ugence_agentic_proposer-")):
            raise AssertionError(f"foreign wheel entry {name!r}")
        for bad in FORBIDDEN_WHEEL_SUBSTRINGS:
            assert bad not in low, f"forbidden wheel content {name!r} (matched {bad!r})"
    print("  wheel audit OK:", len(names), "entries; py.typed present; no foreign content")


def main() -> int:
    print("== build ==")
    work = Path(tempfile.mkdtemp(prefix="agentic_proposer_dist_"))
    try:
        dist1 = work / "dist1"
        wheel1, sdist1 = _build(dist1)
        print("  wheel:", wheel1.name, _sha256(wheel1)[:16])
        print("  sdist:", sdist1.name, _sha256(sdist1)[:16])

        print("== wheel content audit ==")
        _audit_wheel(wheel1)

        print("== clean-install outside the repo ==")
        env_dir = work / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / "bin" / "python"
        # ugence-jcs is unpublished; build it from the sibling package so the declared
        # dependency resolves from a real wheel rather than being skipped.
        wheelhouse = work / "wheelhouse"
        _run([sys.executable, "-m", "build", "--outdir", str(wheelhouse), str(JCS_PKG)],
             env=_BUILD_ENV, stdout=subprocess.DEVNULL)
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(wheelhouse), str(wheel1)])
        # The dependency is installed, but the S0 skeleton must not import it: S0
        # implements no proposal identity.
        _run([str(py), "-c", "import ugence_jcs; assert ugence_jcs.__version__"],
             stdout=subprocess.DEVNULL)

        for i in (1, 2):  # two SEPARATE processes
            res = _run([str(py), "-c", CLEAN_INSTALL_CHECK], capture_output=True, text=True)
            line = [l for l in res.stdout.splitlines() if l.startswith("S0_OK:")][0]
            print(f"  process {i}: vocabulary + leaf boundary OK ({line[6:]})")

        print("== reproducibility ==")
        dist2 = work / "dist2"
        wheel2, sdist2 = _build(dist2)
        print(f"  wheel bit-for-bit reproducible: {_sha256(wheel1) == _sha256(wheel2)}")
        print(f"  sdist bit-for-bit reproducible: {_sha256(sdist1) == _sha256(sdist2)} "
              f"(content-stable; gzip mtime may vary)")

        print("\nARTIFACT HASHES")
        print("  wheel:", _sha256(wheel1))
        print("  sdist:", _sha256(sdist1))
        print("\nAGENTIC_PROPOSER_S0_DISTRIBUTION_VERIFIED")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

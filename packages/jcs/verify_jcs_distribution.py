#!/usr/bin/env python3
"""Reproducible independent-packaging proof for ``ugence-jcs``.

Builds the wheel + sdist, audits wheel contents, installs the wheel into a fresh
virtualenv with NO monorepo path and NO index access, and proves the canonicalizer
behaves identically outside the repository:

  1. build wheel + sdist and record artifact hashes;
  2. audit wheel contents — only ``ugence_jcs`` source + metadata; ``py.typed``
     present; NO tests/docs; NO foreign package bundled;
  3. clean-install the wheel with ``--no-index`` (it must need nothing at all) and,
     with no ``/symbolu`` on ``sys.path``, reproduce the frozen canonical-byte
     vectors captured before extraction, confirm ``canonical_sha256_hex`` digests
     those same bytes, confirm the Action-Profile rejections,
     confirm no forbidden module is loaded, and prove determinism ACROSS TWO
     SEPARATE PROCESSES;
  4. report wheel reproducibility honestly.

Run:  python packages/jcs/verify_jcs_distribution.py
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

#: A fixed timestamp so wheel zip entries are deterministic (bit-for-bit builds).
_BUILD_ENV = {**os.environ, "SOURCE_DATE_EPOCH": "1704067200", "PYTHONHASHSEED": "0"}

CLEAN_INSTALL_CHECK = r'''
import hashlib, sys
import ugence_jcs
from ugence_jcs import canonical_bytes, canonical_sha256_hex
from ugence_jcs.errors import (BareNumberError, DuplicateSetElementError,
                               NonFiniteNumberError, NonNFCError, UnsupportedTypeError)

assert ugence_jcs.__version__ == "0.2.0", ugence_jcs.__version__
assert "site-packages" in ugence_jcs.__file__, ugence_jcs.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

# Canonical-byte vectors captured from cer_v0_3/cleanroom/canon.py BEFORE extraction.
VECTORS = [
    ({"b": "1", "a": "2"}, frozenset(),
     "f7a837dc9b605d08d450f14bb4927ae8ab268b757d17b579b4e8e61500d87c4a"),
    ({"s": ["b", "a", "c"]}, frozenset({"s"}),
     "0ddc22f3560af6a4745e12d3f5d4494ab6bc254204fbbf9db57d0d6b2e80d442"),
    ({"t": "a\tb\nc\"d\\e\x01f\x1f"}, frozenset(),
     "b5c62320cba9d0188d729b636d87d4e253e68c6d99f093ab77c18a3cd49009ea"),
    ({"u": "café 中文 \U0001F600"}, frozenset(),
     "74914e10ec99775cea06641ae1bff2fd3b7682fbe27466f3c75b739c689de235"),
    ({"a": "1", "A": "2", "é": "3", "\U0001F600": "4", "b": "5", "ﬀ": "6"},
     frozenset(),
     "1dde3b94ff5ec761182b96f039c7ce017cd6f34896ca7797842fa5fe60b32676"),
    ({"nested": {"arr": [{"q": "1"}, {"p": "2"}]}}, frozenset(),
     "f5c96be1edb62795e9fb2426435cb9b0e92c5d6f9846fd21c84f1ef39435d85d"),
]
rolling = hashlib.sha256()
for value, set_paths, digest in VECTORS:
    produced = canonical_bytes(value, set_paths)
    assert hashlib.sha256(produced).hexdigest() == digest, (value, produced)
    rolling.update(produced)

# canonical_sha256_hex is the bare SHA-256 of exactly those canonical bytes.
import re as _re
for value, set_paths, digest in VECTORS:
    hex_digest = canonical_sha256_hex(value, set_paths)
    assert hex_digest == digest, (value, hex_digest)
    assert _re.fullmatch(r"[0-9a-f]{64}", hex_digest), hex_digest
assert "canonical_sha256_hex" in ugence_jcs.__all__

# Action Profile fails closed.
for thunk, exc in (
    (lambda: canonical_bytes({"a": 1}), BareNumberError),
    (lambda: canonical_bytes({"a": 0.5}), BareNumberError),
    (lambda: canonical_bytes({"a": float("inf")}), NonFiniteNumberError),
    (lambda: canonical_bytes({"a": {"b"}}), UnsupportedTypeError),
    (lambda: canonical_bytes({"a": ["b", "b"]}, frozenset({"a"})), DuplicateSetElementError),
    (lambda: canonical_bytes({"a": "é"}, frozenset(), frozenset({"a"})), NonNFCError),
):
    try:
        thunk()
    except exc:
        pass
    else:
        raise AssertionError("Action Profile did not fail closed for " + exc.__name__)

FORBIDDEN = {"action_gate_ref", "cer_v0_1", "cer_v0_2", "cer_v0_3", "symbolu_robotics",
             "agentic", "control_plane", "requests", "httpx", "openai", "anthropic",
             "pydantic"}
loaded = {m.split(".")[0] for m in sys.modules}
assert not (loaded & FORBIDDEN), sorted(loaded & FORBIDDEN)

print("VEC:" + rolling.hexdigest())
'''

FORBIDDEN_WHEEL_SUBSTRINGS = ("cer_v0_", "action_gate", "cleanroom", "agentic",
                              "pydantic", "/tests/", "conftest", "/docs/")


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
    assert any(n.endswith("ugence_jcs/py.typed") for n in names), "py.typed missing"
    assert any(n.endswith("ugence_jcs/canon.py") for n in names), "canon.py missing"
    assert any(n.endswith("ugence_jcs/errors.py") for n in names), "errors.py missing"
    for name in names:
        low = name.lower()
        if low.startswith("ugence_jcs/") or low.startswith("ugence_jcs-"):
            for bad in FORBIDDEN_WHEEL_SUBSTRINGS:
                assert bad not in low, f"forbidden wheel content {name!r} (matched {bad!r})"
        else:
            raise AssertionError(f"foreign wheel entry {name!r}")
    print("  wheel audit OK:", len(names), "entries; py.typed present; no foreign content")


def main() -> int:
    print("== build ==")
    work = Path(tempfile.mkdtemp(prefix="ugence_jcs_dist_"))
    try:
        dist1 = work / "dist1"
        wheel1, sdist1 = _build(dist1)
        print("  wheel:", wheel1.name, _sha256(wheel1)[:16])
        print("  sdist:", sdist1.name, _sha256(sdist1)[:16])

        print("== wheel content audit ==")
        _audit_wheel(wheel1)

        print("== clean-install outside the repo (--no-index: zero dependencies) ==")
        env_dir = work / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index", str(wheel1)])

        vectors = []
        for i in (1, 2):  # two SEPARATE processes -> determinism across processes
            res = _run([str(py), "-c", CLEAN_INSTALL_CHECK], capture_output=True, text=True)
            line = [l for l in res.stdout.splitlines() if l.startswith("VEC:")][0]
            vectors.append(line[4:])
            print(f"  process {i} rolling vector digest:", vectors[-1][:24])
        assert vectors[0] == vectors[1], "non-deterministic across processes"
        print("  frozen vectors reproduced; Action Profile fails closed; determinism OK")

        print("== reproducibility ==")
        dist2 = work / "dist2"
        wheel2, sdist2 = _build(dist2)
        print(f"  wheel bit-for-bit reproducible: {_sha256(wheel1) == _sha256(wheel2)}")
        print(f"  sdist bit-for-bit reproducible: {_sha256(sdist1) == _sha256(sdist2)} "
              f"(content-stable; gzip mtime may vary)")

        print("\nARTIFACT HASHES")
        print("  wheel:", _sha256(wheel1))
        print("  sdist:", _sha256(sdist1))
        print("\nUGENCE_JCS_DISTRIBUTION_VERIFIED")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

"""Deterministic tree / suite / snapshot hashing (Task 5/10).

Reproducible SHA-256 hashes over package source trees, conformance suites, and
canonical JSON.

**The file set is scoped by ``git ls-files``, not by walking the directory.** These
functions used to ``rglob("*.py")`` and exclude only ``__pycache__``, which meant they
hashed whatever happened to be on disk — including untracked build output. Running
``python -m build`` leaves a ``build/lib/…`` copy of every module and an ``egg-info``
directory, and both are full of ``.py`` files that the walk cannot tell apart from source.
On a package tree that is not a small number: 10 of 46 files for
``cloud-scaling-authorization-contracts`` and 78 of 214 for ``cloud-scaling-controller``,
and the digest verifiably differs with and without them. A baseline computed after a build
would not reproduce on a clean checkout, and the failure would look like tampering.

The currently frozen surfaces happen to be clean — every tree in ``CORE_TREES`` and
``BEHAVIOUR_TREES`` has zero untracked ``.py`` today, so this change moves none of the
pinned values. That is luck about which trees are frozen, not a property of the old
implementation, and it is exactly the kind of latent defect that only shows up once
someone points these functions at a package tree.

**The ``*.py`` restriction is kept deliberately.** Widening to every tracked file is a
separate, unratified question: it would bring `pyproject.toml`, `README.md`,
`guard_inventory.json` and similar into scope, changing what "the tree" means and moving
pinned values for a second, unrelated reason. This change fixes tracked-versus-untracked
only. The two decisions should not ride together, because a single moved digest would then
have two possible causes.

**No git means failure, not a fallback.** Tracked-ness is not derivable from the
filesystem, so without git these functions cannot compute the value they claim to. Falling
back to a directory walk would return a *different* digest under the same name — silently
wrong rather than loudly absent, and indistinguishable from a real mismatch. This matches
the reasoning already recorded in the tree guards: for something whose whole job is to
notice a change, silence and success are not the same thing.
"""
from __future__ import annotations

import functools
import hashlib
import json
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]


class TrackedFilesUnavailable(RuntimeError):
    """``git ls-files`` could not be consulted, so tracked-ness is unknown."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: pathlib.Path) -> str:
    return _sha(path.read_bytes())


@functools.lru_cache(maxsize=None)
def _tracked(prefix: str) -> tuple[str, ...]:
    """Repo-relative paths git tracks under ``prefix``.

    Cached because a manifest hashes the same trees repeatedly and the answer cannot
    change within a run.
    """

    try:
        completed = subprocess.run(
            ("git", "-C", str(REPO), "ls-files", "--", prefix),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TrackedFilesUnavailable(
            f"cannot list tracked files under {prefix!r}: these hashes are defined over "
            "the tracked tree, and a directory walk would silently include untracked "
            "build output and return a different value under the same name"
        ) from exc
    return tuple(line for line in completed.stdout.split("\n") if line.strip())


def _tracked_py(pkg: str, *, include_tests: bool) -> list[pathlib.Path]:
    """Tracked ``*.py`` under ``pkg``, sorted, as absolute paths that exist on disk.

    A tracked path can be absent from the working tree — mid-rebase, or a sparse
    checkout — and hashing would then raise where the old walk simply did not see the
    file. Skipping keeps the function total; a *missing* file is a checkout problem, not a
    content change, and the guards that care about deletions look at git, not at this.
    """

    root = REPO / pkg
    chosen = []
    for rel in _tracked(pkg):
        path = REPO / rel
        if path.suffix != ".py" or "__pycache__" in path.parts:
            continue
        if not include_tests and "tests" in path.relative_to(root).parts:
            continue
        if path.is_file():
            chosen.append(path)
    return sorted(chosen)


def tree_hash(pkg: str, *, include_tests: bool = True) -> str:
    root = REPO / pkg
    entries = [
        (str(p.relative_to(root)), file_hash(p))
        for p in _tracked_py(pkg, include_tests=include_tests)
    ]
    return _sha(json.dumps(entries, sort_keys=True).encode())


def tree_manifest(pkg: str, *, include_tests: bool = True) -> dict:
    root = REPO / pkg
    files = {
        str(p.relative_to(root)): file_hash(p)
        for p in _tracked_py(pkg, include_tests=include_tests)
    }
    return {
        "package": pkg,
        "file_count": len(files),
        "tree_hash": tree_hash(pkg, include_tests=include_tests),
        "files": files,
    }


def conformance_hash(pkg: str) -> str:
    """Hash the conformance suite files that certify a package."""

    root = REPO / pkg / "conformance"
    if not root.exists():
        return ""
    rel_root = str(root.relative_to(REPO))
    entries = [
        (str(path.relative_to(root)), file_hash(path))
        for path in sorted(
            REPO / rel
            for rel in _tracked(rel_root)
            if rel.endswith(".py") and (REPO / rel).is_file()
        )
    ]
    return _sha(json.dumps(entries, sort_keys=True).encode())


def canonical_hash(obj) -> str:
    return _sha(json.dumps(obj, sort_keys=True, default=str).encode())

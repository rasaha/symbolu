"""Assert every COPY source of a Dockerfile survives the .dockerignore the build reads.

BLOCKING, offline pre-build gate. Opens no socket, pulls nothing, needs no container
runtime, and is therefore the one build-integrity check that can run on every push
rather than behind registry access.

**Why this exists.** Both deployment images are built with the REPOSITORY ROOT as the
build context (``docker buildx build ... -f deployment/<unit>/Dockerfile .``), and Docker
reads the ``.dockerignore`` at the *context root*, never one merely sitting beside the
Dockerfile. The repository root file is ``*`` plus re-includes for ``symbolu/`` — it
belongs to the GKE controller image. Under it, every COPY source of both deployment
Dockerfiles fell outside the context, so neither image could be built at all. Nothing
caught it: every check that would have needed the registry, and the container jobs went
red for the unconfigured mirror before the build could go red for the context. See
``docs/audits/ugence_governance_studio_p3e/BUILD_CONTEXT_EXCLUSION_DEFECT.json``.

The fix is a sibling ``<dockerfile>.dockerignore``, which BuildKit reads in preference to
the context root's. This gate holds that arrangement in place: it resolves the file the
build will actually read, applies dockerignore semantics to every COPY source, and fails
if any source is excluded or absent from disk.

**What it does not do.** It builds nothing and proves no image. A source being reachable
is necessary for a build, never sufficient for one. This check belongs to no ratified gate
family: it is not a member of P3E-CTR or GRW-CTR, satisfies no gate identifier of either,
and admitting it to either family is an owner decision.

    python deployment/governance-studio/ci/verify_build_context.py \
        deployment/governance-studio/Dockerfile \
        deployment/governed-runtime-worker/Dockerfile

Exit codes: 0 every source resolves; 1 a source is excluded or missing; 2 usage or a
Dockerfile that cannot be read.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import sys
from typing import List, Optional, Sequence, Tuple

__all__ = [
    "compile_pattern",
    "copy_sources",
    "effective_ignore_file",
    "is_excluded",
    "load_patterns",
    "verify",
]


# ---- dockerignore semantics ------------------------------------------------------- #
# Patterns are anchored at the context root (unlike .gitignore), cleaned, and evaluated
# in order; the last one matching the path OR one of its parent directories decides, and
# a leading `!` re-includes. `*` and `?` do not cross a path separator; `**` does.

def compile_pattern(pattern: str) -> Tuple[bool, "re.Pattern[str]"]:
    """(negated, regex) for one dockerignore line, anchored at the context root."""
    negated = pattern.startswith("!")
    body = pattern[1:] if negated else pattern
    body = posixpath.normpath(body.strip().rstrip("/")) if body.strip() else body
    out: List[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "*":
            if body.startswith("**", i):
                i += 2
                if body.startswith("/", i):  # `**/` — any number of leading segments
                    out.append("(?:[^/]+/)*")
                    i += 1
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return negated, re.compile("^" + "".join(out) + "$")


def load_patterns(path: str) -> List[str]:
    lines: List[str] = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def is_excluded(path: str, patterns: Sequence[str]) -> Optional[str]:
    """The pattern that excludes ``path``, or None. Parents are matched as Docker does."""
    parts = posixpath.normpath(path).split("/")
    ancestors = ["/".join(parts[: i + 1]) for i in range(len(parts))]
    verdict: Optional[str] = None
    for pattern in patterns:
        negated, regex = compile_pattern(pattern)
        if any(regex.match(ancestor) for ancestor in ancestors):
            verdict = None if negated else pattern
    return verdict


# ---- the Dockerfile --------------------------------------------------------------- #

def copy_sources(dockerfile: str) -> List[str]:
    """Every context-relative COPY source. Stage copies (``--from=``) are not context."""
    with open(dockerfile, "r", encoding="utf-8") as handle:
        text = handle.read()
    text = re.sub(r"\\\s*\n", " ", text)  # join continuations
    sources: List[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*COPY\s+(.+)$", line, re.IGNORECASE)
        if not match:
            continue
        rest = match.group(1).strip()
        if rest.startswith("["):  # JSON form
            args = re.findall(r'"([^"]*)"', rest)
        else:
            args = rest.split()
        if any(arg.lower().startswith("--from=") for arg in args):
            continue
        args = [arg for arg in args if not arg.startswith("--")]
        if len(args) < 2:
            continue
        sources.extend(args[:-1])  # the last argument is the destination
    return sources


def effective_ignore_file(dockerfile: str, context: str) -> Tuple[Optional[str], str]:
    """The ignore file this build reads, and why. BuildKit prefers the sibling."""
    sibling = dockerfile + ".dockerignore"
    if os.path.isfile(sibling):
        return sibling, "sibling <dockerfile>.dockerignore (BuildKit reads this first)"
    root = os.path.join(context, ".dockerignore")
    if os.path.isfile(root):
        return root, "the context root's .dockerignore (no sibling file exists)"
    return None, "no .dockerignore applies"


# ---- the check -------------------------------------------------------------------- #

def verify(dockerfile: str, context: str) -> List[str]:
    """Every reason this Dockerfile's sources would not reach the build. Empty is pass."""
    errors: List[str] = []
    ignore_file, why = effective_ignore_file(dockerfile, context)
    patterns = load_patterns(ignore_file) if ignore_file else []
    sources = copy_sources(dockerfile)
    print(f"{dockerfile}")
    print(f"  context      {context}")
    print(f"  ignore file  {ignore_file or '(none)'} — {why}")
    print(f"  COPY sources {len(sources)}")
    if not sources:
        errors.append(f"{dockerfile}: no COPY source found; the parser or the file is wrong")
    for source in sources:
        relative = posixpath.normpath(source.lstrip("./"))
        on_disk = os.path.exists(os.path.join(context, relative))
        excluded_by = is_excluded(relative, patterns)
        status = "ok" if on_disk and not excluded_by else "FAIL"
        note = ""
        if not on_disk:
            note = " — not on disk"
            errors.append(f"{dockerfile}: COPY source {relative!r} does not exist")
        if excluded_by:
            note += f" — excluded by {excluded_by!r} in {ignore_file}"
            errors.append(
                f"{dockerfile}: COPY source {relative!r} is excluded from the build context "
                f"by {excluded_by!r} in {ignore_file}"
            )
        print(f"  {status:4} {relative}{note}")
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_build_context.py",
        description="Assert every COPY source survives the .dockerignore the build reads.",
    )
    parser.add_argument("dockerfile", nargs="+", help="Dockerfile paths, relative to the context")
    parser.add_argument("--context", default=".", help="build context root (default: the repository root)")
    args = parser.parse_args(argv)

    errors: List[str] = []
    for dockerfile in args.dockerfile:
        if not os.path.isfile(dockerfile):
            print(f"no such Dockerfile: {dockerfile}", file=sys.stderr)
            return 2
        errors.extend(verify(dockerfile, args.context))
        print()

    if errors:
        print("BUILD CONTEXT CONFORMANCE FAILED", file=sys.stderr)
        for error in errors:
            print("  - " + error, file=sys.stderr)
        print(
            "\nDocker reads the .dockerignore at the CONTEXT ROOT unless a sibling\n"
            "<dockerfile>.dockerignore exists, which BuildKit prefers. A source excluded here\n"
            "is not in the build context and its COPY will fail. This gate proves reachability\n"
            "only; it builds nothing and satisfies no ratified gate identifier.",
            file=sys.stderr,
        )
        return 1

    print("build context conformance OK: every COPY source is present and not excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

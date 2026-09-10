"""Assert every local COPY source of a Dockerfile survives the ignore file the build reads.

BLOCKING, offline pre-build gate. Opens no socket, pulls nothing, needs no container
runtime, and is therefore the one build-integrity check that can run on every push rather
than behind registry access.

**Why this exists.** Both deployment images are built with the REPOSITORY ROOT as the
build context (``docker buildx build ... -f deployment/<unit>/Dockerfile .``), and Docker
reads the ``.dockerignore`` at the *context root*, never one merely sitting beside the
Dockerfile. Until 2026-09-08 the repository root file was ``*`` plus re-includes for
``symbolu/`` — rules belonging to the GKE controller image, which now carries them in its
own ``deploy/gke/Dockerfile.dockerignore``. Under them every COPY source of both
deployment Dockerfiles fell outside the context, so neither image could be built at all,
and nothing caught it: every check that could have seen it sat behind the registry
blocker, and the container jobs went red for the unconfigured mirror before a build could
go red for the context. See
``docs/audits/ugence_governance_studio_p3e/BUILD_CONTEXT_EXCLUSION_DEFECT.json``.

**What it proves, and what it does not.** A source being reachable is necessary for a
build and never sufficient for one. This check builds nothing, pulls nothing and proves no
image. It belongs to no ratified gate family: it is not a member of P3E-CTR or GRW-CTR,
satisfies no gate identifier of either, and admitting it to either family is an owner
decision.

**It fails closed.** Docker's parser accepts forms this checker does not model —
interpolated variables, ``--exclude`` filters, heredoc sources, ``ADD`` with a local
path. Approximating them would let a real exclusion pass silently, which is the exact
failure this gate exists to catch. Every such form is an error naming the instruction, not
a guess.

**Directories are judged by what survives inside them.** A directory whose descendants are
partly ignored is valid and common — ``packages/x`` with its ``__pycache__`` excluded still
builds. A directory with nothing left inside it is a build failure waiting to happen. The
two are distinguished by walking for the first surviving file, not by testing the
directory's own path.

    python deployment/governance-studio/ci/verify_build_context.py --root-build \
        deployment/governance-studio/Dockerfile \
        deployment/governed-runtime-worker/Dockerfile

Exit codes: 0 every source resolves; 1 a source is missing, excluded, or in a form this
checker refuses to approximate; 2 usage or a Dockerfile that cannot be read.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import sys
from typing import Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "ROOT_BUILD_INPUTS",
    "SUPPORTED_COPY_FLAGS",
    "Failure",
    "compile_pattern",
    "copy_instructions",
    "directory_retains_content",
    "effective_ignore_file",
    "is_excluded",
    "load_patterns",
    "resolve_source",
    "verify",
    "verify_root_build",
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


def directory_retains_content(context: str, relative: str, patterns: Sequence[str]) -> bool:
    """Does anything inside this directory survive the ignore file?

    A directory whose descendants are *partly* ignored still builds; one whose every
    descendant is excluded copies nothing, and the instruction that consumes it will fail.
    Walks for the first survivor and stops there. An excluded directory holding a
    re-included descendant therefore passes, which is what Docker does.
    """
    root = os.path.join(context, relative)
    saw_file = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            saw_file = True
            absolute = os.path.join(dirpath, name)
            entry = posixpath.normpath(
                os.path.relpath(absolute, context).replace(os.sep, "/"))
            if is_excluded(entry, patterns) is None:
                return True
    # An empty directory carries nothing to survive; judge it by its own path.
    return not saw_file and is_excluded(relative, patterns) is None


# ---- the Dockerfile --------------------------------------------------------------- #

#: COPY flags whose presence does not change which context paths a source names. Anything
#: else — `--exclude` above all, which filters the source set — is refused rather than
#: approximated.
SUPPORTED_COPY_FLAGS: Tuple[str, ...] = ("--from=", "--chown=", "--chmod=", "--link")

#: Characters that make a source a pattern rather than a literal path.
_GLOB = re.compile(r"[*?\[]")

#: What the repository-root buildpack build needs in its context. ``nixpacks.toml``
#: installs the project itself (``pip install -e .``), which reads ``pyproject.toml``; the
#: ``Procfile`` names the start command; the builder copies ``requirements.txt``; and the
#: start command imports the ``symbolu`` package. None of these is a COPY line anywhere,
#: so nothing else in CI would notice them leaving the context.
ROOT_BUILD_INPUTS: Tuple[Tuple[str, str], ...] = (
    ("pyproject.toml", "nixpacks.toml installs the project with `pip install -e .`"),
    ("requirements.txt", "copied by the builder's install phase"),
    ("nixpacks.toml", "the build definition itself"),
    ("Procfile", "names the start command"),
    ("symbolu", "the package the start command imports"),
)


class Failure(Exception):
    """A source this checker will not approximate. Raised only while parsing."""


def copy_instructions(dockerfile: str) -> List[Tuple[int, str, List[str]]]:
    """(line number, instruction text, local sources) for every COPY that names the context.

    Stage copies (``--from=``) name another stage or image and are skipped. Every other
    form this checker cannot model exactly raises ``Failure`` rather than being guessed at.
    """
    with open(dockerfile, "r", encoding="utf-8") as handle:
        raw = handle.read()
    if re.search(r"^\s*(COPY|ADD)\s+<<", raw, re.IGNORECASE | re.MULTILINE):
        raise Failure("a heredoc COPY/ADD source is present; this checker does not model it")
    if re.search(r"^\s*ADD\s+(?!http)", raw, re.IGNORECASE | re.MULTILINE):
        raise Failure("an ADD instruction with a local source is present; "
                      "this checker models COPY only")

    # Join continuations, keeping the line number the instruction started on.
    lines = raw.split("\n")
    joined: List[Tuple[int, str]] = []
    buffer, start = "", 0
    for number, line in enumerate(lines, start=1):
        stripped = line.rstrip()
        if not buffer:
            start = number
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        joined.append((start, buffer + stripped))
        buffer = ""
    if buffer:
        joined.append((start, buffer))

    out: List[Tuple[int, str, List[str]]] = []
    for number, text in joined:
        match = re.match(r"\s*COPY\s+(.+)$", text, re.IGNORECASE)
        if not match:
            continue
        rest = match.group(1).strip()
        instruction = " ".join(text.split())
        if rest.startswith("["):  # JSON array form
            args = re.findall(r'"((?:[^"\\]|\\.)*)"', rest)
            if not args:
                raise Failure(f"line {number}: JSON-form COPY whose arguments cannot be read")
            args = [a.replace('\\"', '"') for a in args]
        else:
            args = rest.split()

        flags = [a for a in args if a.startswith("--")]
        for flag in flags:
            if not any(flag == f or flag.startswith(f) for f in SUPPORTED_COPY_FLAGS):
                raise Failure(f"line {number}: unsupported COPY flag {flag!r}; "
                              "this checker will not guess what it selects")
        if any(f.startswith("--from=") for f in flags):
            continue  # another stage or image, not this context

        operands = [a for a in args if not a.startswith("--")]
        if len(operands) < 2:
            raise Failure(f"line {number}: COPY with fewer than two operands")
        for source in operands[:-1]:
            if "$" in source:
                raise Failure(f"line {number}: source {source!r} interpolates a variable; "
                              "this checker does not resolve build arguments")
            if posixpath.isabs(source):
                raise Failure(f"line {number}: absolute source {source!r} is not a "
                              "context-relative path")
        out.append((number, instruction, operands[:-1]))
    return out


def resolve_source(context: str, source: str) -> List[str]:
    """Context-relative paths a source names on disk. Empty means it matches nothing."""
    # Strip a leading "./" as a prefix, never as a character set: lstrip("./") would turn
    # "../outside" into "outside" and silently normalise an escape into a context path.
    stripped = source
    while stripped.startswith("./"):
        stripped = stripped[2:]
    relative = posixpath.normpath(stripped)
    if relative == ".." or relative.startswith("../"):
        raise Failure(f"source {source!r} escapes the build context")
    if not _GLOB.search(relative):
        return [relative] if os.path.exists(os.path.join(context, relative)) else []
    import glob as _glob
    matches = _glob.glob(os.path.join(context, relative), recursive="**" in relative)
    return sorted(
        posixpath.normpath(os.path.relpath(m, context).replace(os.sep, "/"))
        for m in matches
    )


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

def _judge(context: str, relative: str, patterns: Sequence[str]) -> Tuple[bool, str]:
    """(survives, why) for one existing context path."""
    if os.path.isdir(os.path.join(context, relative)):
        if directory_retains_content(context, relative, patterns):
            excluded_by = is_excluded(relative, patterns)
            if excluded_by:
                return True, f"directory excluded by {excluded_by!r} but re-included content remains"
            return True, "directory retains included content"
        return False, "every path inside this directory is excluded"
    excluded_by = is_excluded(relative, patterns)
    if excluded_by:
        return False, f"excluded by {excluded_by!r}"
    return True, ""


def verify(dockerfile: str, context: str) -> List[str]:
    """Every reason this Dockerfile's sources would not reach the build. Empty is pass."""
    errors: List[str] = []
    ignore_file, why = effective_ignore_file(dockerfile, context)
    patterns = load_patterns(ignore_file) if ignore_file else []
    print(f"{dockerfile}")
    print(f"  context      {context}")
    print(f"  ignore file  {ignore_file or '(none)'} — {why}")

    try:
        instructions = copy_instructions(dockerfile)
    except Failure as failure:
        print(f"  FAIL {failure}")
        return [f"{dockerfile}: {failure}"]

    sources = [(n, i, s) for n, i, ss in instructions for s in ss]
    print(f"  COPY sources {len(sources)} (in {len(instructions)} context instructions)")
    if not sources:
        errors.append(f"{dockerfile}: no context COPY source found; the parser or the file is wrong")

    for number, instruction, source in sources:
        try:
            matches = resolve_source(context, source)
        except Failure as failure:
            print(f"  FAIL {source} — {failure}")
            errors.append(f"{dockerfile}:{number}: {failure}\n      {instruction}")
            continue

        if not matches:
            kind = "matches nothing on disk" if _GLOB.search(source) else "does not exist"
            print(f"  FAIL {source} — {kind}")
            errors.append(f"{dockerfile}:{number}: source {source!r} {kind}\n      {instruction}")
            continue

        survivors = [(m, _judge(context, m, patterns)) for m in matches]
        kept = [(m, why) for m, (ok, why) in survivors if ok]
        if not kept:
            reasons = "; ".join(sorted({why for _, (ok, why) in survivors if not ok}))
            print(f"  FAIL {source} — {len(matches)} path(s) matched, all excluded")
            errors.append(
                f"{dockerfile}:{number}: source {source!r} reaches the build empty — "
                f"every path it matches is excluded from the context by {ignore_file} "
                f"({reasons})\n      {instruction}")
            continue

        note = kept[0][1]
        detail = f" — {note}" if note else ""
        if len(matches) > 1:
            detail = f" — {len(kept)} of {len(matches)} matched paths survive"
        print(f"  ok   {source}{detail}")
    return errors


def verify_root_build(context: str) -> List[str]:
    """The root buildpack build has no Dockerfile, so it reads the context root's file."""
    errors: List[str] = []
    ignore_file = os.path.join(context, ".dockerignore")
    patterns = load_patterns(ignore_file) if os.path.isfile(ignore_file) else []
    print("root buildpack build (nixpacks.toml, Procfile — no Dockerfile)")
    print(f"  context      {context}")
    print(f"  ignore file  {ignore_file if patterns else '(none)'} — a build with no "
          "Dockerfile has no sibling file to prefer")
    print(f"  inputs       {len(ROOT_BUILD_INPUTS)}")
    for path, why in ROOT_BUILD_INPUTS:
        if not os.path.exists(os.path.join(context, path)):
            print(f"  FAIL {path} — not on disk")
            errors.append(f"root build input {path!r} does not exist ({why})")
            continue
        ok, note = _judge(context, path, patterns)
        print(f"  {'ok  ' if ok else 'FAIL'} {path}{(' — ' + note) if note else ''}")
        if not ok:
            errors.append(
                f"root build input {path!r} is excluded from the build context: {note} "
                f"({why})")
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_build_context.py",
        description="Assert every local COPY source survives the .dockerignore the build reads.",
    )
    parser.add_argument("dockerfile", nargs="*", help="Dockerfile paths, relative to the context")
    parser.add_argument("--context", default=".", help="build context root (default: the repository root)")
    parser.add_argument("--root-build", action="store_true",
                        help="also check the declared inputs of the root buildpack build, "
                             "which has no Dockerfile and no sibling ignore file")
    args = parser.parse_args(argv)
    if not args.dockerfile and not args.root_build:
        parser.error("give at least one Dockerfile, or --root-build, or both")

    errors: List[str] = []
    for dockerfile in args.dockerfile:
        if not os.path.isfile(dockerfile):
            print(f"no such Dockerfile: {dockerfile}", file=sys.stderr)
            return 2
        errors.extend(verify(dockerfile, args.context))
        print()

    if args.root_build:
        errors.extend(verify_root_build(args.context))
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

    print("build context conformance OK: every COPY source and root build input reaches "
          "the build with content")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

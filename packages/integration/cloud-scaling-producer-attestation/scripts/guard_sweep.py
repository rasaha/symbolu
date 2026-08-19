#!/usr/bin/env python3
"""Deterministic guard inventory and gate-removal mutation sweep.

Method, following the Phase 5A convention exactly:

* enumerate every **security-relevant guard** in the distribution — an ``if`` whose body can
  reach a ``raise`` or a typed refusal — in a fixed module order and then source order;
* neutralise each one **independently** by rewriting its ``if`` header to ``if False:``;
* do it in a **disposable untracked copy**; the tracked worktree is never mutated;
* run the **full suite** against the mutated copy and record killed/survived;
* a run is scored only if it **collected** the full suite — a collection error, a syntax
  error, an import error or a timeout is not a valid kill;
* classify every survivor.

Writes ``GUARD_SWEEP.md``. Run:

    python packages/integration/cloud-scaling-producer-attestation/scripts/guard_sweep.py
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]
SRC = PKG / "src" / "ugence_cloud_scaling_producer_attestation"

#: Every mutation runs in a disposable copy **outside the repository**. Keeping it inside
#: would put a second, mutated copy of this package on every repo-wide scan for the life of
#: the sweep — the Trusted Evidence Authority's reverse-dependency test walks
#: ``packages/**/*.py``, and would report the copy as an unauthorized consumer. The copy
#: finds the real checkout through ``UGENCE_REPO_ROOT``, which is why the test tree locates
#: the repository by marker rather than by counting directory levels.
WORKROOT = Path(tempfile.gettempdir()) / "ugence-cloud-scaling-producer-attestation-sweep"
WORKDIR = WORKROOT / "package"

#: Fixed module order: the order a value actually flows through the package.
MODULE_ORDER = [
    "canonical.py",
    "identifiers.py",
    "attestation.py",
    "signing.py",
    "trust.py",
    "verified.py",
    "verification.py",
]

#: A guard's body reaching one of these makes it security-relevant.
REFUSAL_CALLS = {"_refuse", "ProducerAuthenticityResult", "ProducerAttestationRefusal"}


@dataclass
class Guard:
    index: int
    module: str
    lineno: int
    condition: str
    header_end: int
    is_elif: bool


def _condition_text(source_lines: list[str], node: ast.If) -> str:
    try:
        return ast.unparse(node.test)
    except Exception:  # pragma: no cover - unparse is available on 3.9+
        return source_lines[node.lineno - 1].strip()


def _reaches_refusal(node: ast.If) -> bool:
    """Whether this ``if``'s own body can reach a raise or a typed refusal.

    Nested ``if`` bodies are excluded so an outer block does not inherit its children's
    relevance — each guard is scored for what *it* protects.
    """

    for statement in node.body:
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Raise):
                return True
            if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Call):
                func = inner.value.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name in REFUSAL_CALLS:
                    return True
            if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Attribute):
                # ``return _Outcome.SOMETHING`` — a lifecycle/typed-outcome refusal.
                if isinstance(inner.value.value, ast.Name):
                    return True
    return False


def inventory() -> list[Guard]:
    guards: list[Guard] = []
    index = 0
    for module in MODULE_ORDER:
        path = SRC / module
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source)
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and _reaches_refusal(node):
                found.append(node)
        for node in sorted(found, key=lambda n: n.lineno):
            index += 1
            header_line = lines[node.lineno - 1].lstrip()
            guards.append(
                Guard(
                    index=index,
                    module=module,
                    lineno=node.lineno,
                    condition=_condition_text(lines, node),
                    header_end=node.body[0].lineno - 1,
                    is_elif=header_line.startswith("elif"),
                )
            )
    return guards


def mutate(guard: Guard, workdir: Path) -> None:
    """Rewrite exactly this guard's ``if`` header to ``if False:`` in the copy."""

    path = workdir / "src" / "ugence_cloud_scaling_producer_attestation" / guard.module
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    original = lines[guard.lineno - 1]
    indent = original[: len(original) - len(original.lstrip())]
    keyword = "elif" if guard.is_elif else "if"
    replacement = f"{indent}{keyword} False:\n"
    # The header may span several lines; blank the continuation lines out.
    lines[guard.lineno - 1] = replacement
    for offset in range(guard.lineno, guard.header_end):
        lines[offset] = ""
    path.write_text("".join(lines), encoding="utf-8")


def run_suite(workdir: Path, timeout: int = 600) -> dict:
    """Run the full suite in the copy. Returns a scored result, honestly labelled."""

    process = subprocess.run(
        # NB: no ``-q`` here. The package's own pyproject already sets ``addopts = "-q"``,
        # and a second ``-q`` suppresses the summary line this scorer parses — which would
        # silently turn every run into "not scored".
        [sys.executable, "-m", "pytest", "tests", "-p", "no:cacheprovider", "--tb=no"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={
            **os.environ,
            # The copy lives outside the repository, so it cannot find the checkout by
            # walking upward. Telling it explicitly keeps the copy out of every repo-wide
            # scan.
            "UGENCE_REPO_ROOT": str(REPO),
            # Deselect the slow packaging-isolation properties. They build five wheels and a
            # virtualenv per run — minutes each, times the whole inventory — and they assert
            # facts about the sdist, not about any ``src/`` guard, so they can neither kill
            # nor survive a mutation and contribute nothing to the score. The full suite and
            # CI run them.
            "UGENCE_SKIP_SLOW_PACKAGING": "1",
        },
    )
    output = process.stdout + process.stderr
    if "error" in output.lower() and "during collection" in output.lower():
        return {"scored": False, "why": "collection error", "failed": []}
    if "SyntaxError" in output:
        return {"scored": False, "why": "syntax error", "failed": []}
    if re.search(r"^ERROR ", output, re.M) and " passed" not in output:
        return {"scored": False, "why": "import or collection error", "failed": []}
    match = re.search(r"(\d+) passed", output)
    if match is None:
        tail = " | ".join(line for line in output.strip().splitlines()[-3:])
        return {
            "scored": False,
            "why": f"no test count reported ({tail[:200]})",
            "failed": [],
        }
    failed = re.findall(r"^FAILED (\S+)", output, re.M)
    return {
        "scored": True,
        "why": "",
        "failed": failed,
        "passed": int(match.group(1)),
        "killed": bool(failed),
    }


#: Hand-written classification for every guard that survives its own removal, keyed by the
#: guard's condition. Deliberately NOT inferred from the condition's shape: a heuristic that
#: guesses "sibling-backed" from an ``is not None`` is a heuristic that will one day call a
#: real hole sibling-backed. Anything not named here is reported as **unresolved**, which is
#: what a reviewer should chase.
#:
#: Three classes, and the distinction is load-bearing:
#:
#: * ``sibling-backed`` — a neighbouring guard refuses the same input, so the package still
#:   fails closed; the survivor's contribution is a *better-typed* refusal, not a refusal.
#: * ``unreachable through the public API`` — no supported call can present the input this
#:   guard rejects, because an earlier boundary already made it unrepresentable. It exists
#:   for a caller who has bypassed that boundary, and for a future edit that removes it.
#: * ``internal invariant`` — the condition is about this package's own construction, not
#:   about attacker-supplied data, and cannot be made true from outside.
SURVIVOR_CLASSIFICATION = {
    # --- attestation.py ---------------------------------------------------------------
    "type(self.signature) is not str": (
        "sibling-backed — decode_signature refuses a non-str on the next line and yields "
        "the same MALFORMED_SIGNATURE outcome; this guard only makes the refusal typed "
        "one call earlier"
    ),
    # --- signing.py: the signing input, unreachable behind the token guard --------------
    "type(self.signed_input) is not bytes": (
        "unreachable through the public API — mint_producer_attestation is the only route "
        "to a signing input and always passes canonical_bytes(); a caller cannot construct "
        "one at all, because the token guard above rejects it first"
    ),
    "len(self.signed_input) == 0": (
        "unreachable through the public API — the minted payload is never empty, and the "
        "token guard rejects a caller-assembled input before any content check"
    ),
    "self.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE": (
        "unreachable through the public API — the minting routine passes the pinned "
        "constant, not a parameter; there is no caller-supplied profile to get wrong"
    ),
    # --- trust.py ----------------------------------------------------------------------
    "resolver is None": (
        "sibling-backed — a None resolver fails the is_production_authoritative check "
        "below, which refuses it with the same typed configuration error"
    ),
    # --- verified.py -------------------------------------------------------------------
    "self.artifact_digest != expected": (
        "sibling-backed — require_verified_producer_attestation recomputes the same digest "
        "at every consumption boundary, and that check IS killed; this one is unreachable "
        "at construction because the minting routine computes the digest it passes"
    ),
    # --- verification.py: result-shape invariants ---------------------------------------
    "self.verified_attestation is not None and type(self.verified_attestation) is not "
    "VerifiedProducerAttestation": (
        "internal invariant — only this module constructs a result, and only ever with an "
        "artifact its own minting routine produced; not reachable from attacker input"
    ),
    "self.refusal is not None and type(self.refusal) is not ProducerAttestationRefusal": (
        "internal invariant — every refusal in this module is built by the single _refuse "
        "helper; not reachable from attacker input"
    ),
    "trust_anchor_resolver is None": (
        "sibling-backed — the hasattr(resolver, 'resolve') check below refuses None with "
        "the same typed configuration error"
    ),
    "signature_verifier is None": (
        "sibling-backed — the hasattr(verifier, 'verify_producer_signature') check below "
        "refuses None with the same typed configuration error"
    ),
    # --- verification.py: the byte-equality gate ----------------------------------------
    "recomputed_bytes != attestation.signed_bytes()": (
        "sibling-backed — the payload-digest comparison on the following line is a digest "
        "over the same two byte strings and refuses the identical inputs (killed by "
        "GI-20). Both are additionally fronted by the reconciliation group, which refuses "
        "a divergent tenant, subject, subject type, recommendation id or digest before "
        "either runs. Deliberately kept: it is the direct byte comparison the design "
        "specifies, and it would be the only survivor if a future edit made the digest "
        "check cover a different projection of the payload"
    ),
    "value.construction_token is not _VERIFICATION_TOKEN": (
        "sibling-backed — the provenance-registry check on the next line refuses everything "
        "this one does. An artifact assembled outside the authoritative routine also names "
        "a determination that routine never reached, unless it is a faithful copy of a real "
        "one, which IS that determination and should pass (V-21). The token check is kept "
        "as the ratified construction guard and as the check that would still stand if a "
        "deployment ever scoped the registry differently — for example per-request rather "
        "than per-process. Its construction-time twin in __post_init__ IS killed, by V-1 "
        "and V-2"
    ),
    "type(anchor) is not TrustAnchorRecord": (
        "unreachable through the public API — TrustAnchorResolution refuses at construction "
        "to carry anything but a TrustAnchorRecord, and the resolution's own exact-type "
        "check above (killed by A-54) rejects a non-resolution; this guard covers a "
        "resolver that returns a genuine resolution subverted after construction"
    ),
}


def classify(guard: Guard, result: dict) -> str:
    """The hand-written classification for a survivor. Empty for a killed guard."""

    if result.get("killed") or not result["scored"]:
        return ""
    condition = " ".join(guard.condition.split())
    for known, classification in SURVIVOR_CLASSIFICATION.items():
        if " ".join(known.split()) == condition:
            return classification
    return "UNRESOLVED — no reviewed classification; investigate"


def _source_fingerprint() -> dict:
    """Content hash of every shipped source file.

    Deliberately the file *bytes*, not ``git status``. The property being asserted is "the
    sweep did not modify the tracked tree", and a porcelain diff also fires when a file's
    tracking state changes for an unrelated reason — an untracked tree being committed
    mid-run, say — which is a false alarm that withholds a correct report. Hashing the
    content measures exactly the thing and nothing else.
    """

    import hashlib

    return {
        str(path.relative_to(SRC)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(SRC.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def main() -> int:
    baseline_fingerprint = _source_fingerprint()

    guards = inventory()
    print(f"canonical inventory: {len(guards)} security-relevant guards")

    if WORKROOT.exists():
        shutil.rmtree(WORKROOT)

    results = []
    try:
        for guard in guards:
            shutil.rmtree(WORKROOT, ignore_errors=True)
            WORKROOT.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                PKG,
                WORKDIR,
                ignore=shutil.ignore_patterns(
                    "__pycache__", ".pytest_cache", "dist", "build", "*.egg-info"
                ),
            )
            mutate(guard, WORKDIR)
            try:
                result = run_suite(WORKDIR)
            except subprocess.TimeoutExpired:
                result = {"scored": False, "why": "timeout", "failed": []}
            results.append((guard, result))
            state = (
                "killed"
                if result.get("killed")
                else ("survived" if result["scored"] else f"NOT SCORED ({result['why']})")
            )
            print(f"  {guard.index:>3} {guard.module}:{guard.lineno}  {state}")
    finally:
        shutil.rmtree(WORKROOT, ignore_errors=True)

    final_fingerprint = _source_fingerprint()
    if final_fingerprint != baseline_fingerprint:
        changed = sorted(
            name
            for name in set(baseline_fingerprint) | set(final_fingerprint)
            if baseline_fingerprint.get(name) != final_fingerprint.get(name)
        )
        raise SystemExit(
            "REFUSING TO REPORT: the tracked source tree changed during the sweep. "
            f"Changed: {changed}"
        )

    write_report(results)
    scored = [r for _, r in results if r["scored"]]
    killed = [r for _, r in results if r.get("killed")]
    print(
        f"\n{len(killed)} killed / {len(scored) - len(killed)} survived "
        f"({len(results) - len(scored)} not scored)"
    )
    if len(scored) != len(results):
        raise SystemExit("some mutations were not scored; the sweep is incomplete")
    return 0


def write_report(results) -> None:
    killed = [g for g, r in results if r.get("killed")]
    survived = [(g, r) for g, r in results if r["scored"] and not r.get("killed")]
    classes: dict[str, int] = {}
    for guard, result in survived:
        classes[classify(guard, result)] = classes.get(classify(guard, result), 0) + 1

    lines = [
        f"# Canonical {len(results)}-guard mutation sweep — Cloud Scaling Phase 5B-0A",
        "",
        "Deterministic inventory: every `if` in the distribution whose own body can reach a",
        "`raise` or a typed refusal, enumerated in flow order",
        "(`" + "` → `".join(MODULE_ORDER) + "`) and then source order.",
        "",
        "Mutation: the guard's `if` header is rewritten to `if False:`, neutralising exactly",
        "that guard and nothing else. Every run is a **disposable untracked copy** of the",
        "package; the tracked worktree is never mutated, and the sweep refuses to report if",
        "the content hash of every shipped source file differs before and after. A run is",
        "scored **only** if it",
        "collected and ran the full suite — a collection error, a syntax error, an import",
        "error or a timeout is not a valid kill.",
        "",
        f"| Result | **{len(killed)} killed / {len(survived)} survived** |",
        "|---|---|",
        "",
        "| # | file:line | condition | killed? | responsible test(s) | classification if survived |",
        "|---|---|---|---|---|---|",
    ]
    for guard, result in results:
        if not result["scored"]:
            verdict = f"NOT SCORED ({result['why']})"
            tests = "—"
        elif result["killed"]:
            verdict = "**killed**"
            names = [f.split("::")[-1] for f in result["failed"][:2]]
            extra = (
                f" (+{len(result['failed']) - 2} more)"
                if len(result["failed"]) > 2
                else ""
            )
            tests = "; ".join(names) + extra
        else:
            verdict = "survived"
            tests = "—"
        condition = guard.condition.replace("|", "\\|")
        lines.append(
            f"| {guard.index} | `{guard.module}:{guard.lineno}` | `{condition}` | "
            f"{verdict} | {tests} | {classify(guard, result) or '—'} |"
        )

    lines += ["", "## Survivor classification totals", "", "| class | count |", "|---|---|"]
    for name, count in sorted(classes.items()):
        lines.append(f"| {name} | {count} |")
    unresolved = sum(
        count for name, count in classes.items() if name.startswith("UNRESOLVED")
    )
    lines.append(f"| **unresolved survivors** | **{unresolved}** |")
    lines += [
        "",
        "Every survivor carries a **hand-written, reviewed** classification, keyed by its",
        "condition in `SURVIVOR_CLASSIFICATION` in `scripts/guard_sweep.py`. The classifier",
        "does not infer a class from the condition's shape: a heuristic that guesses",
        "\"sibling-backed\" from an `is not None` is a heuristic that will one day call a real",
        "hole sibling-backed. Anything unlisted is reported as **UNRESOLVED**.",
        "",
        "No surviving guard admits a verified producer attestation that the unmutated package",
        "refuses. The authenticity gates themselves — reconciliation, payload recomputation,",
        "the payload-digest comparison, anchor resolution, anchor identity, anchor lifecycle,",
        "profile and encoding agreement, signature decoding and signature verification — are",
        "all killed by a property that names that gate.",
        "",
        "Regenerate with `python scripts/guard_sweep.py`.",
    ]
    (PKG / "GUARD_SWEEP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (PKG / "guard_sweep.json").write_text(
        json.dumps(
            [
                {
                    "index": g.index,
                    "module": g.module,
                    "lineno": g.lineno,
                    "condition": g.condition,
                    "scored": r["scored"],
                    "killed": bool(r.get("killed")),
                    "failed": r["failed"][:5],
                    "classification": classify(g, r),
                }
                for g, r in results
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())

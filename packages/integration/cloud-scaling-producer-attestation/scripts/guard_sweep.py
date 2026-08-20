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


def _reaches_refusal(node) -> bool:
    """Whether this node's body can reach a raise or a typed refusal, **nested bodies
    included**.

    Takes an ``ast.If`` for the inventory and an ``ast.ExceptHandler`` for the
    excluded-count report; both carry a ``body``.

    Stated precisely, because an earlier revision of this docstring claimed the opposite —
    "nested ``if`` bodies are excluded so an outer block does not inherit its children's
    relevance" — while the code below has always used ``ast.walk``, which descends into
    them. The code is right and the claim was wrong: an outer ``if`` that contains nothing
    but a guarded block is itself a guard, because neutralising it disables everything
    inside. ``verification.py``'s ``if production_mode:`` is the case in point — remove it
    and the entire production-mode enforcement block stops running.

    The consequence for the headline number is disclosed rather than left implicit: under
    the stricter reading the inventory would be **one smaller**, and ``GUARD_SWEEP.md`` says
    so and names the guard.

    The typed-refusal arm below is also looser than "``return _Outcome.SOMETHING``": any
    ``return X.y`` counts. That admits no false guard in this source — every match is a real
    refusal — but it is a heuristic, not a proof, and is recorded as one.
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


def excluded_from_the_inventory() -> tuple[int, int]:
    """What the ``if``-guard denominator leaves out, measured rather than claimed.

    Two kinds of fail-closed logic exist in the source and are not scored as guards:

    * ``except`` arms whose body raises or returns a typed refusal. The ``if False:``
      rewrite cannot neutralise a handler, so they are out of scope for this mutation
      operator rather than overlooked;
    * the extra sub-terms of a boolean guard. ``if a and b:`` is neutralised and scored as
      **one** guard; scoring each side independently is a different operator.

    Reported in ``GUARD_SWEEP.md`` so the CI job's claim is bounded by a number this script
    produced, not by a phrase somebody wrote once. (closure-audit L-3)
    """

    except_arms = 0
    boolean_subterms = 0
    for module in MODULE_ORDER:
        tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _reaches_refusal(node):
                except_arms += 1
            elif (
                isinstance(node, ast.If)
                and _reaches_refusal(node)
                and isinstance(node.test, ast.BoolOp)
            ):
                boolean_subterms += len(node.test.values) - 1
    return except_arms, boolean_subterms


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
    """Run the suite in the copy. Returns a scored result, honestly labelled.

    Not quite the *full* suite: ``UGENCE_SKIP_SLOW_PACKAGING=1`` deselects the packaging
    module below, so this collects fewer properties than a plain ``pytest tests`` in the
    tracked tree. The deselection is a cost decision whose safety condition is asserted by
    ``tests/test_property_ledger.py`` PL-6; see the comment on the environment below.
    """

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
            # Deselect the slow packaging-distribution properties. They build five wheels
            # and a virtualenv per run — minutes each, times the whole inventory.
            #
            # This is a COST decision and it is not free. SD-6..SD-9 build the sdist from
            # the package under test and run the *shipped* suite against it, so under a
            # mutation they fail exactly as the same properties fail here: they would
            # score. What makes dropping them sound is that every module the sdist ships
            # is also run directly, un-deselected, in this same run — so the score is
            # unchanged and only the wall-clock differs. tests/test_property_ledger.py
            # PL-6 asserts that relationship, so a property added behind this switch that
            # reaches src/ behaviour fails rather than silently shrinking the sweep.
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
    # ``value.construction_token is not _VERIFICATION_TOKEN`` (verified.py, the
    # consumption-boundary check) was classified here as "sibling-backed — the
    # provenance-registry check on the next line refuses everything this one does".
    # That was wrong, and wrong in the direction that matters: it described the only
    # guard standing between a rebuilt artifact and admission as redundant.
    #
    # A ``copy.deepcopy``d or unpickled artifact bypasses ``__init__``, so it carries a
    # freshly rebuilt token — but ``artifact_digest`` is a string, copied verbatim, so it
    # names a determination this process really did reach. The registry admits it, the
    # exact-type check admits it, the field-presence check admits it and the recomputed
    # self-digest admits it. Only this guard refuses it. Reproduced by neutralising this
    # guard alone in a disposable copy: both rebuilds were ADMITTED.
    #
    # It is no longer a survivor. ``tests/test_verified_artifact.py`` V-24 (deepcopy and
    # pickle, asserting the other four checks pass first) and V-25 score it, and it is
    # reported as **killed** by the table below. The entry is left here as a comment
    # rather than deleted so the correction is visible to the next reader.
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


def _baseline_run() -> dict:
    """Run the suite **unmutated** first, and refuse to sweep unless it is green.

    Without this the sweep's headline number is not trustworthy, and the failure mode is
    silent rather than loud. A test that fails for a reason unrelated to any mutation — a
    missing build backend on the runner, a stale artifact, an environment gap — fails on
    *every* run, so every guard looks killed, and a guard that genuinely survives is
    reported as load-bearing. That is precisely the wrong direction for a security claim to
    be wrong in: it manufactures reassurance.

    This happened. The packaging-distribution properties invoke ``python -m build``, the
    sweep job installs pytest but not ``build``, and one property therefore errored on all
    91 runs — converting two genuine survivors into kills and appearing in every guard's
    attribution list. The module is now deselected in sweep runs; this check is what makes
    the next instance of the same class impossible to publish.
    """

    shutil.rmtree(WORKROOT, ignore_errors=True)
    WORKROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        PKG,
        WORKDIR,
        ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", "dist", "build", "*.egg-info"
        ),
    )
    try:
        result = run_suite(WORKDIR)
    except subprocess.TimeoutExpired:
        raise SystemExit("baseline run timed out; the sweep would score noise")
    finally:
        shutil.rmtree(WORKROOT, ignore_errors=True)

    if not result["scored"]:
        raise SystemExit(f"baseline run was not scored ({result['why']}); refusing to sweep")
    if result["failed"]:
        listed = "\n  ".join(result["failed"][:20])
        raise SystemExit(
            "the UNMUTATED suite does not pass, so every mutation would inherit these "
            "failures and be scored as killed. Fix the environment or the tests before "
            f"sweeping.\n  {listed}"
        )
    return result


def main() -> int:
    baseline_fingerprint = _source_fingerprint()

    guards = inventory()
    print(f"canonical inventory: {len(guards)} security-relevant guards")

    if WORKROOT.exists():
        shutil.rmtree(WORKROOT)

    baseline = _baseline_run()
    print(f"baseline (unmutated): {baseline['passed']} passed, no failures")

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
    _EXCLUDED_EXCEPT_ARMS, _EXCLUDED_BOOLEAN_SUBTERMS = excluded_from_the_inventory()
    #: The outer scaffolding guard named in the disclosure below. Located rather than
    #: hard-coded, so the line number cannot rot.
    _SCAFFOLDING_LINENO = next(
        (
            guard.lineno
            for guard, _ in results
            if guard.module == "verification.py"
            and " ".join(guard.condition.split()) == "production_mode"
        ),
        "(none)",
    )
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
        "**Baseline precondition.** Before any mutation, the sweep runs the suite *unmutated*",
        "and refuses to proceed unless it is green. A test that fails for a reason unrelated",
        "to the mutation fails on every run, so every guard looks killed and a genuinely",
        "surviving guard is published as load-bearing — the wrong direction for a security",
        "claim to be wrong in. This is not hypothetical: the packaging-distribution",
        "properties invoke `python -m build`, the sweep job installs pytest but not `build`,",
        "and one of them therefore errored on all 91 runs, converting two real survivors into",
        "kills. This precondition is what stops the next instance of that class from being",
        "published as a result.",
        "",
        "**Why the packaging module is deselected, stated accurately.** For **cost**, and",
        "not because it scores nothing. An earlier revision of this document and of the",
        "module's own comment claimed \"nothing there can score a guard in `src/`: a mutated",
        "package builds into a distribution exactly as an unmutated one does\". That is true",
        "of SD-1 … SD-5 and **false** of SD-6 … SD-9, which build the sdist *from the package",
        "under test* and run the shipped suite against it — under a mutation the shipped",
        "adversarial properties fail there exactly as they fail here, so SD-7 would score.",
        "Dropping them is sound for a different reason, and a checkable one: **every module",
        "the sdist ships is also run directly, un-deselected, in this same sweep run**, so",
        "the score is identical and only the wall-clock differs.",
        "`tests/test_property_ledger.py::PL-6` asserts that relationship in both directions,",
        "so a property added behind the switch that reaches `src/` behaviour the sweep does",
        "not otherwise run fails rather than quietly shrinking the sweep.",
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
        "### What the inventory counts, and what it leaves out",
        "",
        "The denominator is every `if` in the shipped source whose own body can reach a",
        "`raise` or a typed refusal. Two kinds of fail-closed logic are **not** in it, and",
        "the count should not be read as \"every security gate in the package\":",
        "",
        f"* **{_EXCLUDED_EXCEPT_ARMS} fail-closed `except` arms.** An `except` cannot be",
        "  neutralised by the `if False:` rewrite this sweep is built on, so it is out of",
        "  scope for this mutation operator rather than overlooked;",
        f"* **{_EXCLUDED_BOOLEAN_SUBTERMS} boolean sub-terms.** A two-term `and` guard is",
        "  neutralised and scored as **one** guard. Scoring each side independently is a",
        "  different operator, and this sweep does not claim it.",
        "",
        "Two further facts about the denominator, disclosed because a reader could otherwise",
        "infer them wrongly from the count alone:",
        "",
        "* **An outer `if` that only wraps a guarded block is itself inventoried.**",
        "  Relevance is computed over the whole nested body, so",
        f"  `verification.py:{_SCAFFOLDING_LINENO}` (`if production_mode:`) is scored as a",
        "  guard even though it reaches a `raise` only through its nested child. That is",
        "  deliberate — neutralise it and the entire production-mode enforcement block stops",
        "  running — but it means a stricter reading that excluded nested bodies would report",
        f"  **{len(results) - 1}** guards rather than {len(results)}. Both numbers describe",
        "  the same source; this one is the count the published table is built from.",
        "* **One of the five checks in `require_verified_producer_attestation` is an `except`",
        "  arm**, and is therefore among the excluded arms above rather than among the scored",
        "  guards. It is the field-presence check, and it is the one that refuses an",
        "  `object.__new__` fabrication. It is covered by properties",
        "  (`test_verified_artifact.py` V-3, `test_typed_outcomes.py` O-13) but not by this",
        "  sweep, so \"four of that function's five checks are mutation-scored\" is the exact",
        "  claim, not five.",
        "",
        "The CI job used to be called *\"every security gate is scored\"*, which overstated",
        "exactly this; it now says *\"every inventoried `if` guard scored\"*. The two counts",
        "above are measured by `scripts/guard_sweep.py` at report time, not asserted.",
        "",
        "### What \"killed\" does and does not claim",
        "",
        "A **killed** row means a property fails when that `if` header alone is neutralised.",
        "That is a statement about **scoring** — the guard is exercised and attributed — and",
        "it is not, on its own, a statement that removing the guard opens an attack. Where a",
        "later guard would refuse the same value with a different message, killing the earlier",
        "one proves the earlier one is reached and diagnostic, not that it is the only thing",
        "standing between an attacker and admission.",
        "",
        "The three import-time capability separations in `identifiers.py` are the clearest",
        "case, and are called out here so the table is not over-read:",
        "",
        "* the catch-all `PRODUCER_ATTESTATION_CAPABILITY is not _DEDICATED` (#17) is the",
        "  **load-bearing** one. It is the check that fails closed on capability drift; remove",
        "  it and any capability that is not one of the two explicitly named ones — a member",
        "  added to the enum later, say — is admitted;",
        "* the explicit `RECEIPT_ISSUANCE` (#15) and `EVIDENCE_PRODUCTION` (#16) branches are",
        "  **scored for typed attribution and diagnostic precision**. Removing either one",
        "  alone does not open the attack: the catch-all below refuses the same value, because",
        "  neither borrowed capability is the dedicated one. They are killed because each",
        "  test asserts the phrase only that branch emits, which is what keeps them scored;",
        "  the design keeps them because a refusal that names the cross-domain reuse is worth",
        "  more to an operator than a generic drift message.",
        "",
        "`tests/test_gate_isolation.py::GI-4c` asserts this relationship directly rather than",
        "leaving it as prose.",
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

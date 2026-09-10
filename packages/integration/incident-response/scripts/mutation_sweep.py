#!/usr/bin/env python3
"""Disable each refusal in ``src/`` in turn and report which ones no test catches.

Five review rounds each found a guard this package refused to enforce, or a claim
about coverage broader than the coverage itself. Three of those rounds found the
sweep behind the claim narrower than the claim: first it saw only ``raise`` guards
and missed ``reasons.append``; then it reached only ``records.py`` and ``states.py``
and missed ``journal.py``'s tenant filters entirely; then it skipped ``else``-bearing
guards and unconditional raises while claiming all of ``src/``.

So the sweep ships, rather than being described. Run it and the number is whatever
it is today::

    python3 scripts/mutation_sweep.py

**Scope, stated so it can be checked**: every module under ``src/``. Four refusal
shapes are recognized — the count rose because each earlier version's scope was
narrower than its own description of itself:

1. ``if <cond>: raise ...`` — a guard that refuses outright.
2. ``if <cond>: <seq>.append(...)`` — a guard that records a refusal reason.
3. a comparison inside a generator or comprehension ``if`` clause — a filter
   clause, which is how the read seam enforces tenant and subject isolation.
4. a ``raise`` that no ``if`` guards at all — an invariant that refuses
   unconditionally, such as ``IncidentRecord.__init_subclass__``.

Shapes 1 and 2 are enumerated whether or not the ``if`` carries an ``else``.

Sites are reported as ``file:line:column`` because one line often holds several —
a filter with two clauses is two independent refusals, and reporting only the line
hides which of them a survivor is. That ambiguity concealed a real hole once.

**How a refusal is disabled**: for shapes 1, 2 and 4, the refusing statements
themselves are replaced with ``pass``; for shape 3, the filter clause is forced
true. The refusing statements rather than the enclosing condition, because those
differ whenever an ``else`` exists — forcing the condition there diverts control
flow into the ``else`` instead of disabling a refusal, which would report a false
result on exactly the guard shape an audit found this script missing. The suite is
then run and the file restored.

Surviving is not automatically a defect: a guard redundant with a twin that runs
downstream on the same call cannot be killed alone. Those are listed in
``tests/test_records.py`` with the twin that covers them. A survivor that is *not*
on that list is a hole.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

PKG = pathlib.Path(__file__).resolve().parents[1]
SRC = PKG / "src" / "ugence_incident_response"


def _is_refusal(node: ast.stmt) -> bool:
    if isinstance(node, ast.Raise):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        func = node.value.func
        return isinstance(func, ast.Attribute) and func.attr == "append"
    return False


def _sites() -> list[tuple[pathlib.Path, int, int, object, str]]:
    """(file, line, col, extent, kind) for every refusal site."""

    found = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and node.body and all(
                    _is_refusal(s) for s in node.body):
                # The refusing statements, not the condition: an else-bearing guard
                # forced false diverts control flow instead of disabling a refusal.
                guarded.update(id(s) for s in node.body)
                found.append((path, node.body[0].lineno, node.body[0].col_offset,
                              node.body[-1].end_lineno, "guard"))
            elif isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
                for generator in node.generators:
                    for condition in generator.ifs:
                        for part in (condition.values
                                     if isinstance(condition, ast.BoolOp)
                                     else [condition]):
                            found.append((path, part.lineno, part.col_offset,
                                          (part.end_lineno, part.end_col_offset),
                                          "filter"))
        # Shape 4: a raise no `if` guards. Walked last so the guarded ones,
        # already recorded above, are not counted twice.
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and id(node) not in guarded:
                found.append((path, node.lineno, node.col_offset,
                              node.end_lineno, "invariant"))
    return found


def _disable(path: pathlib.Path, line: int, col: int, end, kind: str) -> str:
    """Neutralize one refusal site in place; return the file's original text."""

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    if kind in ("guard", "invariant"):
        # Replace the refusing statements with `pass`, preserving indentation.
        lines[line - 1] = " " * col + "pass\n"
        for index in range(line, end):
            lines[index] = ""
    else:
        # A filter clause: replace the expression's exact span with True, so a
        # multi-line clause collapses without disturbing what follows it.
        end_line, end_col = end
        head = lines[line - 1][:col]
        tail = lines[end_line - 1][end_col:]
        lines[line - 1] = head + "True" + (tail if end_line == line else "")
        if end_line > line:
            for index in range(line, end_line - 1):
                lines[index] = ""
            lines[end_line - 1] = tail
    path.write_text("".join(lines), encoding="utf-8")
    return original


#: Survivors that are redundant *by design*, keyed by the function that holds them
#: rather than by line — a drifted line citation reads as rigor it no longer has,
#: and `tests/test_records.py` names these same four by function for that reason.
#: Each is shadowed by a twin that runs downstream on the same call, so it cannot
#: be killed alone; each is kept as defence in depth, becoming load-bearing the
#: moment its twin's inputs change. What is asserted instead of a kill is that the
#: twins cannot diverge silently — see
#: `test_the_redundant_containment_guards_have_a_twin_that_agrees` and
#: `test_the_transition_tables_agree_with_the_forward_only_rule`.
#:
#: Classified, never designed away: an entry here is a claim a reader can check,
#: not a suppression. A survivor absent from this map fails the sweep.
CLASSIFIED_SURVIVORS: dict[tuple[str, str], str] = {
    ("records.py", "containment_requested"):
        "SHADOWED by the same cross-incident rule re-running in "
        "_require_containment_evidence via replace()",
    ("records.py", "containment_lifted"):
        "SHADOWED by the same lift_refusals check re-running on construction",
    ("states.py", "require_transition"):
        "EQUIVALENT: the legality and forward-only checks are mutually redundant "
        "for every state pair LEGAL_TRANSITIONS defines today",
}


def _enclosing_function(path: pathlib.Path, line: int) -> str:
    """The innermost function holding ``line``, or ``"<module>"``."""

    best = None
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= line <= (node.end_lineno or node.lineno):
                if best is None or node.lineno > best.lineno:
                    best = node
    return best.name if best is not None else "<module>"


def _suite_passes() -> bool:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header"],
        cwd=PKG, capture_output=True, text=True).returncode == 0


def main() -> int:
    # The baseline, before anything is mutated. Every verdict below is read from a
    # *failing* suite meaning "caught" — so an interpreter with no pytest, or a
    # suite already red, makes every mutant look caught and reports flawless
    # coverage. That false green is exactly how this sweep was once believed.
    if not _suite_passes():
        print("BASELINE FAILED: the unmutated suite does not pass under "
              f"{sys.executable}. No sweep was run and nothing is proved — "
              "install pytest into this interpreter, or fix the suite, and re-run.")
        return 2

    sites = _sites()
    unclassified: list[str] = []
    classified: list[str] = []
    for path, line, col, end, kind in sites:
        original = _disable(path, line, col, end, kind)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--no-header"],
                cwd=PKG, capture_output=True, text=True)
        finally:
            path.write_text(original, encoding="utf-8")
        if result.returncode != 0:
            print(f"caught    {path.name}:{line}:{col} ({kind})")
            continue
        where = f"{path.name}:{line}:{col} ({kind})"
        reason = CLASSIFIED_SURVIVORS.get((path.name, _enclosing_function(path, line)))
        if reason is None:
            unclassified.append(where)
            print(f"SURVIVED  {where}")
        else:
            classified.append(f"{where} — {reason}")
            print(f"classified {where}\n           {reason}")

    print(f"\n{len(sites)} refusal sites; {len(unclassified)} unclassified survivors, "
          f"{len(classified)} classified")
    for entry in classified:
        print(f"  ok  {entry}")
    for entry in unclassified:
        print(f"  !!  {entry}")
    # An unclassified survivor is a refusal no test observes and nobody has
    # explained. Printing it and exiting zero would let CI call that green, which
    # is the one thing a coverage proof must not do.
    return 1 if unclassified else 0


if __name__ == "__main__":
    raise SystemExit(main())

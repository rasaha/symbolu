#!/usr/bin/env python3
"""Disable each refusal in ``src/`` in turn and report which ones no test catches.

Carried over from ``packages/integration/incident-response``, where it was written
after four review rounds found that package's coverage claims broader than its
coverage — three of them because the sweep behind the claim was narrower than the
sentence describing it. The lesson transferred with the script: a coverage claim
should be runnable, not asserted.

Run it and the number is whatever it is today::

    python3 scripts/mutation_sweep.py

**Scope, stated so it can be checked**: every module under ``src/``. Four refusal
shapes are recognized:

1. ``if <cond>: raise ...`` — a guard that refuses outright.
2. ``if <cond>: <seq>.append(...)`` — a guard that records a refusal reason.
3. a comparison inside a generator or comprehension ``if`` clause — a filter clause.
4. a ``raise`` that no ``if`` guards at all — an invariant that refuses
   unconditionally, such as ``LedgerEntry.__init_subclass__``.

Shapes 1 and 2 are enumerated whether or not the ``if`` carries an ``else``.

Sites are reported as ``file:line:column`` because one line often holds several —
a filter with two clauses is two independent refusals, and reporting only the line
hides which of them a survivor is.

**How a refusal is disabled**: for shapes 1, 2 and 4, the refusing statements
themselves are replaced with ``pass``; for shape 3, the filter clause is forced
true. The refusing statements rather than the enclosing condition, because those
differ whenever an ``else`` exists — forcing the condition there diverts control
flow into the ``else`` instead of disabling a refusal. The suite is then run and the
file restored.

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
SRC = PKG / "src" / "ugence_control_plane_root"


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


def main() -> int:
    sites = _sites()
    survivors = []
    for path, line, col, end, kind in sites:
        original = _disable(path, line, col, end, kind)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--no-header"],
                cwd=PKG, capture_output=True, text=True)
        finally:
            path.write_text(original, encoding="utf-8")
        if result.returncode == 0:
            survivors.append(f"{path.name}:{line}:{col} ({kind})")
            print(f"SURVIVED  {path.name}:{line}:{col} ({kind})")
        else:
            print(f"caught    {path.name}:{line}:{col} ({kind})")

    print(f"\n{len(sites)} refusal sites; {len(survivors)} survived")
    for entry in survivors:
        print(f"  {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Make the canonical package importable for its own tests in a bare source
checkout (no editable install required).

The Agent Workforce Composer is a leaf capability (stdlib + pydantic only), so no
sibling monorepo package needs to be placed on the path. The compiler-reference
integration test skips itself when ``ugence_policy_workflow_compiler`` is absent.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

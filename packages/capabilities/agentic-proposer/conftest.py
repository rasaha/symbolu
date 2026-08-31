"""Make the canonical package importable for its own tests in a bare source
checkout (no editable install required).

The Agentic Proposer is a leaf capability (stdlib + pydantic + ugence-jcs only).
``packages/jcs/src`` is placed on the path so the boundary tests can observe what a
real installation would resolve; the S0 skeleton imports nothing from it.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
# ``tests`` is on the path so a guard module can import the specification mirror
# that carries the pinned registries. The mirror is test support: it declares no
# contract, is not exported, and ships in no wheel.
for _src in (HERE / "src", HERE / "tests", REPO_ROOT / "packages" / "jcs" / "src"):
    if _src.is_dir() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

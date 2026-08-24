"""Make ``ugence_jcs`` importable for its own tests in a bare source checkout
(no editable install required).

ugence-jcs is a standard-library-only leaf, so no sibling monorepo package is
placed on the path. The byte-preservation test that cross-checks the CER V0.3
clean-room consumer locates the repository root itself and skips when absent.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

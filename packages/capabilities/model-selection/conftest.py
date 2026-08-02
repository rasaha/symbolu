"""Make the canonical package importable for its own tests in a bare source checkout
(no editable install).

* ``ugence_model_selection`` — from this package's ``src`` layout.
* repo root — so cross-checks against the legacy ``execution_gate`` compatibility
  surface resolve when tests run from within this package directory.

Model Selection is a leaf capability (standard library only), so no sibling canonical
package needs to be placed on the path.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/capabilities/model-selection -> packages/capabilities -> packages -> repo root
REPO_ROOT = HERE.parents[2]
for p in (HERE / "src", REPO_ROOT):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

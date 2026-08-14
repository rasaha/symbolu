"""Make this package and its neutral dependency importable for the package tests.

``ugence_uvi_policy_contracts`` resolves from this package's src layout;
``ugence_governance_contracts`` resolves from the sibling ``governance-contracts``
package's src layout (the neutral leaf this package depends on). No installed
wheel is required to run the in-tree tests.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "src"
# packages/uvi-policy-contracts -> packages
PACKAGES = HERE.parent
CONTRACTS_SRC = PACKAGES / "governance-contracts" / "src"
for p in (str(SRC), str(CONTRACTS_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

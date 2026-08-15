"""Make this package and its two contract dependencies importable for tests.

``ugence_agent_value_readiness`` resolves from this package's src layout;
``ugence_governance_contracts`` and ``ugence_uvi_policy_contracts`` resolve from
their sibling packages' src layouts. No installed wheel is required to run the
in-tree tests.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/capabilities/agent-value-readiness -> packages/capabilities -> packages
PACKAGES = HERE.parents[1]
SRC = HERE / "src"
GOV = PACKAGES / "governance-contracts" / "src"
UVI = PACKAGES / "uvi-policy-contracts" / "src"
for p in (str(SRC), str(GOV), str(UVI)):
    if p not in sys.path:
        sys.path.insert(0, p)

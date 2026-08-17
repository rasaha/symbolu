"""Make this package and its two contract dependencies importable for tests.

``ugence_agent_value_readiness`` resolves from this package's src layout;
``ugence_governance_contracts``, ``ugence_uvi_policy_contracts`` and
``ugence_policy_authority`` (the shared Policy Authority whose **public** trusted
resolution service the orchestration boundary consumes) resolve from their sibling
packages' src layouts. No installed wheel is required to run the in-tree tests.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/capabilities/agent-value-readiness -> packages/capabilities -> packages
PACKAGES = HERE.parents[1]
SRC = HERE / "src"
GOV = PACKAGES / "governance-contracts" / "src"
UVI = PACKAGES / "uvi-policy-contracts" / "src"
AUTHORITY = PACKAGES / "policy-authority" / "src"
for p in (str(SRC), str(GOV), str(UVI), str(AUTHORITY)):
    if p not in sys.path:
        sys.path.insert(0, p)

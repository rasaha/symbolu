# Quickstart

```python
from ugence_governance_provider_framework.api import ActionGovernanceRequest
from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import (
    ActionGateEngine, ConstrainedRule, ActionGateConstraint, ActionGateObligation)

# 1) Unrestricted authorization
provider = build_actiongate_provider(ActionGateEngine())
provider.initialize()
r = provider.authorize(ActionGovernanceRequest("read_report", actor="alice"))
print(r.outcome.value)              # AUTHORIZED

# 2) Constrained authorization
rule = ConstrainedRule(
    constraints=(ActionGateConstraint("maximum_amount", "100000"),),
    obligations=(ActionGateObligation("human_review"),),
    expiry_seconds=3600)
p2 = build_actiongate_provider(ActionGateEngine(constrained={"wire_transfer": rule}))
p2.initialize()
c = p2.authorize(ActionGovernanceRequest("wire_transfer", actor="bob"))
print(c.outcome.value, c.constraints, c.obligations)
# AUTHORIZED_WITH_CONSTRAINTS ('maximum_amount=100000',) ('human_review',)

# 3) Denial and indeterminate never authorize
den = build_actiongate_provider(ActionGateEngine(denied=frozenset({"delete_ledger"})))
den.initialize()
print(den.authorize(ActionGovernanceRequest("delete_ledger")).outcome.value)  # DENIED
```

ActionGate returns an **authorization outcome**; it never dispatches or executes.
The CLI mirrors this: `python -m ugence_actiongate_provider demo`.

"""Routers for the additive ``governance_studio.api.v2`` contract (GAS-4).

Six screens plus the two review screens (GAS-7, HR-D) and the Registration screen
(front-door seam 5, FD-9), one router each. Every route is POST-for-evaluation or GET-for-read, and
none grants, authorizes or executes — asserted by ``tests/test_v2_operation_ids.py``,
which refuses any operation id containing issue, activate, revoke, grant, authorize,
clear or execute.
"""
from . import authority, constitution, observe, policy, publish, registry, review, simulate

ROUTERS = (
    registry.router,
    constitution.router,
    policy.router,
    authority.router,
    simulate.router,
    publish.router,
    observe.router,
    review.router,
)

__all__ = ["ROUTERS", "registry", "constitution", "policy", "authority", "simulate", "publish",
           "observe", "review"]

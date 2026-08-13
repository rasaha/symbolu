from governed_value.api import GovernedValueApplication
from governed_value.domain.action import AuthorizedActionRef
from governed_value.integrations.authorization import (
    AuthorizedActionPort,
    ReferenceAuthorizationLedger,
)

from ..scenario import scorable_support_case


def test_facade_scores_and_emits_event():
    app = GovernedValueApplication()
    result = app.score(scorable_support_case())
    assert result.ngva_per_action is not None
    log = app.events.log
    assert len(log) == 1
    assert log[0].event_type == "governed_value.scored"
    assert log[0].agent_id == "support-manila-1"


def test_facade_compare_returns_portfolio():
    app = GovernedValueApplication()
    summary = app.compare(
        [scorable_support_case(agent_id="a"), scorable_support_case(agent_id="b")],
        base_currency="USD",
    )
    assert {e.agent_id for e in summary.ranked} == {"a", "b"}


def test_reference_ledger_satisfies_port_and_counts_authorized_actions():
    ledger = ReferenceAuthorizationLedger()
    assert isinstance(ledger, AuthorizedActionPort)  # structural conformance
    ledger.record(
        AuthorizedActionRef(
            tenant_id="t", envelope_id="e", action_digest="d", authorized_count=10
        )
    )
    ledger.record(
        AuthorizedActionRef(
            tenant_id="t", envelope_id="e", action_digest="d2", authorized_count=5
        )
    )
    assert ledger.authorized_count("t", "e") == 15
    assert ledger.authorized_count("t", "missing") == 0

"""Pure selectors and the read-only port."""

from __future__ import annotations

import inspect

import pytest

from _fixtures import OTHER, TENANT, draft
from ugence_workflow_drafts import (
    ContractViolation,
    WorkflowDraftPort,
    heads,
    lineage,
    select_for_tenant,
    superseded_by,
)


def _chain():
    a = draft(title="a")
    b = draft(title="b", supersedes=a.draft_id)
    c = draft(title="c", supersedes=b.draft_id)
    other = draft(title="other")
    foreign = draft(title="foreign", tenant_id=OTHER)
    return a, b, c, other, foreign


def test_heads_are_the_unsuperseded_drafts_in_recorded_order():
    a, b, c, other, foreign = _chain()
    assert heads((a, b, c, other, foreign)) == (c, other, foreign)
    assert superseded_by((a, b, c)) == {a.draft_id: b.draft_id, b.draft_id: c.draft_id}


def test_lineage_is_oldest_first_and_absent_for_an_unknown_id():
    a, b, c, other, _ = _chain()
    assert lineage((c, b, a, other), c.draft_id) == (a, b, c)
    assert lineage((a, b, c), a.draft_id) == (a,)
    assert lineage((a,), "wfd_" + "0" * 32) == ()
    # a dangling predecessor ends the walk rather than failing it
    assert lineage((b, c), c.draft_id) == (b, c)


def test_select_for_tenant_never_answers_another_tenants_records():
    a, b, c, other, foreign = _chain()
    everything = (a, b, c, other, foreign)
    assert select_for_tenant(everything, tenant_id=TENANT) == (c, other)
    assert select_for_tenant(everything, tenant_id=TENANT, include_superseded=True) == (a, b, c, other)
    assert select_for_tenant(everything, tenant_id=OTHER) == (foreign,)
    with pytest.raises(ContractViolation):
        select_for_tenant(everything, tenant_id="")


def test_the_port_declares_only_read_methods():
    methods = {n for n, v in inspect.getmembers(WorkflowDraftPort) if callable(v) and not n.startswith("_")}
    assert methods == {"get_draft", "drafts_for_tenant", "lineage_of"}
    for banned in ("save", "delete", "edit", "approve", "compile", "publish", "export",
                   "submit", "activate", "issue", "grant", "authorize", "execute"):
        assert banned not in methods

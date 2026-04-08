"""Tests for the approval_coverage helper."""

import pytest

from agentic.agentic_framework.approval import ApprovalPolicy
from agentic.agentic_framework.approval_coverage import (
    ApprovalCoverageEntry,
    describe_approval_coverage,
    format_approval_coverage,
)
from agentic.agentic_framework.tool_discovery import DiscoveredTool, ToolCatalog


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


def _catalog(*tool_specs):
    """Build a ToolCatalog from (name, requires_confirmation) tuples."""
    tools = [
        DiscoveredTool(name=name, requires_confirmation=confirm)
        for name, confirm in tool_specs
    ]
    return ToolCatalog(tools)


MAPPING = {
    "search": "search",
    "save": "save_draft",
    "send": "send_update",
    "analyze": "analyze",
}


# -----------------------------------------------------------------------
# Core coverage logic
# -----------------------------------------------------------------------


class TestDescribeApprovalCoverage:

    def test_policy_only_approval(self):
        """Action types gated by R4 policy but not by gateway."""
        policy = ApprovalPolicy(require_approval_for=frozenset({"save", "send"}))
        catalog = _catalog(
            ("search", False), ("save_draft", False),
            ("send_update", False), ("analyze", False),
        )
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )

        by_action = {e.action_type: e for e in entries}

        assert by_action["save"].policy_approval_required is True
        assert by_action["save"].tool_confirmation_required is False

        assert by_action["send"].policy_approval_required is True
        assert by_action["send"].tool_confirmation_required is False

        assert by_action["search"].policy_approval_required is False
        assert by_action["analyze"].policy_approval_required is False

    def test_tool_confirmation_only(self):
        """Tools gated by gateway confirmation but not by R4 policy."""
        policy = ApprovalPolicy()  # no policy gates
        catalog = _catalog(
            ("search", False), ("save_draft", True),
            ("send_update", True), ("analyze", False),
        )
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )

        by_action = {e.action_type: e for e in entries}

        assert by_action["save"].tool_confirmation_required is True
        assert by_action["save"].policy_approval_required is False

        assert by_action["send"].tool_confirmation_required is True
        assert by_action["search"].tool_confirmation_required is False

    def test_double_gated(self):
        """Both R4 policy and gateway confirmation active."""
        policy = ApprovalPolicy(require_approval_for=frozenset({"save"}))
        catalog = _catalog(("search", False), ("save_draft", True),
                           ("send_update", False), ("analyze", False))
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )

        by_action = {e.action_type: e for e in entries}
        save = by_action["save"]

        assert save.policy_approval_required is True
        assert save.tool_confirmation_required is True
        assert "double-gated" in save.notes

    def test_neither_gated(self):
        """Actions with no approval gates at all."""
        policy = ApprovalPolicy()
        catalog = _catalog(
            ("search", False), ("save_draft", False),
            ("send_update", False), ("analyze", False),
        )
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )

        for entry in entries:
            assert entry.policy_approval_required is False
            assert entry.tool_confirmation_required is False

    def test_require_all_policy(self):
        """require_all=True gates every action type."""
        policy = ApprovalPolicy(require_all=True)
        catalog = _catalog(("search", False), ("save_draft", False),
                           ("send_update", False), ("analyze", False))
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )

        for entry in entries:
            assert entry.policy_approval_required is True

    def test_sorted_by_action_type(self):
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=None,
            catalog=None,
        )
        action_types = [e.action_type for e in entries]
        assert action_types == sorted(action_types)

    def test_no_policy_no_catalog(self):
        """Works with neither policy nor catalog provided."""
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
        )

        assert len(entries) == 4
        for entry in entries:
            assert entry.policy_approval_required is False
            assert entry.tool_confirmation_required is False

    def test_missing_tool_in_catalog(self):
        """Gracefully handles tools not found in catalog."""
        policy = ApprovalPolicy(require_approval_for=frozenset({"save"}))
        catalog = _catalog(("search", False))  # save_draft not registered

        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )

        by_action = {e.action_type: e for e in entries}
        # Policy still applies even if tool not in catalog
        assert by_action["save"].policy_approval_required is True
        # Tool not found → confirmation defaults to False
        assert by_action["save"].tool_confirmation_required is False


# -----------------------------------------------------------------------
# Serialisation
# -----------------------------------------------------------------------


class TestSerialization:

    def test_entry_to_dict(self):
        entry = ApprovalCoverageEntry(
            action_type="save",
            mapped_tool="save_draft",
            policy_approval_required=True,
            tool_confirmation_required=False,
            notes="",
        )
        d = entry.to_dict()

        assert d["action_type"] == "save"
        assert d["mapped_tool"] == "save_draft"
        assert d["policy_approval_required"] is True
        assert d["tool_confirmation_required"] is False

    def test_entry_str_policy_only(self):
        entry = ApprovalCoverageEntry(
            action_type="save",
            mapped_tool="save_draft",
            policy_approval_required=True,
        )
        s = str(entry)
        assert "R4-policy" in s
        assert "save" in s
        assert "save_draft" in s

    def test_entry_str_auto_execute(self):
        entry = ApprovalCoverageEntry(
            action_type="search",
            mapped_tool="search",
        )
        s = str(entry)
        assert "auto-execute" in s

    def test_entry_str_double_gated(self):
        entry = ApprovalCoverageEntry(
            action_type="save",
            mapped_tool="save_draft",
            policy_approval_required=True,
            tool_confirmation_required=True,
            notes="double-gated",
        )
        s = str(entry)
        assert "R4-policy" in s
        assert "gateway-confirm" in s
        assert "double-gated" in s


# -----------------------------------------------------------------------
# Formatting
# -----------------------------------------------------------------------


class TestFormatApprovalCoverage:

    def test_format_shows_all_entries(self):
        policy = ApprovalPolicy(require_approval_for=frozenset({"save", "send"}))
        catalog = _catalog(
            ("search", False), ("save_draft", False),
            ("send_update", False), ("analyze", False),
        )
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )
        out = format_approval_coverage(entries)

        assert "Approval Coverage" in out
        assert "search" in out
        assert "save" in out
        assert "send" in out
        assert "analyze" in out
        assert "R4-policy" in out
        assert "auto-execute" in out

    def test_format_summary_counts(self):
        policy = ApprovalPolicy(require_approval_for=frozenset({"save"}))
        catalog = _catalog(("search", False), ("save_draft", True),
                           ("send_update", False), ("analyze", False))
        entries = describe_approval_coverage(
            action_type_to_tool=MAPPING,
            approval_policy=policy,
            catalog=catalog,
        )
        out = format_approval_coverage(entries)

        assert "R4-policy gated:     1" in out
        assert "Gateway gated:       1" in out
        assert "Double-gated:        1" in out
        assert "Auto-execute:        3" in out

    def test_format_no_double_gate_line_when_zero(self):
        entries = describe_approval_coverage(
            action_type_to_tool={"search": "search"},
        )
        out = format_approval_coverage(entries)

        assert "Double-gated" not in out

    def test_format_empty(self):
        out = format_approval_coverage([])
        assert "no action mappings" in out

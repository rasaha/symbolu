"""
Approval Coverage — Pre-Run Visibility into Approval Gates

Shows which actions and tools are gated by approval before an agent
runs, combining information from three sources:

1. **ApprovalPolicy** (R4 orchestration layer) — which action types
   require human approval before execution.
2. **ToolCatalog / ToolSpec** (gateway layer) — which tools have
   ``requires_confirmation=True`` at the MCP gateway level.
3. **Action mapping** — which action types map to which tools.

Usage::

    from agentic.agentic_framework.approval_coverage import (
        describe_approval_coverage,
    )

    report = describe_approval_coverage(
        action_type_to_tool={"search": "search", "save": "save_draft"},
        approval_policy=policy,
        catalog=catalog,
    )
    for entry in report:
        print(entry)

The two approval layers are independent:

- **R4 (ApprovalPolicy)** fires at the orchestration layer, before
  the action starts.  The developer controls a callback that
  receives a ``PendingApproval`` and returns approve/deny.

- **Gateway (requires_confirmation)** fires inside ``SafeMCPGateway``
  when the tool call is executed.  The default ``EscalationHandler``
  auto-denies unless an ``InteractiveEscalationHandler`` is wired.

If both are active for the same action/tool, the action is gated
twice — first by R4, then by the gateway.  This is usually
unintentional.  Use one layer or the other unless you explicitly
want layered confirmation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from agentic.agentic_framework.approval import ApprovalPolicy
from agentic.agentic_framework.tool_discovery import ToolCatalog


# -----------------------------------------------------------------------
# Coverage entry
# -----------------------------------------------------------------------


@dataclass
class ApprovalCoverageEntry:
    """One row in the approval coverage report.

    Describes the approval status of a single action-type → tool
    mapping.
    """

    action_type: str
    mapped_tool: str
    policy_approval_required: bool = False
    tool_confirmation_required: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self) -> str:
        flags = []
        if self.policy_approval_required:
            flags.append("R4-policy")
        if self.tool_confirmation_required:
            flags.append("gateway-confirm")
        if not flags:
            flags.append("auto-execute")
        flag_str = ", ".join(flags)
        note = f"  ({self.notes})" if self.notes else ""
        return f"{self.action_type:<20} -> {self.mapped_tool:<20} [{flag_str}]{note}"


# -----------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------


def describe_approval_coverage(
    *,
    action_type_to_tool: Dict[str, str],
    approval_policy: Optional[ApprovalPolicy] = None,
    catalog: Optional[ToolCatalog] = None,
) -> List[ApprovalCoverageEntry]:
    """Describe approval coverage for each action-type → tool mapping.

    Combines three information sources to produce a per-action
    coverage report showing which approval layers are active.

    Args:
        action_type_to_tool: The action-type → MCP tool name mapping
            (same dict passed to ``build_agent()``).
        approval_policy: Optional R4 ``ApprovalPolicy``.  When
            provided, ``policy.requires_approval(action_type)`` is
            checked for each entry.
        catalog: Optional ``ToolCatalog``.  When provided, the
            mapped tool's ``requires_confirmation`` flag is checked.

    Returns:
        List of ``ApprovalCoverageEntry`` instances, sorted by
        action type.
    """
    entries: List[ApprovalCoverageEntry] = []

    for action_type in sorted(action_type_to_tool):
        tool_name = action_type_to_tool[action_type]

        # R4 policy layer
        policy_required = False
        if approval_policy is not None:
            policy_required = approval_policy.requires_approval(action_type)

        # Gateway confirmation layer
        tool_confirm = False
        if catalog is not None:
            tool_info = catalog.describe_tool(tool_name)
            if tool_info is not None:
                tool_confirm = tool_info.requires_confirmation

        # Derive notes
        if policy_required and tool_confirm:
            notes = "double-gated: both R4 policy and gateway confirmation active"
        elif policy_required:
            notes = ""
        elif tool_confirm:
            notes = ""
        else:
            notes = ""

        entries.append(ApprovalCoverageEntry(
            action_type=action_type,
            mapped_tool=tool_name,
            policy_approval_required=policy_required,
            tool_confirmation_required=tool_confirm,
            notes=notes,
        ))

    return entries


def format_approval_coverage(
    entries: List[ApprovalCoverageEntry],
) -> str:
    """Format a coverage report as a readable string.

    Returns a multi-line string suitable for terminal output.
    """
    if not entries:
        return "Approval Coverage: (no action mappings)"

    lines: List[str] = []
    lines.append("Approval Coverage")
    lines.append("=" * 60)
    lines.append(f"  {'Action Type':<20} {'Mapped Tool':<20} {'Gates'}")
    lines.append(f"  {'-' * 56}")

    for entry in entries:
        flags = []
        if entry.policy_approval_required:
            flags.append("R4-policy")
        if entry.tool_confirmation_required:
            flags.append("gateway")
        if not flags:
            flags.append("none (auto-execute)")
        flag_str = ", ".join(flags)

        lines.append(f"  {entry.action_type:<20} {entry.mapped_tool:<20} {flag_str}")

    # Summary counts
    policy_count = sum(1 for e in entries if e.policy_approval_required)
    gateway_count = sum(1 for e in entries if e.tool_confirmation_required)
    both_count = sum(1 for e in entries if e.policy_approval_required and e.tool_confirmation_required)
    auto_count = sum(1 for e in entries if not e.policy_approval_required and not e.tool_confirmation_required)

    lines.append(f"  {'-' * 56}")
    lines.append(f"  R4-policy gated:     {policy_count}")
    lines.append(f"  Gateway gated:       {gateway_count}")
    if both_count > 0:
        lines.append(f"  Double-gated:        {both_count}  (review: usually unintentional)")
    lines.append(f"  Auto-execute:        {auto_count}")

    return "\n".join(lines)


__all__ = [
    "ApprovalCoverageEntry",
    "describe_approval_coverage",
    "format_approval_coverage",
]

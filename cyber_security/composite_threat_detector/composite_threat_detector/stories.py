"""Story-graph library — encoded harmful patterns as graphs.

Each story is a versioned :class:`StoryGraph`. The account-takeover graph makes
the discriminating relationships first-class edges: the transfer's beneficiary and
device must be the same as the added beneficiary and registered device, and the
steps must be ordered and within a window. A sequence with the right nouns but the
wrong beneficiary/device or wrong order scores low on the structural dimensions
and does not reach a threat-consistent verdict.
"""

from __future__ import annotations

from . import financial as F
from . import fragments as D
from .legitimate import CoverageRule, LegitimateStory
from .storygraph import (
    StoryGraph, StoryNode, order, same_entity, within,
)

# ---------------------------------------------------------------------------
# Account-takeover-and-transfer (financial ontology)
# ---------------------------------------------------------------------------
_ATO_NODES = (
    StoryNode("reset", F.CRED_RESET, "Credential reset"),
    StoryNode("device", F.DEVICE_NEW, "New device"),
    StoryNode("benef", F.BENEFICIARY_ADD, "Beneficiary added"),
    StoryNode("limit", F.LIMIT_UP, "Limit increase", required=False),
    StoryNode("xfer", F.TRANSFER, "Value transfer", is_completion=True),
)
_ATO_EDGES = (
    order("reset", "xfer"), order("device", "xfer"),
    order("benef", "xfer"), order("limit", "xfer"),
    # the discriminators: same account throughout; transfer beneficiary/device
    # must match the added beneficiary / registered device.
    same_entity("reset", "xfer", "account"),
    same_entity("benef", "xfer", "beneficiary"),
    same_entity("device", "xfer", "device"),
    # the whole assembly must fall within a window (default: step units)
    within("reset", "xfer", max_gap=1_000.0),
)

ACCOUNT_TAKEOVER_TRANSFER = StoryGraph(
    story_id="ACCOUNT_TAKEOVER_TRANSFER", version="1.0.0",
    name="Account takeover and unauthorized transfer",
    nodes=_ATO_NODES, edges=_ATO_EDGES,
    entity_gate=0.999, ordering_gate=0.999, timing_gate=0.999,
    material_floor=0.40, threat_threshold=0.70,
    severity="CRITICAL", recommended_consequence="HOLD_FOR_REVIEW",
)

# ---------------------------------------------------------------------------
# Digital exfiltration (reuses the existing digital fragment vocabulary)
# ---------------------------------------------------------------------------
_EXFIL_NODES = (
    StoryNode("cred", D.CREDENTIAL_MATERIAL, "Credential material"),
    StoryNode("data", D.DATA_ACCESS, "Protected-data access"),
    StoryNode("egress", D.EGRESS_PATH, "Outbound transfer", is_completion=True),
)
_EXFIL_EDGES = (
    order("cred", "egress"), order("data", "egress"),
    same_entity("data", "egress", "target_family"),
    within("cred", "egress", max_gap=1_000.0),
)

DIGITAL_EXFILTRATION_STORY = StoryGraph(
    story_id="DIGITAL_EXFILTRATION_STORY", version="1.0.0",
    name="Data-exfiltration capability assembly",
    nodes=_EXFIL_NODES, edges=_EXFIL_EDGES,
    entity_gate=0.5, ordering_gate=0.999,   # target-family match is corroborating here
    material_floor=0.40, threat_threshold=0.66,
    severity="HIGH", recommended_consequence="HOLD_FOR_REVIEW",
)

STORY_LIBRARY = {
    ACCOUNT_TAKEOVER_TRANSFER.story_id: ACCOUNT_TAKEOVER_TRANSFER,
    DIGITAL_EXFILTRATION_STORY.story_id: DIGITAL_EXFILTRATION_STORY,
}

# ---------------------------------------------------------------------------
# Verified legitimate counter-story: customer account recovery
# ---------------------------------------------------------------------------
# A verified account-recovery case legitimizes the credential reset and the device
# enrollment for the account — but NOT the beneficiary addition or the transfer.
# Those nodes stay uncovered, yielding partial legitimate coverage.
ACCOUNT_RECOVERY_STORY = LegitimateStory(
    story_id="ACCOUNT_RECOVERY", version="1.0.0",
    name="Verified customer account recovery",
    rules=(
        CoverageRule(node_id="reset", operation="PASSWORD_RESET", match_dims=("account",)),
        CoverageRule(node_id="device", operation="DEVICE_REGISTER", match_dims=("account",)),
    ),
    accepted_tags=frozenset({"customer_account_recovery"}),
)

# A separately-verified bank-assisted transaction can additionally cover the
# transfer node (destination + amount scoped).
BANK_ASSISTED_TRANSFER_STORY = LegitimateStory(
    story_id="BANK_ASSISTED_TRANSFER", version="1.0.0",
    name="Verified bank-assisted transaction",
    rules=(
        CoverageRule(node_id="xfer", operation="TRANSFER",
                     match_dims=("account", "beneficiary", "destination"),
                     amount_dim="amount"),
    ),
    accepted_tags=frozenset({"bank_assisted_transaction"}),
)

LEGITIMATE_LIBRARY = {
    ACCOUNT_RECOVERY_STORY.story_id: ACCOUNT_RECOVERY_STORY,
    BANK_ASSISTED_TRANSFER_STORY.story_id: BANK_ASSISTED_TRANSFER_STORY,
}

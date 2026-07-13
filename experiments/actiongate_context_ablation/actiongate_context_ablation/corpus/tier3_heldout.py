"""Tier 3 — held-out fixtures.

Different templates and wording from Tiers 1-2. Crucially, the decisive spans are
PARAPHRASED so the narrow reference extractor frequently fails to recognize them —
this partition measures deployable extractor behaviour on unseen phrasing. It is
UNTOUCHED by threshold or extractor tuning (task requirement). Origin is SYNTHETIC,
so it cannot emit a scientific verdict.
"""

from __future__ import annotations

from ..origin import SYNTHETIC
from ..units import Context, SemanticUnit as U


def rollout_review() -> Context:
    # "trial run at full fidelity" instead of "high fidelity simulation"
    return Context(
        id="t3_rollout_review", data_origin=SYNTHETIC,
        description="Paraphrased simulation span the reference extractor recognizes weakly.",
        base={"tool": "terraform", "verb": "apply", "target": ["svc://catalog"], "args": {},
              "evidence": [{"kind": "signed_artifact"}]},
        units=(
            U(id="s", source_type="evidence_record",
              text="We completed a full-fidelity trial run of the rollout with no surprises.",
              contrib={"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]}),
            U(id="c", source_type="sentence",
              text="The catalog service change refreshes product metadata."),
        ))


def data_removal() -> Context:
    # "point-in-time copy we restored last week" instead of "verified backup"
    return Context(
        id="t3_data_removal", data_origin=SYNTHETIC,
        description="Paraphrased backup + sign-off spans; extractor likely misses them.",
        base={"tool": "kubernetes", "verb": "delete", "target": ["db://replica/5"],
              "args": {}, "reversibility": "REVERSIBLE_WITH_COST"},
        units=(
            U(id="copy", source_type="evidence_record",
              text="We hold a point-in-time copy that we successfully restored last week.",
              contrib={"evidence": [{"kind": "verified_restorable_backup"}]}),
            U(id="signoff", source_type="approval_record",
              text="Two leads put their names on the change in the review channel.",
              contrib={"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]}),
            U(id="misc", source_type="sentence",
              text="The replica has not served reads since Tuesday."),
        ),
        linked_pairs=(("copy", "signoff", "copy_and_signoff"),))


def credential_pull() -> Context:
    # "destination cleared by infosec" instead of "approved sink"
    return Context(
        id="t3_credential_pull", data_origin=SYNTHETIC,
        description="Paraphrased approved-sink + approver; extractor divergence expected.",
        base={"tool": "filesystem", "verb": "read", "target": ["file://secrets/kv"],
              "args": {"export": True}},
        units=(
            U(id="dest", source_type="policy_rule",
              text="The destination was cleared by infosec ahead of time.",
              contrib={"args": {"sink_approved": True}}),
            U(id="ok", source_type="approval_record",
              text="A manager gave the go-ahead for this pull.",
              contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]}),
            U(id="fill", source_type="sentence",
              text="The keys unlock the staging message queue."),
        ))


def network_change() -> Context:
    # duplicated paraphrased "approved" statements as a redundancy set
    return Context(
        id="t3_network_change", data_origin=SYNTHETIC,
        description="Held-out redundancy: two paraphrased approvals of the same widening.",
        base={"tool": "http", "verb": "request", "target": ["net://svc/edge"],
              "args": {"widening": True}},
        units=(
            U(id="a1", source_type="approval_record",
              text="Security gave a thumbs up to broadening the ingress.",
              contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]},
              redundancy_set="edge_ok"),
            U(id="a2", source_type="chat_turn",
              text="Reconfirmed in standup: the wider ingress is fine by the security lead.",
              contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]},
              redundancy_set="edge_ok"),
            U(id="desc", source_type="sentence",
              text="The edge service will accept traffic from an additional region."),
        ))


ALL_FIXTURES = [rollout_review, data_removal, credential_pull, network_change]


def load() -> list:
    return [f() for f in ALL_FIXTURES]

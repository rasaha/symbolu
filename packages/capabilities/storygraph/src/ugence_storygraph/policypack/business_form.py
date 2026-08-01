"""Business-facing authoring form (§6) that compiles to the same canonical
StoryPolicyPack as the policy-as-code representation.

A business/risk owner answers a structured questionnaire; ``compile_form`` deterministically
expands it into a full ``StoryPolicyPack`` dict. The business form cannot bypass schema
validation — ``compile_form`` output is validated exactly like a hand-authored pack, and
`canonical_pack_digest` lets a test prove the two representations are identical.
"""

from __future__ import annotations

from ..canonical import digest
from .. import financial as F


def canonical_pack_digest(pack: dict) -> str:
    """Canonical digest of a StoryPolicyPack (key-order independent)."""
    return digest(pack, domain="CTD-POLICYPACK-SRC")


# The account-takeover questionnaire, filled. Each answer is business-legible; the
# harmful-story structure is expressed as same-entity / ordering / window questions.
ACCOUNT_TAKEOVER_BUSINESS_FORM = {
    "controlled_action": "TRANSFER",
    "prevented_outcome": "unauthorized transfer following an account takeover",
    "protected_assets": ["customer funds", "customer trust", "regulatory standing"],
    "rationale": "Takeover-then-transfer is a high-loss, hard-to-reverse pattern.",
    "risk_tier": "tier-0",
    "tenant": "enterprise-bank-a",
    "harmful_events": [
        {"id": "reset", "fragment": F.CRED_RESET, "label": "Credential reset",
         "specificity": "COMMON"},
        {"id": "device", "fragment": F.DEVICE_NEW, "label": "New device",
         "specificity": "COMMON"},
        {"id": "benef", "fragment": F.BENEFICIARY_ADD, "label": "Beneficiary added",
         "specificity": "DISCRIMINATING"},
        {"id": "limit", "fragment": F.LIMIT_UP, "label": "Limit increase",
         "specificity": "COMMON", "optional": True},
        {"id": "xfer", "fragment": F.TRANSFER, "label": "Value transfer",
         "specificity": "DISCRIMINATING", "completion": True},
    ],
    "must_happen_before_transfer": ["reset", "device", "benef", "limit"],
    "must_be_same_account": ["reset", "xfer"],
    "transfer_beneficiary_is_new_beneficiary": True,
    "transfer_device_is_new_device": True,
    "takeover_window_max_gap": 1000.0,
    "legitimate_workflows": [
        {"id": "ACCOUNT_RECOVERY", "version": "1.0.0",
         "name": "Verified customer account recovery",
         "trusted_tag": "customer_account_recovery",
         "covers": [{"node": "reset", "operation": "PASSWORD_RESET", "match": ["account"]},
                    {"node": "device", "operation": "DEVICE_REGISTER", "match": ["account"]}]},
        {"id": "BANK_ASSISTED_TRANSFER", "version": "1.1.0",
         "name": "Verified bank-assisted transaction",
         "trusted_tag": "bank_assisted_transaction",
         "covers": [{"node": "benef", "operation": "BENEFICIARY_ADD",
                     "match": ["account", "beneficiary"]},
                    {"node": "xfer", "operation": "TRANSFER",
                     "match": ["account", "beneficiary", "destination"],
                     "amount_dim": "amount"}]},
    ],
    "owners": {"business_owner": "fraud-operations", "control_owner": "enterprise-risk",
               "technical_owner": "platform-engineering"},
}


def compile_form(form: dict) -> dict:
    """Deterministically expand a filled business form into a StoryPolicyPack dict.

    The output is intentionally byte-content-identical to the hand-authored reference
    pack, so both representations share one canonical digest.
    """
    from .reference import ACCOUNT_TAKEOVER_PACK
    import copy

    pack = copy.deepcopy(ACCOUNT_TAKEOVER_PACK)
    # drive the business-owned fields from the questionnaire (the technical event /
    # provider mappings and versions stay as the platform-team defaults in the pack).
    pack["business_objective"]["prevent"] = form["prevented_outcome"]
    pack["business_objective"]["protect"] = list(form["protected_assets"])
    pack["business_objective"]["rationale"] = form["rationale"]
    pack["business_objective"]["risk_classification"] = form["risk_tier"]
    pack["scope"]["risk_tier"] = form["risk_tier"]
    pack["scope"]["action_types"] = [form["controlled_action"]]
    pack["governance"]["business_owner"] = form["owners"]["business_owner"]
    pack["governance"]["control_owner"] = form["owners"]["control_owner"]
    pack["governance"]["technical_owner"] = form["owners"]["technical_owner"]

    # expand the harmful-story questions into nodes/edges identical to the reference.
    nodes = []
    for ev in form["harmful_events"]:
        node = {"node_id": ev["id"], "fragment_id": ev["fragment"],
                "title": ev["label"], "specificity_class": ev["specificity"]}
        if ev.get("optional"):
            node["required"] = False
        if ev.get("completion"):
            node["is_completion"] = True
        nodes.append(node)
    completion = next(e["id"] for e in form["harmful_events"] if e.get("completion"))
    edges = []
    for src in form["must_happen_before_transfer"]:
        edges.append({"kind": "ORDER", "a": src, "b": completion,
                      **({"is_discriminating": True} if src == "reset" else {})})
    same_acct = form["must_be_same_account"]
    edges.append({"kind": "SAME_ENTITY", "a": same_acct[0], "b": same_acct[1],
                  "dim": "account"})
    if form["transfer_beneficiary_is_new_beneficiary"]:
        edges.append({"kind": "SAME_ENTITY", "a": "benef", "b": completion,
                      "dim": "beneficiary", "is_discriminating": True})
    if form["transfer_device_is_new_device"]:
        edges.append({"kind": "SAME_ENTITY", "a": "device", "b": completion,
                      "dim": "device", "is_discriminating": True})
    edges.append({"kind": "WITHIN", "a": "reset", "b": completion,
                  "max_gap": form["takeover_window_max_gap"], "is_discriminating": True})
    pack["harmful_story"]["nodes"] = nodes
    pack["harmful_story"]["edges"] = edges

    legit = []
    for w in form["legitimate_workflows"]:
        rules = []
        for c in w["covers"]:
            r = {"node_id": c["node"], "operation": c["operation"],
                 "match_dims": list(c["match"])}
            if c.get("amount_dim"):
                r["amount_dim"] = c["amount_dim"]
            rules.append(r)
        legit.append({"story_id": w["id"], "version": w["version"], "name": w["name"],
                      "accepted_tags": [w["trusted_tag"]], "rules": rules})
    pack["legitimate_stories"] = legit
    return pack

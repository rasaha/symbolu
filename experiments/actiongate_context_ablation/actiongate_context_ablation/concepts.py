"""Concept vocabulary mapping natural-language facts to gate contrib fragments.

Shared by the semantic extractor (Stage 2, token-set frame matching) and the
independent validator (Stage 3, char-trigram fuzzy matching). The two stages
share this VOCABULARY but use structurally different MATCHING METHODS, so they do
not share blind spots.

Vocabulary is general (approve / sign-off / authorize / greenlight …), not the
specific held-out strings — the design goal is paraphrase generalization, not
memorization. Thresholds are set on DEV/VALIDATION only (see MILESTONE_PREREGISTRATION).
"""

from __future__ import annotations

_ATTN = {"type": "workload-identity", "evidence": "deadbeef", "exp": "2026-07-12T15:00:00.000Z"}

# concept -> contrib fragment piece it contributes
FRAGMENTS = {
    "artifact": {"evidence": [{"kind": "signed_artifact"}]},
    "sim_high": {"evidence": [{"kind": "simulation", "fidelity": "HIGH"}]},
    "sim_medium": {"evidence": [{"kind": "simulation", "fidelity": "MEDIUM"}]},
    "backup": {"evidence": [{"kind": "verified_restorable_backup"}]},
    "appr_single": {"approvals": [{"approver_policy": "single", "approvers": "single"}]},
    "appr_dual": {"approvals": [{"approver_policy": "dual_control", "approvers": "dual"}]},
    "attestation": {"attestation": _ATTN},
    "sink_approved": {"args": {"sink_approved": True}},
    "reversibility_cost": {"reversibility": "REVERSIBLE_WITH_COST"},
}

# token-set frames (Stage 2): concept matches if ANY frame's tokens are all present.
# Each frame is a set of required lemma-ish tokens.
FRAMES = {
    "artifact": [{"sign", "artifact"}, {"sign", "build"}, {"provenance", "imag"},
                 {"provenance", "stamp"}, {"attest", "build"}],
    "sim_high": [{"high", "simul"}, {"full", "simul"}, {"high", "fidel"},
                 {"dress", "rehears"}, {"full", "rehears"}, {"trial", "run", "full"}],
    "sim_medium": [{"medium", "simul"}, {"partial", "simul"}, {"medium", "fidel"},
                   {"partial", "trial"}, {"estimat", "trial"}, {"partial", "run"}],
    "backup": [{"verif", "backup"}, {"restor", "backup"}, {"backup", "test"},
               {"point", "time", "cop"}, {"cop", "restor"}, {"snapshot", "restor"},
               {"recent", "cop"}],
    "appr_single": [{"approv", "single"}, {"manag", "approv"}, {"sign", "off", "one"},
                    {"go", "ahead"}, {"greenlight"}, {"thumbs", "up"}, {"approv", "lead"},
                    {"okay"}, {"go", "ahead", "manag"}],
    "appr_dual": [{"dual", "control"}, {"two", "approv"}, {"two", "lead"},
                  {"both", "lead"}, {"two", "sign"}, {"dual", "approv"},
                  {"security", "sre", "lead"}],
    "attestation": [{"attest"}, {"workload", "ident"}, {"machin", "credential"},
                    {"verif", "runtime", "credential"}, {"workload", "credential"}],
    "sink_approved": [{"approv", "sink"}, {"approv", "destin"}, {"clear", "infosec"},
                      {"sanction", "sink"}, {"whitelist", "destin"}, {"allowlist", "sink"},
                      {"approv", "bucket"}, {"clear", "destin"}],
    "reversibility_cost": [{"revers", "cost"}, {"rollback", "restor"}, {"walk", "back"},
                           {"roll", "back", "restor"}, {"revers", "restor"}],
}

# canonical exemplar strings (Stage 3 fuzzy): representative phrasings per concept.
EXEMPLARS = {
    "artifact": ["a signed build artifact is attached",
                 "ci produced a provenance stamped image"],
    "sim_high": ["a high fidelity simulation passed",
                 "we ran a full dress rehearsal of the rollout"],
    "sim_medium": ["a medium fidelity simulation estimated the impact",
                   "a partial trial run gave an estimate"],
    "backup": ["a verified restorable backup exists and restore was tested",
               "we hold a point in time copy we successfully restored"],
    "appr_single": ["approved by the security lead single approver",
                    "a manager gave the go ahead"],
    "appr_dual": ["dual control approval from security and sre leads",
                  "two leads put their names on the change"],
    "attestation": ["workload identity attestation is attached",
                    "the runtime presented a verified machine credential"],
    "sink_approved": ["the destination is on the approved sink allowlist",
                      "the destination was cleared by infosec"],
    "reversibility_cost": ["rollback plan restore from the verified backup reversible with cost",
                           "we can walk it back by restoring the copy at some cost"],
}

# concepts that are mutually exclusive fidelity choices (avoid double-adding sims)
_SIM_GROUP = ("sim_high", "sim_medium")


def all_concepts():
    return list(FRAGMENTS.keys())


def merge_fragment(concepts) -> dict:
    """Merge the contrib fragments for a set of concepts into one fragment dict."""
    frag: dict = {}
    concepts = list(concepts)
    # if both sim fidelities somehow fire, prefer HIGH (conservative for DEPLOY)
    if "sim_high" in concepts and "sim_medium" in concepts:
        concepts = [c for c in concepts if c != "sim_medium"]
    for c in concepts:
        piece = FRAGMENTS[c]
        for k, v in piece.items():
            if k == "args":
                frag.setdefault("args", {}).update(v)
            elif k in ("evidence", "approvals"):
                frag.setdefault(k, []).extend(v)
            else:
                frag[k] = v
    return frag

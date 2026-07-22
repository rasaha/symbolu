#!/usr/bin/env python3
"""The four evaluation arms (A/B/C/D) + Arm-B ablations, as deterministic prompt constructors.

Only the {conditioning} slot differs between arms; the wrapper/brief/constraints are identical, so any
downstream difference is attributable to the conditioning, not the framing. Uses the FROZEN runtime
(symbolic_profile.build_symbolic_profile) read-only. No model is called here.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_VL = _HERE.parent.parent                      # varna_lens/
sys.path.insert(0, str(_VL))
import symbolic_profile as SP                  # noqa: E402  (frozen canonical profile)

WRAPPER = (
    "You are a professional naming consultant. Propose 8 candidate names for the brief below. "
    "Return only the names, one per line, no commentary.\n\n"
    "BRIEF: {brief}\n"
    "CONSTRAINTS: {constraints}\n"
    "{conditioning}"
)

_PROFILE_CACHE = {}


def profile_for(seed_concept):
    if seed_concept not in _PROFILE_CACHE:
        _PROFILE_CACHE[seed_concept] = SP.build_symbolic_profile(source_text=seed_concept, by="spelling")
    return _PROFILE_CACHE[seed_concept]


def _constraints_str(c):
    return "; ".join(f"{k}={v}" for k, v in c.items())


# ---- conditioning blocks (deterministic serializations of profile data; no interpretation) ---------
def full_profile_block(p, *, trajectory=True, binding=True, liberating=True, provenance=True, order="source"):
    keys = p.decomposition["varna_keys"]
    L = ["SYMBOLIC PROFILE (deterministic data; not an interpretation):",
         "varṇa sequence: " + " · ".join(keys)]
    bpoles = list(p.poles["binding"]); lpoles = list(p.poles["liberating"])
    if order == "reversed":
        bpoles = list(reversed(bpoles)); lpoles = list(reversed(lpoles))
    if binding:
        L.append("binding drives:")
        L += [f"- {c['varna_key']}: {c['text']}" for c in bpoles]
    if liberating:
        L.append("liberating drives:")
        L += [f"- {c['varna_key']}: {c['text']}" for c in lpoles]
    if trajectory:
        t = p.trajectory
        L.append(f"trajectory: roles={t['roles']}; valence={t['valence']}; "
                 f"controlling_element={t['controlling_element']}; tone={t['tone']}")
    if provenance:
        pr = p.provenance
        L.append(f"provenance: mapping={pr['mapping_source']} sha={pr['mapping_sha256'][:16]}")
    return "\n".join(L)


def minimal_block(p):
    keys = p.decomposition["varna_keys"]
    b = p.poles["binding"]; l = p.poles["liberating"]
    L = ["SYMBOLIC SUMMARY (varṇas + dominant poles only; no trajectory/structure):",
         "varṇas: " + " ".join(keys)]
    if b:
        L.append(f"dominant binding pole ({b[0]['varna_key']}): {b[0]['text']}")
    if l:
        L.append(f"dominant liberating pole ({l[-1]['varna_key']}): {l[-1]['text']}")
    return "\n".join(L)


# ---- arms -----------------------------------------------------------------------------------------
def arm_A(item):
    return WRAPPER.format(brief=item["brief"], constraints=_constraints_str(item["constraints"]),
                          conditioning="")


def arm_B(item):
    p = profile_for(item["seed_concept"])
    return WRAPPER.format(brief=item["brief"], constraints=_constraints_str(item["constraints"]),
                          conditioning=full_profile_block(p))


def arm_C(item, corpus):
    """Random symbolic control: inject a REAL profile from a DIFFERENT seed, chosen deterministically to
    have the most similar block length (isolates 'structured text of similar size' from real content)."""
    mine = full_profile_block(profile_for(item["seed_concept"]))
    target = len(mine)
    others = [c for c in corpus if c["seed_concept"] != item["seed_concept"]]
    pick = min(others, key=lambda c: (abs(len(full_profile_block(profile_for(c["seed_concept"]))) - target),
                                      c["id"]))
    block = full_profile_block(profile_for(pick["seed_concept"]))
    block = "SYMBOLIC PROFILE (deterministic data; not an interpretation):" + \
            block.split("\n", 1)[1]                       # keep the header, swap in the mismatched body
    return (WRAPPER.format(brief=item["brief"], constraints=_constraints_str(item["constraints"]),
                           conditioning=block), pick["seed_concept"])


def arm_D(item):
    p = profile_for(item["seed_concept"])
    return WRAPPER.format(brief=item["brief"], constraints=_constraints_str(item["constraints"]),
                          conditioning=minimal_block(p))


# ---- ablations (variants of Arm B, each removing one field) ---------------------------------------
def ablations(item):
    p = profile_for(item["seed_concept"])
    base = dict(brief=item["brief"], constraints=_constraints_str(item["constraints"]))
    return {
        "B_full": WRAPPER.format(conditioning=full_profile_block(p), **base),
        "abl_no_trajectory": WRAPPER.format(conditioning=full_profile_block(p, trajectory=False), **base),
        "abl_no_binding": WRAPPER.format(conditioning=full_profile_block(p, binding=False), **base),
        "abl_no_liberating": WRAPPER.format(conditioning=full_profile_block(p, liberating=False), **base),
        "abl_no_provenance": WRAPPER.format(conditioning=full_profile_block(p, provenance=False), **base),
        "abl_shuffled_order": WRAPPER.format(conditioning=full_profile_block(p, order="reversed"), **base),
    }


def all_arms(item, corpus):
    c_prompt, c_source = arm_C(item, corpus)
    return {"A_baseline": arm_A(item), "B_profile": arm_B(item),
            "C_random": c_prompt, "D_minimal": arm_D(item)}, c_source


if __name__ == "__main__":
    from corpus import CORPUS
    it = CORPUS[0]
    arms, csrc = all_arms(it, CORPUS)
    for a, pr in arms.items():
        print(f"\n===== {a} ({len(pr)} chars) =====\n{pr}")
    print(f"\n[Arm C used a random profile from seed: {csrc}]")

#!/usr/bin/env python3
"""B1.12 Gate-G1 reassessment — outcome-blind identifiability / exchangeability analysis (opaque symbols only).

Formalizes: with leakage-safe opaque IDs and NO external key, can an evaluator identify which arm is a word's
TRUE order? The key-free information about an arm is exactly its relabeling-canonical form (relabel tokens by
order of first appearance). If arms share that canonical form, they are indistinguishable without a key -> any
decision is at chance, and any above-chance performance implies leakage / memorization / an undocumented prior.

NO Sanskrit candidate words, NO parser, NO judges. Deterministic. Preserved as the reassessment record.
"""
from __future__ import annotations

import itertools
import json


def canon(seq):
    """Relabel-invariant canonical form: rename tokens by order of first appearance (a,b,c,...).

    This is EXACTLY the information available from an opaque sequence with no key: repetition structure and
    length. Two sequences share it iff no key-free feature can tell them apart."""
    m, out, nxt = {}, [], 0
    for t in seq:
        if t not in m:
            m[t] = chr(ord("a") + nxt)
            nxt += 1
        out.append(m[t])
    return "".join(out)


def demo_distinct():
    """Distinct-token multiset (like every selected-six word): all permutations canonicalize identically."""
    tokens = ["U09", "U22", "U29", "U14", "U25"]     # opaque, distinct
    A = tokens                                        # 'true' order (arbitrary designation)
    B = ["U29", "U14", "U09", "U25", "U22"]           # a scramble (same multiset)
    D = sorted(tokens)                                # unordered canonical
    perms = list(itertools.permutations(tokens))
    canons = {canon(list(p)) for p in perms}
    return {
        "multiset_kind": "distinct_tokens",
        "canon_A": canon(A), "canon_B": canon(B), "canon_D": canon(D),
        "A_B_indistinguishable_keyfree": canon(A) == canon(B),
        "A_D_indistinguishable_keyfree": canon(A) == canon(D),
        "n_permutations": len(perms),
        "n_distinct_canonical_forms": len(canons),           # 1 -> all permutations look identical without a key
        "keyfree_identify_true_expected_accuracy": 1.0 / 2,  # A vs B: exchangeable -> chance 1/2
    }


def demo_repeated():
    """Repeated-token multiset: canonical form carries the repetition PATTERN (relabel-invariant) but still not
    'truth' — permutations with the same repetition pattern remain mutually indistinguishable without a key."""
    tokens = ["U01", "U01", "U02", "U03"]
    A = ["U01", "U01", "U02", "U03"]
    B = ["U01", "U02", "U01", "U03"]                  # same multiset, different order
    perms = list(dict.fromkeys(itertools.permutations(tokens)))
    canons = {}
    for p in perms:
        canons.setdefault(canon(list(p)), []).append("".join(p))
    return {
        "multiset_kind": "repeated_tokens",
        "canon_A": canon(A), "canon_B": canon(B),
        "A_B_share_canonical": canon(A) == canon(B),
        "n_distinct_permutations": len(perms),
        "n_distinct_canonical_forms": len(canons),           # >1: repeats leak *pattern*, still not 'true' arm
        "note": "repetition pattern is key-free-visible but does not identify which arrangement is the word's true order",
    }


def demo_semantic_key_breaks_exchangeability():
    """A semantic key (token->gloss) + a target meaning creates a feature correlated with truth -> identifiable
    IN PRINCIPLE. Schematic/synthetic: 'meaning-match' is higher for the arrangement whose ordered glosses match
    the target pattern. This is the ONLY route to identifiability, and it requires supplying glosses."""
    key = {"U09": "g1", "U22": "g2", "U29": "g3", "U14": "g4", "U25": "g5"}
    target_ordered_pattern = ["g1", "g2", "g3", "g4", "g5"]     # supplied independently of the test
    A = ["U09", "U22", "U29", "U14", "U25"]                     # ordered glosses == target -> match 1.0
    B = ["U29", "U14", "U09", "U25", "U22"]                     # scrambled glosses -> lower match

    def match(seq):
        gl = [key[t] for t in seq]
        return sum(1 for i in range(len(gl)) if gl[i] == target_ordered_pattern[i]) / len(gl)
    return {"key_supplied": True, "match_A_true": match(A), "match_B_scramble": match(B),
            "identifiable_with_key": match(A) > match(B),
            "note": "only a supplied key/gloss + target breaks A/B exchangeability; opaque-only cannot"}


if __name__ == "__main__":
    out = {"distinct": demo_distinct(), "repeated": demo_repeated(),
           "semantic_key": demo_semantic_key_breaks_exchangeability()}
    print(json.dumps(out, indent=2))
    # assertions that anchor the reassessment
    assert out["distinct"]["A_B_indistinguishable_keyfree"] is True
    assert out["distinct"]["n_distinct_canonical_forms"] == 1
    assert out["semantic_key"]["identifiable_with_key"] is True
    print("\nCONCLUSION: opaque-only 'identify the true order' is UNDERDETERMINED (chance); a supplied "
          "semantic key is required for identifiability.")

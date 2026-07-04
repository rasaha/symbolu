#!/usr/bin/env python3
"""Layer 4 synonym-attribute attribution check — INSPECTION ONLY (no model, no scoring, no network).

For a key word, compares a FROZEN synonym-derived attribute inventory against the emitted Layer 1/2
evidence terms and labels each INDIVIDUAL attribute SUPPORTED / UNSUPPORTED / UNRESOLVED, with an
explicit evidence path for each SUPPORTED attribute. It is a reader/attributor: it does NOT alter
Layer 1/2/3, does NOT look up a dictionary/thesaurus at runtime, does NOT call the web or a model,
does NOT generate text, and writes no result files.

STRICT SCORE GUARD: Layer 4 emits ONLY per-attribute labels + evidence paths. It never emits a total
score, aggregate, percentage, N/M fraction, pass/fail, ranking, confidence, p-value, accuracy,
verdict, signal, A_vs comparison, or any single summary metric.

Attribute support means only that a frozen attribute term overlaps a frozen Layer 1/2 emitted term.
It is NOT semantic proof. A random or scrambled lexicon can support a different attribute set equally
well; prior controlled tests returned NO_SIGNAL.

Independent of Layer 3 (does not import it, does not use dictionary anchors as proof). NOT wired into
Layer 3, the Layer 5 prompt demo, any evaluation prereg path, or any scored path. No ontology, no
Sanskrit privilege, no semantic-truth claim, no Track G rescue, no Track B unblock.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample_text_rule_harness as H   # noqa: E402  (Layer 1/2 producer: profile, synthesize)

LABEL = "LAYER4_SYNONYM_ATTRIBUTE_CHECK — not scored, not evidence"
CAVEAT = ("Attribute support means only that a frozen attribute term overlaps a frozen Layer 1/2 "
          "emitted term. It is not semantic proof. A random or scrambled lexicon can support a "
          "different attribute set equally well; prior controlled tests returned NO_SIGNAL.")
SUPPORTED, UNSUPPORTED, UNRESOLVED = "SUPPORTED", "UNSUPPORTED", "UNRESOLVED"

_INVENTORY_JSON = HERE / "layer4_attribute_inventory.json"

# phrases L4 must never emit (defense-in-depth; asserted by tests too)
_FORBIDDEN = ("therefore means", "the word means", "therefore the word", "true meaning", "proves",
              "semantic truth", "ontolog", "sanskrit proves", "track b support", "validat")


class ForbiddenClaim(ValueError):
    """Raised if an L4 output would assert meaning/truth/ontology/Sanskrit/Track-B/validation."""


def _load_inventory():
    """Load the FROZEN local attribute inventory. No runtime dictionary/thesaurus/web/model lookup."""
    data = json.loads(_INVENTORY_JSON.read_text(encoding="utf-8"))
    return data.get("items", {})


INVENTORY = _load_inventory()


def _tokens(text):
    """Lowercased word tokens, splitting slash-compounded glosses (e.g. 'friendliness/affection' ->
    {'friendliness','affection'}) so a single-word support term inside a compound is still matched."""
    return set(re.findall(r"[a-z]+", (text or "").lower()))


def _l2_unresolved(l2_text):
    """True when the Layer 2 synthesis carries no resolved content (fully unbridged)."""
    t = (l2_text or "").strip()
    if not t or t == "[unresolved]":
        return True
    content = _tokens(t) - H._SYNTH_STOP - {"unresolved"}
    return not content


def _evidence_phrases(prof):
    """Reconstruct (bridge_phrase, varna_role) pairs exactly as Layer 2 synthesize emits them, so a
    SUPPORTED attribute can be traced to the phrase and role it came from. Mirrors H.synthesize; never
    invents. [unresolved] phrases are skipped as evidence."""
    units = prof["units"]
    seed = next((r for r in units if r["role"] == "ONSET_SEED"), None)
    trans = next((r for r in reversed(units) if r["role"] == "TRANSFORMER"), None)
    pairs = []
    if seed is not None:
        e = H._lex_entry("C", seed["key"])
        if e:
            b_bind = H._bridge(e["binding_state"]) or "[unresolved]"
            b_counter = H._bridge(e["liberating_state"]) or "[unresolved]"
            pairs.append((b_bind, "ONSET_SEED (binding)"))
            pairs.append((b_counter, "ONSET_SEED (counter/liberating)"))
    if trans is not None and trans is not seed:
        e = H._lex_entry("C", trans["key"])
        if e:
            b_tr = H._bridge(e["liberating_state"]) or "[unresolved]"
            pairs.append((b_tr, "TRANSFORMER (liberating)"))
    return [(p, role) for (p, role) in pairs if p != "[unresolved]"]


def _evidence_for(key_word):
    """(l2_text, phrase_role_pairs, note). Never alters L1/L2. On G2P-unavailable → ('[unresolved]',[])."""
    try:
        prof = H.profile(key_word)
    except H.G2PUnavailable as e:
        return "[unresolved]", [], f"G2P unavailable: {e}"
    syn, _used = H.synthesize(prof)
    return syn, _evidence_phrases(prof), None


def _paths_for_term(term, phrase_pairs):
    """Explicit evidence path fragments for a support term: which emitted phrase(s) contain it, and
    the varṇa role of each. Single words match a phrase token; multiword terms match as a substring."""
    t = term.lower()
    frags = []
    for phrase, role in phrase_pairs:
        hit = (t in _tokens(phrase)) if (" " not in t and "/" not in t) else (t in phrase.lower())
        if hit:
            frags.append(f'{term} ← layer2_phrase: "{phrase}" ← varna_role: {role}')
    return frags


def attribute_check(key_word):
    """Deterministic, conservative per-attribute attribution. Returns a dict with per-attribute
    status + evidence_path. NO aggregate score, NO ranking, NO verdict — labels + paths only."""
    kw = (key_word or "").lower()
    inv = INVENTORY.get(kw)
    l2_text, phrase_pairs, note = _evidence_for(key_word)

    if inv is None:
        return {"key_word": key_word, "layer2_synthesis": l2_text, "note": note,
                "frozen_attributes": [], "attribution": [],
                "reason_all": "no frozen inventory for this key word"}

    frozen_attrs = [a["attribute"] for a in inv["attributes"]]
    unresolved_l2 = _l2_unresolved(l2_text)
    evidence_tokens = set()
    for phrase, _role in phrase_pairs:
        evidence_tokens |= _tokens(phrase)
    evidence_tokens |= (_tokens(l2_text) - H._SYNTH_STOP - {"unresolved"})

    rows = []
    for a in inv["attributes"]:
        attr, support_terms = a["attribute"], a.get("support_terms", [])
        if unresolved_l2:
            rows.append({"attribute": attr, "status": UNRESOLVED, "evidence_path": [],
                         "reason": "Layer 2 synthesis is unresolved"})
            continue
        frags = []
        for st in support_terms:
            s = st.lower()
            present = (s in evidence_tokens) if (" " not in s and "/" not in s) else (s in l2_text.lower())
            if present:
                frags.extend(_paths_for_term(st, phrase_pairs))
        if frags:
            rows.append({"attribute": attr, "status": SUPPORTED, "evidence_path": frags})
        else:
            rows.append({"attribute": attr, "status": UNSUPPORTED, "evidence_path": [],
                         "reason": "no support term overlaps the resolved Layer 2 evidence"})
    return {"key_word": key_word, "layer2_synthesis": l2_text, "note": note,
            "frozen_attributes": frozen_attrs, "attribution": rows, "reason_all": None}


def render_layer4(key_word):
    """One inspection block: per-attribute SUPPORTED/UNSUPPORTED/UNRESOLVED + evidence paths.
    No model, no aggregate score, no files."""
    r = attribute_check(key_word)
    lines = [LABEL,
             f"key_word: {key_word!r}",
             f"layer2_synthesis: {r['layer2_synthesis']}",
             f"frozen_attributes: {r['frozen_attributes']}"]
    if r["reason_all"]:
        lines.append(f"attribution: (none) — {r['reason_all']}; every attribute is treated as UNRESOLVED")
    else:
        lines.append("attribution:")
        for row in r["attribution"]:
            lines.append(f"  - attribute: {row['attribute']}")
            lines.append(f"    status: {row['status']}")
            if row["evidence_path"]:
                lines.append("    evidence_path:")
                for frag in row["evidence_path"]:
                    lines.append(f"      - {frag}")
            else:
                lines.append("    evidence_path: []")
                if row.get("reason"):
                    lines.append(f"    reason: {row['reason']}")
    if r["note"]:
        lines.append(f"note: {r['note']}")
    lines.append(f"caveat: {CAVEAT}")
    lines.append("no_model_called: true | no_generated_answer_produced: true | not_scored: true")
    lines.append(LABEL)
    out = "\n".join(lines)
    low = out.lower()
    for bad in _FORBIDDEN:
        if bad in low:
            raise ForbiddenClaim(f"L4 output contains forbidden claim {bad!r}")
    return out


_SAMPLES = ("mercy", "love", "anger", "peace")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Layer 4 synonym-attribute attribution check — INSPECTION ONLY (no model, no "
                    "scoring, no aggregate score, no evidence).")
    ap.add_argument("--key", default=None, help="key word to inspect")
    ap.add_argument("--all-demo", action="store_true", help="inspect the four frozen demo words")
    args = ap.parse_args(argv)
    if args.key:
        print(render_layer4(args.key))
    elif args.all_demo:
        for kw in _SAMPLES:
            print(render_layer4(kw))
            print("\n" + "=" * 88 + "\n")
    else:
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

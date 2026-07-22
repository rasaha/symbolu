#!/usr/bin/env python3
"""Layer 3 dictionary-meaning bridge — INSPECTION ONLY (no model, no generation, no scoring, no evidence).

Reads the Layer 2 latent-process synthesis produced by the committed harness
(`sample_text_rule_harness.synthesize`) and relates it to a FROZEN local dictionary anchor for the
key word, emitting one of four *interpretive* relation labels — ALIGNS / PARTIALLY_ALIGNS /
DIVERGES / UNRESOLVED. It is a reader/relater: it does NOT alter Layer 1 or Layer 2, does NOT look up
a dictionary at runtime, does NOT call the web or a model, does NOT generate text, does NOT score,
and writes no result files.

The relation label is an INTERPRETIVE inspection label, NOT a score and NOT evidence. A random or
scrambled conditioning field can appear equally aligned; prior controlled tests returned NO_SIGNAL.

NOT an experiment, NOT a prereg, NOT evidence, NOT wired into any scored/eval path, NOT a Track G
rescue, NOT a Track B unblock. No ontology, no Sanskrit privilege, no semantic-truth claim.
"""
from __future__ import annotations
# RETIRED (research-only) — reads the retired Layer-2 synthesis; superseded by the canonical Symbolic
# Profile. Kept for reproducibility; not on any production path. See experiments/retired/layer2_bridge/.

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample_text_rule_harness as H   # noqa: E402  (Layer 1/2 producer: profile, synthesize)

LABEL = "LAYER3_DICTIONARY_BRIDGE — interpretive only, not scored, not evidence"
CAVEAT = ("Dictionary bridge is interpretive only. A random or scrambled conditioning field can "
          "appear equally aligned. Prior controlled tests returned NO_SIGNAL.")
# relation labels are interpretive only, never scores
ALIGNS, PARTIALLY_ALIGNS, DIVERGES, UNRESOLVED = (
    "ALIGNS", "PARTIALLY_ALIGNS", "DIVERGES", "UNRESOLVED")

_ANCHORS_JSON = HERE / "layer3_dictionary_anchors.json"


class ForbiddenClaim(ValueError):
    """Raised if an L3 output would assert meaning/truth/ontology/Sanskrit/Track-B."""


# phrases L3 must never emit (defense-in-depth; asserted by tests too)
_FORBIDDEN = ("therefore means", "true meaning", "proves", "semantic truth", "ontolog",
              "sanskrit proves", "track b support", "the word means", "therefore the word")


def _load_anchors():
    """Load the FROZEN local anchor table. No runtime dictionary/web/model lookup."""
    data = json.loads(_ANCHORS_JSON.read_text(encoding="utf-8"))
    return data.get("anchors", {})


ANCHORS = _load_anchors()


def _tokens(text):
    """Lowercased word tokens, splitting slash-compounded glosses (e.g. 'restraint/containment' ->
    {'restraint','containment'}) so a single-word anchor keyword inside a compound is still matched."""
    return set(re.findall(r"[a-z]+", (text or "").lower()))


def _l2_unresolved(l2_text):
    """True when the Layer 2 synthesis carries no resolved content (fully unbridged)."""
    t = (l2_text or "").strip()
    if not t or t == "[unresolved]":
        return True
    # ignore fixed template stopwords and the [unresolved] marker; anything left is real content
    content = _tokens(t) - H._SYNTH_STOP - {"unresolved"}
    return not content


def _hits(keywords, l2_tokens, l2_text):
    """Conservative overlap: exact token hit, or a multiword keyword appearing verbatim in the text."""
    low = (l2_text or "").lower()
    found = []
    for kw in keywords:
        k = kw.lower()
        if " " in k or "/" in k:
            if k in low:
                found.append(kw)
        elif k in l2_tokens:
            found.append(kw)
    # stable, de-duplicated
    seen, out = set(), []
    for k in found:
        if k not in seen:
            seen.add(k); out.append(k)
    return out


def relate(key_word, l2_text):
    """Deterministic, conservative relation of a Layer 2 synthesis to the frozen anchor.

    Returns a dict: {key_word, layer2_synthesis, anchor_phrase, anchor_source, relation,
    matched_terms, opposite_terms, reason}. Interpretive only — NO numeric score. Infers nothing
    beyond the frozen anchor + the literal L2 text (no model similarity, no runtime lookup)."""
    kw = (key_word or "").lower()
    anchor = ANCHORS.get(kw)
    if anchor is None:
        return {"key_word": key_word, "layer2_synthesis": l2_text, "anchor_phrase": None,
                "anchor_source": None, "relation": UNRESOLVED, "matched_terms": [],
                "opposite_terms": [], "reason": "no frozen anchor for this key word"}
    if _l2_unresolved(l2_text):
        return {"key_word": key_word, "layer2_synthesis": l2_text,
                "anchor_phrase": anchor["anchor_phrase"], "anchor_source": anchor.get("source_note"),
                "relation": UNRESOLVED, "matched_terms": [], "opposite_terms": [],
                "reason": "Layer 2 synthesis is unresolved"}

    l2_tokens = _tokens(l2_text)
    matched = _hits(anchor.get("anchor_keywords", []), l2_tokens, l2_text)
    opposite = _hits(anchor.get("opposite_keywords", []), l2_tokens, l2_text)

    if opposite:
        rel, reason = DIVERGES, "explicit opposite term(s) present in Layer 2"
    elif len(matched) >= 2:
        rel, reason = ALIGNS, "two or more anchor keyword(s) overlap Layer 2"
    elif len(matched) == 1:
        rel, reason = PARTIALLY_ALIGNS, "one anchor keyword overlaps Layer 2"
    else:
        rel, reason = UNRESOLVED, "no anchor/opposite overlap with Layer 2"
    return {"key_word": key_word, "layer2_synthesis": l2_text,
            "anchor_phrase": anchor["anchor_phrase"], "anchor_source": anchor.get("source_note"),
            "relation": rel, "matched_terms": matched, "opposite_terms": opposite, "reason": reason}


def _layer2_for(key_word):
    """Fetch the Layer 2 synthesis string for a word via the committed harness. Never alters L1/L2.
    Returns (l2_text, note). On G2P-unavailable, returns ('[unresolved]', reason) → UNRESOLVED."""
    try:
        prof = H.profile(key_word)
    except H.G2PUnavailable as e:
        return "[unresolved]", f"G2P unavailable: {e}"
    syn, _used = H.synthesize(prof)
    return syn, None


def render_layer3(key_word, l2_text=None):
    """One inspection block relating Layer 2 → frozen anchor. No model, no score, no files."""
    note = None
    if l2_text is None:
        l2_text, note = _layer2_for(key_word)
    r = relate(key_word, l2_text)
    lines = [LABEL,
             f"key_word: {key_word!r}",
             f"layer2_synthesis: {r['layer2_synthesis']}",
             f"frozen_anchor:    {r['anchor_phrase'] if r['anchor_phrase'] else '[no frozen anchor]'}"
             + (f"   [source: {r['anchor_source']}]" if r['anchor_source'] else ""),
             f"relation:         {r['relation']}",
             f"matched_terms:    {r['matched_terms']}",
             f"opposite_terms:   {r['opposite_terms']}",
             f"reason:           {r['reason']}"]
    if note:
        lines.append(f"note:             {note}")
    lines.append(f"caveat:           {CAVEAT}")
    lines.append("no_model_called: true | no_generated_answer_produced: true | not_scored: true")
    lines.append(LABEL)
    out = "\n".join(lines)
    low = out.lower()
    for bad in _FORBIDDEN:
        if bad in low:
            raise ForbiddenClaim(f"L3 output contains forbidden claim {bad!r}")
    return out


_SAMPLES = ("mercy", "love", "anger", "peace")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Layer 3 dictionary-meaning bridge — INSPECTION ONLY (no model, no generation, "
                    "no scoring, no evidence).")
    ap.add_argument("--key", default=None, help="key word to inspect (defaults to the frozen samples)")
    args = ap.parse_args(argv)
    if args.key:
        print(render_layer3(args.key))
    else:
        for kw in _SAMPLES:
            print(render_layer3(kw))
            print("\n" + "=" * 88 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

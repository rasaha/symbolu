#!/usr/bin/env python3
"""B1.10 — packet-blind SURFACE validator (per-word-pair scope).

Operational improvement only. This module extracts the *exact* surface rules that the
six-word author runner already enforced (see `B1_10_NONCLAUDE_AUTHOR_HANDOFF.md` and the
two FAILED-attempt CAPTURE_NOTEs) and applies them to a SINGLE word-pair (one A + one B).

NO RULE IS RELAXED. The rule set is identical to the six-word validator; only the *scope*
changes (one word-pair per call instead of all six at once), which is the whole point of the
per-word decomposition: a fail isolates to one word and only that word is regenerated.

The validator makes NO packet comparison. It never sees any Tier-1/Tier-2/Tier-3 packet,
varṇa mapping, audit, prior context set, or result. It checks only the author-packet surface
rules:
  - exactly 2 sentences for the pair: one labelled A, one labelled B;
  - each sentence 12-22 words;
  - the target word appears EXACTLY ONCE per sentence (word-boundary, case-insensitive);
  - the four self-check fields present on each sentence;
  - intended class matches the A/B label;
  - mixed-condition detected != yes (relies on the author's own honest self-mark);
  - naturalness != forced;
  - none of the forbidden labels appears.

Guardrails: resonance / phonetic-fidelity refinement only. No GENUTILITY_*; no
ONTOLOGICAL_SIGNAL; no semantic-truth / ontology / Sanskrit-privilege claim. B1.4b' remains
NULL_RETURN_BOTTOM; original B1.4b blocked; Track B blocked. Structure, not validated meaning.
"""

import re

# Forbidden labels — verbatim from the author packet §5 (unchanged).
FORBIDDEN_LABELS = ["binding", "liberating", "source-condition", "self-grounded", "other-conditioned"]

# Word-count band — verbatim from the author packet §5 (unchanged).
WC_MIN, WC_MAX = 12, 22

# The six official words, packet order (author packet §2). Used only to validate the
# per-word job target; never used to relax any rule.
OFFICIAL_WORDS = ["pride", "freedom", "patience", "courage", "control", "doubt"]

# Sentence line:  "A: <sentence>"  /  "B: <sentence>"
_SENT_RE = re.compile(r"^\s*([AB]):\s*(.+?)\s*$", flags=re.M)

# Self-check line:  "intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural"
_SELFCHECK_RE = re.compile(
    r"intended class:\s*(?P<cls>[AB])\s*\|\s*"
    r"confidence:\s*(?P<conf>high|medium|low)\s*\|\s*"
    r"mixed-condition detected:\s*(?P<mixed>yes|no)\s*\|\s*"
    r"naturalness:\s*(?P<nat>natural|slightly forced|forced)",
    flags=re.I,
)


def _word_count(sentence: str) -> int:
    return len(sentence.split())


def _target_word_occurrences(sentence: str, word: str) -> int:
    # Same word-boundary rule the 14B runner used: not preceded/followed by a word char or hyphen,
    # case-insensitive. "uncontrollable" does NOT match "control"; "Control" DOES match "control".
    return len(re.findall(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", sentence, flags=re.I))


def validate_word_pair(raw_text: str, word: str) -> dict:
    """Validate a single word-pair (one A + one B) against the author-packet surface rules.

    `raw_text` is the model's raw output for one per-word job. `word` is the target word.
    Returns {"surface_pass": bool, "issues": [str, ...], "word": word, "n_sentences": int}.
    """
    issues = []

    if word not in OFFICIAL_WORDS:
        issues.append(f"target word '{word}' is not one of the six official words")

    sents = _SENT_RE.findall(raw_text)
    # Self-check blocks, keyed to A/B by proximity: we pair each A/B line with the NEXT self-check.
    selfchecks = list(_SELFCHECK_RE.finditer(raw_text))

    labels = [lab for lab, _ in sents]
    if len(sents) != 2:
        issues.append(f"expected exactly 2 sentences (one A, one B), found {len(sents)}")
    if labels.count("A") != 1:
        issues.append(f"expected exactly one A sentence, found {labels.count('A')}")
    if labels.count("B") != 1:
        issues.append(f"expected exactly one B sentence, found {labels.count('B')}")

    for lab, sentence in sents:
        wc = _word_count(sentence)
        if not (WC_MIN <= wc <= WC_MAX):
            issues.append(f"[{lab}: {sentence[:40]}...] wordcount {wc} out of {WC_MIN}-{WC_MAX}")

        occ = _target_word_occurrences(sentence, word)
        if occ != 1:
            issues.append(f"[{lab}: {sentence[:40]}...] target word '{word}' appears {occ} times (must be exactly 1)")

        low = sentence.lower()
        for f in FORBIDDEN_LABELS:
            if f in low:
                issues.append(f"[{lab}: {sentence[:40]}...] forbidden label '{f}'")

    # Self-check fields: exactly two blocks, one class A one class B, none mixed=yes / naturalness=forced.
    if len(selfchecks) != 2:
        issues.append(f"expected 2 self-check blocks (one per sentence), found {len(selfchecks)}")
    sc_classes = [m.group("cls").upper() for m in selfchecks]
    if sc_classes.count("A") != 1 or sc_classes.count("B") != 1:
        issues.append(f"self-check classes must be one A and one B, found {sc_classes}")
    for m in selfchecks:
        if m.group("mixed").lower() == "yes":
            issues.append("a sentence self-marked mixed-condition detected: yes")
        if m.group("nat").lower() == "forced":
            issues.append("a sentence self-marked naturalness: forced")

    # intended class must agree with the sentence label (A sentence -> intended class A).
    for lab, sentence in sents:
        # find the self-check block that follows this sentence's line
        idx = raw_text.find(sentence)
        following = [m for m in selfchecks if m.start() > idx]
        if following:
            declared = following[0].group("cls").upper()
            if declared != lab:
                issues.append(f"[{lab}: {sentence[:30]}...] intended class '{declared}' != sentence label '{lab}'")

    return {"surface_pass": not issues, "issues": issues, "word": word, "n_sentences": len(sents)}


def _cli_validate(raw_path, word):
    """Validate one raw per-word output file for a target word.

    Prints the validation JSON to stdout and exits 0 on surface_pass, 1 on failure — so the
    per-word workflow can gate on the exit code. Rules are unchanged (no relaxation); this is
    only a standalone entry point around validate_word_pair for operational reproducibility.
    """
    import json
    import pathlib
    import sys

    raw = pathlib.Path(raw_path).read_text(encoding="utf-8")
    result = validate_word_pair(raw, word)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["surface_pass"] else 1)


# ------------------------------------------------------------------ CLI / self-test
if __name__ == "__main__":
    import json
    import sys

    # `--raw <file> --word <word>` validates one per-word output (exit 0 pass / 1 fail).
    # With no args, runs the built-in self-tests (mock only).
    if "--raw" in sys.argv or "--word" in sys.argv:
        import argparse

        ap = argparse.ArgumentParser(description="B1.10 per-word-pair surface validator (rules unchanged).")
        ap.add_argument("--raw", required=True, help="path to one word-pair raw output file")
        ap.add_argument("--word", required=True, help="target word (one of the six official words)")
        a = ap.parse_args()
        _cli_validate(a.raw, a.word)

    good = (
        "pride\n"
        "A: The manager measured his worth against every rival, and his pride swelled whenever colleagues fell behind him.\n"
        "   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural\n"
        "B: Quietly certain of her craft, the potter felt a steady pride that needed no applause to sustain it.\n"
        "   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural\n"
    )
    bad_missing = (
        "pride\n"
        "A: The manager measured his worth against every rival, swelling whenever colleagues happened to fall behind him.\n"
        "   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural\n"
        "B: Quietly certain of her craft, the potter felt a steady pride that needed no applause to sustain it.\n"
        "   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural\n"
    )
    bad_long = (
        "control\n"
        "A: Michael tightened his grip on the steering wheel and fought hard for control as the heavy car slid wildly on the icy winter road.\n"
        "   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural\n"
        "B: She let events unfold without needing control, resting in a calm that outside results could not disturb.\n"
        "   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural\n"
    )
    bad_mixed = (
        "doubt\n"
        "A: His doubt grew as the skeptical board members frowned, each reaction chipping away at his fragile certainty.\n"
        "   intended class: A | confidence: medium | mixed-condition detected: yes | naturalness: natural\n"
        "B: Resting in quiet clarity, she held her doubt lightly and let it pass without disturbing her balance.\n"
        "   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural\n"
    )
    for name, text, word, expect in [
        ("good", good, "pride", True),
        ("bad_missing_word", bad_missing, "pride", False),
        ("bad_over_length", bad_long, "control", False),
        ("bad_self_marked_mixed", bad_mixed, "doubt", False),
    ]:
        r = validate_word_pair(text, word)
        ok = r["surface_pass"] == expect
        print(f"[{'OK ' if ok else 'XX '}] {name}: surface_pass={r['surface_pass']} (expected {expect})")
        if r["issues"]:
            print("      issues: " + json.dumps(r["issues"]))
        assert ok, f"self-test failed for {name}"
    print("all surface-validator self-tests passed")

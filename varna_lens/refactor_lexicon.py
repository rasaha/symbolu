#!/usr/bin/env python3
"""Refactor consonant poles from "Sanskrit (English)" strings into explicit {sanskrit, english} subfields.

Keeps the dual-language content but makes the structure unambiguous. CRITICAL: the split is verified to
reconstruct the original string byte-for-byte via display() (the same reconstruction the engine uses), so
the deterministic engine output — and every prior test — is unchanged. Poles that are descriptive English
(no Sanskrit term) get sanskrit="" and english=the full original. Vowels are left as plain English strings
(they carry no Sanskrit vṛtti term). Idempotent.
"""
import json, pathlib

PATH = pathlib.Path(__file__).with_name("lexicon_authoritative.json")

# poles that are descriptive English (no leading Sanskrit term) — keep whole text as english
FORCE_ENGLISH = {("sha", "positive"), ("sha", "negative"), ("ssa", "positive"), ("sa", "negative")}


def display(p):
    """Reconstruct the canonical display string from a pole (dict or str). Engine uses the same rule."""
    if isinstance(p, dict):
        skt, eng = p.get("sanskrit", ""), p.get("english", "")
        return f"{skt} ({eng})" if skt else eng
    return p


def split_pole(s):
    if s.endswith(")") and " (" in s:
        i = s.rfind(" (")
        return {"sanskrit": s[:i], "english": s[i + 2:-1]}
    return {"sanskrit": "", "english": s}


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    for k, d in data["consonants"].items():
        for field in ("positive", "negative"):
            cur = d[field]
            if isinstance(cur, dict):          # already refactored
                original = display(cur)
            else:
                original = cur
                d[field] = {"sanskrit": "", "english": cur} if (k, field) in FORCE_ENGLISH else split_pole(cur)
            # verify byte-identical reconstruction
            assert display(d[field]) == original, f"MISMATCH {k}.{field}: {display(d[field])!r} != {original!r}"
    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"refactored {len(data['consonants'])} consonants to {{sanskrit, english}}; all reconstructions verified.")


if __name__ == "__main__":
    main()

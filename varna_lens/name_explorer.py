#!/usr/bin/env python3
"""Name Explorer — a nimble naming-reflection edge tool.

See how a name's varṇa propensity chain and its Chaldean numerology number shift across spelling
variants (the "add an extra letter" move people already make for numerology).

Honest framing (same as the rest of varna_lens):
- Neither varṇa nor Chaldean numerology is shown to change real-world outcomes. Both are CONSISTENT
  symbolic systems for reflecting on a naming choice — value is consistency + meaning, not prediction.
- The contrast is the point: Chaldean numerology moves on EVERY letter; the varṇa chain moves only when
  the sound/letter-structure actually changes. So varṇa tracks *resonance*, not letter-count.

Usage:
    python name_explorer.py Vivek Viveck Vivekh
    python name_explorer.py Sara Saara Sarah
"""
import argparse
import varna_lens as V

# Chaldean letter -> number (1-8; 9 is treated as 'sacred' and not assigned to letters).
_CHALDEAN_GROUPS = {1: "AIJQY", 2: "BKR", 3: "CGLS", 4: "DMT", 5: "EHNX", 6: "UVW", 7: "OZ", 8: "FP"}
CHALDEAN = {c: n for n, letters in _CHALDEAN_GROUPS.items() for c in letters}


def chaldean(name):
    """Chaldean total and reduced root (single digit)."""
    vals = [CHALDEAN.get(c.upper(), 0) for c in name if c.isalpha()]
    total = sum(vals)
    root = total
    while root > 9:
        root = sum(int(d) for d in str(root))
    return total, root


def varna_chain(name):
    """Deterministic varṇa propensity chain, read letter-literal (so spelling variants register
    consistently — appropriate for names, which are often non-dictionary)."""
    d, _src, _warn = V.analyze(name.lower(), roman=True)
    return d["essence_short"]


def explore(base, variants):
    base_chain = varna_chain(base)
    base_total, _ = chaldean(base)
    print(f"\nNAME EXPLORER — base: {base!r}\n" + "=" * 66)
    for n in [base] + variants:
        c = varna_chain(n)
        t, r = chaldean(n)
        if n == base:
            tag = "  (base)"
        else:
            tag = (f"  [sound {'SAME' if c == base_chain else 'CHANGED'} · "
                   f"number {'SAME' if t == base_total else 'CHANGED'}]")
        print(f"\n{n!r}{tag}")
        print(f"  varṇa chain : {c}")
        print(f"  Chaldean    : total {t} → root {r}")
    print("\n" + "-" * 66)
    print("varṇa  = consistent propensity chain you can reflect on (resonance, not prediction).")
    print("Chaldean = letter-sum numerology (belief system; shifts on every letter).")
    print("Key contrast: a re-spelling that doesn't change the sound/structure leaves the varṇa")
    print("chain UNCHANGED even when the Chaldean number moves — varṇa tracks resonance, not letters.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Explore varṇa chain + Chaldean number across name spellings.")
    ap.add_argument("base", help="base name")
    ap.add_argument("variants", nargs="*", help="spelling variants to compare")
    a = ap.parse_args(argv)
    explore(a.base, a.variants)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""B1.12 — outcome-blind synthetic verification of the inventory-controlled order-distinctness metric.

NO Sanskrit candidate words, NO parser, NO pool, NO G0 run. Pure opaque-symbol sequences.
Compares three candidate definitions on the five required synthetic cases and on order-magnitude
calibration cases (single adjacent transposition vs full reversal, lengths 2..6):

  o_selfsort(x)          = Lev(x, sort(x)) / max(|x|,1)                 # V1.1 per-word self-sort metric
  d_ord(x,y)             = Lev(x,y) / max(|x|,|y|)                      # order-sensitive (normalized edit)
  d_inv_jaccard(x,y)     = 1 - |X∩Y|_multiset / |X∪Y|_multiset         # inventory (multiset) distance
  proposed(x,y)          = max(0, d_ord - d_inv_jaccard)               # user's proposed pairwise form
  excess(x,y)            = max(0, Lev(x,y) - Lev(sort(x),sort(y))) / max(|x|,|y|)  # formula C (principled)

Identity checked: excess(x, sort(x)) == o_selfsort(x)  (self-case reduces to V1.1's metric).

Deterministic; no randomness; enumerated inputs. Preserved as the calibration record for V1.2.
"""
from collections import Counter


def lev(a, b):
    a, b = list(a), list(b)
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur
    return dp[n]


def d_ord(x, y):
    return lev(x, y) / max(len(x), len(y))


def d_inv_jaccard(x, y):
    cx, cy = Counter(x), Counter(y)
    inter = sum((cx & cy).values())
    union = sum((cx | cy).values())
    return 1 - inter / union if union else 0.0


def o_selfsort(x):
    return lev(x, sorted(x)) / max(len(x), 1)


def proposed(x, y):
    return max(0.0, d_ord(x, y) - d_inv_jaccard(x, y))


def excess(x, y):
    num = lev(x, y) - lev(sorted(x), sorted(y))
    return max(0.0, num) / max(len(x), len(y))


def row(label, x, y):
    return (label, "".join(x), "".join(y),
            round(d_ord(x, y), 3), round(d_inv_jaccard(x, y), 3),
            round(proposed(x, y), 3), round(excess(x, y), 3),
            round(o_selfsort(x), 3), round(o_selfsort(y), 3))


REQUIRED = [
    ("1 same-inv/diff-order", "ABC", "CBA"),
    ("2 diff-inv/same-pattern", "ABC", "DEF"),
    ("3 partial inv+order", "ABC", "ACD"),
    ("4 repeated-inv/diff-order", "AABC", "ABAC"),
    ("5 identical", "ABC", "ABC"),
]


def calibration():
    """Single adjacent transposition vs full reversal, for lengths 2..6 (same inventory)."""
    out = []
    for n in range(2, 7):
        base = [chr(ord("A") + i) for i in range(n)]
        swap = base.copy()
        swap[-1], swap[-2] = swap[-2], swap[-1]          # one adjacent transposition
        rev = list(reversed(base))                        # full reversal
        out.append(("swap len%d" % n, base, swap))
        out.append(("reversal len%d" % n, base, rev))
    return out


if __name__ == "__main__":
    hdr = ("case", "x", "y", "d_ord", "d_inv", "proposed", "excess", "o(x)", "o(y)")
    def show(rows):
        print("  ".join(f"{h:>22}" if i == 0 else f"{h:>8}" for i, h in enumerate(hdr)))
        for r in rows:
            print("  ".join(f"{c:>22}" if i == 0 else f"{c:>8}" for i, c in enumerate(r)))
    print("=== REQUIRED SYNTHETIC CASES ===")
    show([row(*c) for c in REQUIRED])
    print("\n=== ORDER-MAGNITUDE CALIBRATION (single swap vs full reversal) ===")
    show([row(*c) for c in calibration()])
    # identity: excess(x, sort(x)) == o_selfsort(x)
    print("\n=== IDENTITY CHECK: excess(x, sort(x)) == o_selfsort(x) ===")
    ok = True
    for _, xs, ys in REQUIRED + [(l, "".join(a), "".join(b)) for l, a, b in calibration()]:
        for s in (xs, ys):
            lhs = excess(list(s), sorted(s))
            rhs = o_selfsort(list(s))
            if abs(lhs - rhs) > 1e-12:
                ok = False
                print(f"  MISMATCH {s}: excess={lhs} o={rhs}")
    print("  identity holds for all tested sequences:", ok)

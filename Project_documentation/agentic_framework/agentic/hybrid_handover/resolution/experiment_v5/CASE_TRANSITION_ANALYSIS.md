# CASE_TRANSITION_ANALYSIS — Competing Operative Resolution Experiment v0.1

Every case whose C4 outcome differs from C0. Opaque identifiers only; hidden wording
is not reproduced.

## Table 7 — fix / break / abstention transitions

| metric | count |
|---|---|
| fixes (wrong→right) | 0 |
| breaks (right→wrong) | 0 |
| new abstentions | 1 |
| new answers | 0 |
| unchanged correct | 21 |
| unchanged incorrect | 35 |

## Changed cases

| case | C0 (abstain, correct) | C4 (abstain, correct) | kind |
|---|---|---|---|
| HXc074bf7990 | (False, True) | (True, None) | new_abstention |

Exactly one case changes: a `no_relationship` case whose gold requires abstention.
C0 (G3) answered it `unknown` (leniently scored correct because `unknown` matches a
gold abstention); C4 abstains explicitly via `OPERATIVE_TERM_NOT_LOCATED`. This is a
correct abstention (gold abstains) and raises abstention recall, but it removes a
leniently-credited answer from the selective denominator, so selective ticks down
0.011. There are zero fixes and zero breaks: the competing-operative machinery found
no genuine conflict to resolve on this corpus.

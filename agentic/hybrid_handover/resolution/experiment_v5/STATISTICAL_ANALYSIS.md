# STATISTICAL_ANALYSIS — Competing Operative Resolution Experiment v0.1

Paired case-level, hidden pilot (n=60). Emphasis on effect size and mechanism given
the tiny activating subset.

## Table 4 — primary endpoint (C4 vs C0)

| quantity | value |
|---|---|
| C0 (G3) selective | 0.3860 |
| C4 selective | 0.3750 |
| selective gain | -0.0110 |
| abstention-recall gain | 0.0625 (threshold +0.10) |
| coverage C0 → C4 | 0.9500 → 0.9333 |
| primary met | False |

## Exact McNemar (full-pipeline correctness, C4 vs C0)

| fixes | breaks | n discordant | exact p |
|---|---|---|---|
| 0 | 0 | 0 | 1.0000 |

Zero discordant answered pairs: the one changed case is an abstention transition, not
an answer flip, so it does not enter the answered-correctness McNemar. Neither the
selective threshold (+0.03) nor the abstention-recall threshold (+0.10) is met. The
confidence interval is uninformative because the mechanism activated on effectively no
cases — the defensible statistical statement is that the corpus contains too few
genuine competing operatives to test the hypothesis.

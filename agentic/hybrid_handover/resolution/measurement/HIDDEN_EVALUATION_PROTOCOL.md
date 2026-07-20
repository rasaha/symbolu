# HIDDEN_EVALUATION_PROTOCOL — Audit-Only Generalisation Layer

A hidden evaluation layer that varies surface form while preserving capability.
**Audit-only: never used for tuning and never added to benchmark scores.** It
exists to detect overfitting to the visible cases' cue vocabulary.

## Variation families
The visible benchmark cases are NOT modified. Hidden mirrors vary:
- relationship wording ("deleted and replaced" → "struck out and substituted", …)
- override phrasing ("notwithstanding" → "regardless of")
- document order, entity names, section numbering
- effective dates
- nested exceptions
- parallel authorities
- multi-hop references

## Scoring
Relationship-endpoint DISCOVERY (owner: Discovery), per resolver — did the
resolver produce the required `(src, dst)` endpoints under the varied surface?

## Result (endpoint discovery, by family)
| family | frozen | rule | graph_traversal |
|---|---|---|---|
| entity | 1/4 | 4/4 | 4/4 |
| wording | 1/4 | **1/4** | **1/4** |
| date | 1/1 | 1/1 | 1/1 |
| numbering | 1/1 | 1/1 | 1/1 |
| nested | 0/1 | 1/1 | 1/1 |
| parallel | 0/1 | 1/1 | 1/1 |
| multihop | 0/1 | 1/1 | 1/1 |

## Finding
The deterministic resolvers generalise across entity, order, numbering, dates,
nested exceptions, parallel authorities, and multi-hop references — but remain
**brittle to relationship wording (1/4)**. They detect relationships by matching a
fixed cue vocabulary; a paraphrase of the relationship language defeats discovery.

This is a property of the deterministic resolvers, now **measured rather than
hidden**. The metric is trustworthy; the low wording score is honest signal, not a
metric defect.

## Governance for the hidden layer
- Never committed with the visible benchmark as scored cases.
- Never used to tune a resolver.
- Rotated/expanded over time so cue-memorisation cannot track it.
- A large public-minus-hidden gap on any future resolver is evidence of
  overfitting and must be reported alongside headline scores.

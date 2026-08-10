# ABSTENTION_METRICS — Abstention as a Decision Problem

The old single-number `abstention_accuracy` was gameable: an always-abstain
resolver scored 1.0 on it (and on cycle detection). It is replaced by decision
metrics computed over governance-owned cases (OCR/coverage is SafetyGate-owned and
excluded).

## Confusion counts
| | gold: abstain | gold: answer |
|---|---|---|
| resolver abstains | TA (true) | **FA (false — the harm)** |
| resolver answers | MA (missed) | TN (true) |

## Metrics (owner: Governance)
- `abstention_precision` = TA / (TA + FA) — of refusals, how many deserved it
- `abstention_recall`    = TA / (TA + MA) — of deserved refusals, how many caught
- `answer_coverage`      = answered / N   — how often it actually answers
- `selective_accuracy`   = correct / answered — accuracy on the cases it answered

## Why always-abstain now scores poorly
| resolver | precision | recall | coverage | selective_acc |
|---|---|---|---|---|
| always_abstain | **< 0.5** | 1.00 | **0.00** | **0.00** |
| frozen | 0.00 | 0.00 | 0.94 | 0.40 |
| rule | 0.00 | 0.00 | 0.94 | 0.60 |
| graph_traversal | **1.00** | **1.00** | 0.69 | **0.82** |

`always_abstain` still has recall 1.0 (it abstains on everything, so it catches
every deserved abstention) but its **precision is low, coverage is zero, and
selective accuracy is zero** — it answers nothing correctly. High recall alone can
no longer earn a good score. `graph_traversal` is the only resolver that both
abstains precisely (1.00) and answers accurately when it does (0.82).

## Ownership
All four are Governance-owned decision metrics. Coverage/OCR abstention is a
separate SafetyGate concern (`coverage_abstention_accuracy`) validated by SEEB's
frozen coverage validator, not by the resolver.

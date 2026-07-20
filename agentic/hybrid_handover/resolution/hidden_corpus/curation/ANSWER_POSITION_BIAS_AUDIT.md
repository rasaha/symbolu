# ANSWER_POSITION_BIAS_AUDIT

Corpus-level shortcut correlations over the 27 answerable accepted pilot cases
(`answer_position.py`). A rate > 0.8 is flagged excessive. Seed cases are NOT
altered; only new pilot candidates would be rebalanced.

| Shortcut | Rate | Excessive? |
|---|---|---|
| governing is the LAST document | 0.593 | no |
| governing is the FIRST document | 0.444 | no |
| table governs when a table is present | 0.111 | no |
| appendix governs when present | 0.074 | no |
| longest document governs | 0.704 | no |
| abstention by difficulty | L2:3, L3:6, L4:2 | not concentrated at one level |

**Excessive flags: none.**

## Notes
- Governing position is well spread (last 0.59 / first 0.44 — many cases have
  multiple governing nodes, e.g. reference chains, so both can be true).
- Tables and appendices do NOT systematically lose: `tvt_table_wins`,
  `apx_prevails`, and the deep table cases have the table/appendix GOVERN, while
  `apx_body_wins` has the body beat the appendix — the "appendix/table usually
  loses" shortcut is deliberately broken.
- Abstention is spread across L2–L4, not concentrated at one difficulty.
- `longest_doc_governs` at 0.70 is the highest correlation but below threshold; it
  is a natural artifact (the governing clause is often the more detailed one) and
  is flagged here for monitoring as the corpus grows.

No rebalancing was required for this pilot.

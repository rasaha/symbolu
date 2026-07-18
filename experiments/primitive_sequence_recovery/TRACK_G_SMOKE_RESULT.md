# Track G Smoke — Result (exploratory triage only)

- scorer_model: `mistralai/Mistral-7B-Instruct-v0.3` | temp 0.0
- primary_label: `RANDOM_POLARITY_EXPLAINS`
- deltas (A_vs_R & A_vs_X co-primary): {'A_vs_R': -0.1917, 'A_vs_X': -0.075, 'A_vs_B': -0.0167, 'A_vs_I': -0.1167, 'A_vs_D': 0.0667}
- per_arm_mrr: {'A': 0.7583, 'R': 0.95, 'B': 0.775, 'I': 0.875, 'X': 0.8333, 'D': 0.6917}
- per_arm_top1: {'A': 0.6, 'R': 0.9, 'B': 0.6, 'I': 0.8, 'X': 0.7, 'D': 0.5}
- tasks_judged: 10 | dropped: [] | malformed_rate: 0.0

Track G polarity-boundary smoke, exploratory triage only. A is varṇa-table-derived (researcher-authored, high-DOF). Not validation, no varṇa truth. Track B remains blocked. Structure, not validated meaning.

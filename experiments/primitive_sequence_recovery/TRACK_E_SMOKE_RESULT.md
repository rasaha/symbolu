# Track E Smoke Pilot — Result (exploratory triage only)

- **primary_label:** `CONTEXT_ONLY_EXPLAINS`
- **scorer_model:** `mistralai/Mistral-7B-Instruct-v0.3` | generator (recorded): `Qwen/Qwen2.5-7B-Instruct` | temp 0.0
- **malformed_rate:** 0.0093 | contamination: none
- **abort_events:** ['malformed:pkt_b16a28096c415406:MalformedScorerOutput: unknown packet_id: \'pkt_b16a28096c415506\' :: raw=\'{"packet_id": "pkt_b16a28096c415506", "scores": {"opt_1": 0.5, "opt_2": 0.4, "opt_3": 0.0, "opt_4": 0.1, "opt_5": 0.0, "opt_6": 0.0}, "chosen": "opt_1"}\'']
- **full_pilot_justified:** no
- **per-arm means:** {'mrr': {'A': 0.7917, 'B': 0.8056, 'X': 0.9583, 'F': 0.8472, 'D': 0.5236, 'I': 0.875}, 'top1': {'A': 0.6667, 'B': 0.75, 'X': 0.9167, 'F': 0.75, 'D': 0.25, 'I': 0.75}}
- **deltas:** {'A_vs_X': -0.1667, 'A_vs_B': -0.0139, 'A_vs_F': -0.0556, 'A_vs_D': 0.2681, 'A_vs_I': -0.0833}

## Per-case rows (rank of context-correct)

- {'case_id': 'e000', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 1, 'rank_B': 1, 'rank_X': 2, 'rank_F': 2, 'rank_D': 4, 'rank_I': 2}
- {'case_id': 'e001', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 2, 'rank_I': 1}
- {'case_id': 'e002', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 4, 'rank_I': 1}
- {'case_id': 'e003', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 2, 'rank_I': 1}
- {'case_id': 'e004', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 2, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 1, 'rank_I': 1}
- {'case_id': 'e005', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 2, 'rank_I': 2}
- {'case_id': 'e006', 'domain': 'abstract_primary', 'exploratory_only': False, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 4, 'rank_I': 1}
- {'case_id': 'e007', 'domain': 'concrete_control', 'exploratory_only': False, 'rank_A': 6, 'rank_B': 6, 'rank_X': 1, 'rank_F': 1, 'rank_D': 3, 'rank_I': 1}
- {'case_id': 'e008', 'domain': 'concrete_control', 'exploratory_only': False, 'rank_A': 3, 'rank_B': 3, 'rank_X': 1, 'rank_F': 3, 'rank_D': 1, 'rank_I': 1}
- {'case_id': 'e009', 'domain': 'concrete_control', 'exploratory_only': False, 'rank_A': 2, 'rank_B': 6, 'rank_X': 1, 'rank_F': 3, 'rank_D': 1, 'rank_I': 1}
- {'case_id': 'e010', 'domain': 'famous_exploratory', 'exploratory_only': True, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 5, 'rank_I': 2}
- {'case_id': 'e011', 'domain': 'famous_exploratory', 'exploratory_only': True, 'rank_A': 1, 'rank_B': 1, 'rank_X': 1, 'rank_F': 1, 'rank_D': 2, 'rank_I': 1}

Track E smoke pilot completed as exploratory triage only. Track B remains blocked. Structure, not validated meaning.

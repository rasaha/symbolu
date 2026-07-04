# Track F Smoke — Result (exploratory triage only)

- answer_model: `mistralai/Mistral-7B-Instruct-v0.3` | temp 0.0 | judge_mode: single
- primary_label: `CORRECTNESS_DEGRADED`
- packets: 72 | malformed_rate: 0.0278 | aborted: False
- tasks_judged: 10 | dropped_by_judge: ['f010', 'f002']
- judge_note: single-model judge (answer model judged its own anonymized outputs; lexical distances): EXPLORATORY / weaker — no answer≠judge separation
- metrics: {'delta_A_vs_X': 0.6448, 'spec_A_vs_B': 0.569, 'spec_A_vs_I': 0.5675, 'incr_A_vs_F': 0.6478, 'correctness_preserved': -0.1, 'usefulness_gain': -0.1, 'noise_A': 0.05, 'halluc_A': 0.05}
- per_arm_means: {'X': {'correctness': 1.0, 'usefulness': 1.0, 'poetic_noise': 0.0, 'hallucination': 0.0}, 'A': {'correctness': 0.9, 'usefulness': 0.9, 'poetic_noise': 0.05, 'hallucination': 0.05}, 'B': {'correctness': 1.0, 'usefulness': 1.0, 'poetic_noise': 0.0, 'hallucination': 0.0}, 'F': {'correctness': 0.9, 'usefulness': 0.9, 'poetic_noise': 0.0, 'hallucination': 0.0}, 'I': {'correctness': 1.0, 'usefulness': 1.0, 'poetic_noise': 0.0, 'hallucination': 0.0}}

Track F smoke pilot, exploratory triage only. Single-model judge; not validation, no varṇa truth. Track B remains blocked. Structure, not validated meaning.

# Results — main

Config: {'arms': 'Q,L,R,P,PL', 'seeds': '0,1,2', 'steps': 1500, 'N': 160, 'target_params': 2000000, 'tag': 'main'}  ·  vocab=1278  ·  corpus_tokens=55547
Params (arm→count): Q=1999756, L=1999756, R=1999772, P=2000288, PL=2000292
Train wall-s/run (mean): Q=349, L=306, R=222, P=300, PL=414

## Task 1 — LM perplexity (real English corpus), mean±sd over seeds
| arm | ppl@256 (in-dist) | ppl@512 (extrap) |
|---|---|---|
| Q (softmax) | 150.07±8.24 | 155.97±8.48 |
| L (window) | 154.57±5.12 | 158.03±4.83 |
| R (gated-lin-rec) | 65.02±2.87 | 69.57±2.41 |
| P (phase) | 139.36±26.28 | 149.90±29.05 |
| PL (phase+local) | 129.93±13.76 | 137.77±14.01 |

## Task 2 — single-needle accuracy by distance (chance≈0.02)
| arm | d=16 | d=96 | d=220 |
|---|---|---|---|
| Q (softmax) | 0.58±0.40 | 0.53±0.38 | 0.59±0.39 |
| L (window) | 0.01±0.01 | 0.00±0.01 | 0.00±0.00 |
| R (gated-lin-rec) | 0.03±0.01 | 0.02±0.01 | 0.02±0.01 |
| P (phase) | 0.01±0.01 | 0.01±0.01 | 0.01±0.01 |
| PL (phase+local) | 0.03±0.01 | 0.03±0.01 | 0.02±0.01 |

## Task 4 — entity–attribute binding accuracy by #entities (chance≈0.02)
| arm | k=2 | k=4 | k=6 |
|---|---|---|---|
| Q (softmax) | 0.19±0.13 | 0.10±0.07 | 0.06±0.04 |
| L (window) | 0.00±0.01 | 0.00±0.00 | 0.01±0.01 |
| R (gated-lin-rec) | 0.02±0.01 | 0.02±0.02 | 0.02±0.01 |
| P (phase) | 0.03±0.01 | 0.02±0.01 | 0.01±0.00 |
| PL (phase+local) | 0.02±0.01 | 0.02±0.02 | 0.01±0.01 |

## Task 8 — multi-hop integration & distant-evidence causal follow-rate
| arm | multihop acc | perturb-follow (reads distant evidence) |
|---|---|---|
| Q (softmax) | 0.15±0.09 | 0.63±0.36 |
| L (window) | 0.00±0.00 | 0.01±0.02 |
| R (gated-lin-rec) | 0.02±0.01 | 0.03±0.01 |
| P (phase) | 0.02±0.01 | 0.03±0.02 |
| PL (phase+local) | 0.04±0.01 | 0.04±0.01 |

## Task (D) — length generalization (train ctx=256 → eval 256/512/1024)
| arm | needle@256 | needle@512 | needle@1024 | bind@256 | bind@512 | bind@1024 |
|---|---|---|---|---|---|---|
| Q (softmax) | 0.60±0.36 | 0.59±0.41 | 0.59±0.38 | 0.08±0.06 | 0.07±0.05 | 0.06±0.04 |
| L (window) | 0.00±0.01 | 0.00±0.01 | 0.00±0.01 | 0.00±0.01 | 0.00±0.00 | 0.01±0.01 |
| R (gated-lin-rec) | 0.01±0.01 | 0.03±0.01 | 0.01±0.01 | 0.01±0.01 | 0.03±0.02 | 0.02±0.01 |
| P (phase) | 0.01±0.00 | 0.02±0.02 | 0.02±0.01 | 0.03±0.02 | 0.01±0.01 | 0.02±0.02 |
| PL (phase+local) | 0.01±0.01 | 0.00±0.01 | 0.01±0.01 | 0.02±0.03 | 0.02±0.01 | 0.02±0.01 |

## Causal ablations on Phase arms (needle@d96 / binding@k4), mean over seeds
| arm | baseline | phase→zero | state shuffle-pos | no-phase (angles=0) |
|---|---|---|---|---|
| P (phase) needle | 0.01±0.01 | 0.00±0.00 | 0.01±0.01 | 0.03±0.01 |
| P (phase) binding | 0.02±0.01 | 0.00±0.00 | 0.01±0.01 | 0.02±0.01 |
| PL (phase+local) needle | 0.03±0.01 | 0.00±0.00 | 0.02±0.01 | 0.03±0.01 |
| PL (phase+local) binding | 0.02±0.02 | 0.00±0.00 | 0.01±0.01 | 0.03±0.01 |

## Per-seed raw values (key metrics)
| arm | seed | ppl256 | needle96 | bind4 | mhop | follow | ng@512 |
|---|---|---|---|---|---|---|---|
| Q | 0 | 151.2 | 0.57 | 0.13 | 0.24 | 0.75 | 0.74 |
| Q | 1 | 159.6 | 0.05 | 0.01 | 0.03 | 0.13 | 0.04 |
| Q | 2 | 139.5 | 0.98 | 0.18 | 0.19 | 0.99 | 1.00 |
| L | 0 | 149.0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| L | 1 | 153.3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| L | 2 | 161.4 | 0.01 | 0.01 | 0.01 | 0.03 | 0.01 |
| R | 0 | 63.8 | 0.01 | 0.04 | 0.02 | 0.03 | 0.04 |
| R | 1 | 62.3 | 0.03 | 0.00 | 0.03 | 0.04 | 0.03 |
| R | 2 | 69.0 | 0.03 | 0.03 | 0.02 | 0.03 | 0.03 |
| P | 0 | 152.1 | 0.00 | 0.04 | 0.00 | 0.01 | 0.04 |
| P | 1 | 163.2 | 0.01 | 0.01 | 0.01 | 0.05 | 0.01 |
| P | 2 | 102.8 | 0.02 | 0.01 | 0.03 | 0.03 | 0.00 |
| PL | 0 | 132.3 | 0.03 | 0.00 | 0.03 | 0.05 | 0.00 |
| PL | 1 | 112.0 | 0.04 | 0.01 | 0.03 | 0.04 | 0.01 |
| PL | 2 | 145.5 | 0.03 | 0.05 | 0.06 | 0.03 | 0.00 |

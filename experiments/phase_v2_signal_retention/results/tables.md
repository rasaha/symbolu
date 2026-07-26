# Phase v2 signal-retention — tables

## Focus decode from Phase STATE @ distance 256 (chance 0.025)
| variant/mode | state_top1 |
|---|---:|
| V1/e2e | 0.250 |
| V2-S/gate_sup | 1.000 |
| V2-M/gate_sup | 0.217 |
| V2-M/e2e | 0.183 |

## Distance ladder — Phase STATE focus top1
| len | V1 | V2-S/gate_sup |
|---|---:|---:|
| 64 | 0.250 | 0.729 |
| 128 | 0.125 | 0.771 |
| 256 | 0.229 | 0.729 |
| 512 | 0.208 | 0.625 |
| 1024 | 0.208 | 0.521 |

## Gate ablations (V2-S/gate_sup, readout g)
| gate | top1 |
|---|---:|
| learned | 0.450 |
| forced_one | 0.417 |
| forced_zero | 0.100 |
| random | 0.283 |
| shuffled | 0.183 |
| chance | 0.025 |

# Phase-guidance diagnostics — result tables

## Headline: answer accuracy & write-F1 by arm/pressure (seed 0)
| arm/pressure | answer_acc | write_f1 |
|---|---:|---:|
| C_p1x | 0.950 | 0.020 |
| C_p3x | 0.980 | 0.000 |
| D-no-guid_p1x | 0.970 | 0.200 |
| D-no-guid_p3x | 0.400 | 0.077 |
| D-query-only_p1x | 0.890 | 0.000 |
| D-query-only_p3x | 0.710 | 0.000 |
| D-write-only_p1x | 0.760 | 0.000 |
| D-write-only_p3x | 0.110 | 0.015 |
| D_p1x | 0.970 | 0.000 |
| D_p3x | 0.850 | 0.000 |

## Q A/F — topic decodability (D, 3x; chance=0.05)
| feature | top1 | top3 |
|---|---:|---:|
| local_only | 0.367 | 0.583 |
| phase_only | 0.117 | 0.283 |
| local_plus_phase | 0.261 | 0.500 |
| random_state_control | 0.078 | 0.244 |
| shuffled_phase_control | 0.072 | 0.211 |

## Q B — controlled long-filler: Phase topic decode & SNR vs distance
| K (filler) | phase_top1 | state_norm | cos_to_decl | topic_SNR |
|---:|---:|---:|---:|---:|
| 64 | 0.016 | 163 | 0.826 | 0.0103 |
| 128 | 0.047 | 336 | 0.822 | 0.0056 |
| 256 | 0.031 | 698 | 0.801 | 0.0023 |
| 512 | 0.094 | 1279 | 0.811 | 0.0016 |
| 1024 | 0.062 | 2261 | 0.887 | 0.0008 |
| 2048 | 0.047 | 4572 | 0.881 | 0.0004 |
| 4096 | 0.047 | 9430 | 0.870 | 0.0002 |
| 8192 | 0.078 | 19188 | 0.863 | 0.0001 |
| 16384 | 0.062 | 38764 | 0.860 | 0.0000 |
| 32768 | 0.031 | 78004 | 0.858 | 0.0000 |

## Q C — numerator attribution vs distractor count (D, 3x)
| n_cand | seq_len | topic_share | relfact_share | filler_share | rel/distr | Z |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 258 | 0.0421 | 0.0293 | 0.8978 | 9.677 | 5919 |
| 9 | 303 | 0.0075 | 0.0097 | 0.9407 | 2.199 | 6568 |
| 17 | 348 | 0.0114 | 0.0165 | 0.8983 | 0.544 | 8171 |
| 33 | 629 | 0.0076 | 0.0100 | 0.8980 | 0.406 | 13595 |
| 65 | 1192 | 0.0039 | 0.0045 | 0.9317 | 0.294 | 25677 |
| 129 | 2317 | 0.0037 | 0.0044 | 0.9245 | 0.318 | 49995 |

## Q D — imposed-decay intervention (D, 3x; config decay=none)
| gamma | phase_top1 | horizon |
|---:|---:|---:|
| 1.0 | 0.127 | None |
| 0.999 | 0.120 | 1000.0 |
| 0.99 | 0.127 | 100.0 |
| 0.95 | 0.140 | 20.0 |
| 0.9 | 0.127 | 10.0 |

## Q E — per-head (D, 3x); full_top1=0.133, eff_rank=11.5/96, mean|corr|=0.034
| head | topic_top1 | out_norm | ablate_delta |
|---:|---:|---:|---:|
| 0 | 0.120 | 1.143 | -0.013 |
| 1 | 0.107 | 1.650 | -0.053 |
| 2 | 0.127 | 1.522 | -0.040 |
| 3 | 0.093 | 0.924 | +0.047 |

## Q H — content-vs-Phase read score & beta sweep (D, 3x)
R = |s_phase|/|s_content|: mean=0.056, p90=0.107

| beta | answer_acc | frac_read_changed |
|---:|---:|---:|
| 0.0 | 0.900 | 0.000 |
| 0.01 | 0.900 | 0.000 |
| 0.05 | 0.910 | 0.000 |
| 0.1 | 0.910 | 0.000 |
| 0.25 | 0.900 | 0.020 |
| 0.5 | 0.910 | 0.020 |
| 1.0 | 0.910 | 0.030 |

## Q I/J — slot-chain trace (occupancy / eviction / pressure)
| arm/pressure | occ/M | saturated_end | evictions | hard_writes | matches |
|---|---:|---:|---:|---:|---:|
| C/1x | 1.9/8 | 0.00 | 0.0 | 4.4 | 3.6 |
| C/3x | 2.2/8 | 0.00 | 0.0 | 7.3 | 6.4 |
| D/1x | 2.3/8 | 0.00 | 0.0 | 5.6 | 4.7 |
| D/3x | 1.8/8 | 0.00 | 0.0 | 7.6 | 6.8 |

## Q K — shortcut checks (answer acc under corruption)
| mode | C | D |
|---|---:|---:|
| intact | 1.000 | 0.907 |
| shuffle_slot_values | 0.060 | 0.053 |
| shuffle_slot_keys | 0.973 | 0.893 |
| random_slot_values | 0.033 | 0.027 |
| zero_readout_memory | 0.040 | 0.027 |
| mask_query_entity | 1.000 | 0.900 |
| remove_phase_at_query |  | 0.900 |

## Q M — filler masking → Phase topic decode (D, 3x; chance=0.05)
| input | phase_topic_top1 |
|---|---:|
| all_tokens | 0.127 |
| filler_zeroed | 0.093 |
| topic_fact_only | 0.293 |

## Q L — per-loss gradients into shared params (D, 3x)
| group | |g_answer| | |g_write| | grad_cosine | write/answer |
|---|---:|---:|---:|---:|
| guidance_head | 2.765e-02 | 5.163e-02 | +0.389 | 1.867e+00 |
| phase | 1.186e-01 | 4.963e-02 | -0.182 | 4.186e-01 |

## Q G — write-label alignment (3x)
label==1 precision for needed-later: 1.000; topic facts/ex=1.0, distractors/ex=24.0
(topic&needed label1=300, topic&not-needed label1=0)

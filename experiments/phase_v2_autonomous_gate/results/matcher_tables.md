# Matcher study — focus↔event relevance (recurrence unchanged)

| arm | AUROC | rel−distr margin | d2048 | d4096 | focus-removed margin | top10 prec | top10 recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| token | 0.498 | -0.002 | 0.889 | 0.751 | -0.002 | 0.389 | 0.100 |
| cond_mlp | 0.620 | +0.106 | 1.000 | 1.000 | +0.001 | 0.730 | 0.187 |
| cosine | 0.796 | +5.846 | 0.990 | 0.981 | -0.147 | 0.872 | 0.223 |
| bilinear | 0.830 | +48.827 | 0.996 | 0.994 | +0.359 | 0.865 | 0.222 |
| bilinear_hard | 0.837 | +40.910 | 0.995 | 0.996 | +0.574 | 0.842 | 0.228 |

**Best AUROC arm:** bilinear_hard (0.837); COND-MLP baseline 0.620; token 0.498

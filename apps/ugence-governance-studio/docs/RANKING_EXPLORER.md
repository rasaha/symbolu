# Ranking Explorer (P3D)

Per-role ranked candidate list in canonical API rank order. Each candidate shows
rank, agent identity/version, provider, total score, tie group and an expandable
**score decomposition** (criterion, raw value, normalized bp, weight bp, weighted
contribution bp, evidence) plus the result fingerprint. Optional presentation
sort is clearly labeled and never replaces the canonical rank (a reset action
restores it). No score, weight or tie-break is computed in the browser — all come
from `GET /scenarios/{id}/ranking`.

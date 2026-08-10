# CANDIDATE_LIFECYCLE

Explicit, non-skipping states with deterministic transitions (`schema.py`).

```
DRAFT ─▶ AUTHOR_COMPLETE ─▶ READY_FOR_BLIND_ANNOTATION ─▶ ANNOTATED
      ─▶ READY_FOR_ADJUDICATION ─▶ ACCEPTED
                                └▶ REJECTED
                                └▶ QUARANTINED
```

- A candidate must traverse every state in order; skipping is rejected by
  `validate_path` (e.g. DRAFT→ANNOTATED is invalid).
- Terminal states (ACCEPTED / REJECTED / QUARANTINED) have no outgoing transition.
- Only ACCEPTED candidates enter the pilot executable corpus.
- Each candidate must carry all three role artifacts; ACCEPTED requires an
  accepted gold graph; REJECTED/QUARANTINED require a rationale (`lifecycle.py`).

## This pilot
43 candidates, each with a complete, valid lifecycle path (0 lifecycle issues):
- **ACCEPTED: 38**
- **REJECTED: 4**
- **QUARANTINED: 1**

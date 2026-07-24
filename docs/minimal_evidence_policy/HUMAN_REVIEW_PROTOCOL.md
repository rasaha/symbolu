# Human-Review Protocol (Phase 12)

*The protocol for a real human-review study of the minimal policy. In this environment **no real
reviewers are available**, so human validation is **NOT EVALUATED** — the technical evaluation is
completed, but an external customer pilot is **not** recommended on this basis.*

## Status

| | |
|---|---|
| Human validation | **NOT EVALUATED** (no real reviewers) |
| Technical evaluation | complete |
| External-pilot recommendation | **not** made without real human validation |

A deterministic dual-rubric **proxy** (`review_study.py`) characterizes label stability on the
human-review set. It is explicitly **not** human validation and is never reported as such.

## The protocol (for when real reviewers are available)

- **Reviewers:** at least two, preferably three, independent.
- **Set:** the 50-item `HUMAN_REVIEW_SET`, balanced across risk and obligation classes (E1–E4).
- **Blinding:** reviewers judge independently first; the system's obligation is revealed only after their
  independent judgment.
- **Reviewers assess:** claim factuality; risk; source authority; the minimum evidence obligation
  (E0–ER); whether available evidence satisfies the obligation; whether qualification is necessary;
  whether a clean allow would be safe; whether human review is required.
- **Record:** exact agreement; acceptable-obligation agreement; clean-allow agreement; unsafe-allow
  disagreement; source-authority agreement; review time; confidence; override rate + direction; and
  whether the policy's one-trace explanation was useful.

## Proxy result (NOT human validation)

| Metric | Value |
|---|---|
| Independent-rubric agreement | 0.50 |
| Minimal policy matches gold | 0.72 |
| Minimal policy ≥ gold (safe direction) | **0.98** |
| Minimal policy < gold (would-be unsafe) | 1 / 50 |

The policy sits at or above the independent gold on 98% of the review set (errs stronger), with a single
below-gold case — a small divergence to examine with real reviewers. Rubric agreement 0.50 on this
harder, obligation-balanced subset re-confirms that fine labels need human adjudication.

## Consequence

Because human validation is NOT EVALUATED, the architectural/pilot decision (Phase 23) cannot recommend
an external customer pilot; at most an **internal** pilot with the review protocol above run by real
staff. This is a hard gate, not a soft preference.

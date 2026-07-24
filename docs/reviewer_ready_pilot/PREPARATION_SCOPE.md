# Preparation Scope (Phase 1)

*Exactly what this track prepares, and the boundaries it holds. Everything here is apparatus; none of it
requires — or produces — real human evidence.*

## In scope (prepare, build, test)

1. **Reviewer role model** — technical, policy/risk, domain (optional), adjudicator, administrator.
2. **Reviewer governance** — eligibility, confidentiality, pseudonymization, conflict-of-interest,
   withdrawal, no-employment-use, decision independence, no coaching, retention/deletion (templates, not
   real reviewer data).
3. **Reviewer materials** — guide, quick reference, common errors, decision tree (examples excluded from
   the final set).
4. **Training + qualification** — a labelled training set and a qualification protocol + scorer that
   grades *future* reviewer responses (never synthesizes them).
5. **Final review set** — ≥ 75 naturally occurring artifacts, blind, disjoint from all prior/held-out and
   training sets; balanced where naturally available (else actual counts reported).
6. **Label schema + blinded interface** — two-stage (blinded / post-reveal) with strict separation.
7. **Assignment + access** — pseudonymous, role-based, independent, no cross-reviewer visibility, no
   system result before Stage B.
8. **Frozen policy runner** — the minimal policy read-only + frozen EA/AssertionGate/ActionGate,
   preserving the six native ActionGate outcomes.
9. **Audit + adjudication** — separately immutable system/reviewer outputs; disagreement detection with
   no automatic majority-rule; unresolved outcomes.
10. **Metrics** — the full endpoint set, returning `NOT_EVALUATED` until real records exist.
11. **Stop conditions** — immediate technical stops + future cumulative thresholds (not evaluated until
    real data exists).
12. **Simulated workflow test** — deterministic actors, `SIMULATED_WORKFLOW_ONLY`.
13. **Recruitment + onboarding plans; future human-evaluation protocol (frozen in advance).**

## Out of scope (must not do)

- Conduct or claim real human validation, agreement, usability, or review-time.
- Generate fake human reviewers or call simulation "human validation."
- Modify the frozen minimal policy or tune it on the reviewer set.
- Reveal the system result in the blinded state.
- Enable enforcement, execute external actions, onboard an external customer.
- Lower any downstream threshold; collapse native ActionGate outcomes.
- Process prohibited/unapproved data.
- Claim production readiness.

## Readiness vs validation

The deliverable is a **reviewer-ready package** plus a **readiness assessment** whose only allowed values
are READY / PARTIAL / NOT READY / NOT EVALUATED — with **human validation fixed at NOT EVALUATED**. The
final decision is one of eight readiness options; none may imply real human validation.

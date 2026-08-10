# Reviewer Onboarding Plan (Phase 19)

*The step-by-step onboarding a real reviewer goes through before they touch a final-set artifact. No
reviewer has been onboarded in this track; this is the runbook the administrator follows.*

## Onboarding steps (in order)

1. **Assign a pseudonym.** The reviewer is `REV-A`, `REV-B`, … . The identity → pseudonym mapping is held
   separately, access-controlled, and deleted at the retention horizon (Phase 3).
2. **Consent.** The reviewer signs the consent template (Phase 3): logging of decisions/timing/confidence
   for calibration, pseudonymization, and the retention/deletion terms. Voluntary and revocable.
3. **Conflict-of-interest disclosure.** The reviewer completes the COI template. Declared conflicts are
   loaded into the assignment module so conflicted artifacts are never assigned to them.
4. **Role assignment.** The administrator assigns the reviewer's role(s) (Phase 2) based on expertise.
5. **Study the guide.** The reviewer reads `REVIEWER_GUIDE.md`, `REVIEWER_QUICK_REFERENCE.md`,
   `COMMON_REVIEW_ERRORS.md`, and `REVIEW_DECISION_TREE.md`, and works through the training set (Phase 6,
   revealed labels).
6. **Qualify.** The reviewer takes the qualification quiz drawn from the **training** set (never the final
   set). `qualification.py` scores their submitted responses against the frozen criteria (Phase 7). Only a
   reviewer who passes every criterion may submit final-set labels. A failing candidate may re-study and
   retake with a fresh draw.
7. **Access provisioning.** The administrator grants role- and tenant-scoped access (`access.py`). The
   reviewer can now see only the blinded view of the artifacts assigned to them.
8. **Begin blinded review.** The reviewer works each assigned artifact through Stage A (blinded) → reveal
   → Stage B, per the interface (Phase 11). Every action is audited (Phase 14).

## Standing rules during the pilot

- **Blinding:** the reviewer never sees the system result before locking Stage A, and never sees another
  reviewer's label.
- **Independence:** no coaching toward the system's answers on final items.
- **No enforcement:** nothing the reviewer does executes an action or enables enforcement.
- **Withdrawal:** the reviewer may withdraw at any time; in-progress reviews are discarded and personal
  data deleted (Phase 3).

## Offboarding and retention

At the end of the calibration window, decision/timing data is deleted per the retention terms, and the
identity mapping is deleted at or before the horizon (Phase 3). Deletion is tenant-scoped and verifiable.

## Honesty note

Completing onboarding — even qualification — is readiness to review, not validation of the policy. Human
validation of the policy's correctness remains **NOT EVALUATED** until real reviews run and metrics are
computed on real records.

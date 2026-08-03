# Eligibility Explanations

The drawer consumes `POST /explanations/eligibility` and shows passed, failed and
unknown conditions, elimination reason codes with deterministic readable labels,
evidence and policy references, and fingerprints (result, report, profile, role).
Reason labels are a fixed mapping of API codes — no reason is invented and no LLM
is used. The drawer is an accessible dialog with focus trap and restoration.

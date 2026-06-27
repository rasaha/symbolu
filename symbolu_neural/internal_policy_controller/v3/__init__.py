"""internal_policy_controller v3 — corrected per V2_AUDIT_AND_V3_PLAN.md.

Fixes the v2 defects (D1-D8): every CLAIMED Symbol-U variable now drives a DISTINCT
policy axis (enforced by a field-influence self-test), Aspect is computed, sattva is
reachable, dead branches are removed, draft-states are used everywhere, silent
fallbacks are surfaced, and the relabel control permutes every consumed ontology
category. v3 is SELF-CONTAINED (local llm/judge/data — the verified helpers were
relocated here from v2 during cleanup). v1/v2 kept intact only as the audited-
defective record.

No API key in this sandbox -> the quality verdict still cannot run here; the mock
backend is plumbing-only and the pilot refuses a quality verdict.
"""

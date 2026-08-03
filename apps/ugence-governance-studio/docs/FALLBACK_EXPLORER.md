# Fallback Explorer (P3D)

Per role: primary assignment, ordered fallback candidates, and an explicit
fallback state using the live API taxonomy (COMPLETE = fallback available,
PARTIAL = limited, NO_FALLBACK_AVAILABLE, NOT_APPLICABLE). Roles with no
independent fallback are made prominent, never silently omitted. A scenario-level
coverage summary counts API-returned states only (roles with primaries, roles
with ≥1 fallback, roles with no fallback, total candidates) — no fallback
candidate is created in the browser.

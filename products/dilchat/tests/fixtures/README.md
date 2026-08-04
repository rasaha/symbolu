# DilChat astrology test fixtures — two evidence classes

Fixtures are split into two explicit, non-interchangeable evidence classes
(Area E hardening).

## 1. `REGRESSION_FIXTURE` — `golden_charts.json`

- **Generated from the current implementation's own Swiss Ephemeris (`pyswisseph`)
  Moshier stack.**
- Detects **unintended changes** (regression) in the astronomy + derivation
  pipeline.
- **Does NOT independently establish astronomical correctness.** It is a wrapper
  around the same installed Swiss library, so it cannot validate itself.
- Carries the provider version and the derivation method so a mismatch is visible.

Regenerate (only when an intended pipeline change lands, and review the diff):

```bash
python - <<'PY'
import datetime as dt, json
from ugence_dilchat.astrology.swiss import SwissEphemerisProvider
from ugence_dilchat.services.birthtime import compute_birth_interval
from ugence_dilchat.domain.enums import BirthTimePrecision
prov = SwissEphemerisProvider(mode="moshier")
# ... (see tests/integration/test_golden_astrology.py for the case list) ...
PY
```

## 2. `INDEPENDENT_REFERENCE_FIXTURE` — `independent_reference_charts.json`

- Derived from a **separately-implemented / independently-published authoritative
  astronomical reference** (e.g. Skyfield + a separately-sourced JPL DE ephemeris,
  a documented authoritative service, or a professionally-verified manual
  calculation).
- Validates **correctness**, not just regression stability.
- Output from another wrapper around the **same** installed Swiss library does
  **not** qualify as independent.
- Full per-case metadata schema is in the file's `_case_schema`.

**Current status: `INDEPENDENT_REFERENCE_VALIDATION_PENDING`.** No independently
sourced cases have been obtained yet (offline environment). The schema and the
validation harness (`test_golden_astrology.py::test_independent_reference_fixtures`)
exist; while `cases` is empty the harness reports **XFAIL** so the pending state is
visible and is never hidden behind a green pass. User-facing natal release stays
gated on populating and verifying this file.

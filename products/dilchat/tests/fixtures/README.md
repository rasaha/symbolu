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

**Current status: `VERIFIED_INDEPENDENT`.** 16 cases populated from **Astropy**
(pyerfa / IAU-SOFA), an implementation independent of Swiss Ephemeris — see
`docs/DILCHAT_INDEPENDENT_ASTRO_REFERENCE_VALIDATION.md`. Regenerate with
`pip install -e ".[validation,swiss]"` then
`python scripts/generate_independent_reference.py`. The committed suite validates
DilChat's Swiss provider against these frozen values in
`tests/integration/test_independent_astro.py` (no Astropy needed at runtime).
Max observed sidereal difference: **19.8 arcsec**. A JPL-DE (Skyfield) cross-check
remains an optional future tightening (JPL download blocked in this environment).

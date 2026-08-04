"""Golden astrology tests — DEVELOPMENT VALIDATION ONLY.

These recompute a small set of reference charts with the Swiss provider in Moshier
mode (AGPL dev edition) and assert they match the frozen fixtures. They verify
determinism and regression stability of the astronomy + derivation pipeline. They
are explicitly NOT evidence that the draft Guna rule pack is correct, and the
Moshier values are not independently oracle-verified (that is a golden-freeze task
requiring a trusted reference — see DILCHAT_ASTROLOGY_ENGINE_SPEC.md).
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from ugence_dilchat.astrology.fake import FakeAstrologyProvider
from ugence_dilchat.astrology.provider import EphemerisUnavailableError
from ugence_dilchat.domain.enums import BirthTimePrecision
from ugence_dilchat.services.birthtime import compute_birth_instant

swisseph = pytest.importorskip("swisseph")
from ugence_dilchat.astrology.swiss import SwissEphemerisProvider  # noqa: E402

_FIX_DIR = pathlib.Path(__file__).parent.parent / "fixtures"
_FIXTURES = json.loads((_FIX_DIR / "golden_charts.json").read_text())
_INDEPENDENT = json.loads((_FIX_DIR / "independent_reference_charts.json").read_text())
# Moon longitude regression tolerance (deg). Small because we compare the SAME
# provider+version against its own frozen output (determinism/regression).
_TOL = 1e-4


def test_golden_fixtures_are_regression_class_only():
    # These fixtures must never be presented as independent validation (Area E).
    assert _FIXTURES["fixture_class"] == "REGRESSION_FIXTURE"
    assert _INDEPENDENT["fixture_class"] == "INDEPENDENT_REFERENCE_FIXTURE"


def _instant(case) -> dt.datetime:
    r = compute_birth_instant(
        birth_date=dt.date.fromisoformat(case["birth_date"]),
        birth_time_local=dt.time.fromisoformat(case["birth_time_local"]),
        precision=BirthTimePrecision.EXACT,
        iana_timezone=case["iana_timezone"],
        ambiguity_resolution=None,
    )
    return r.utc_instant


@pytest.mark.parametrize("case", _FIXTURES["cases"], ids=lambda c: c["label"])
def test_golden_chart_regression(case):
    prov = SwissEphemerisProvider(mode="moshier")
    assert prov.provider_version == _FIXTURES["provider_version"]  # pinned
    result = prov.compute_moon(_instant(case), input_confidence=1.0)
    d = result.derivation
    assert d.longitude == pytest.approx(case["moon_longitude"], abs=_TOL)
    assert d.rashi_index == case["rashi_index"]
    assert d.rashi_name == case["rashi_name"]
    assert d.nakshatra_index == case["nakshatra_index"]
    assert d.pada == case["pada"]
    assert 0.0 <= d.longitude < 360.0
    assert result.provenance.ayanamsa == "lahiri"
    assert result.provenance.ephemeris_mode == "moshier"
    assert result.provenance.fallback_used is False


def test_swiss_moshier_deterministic():
    p1 = SwissEphemerisProvider(mode="moshier")
    p2 = SwissEphemerisProvider(mode="moshier")
    inst = dt.datetime(1990, 5, 15, 9, 0, tzinfo=dt.UTC)
    r1 = p1.compute_moon(inst, input_confidence=1.0)
    r2 = p2.compute_moon(inst, input_confidence=1.0)
    assert r1.derivation.longitude == r2.derivation.longitude
    assert r1.derivation.nakshatra_index == r2.derivation.nakshatra_index


def test_swieph_mode_fails_explicitly_without_data_files():
    # No .se1 files are present; swieph mode must fail explicitly, never silently
    # falling back to Moshier.
    prov = SwissEphemerisProvider(mode="swieph")
    with pytest.raises(EphemerisUnavailableError):
        prov.compute_moon(dt.datetime(1990, 5, 15, 9, 0, tzinfo=dt.UTC), input_confidence=1.0)


def test_fake_provider_deterministic():
    p = FakeAstrologyProvider()
    inst = dt.datetime(1990, 5, 15, 9, 0, tzinfo=dt.UTC)
    a = p.compute_moon(inst, input_confidence=1.0)
    b = p.compute_moon(inst, input_confidence=1.0)
    assert a.derivation == b.derivation
    assert 0.0 <= a.derivation.longitude < 360.0

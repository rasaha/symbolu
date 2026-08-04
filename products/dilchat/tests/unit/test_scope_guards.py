"""Guard tests: no Guna Milan route is exposed; the draft rule pack stays draft.

The rule pack may be parsed and structurally validated in isolation (permitted),
but this phase must never expose a Guna score. These fixtures are explicitly
DRAFT_UNVERIFIED and non-user-facing.
"""

from __future__ import annotations

import json
import pathlib

from ugence_dilchat.app import create_app
from ugence_dilchat.config import Environment, Settings

_PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_RULE_PACK = _PRODUCT_ROOT / "rules" / "ashtakoota_lahiri_classical_v1"


def test_no_guna_route_registered():
    app = create_app(Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://"))
    paths = list(app.openapi()["paths"].keys())
    assert paths, "expected some routes"
    assert not any("guna" in p.lower() for p in paths)
    assert not any("compatibility" in p.lower() for p in paths)


def test_openapi_exposes_uncertainty_schemas():
    app = create_app(Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://"))
    schemas = app.openapi()["components"]["schemas"]
    # Uncertainty-aware natal response + field-result + interval schemas present.
    assert "NatalMoonResponse" in schemas
    assert "FieldResultModel" in schemas
    assert "UtcIntervalModel" in schemas
    natal = schemas["NatalMoonResponse"]["properties"]
    for key in ("moon_rashi", "moon_nakshatra", "moon_pada", "guna_eligibility",
                "synthetic_calculation", "authoritative", "utc_interval"):
        assert key in natal
    # The single-longitude "moon_longitude"/"rashi_index" answer fields are gone.
    assert "rashi_index" not in natal


def test_rule_pack_is_draft_unverified_and_structurally_sound():
    manifest = json.loads((_RULE_PACK / "manifest.json").read_text())
    # DRAFT_UNVERIFIED: must remain gated out of user-facing use.
    assert manifest["draft"] is True
    assert manifest["review_required"] is True
    # Structural consistency (maxima sum to 36) — safe to validate in isolation.
    maxima = {c["name"]: c["max"] for c in manifest["components"]}
    assert maxima == {
        "varna": 1, "vashya": 2, "tara": 3, "yoni": 4,
        "graha_maitri": 5, "gana": 6, "bhakoot": 7, "nadi": 8,
    }
    assert manifest["total_max"] == 36 == sum(maxima.values())


def test_rule_pack_sources_unverified():
    sources = json.loads((_RULE_PACK / "sources.json").read_text())
    # Every citation is unverified => the pack cannot back a user-facing report.
    assert all(c.get("verified") is False for c in sources["citations"])

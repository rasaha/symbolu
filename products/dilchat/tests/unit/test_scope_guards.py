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
_NEW_PACK = _PRODUCT_ROOT / "rules" / "ashtakoota_muhurta_chintamani_raman_v1"


def test_new_authority_pack_is_non_executable_and_unverified():
    man = json.loads((_NEW_PACK / "manifest.json").read_text())
    # The new named pack must stay non-executable / draft until the authority gate clears.
    assert man["draft"] is True
    assert man["executable"] is False
    maxima = {c["name"]: c["max"] for c in man["components"]}
    assert maxima == {"varna": 1, "vashya": 2, "tara": 3, "yoni": 4,
                      "graha_maitri": 5, "gana": 6, "bhakoot": 7, "nadi": 8}
    assert man["total_max"] == 36
    # Nothing is domain-approved or source-frozen, and no citation is verified.
    src_path = _PRODUCT_ROOT / "rules" / "sources" / "GUNA_SOURCE_MANIFEST.json"
    src = json.loads(src_path.read_text())
    assert src["overall_status"] == "PENDING_ACQUISITION"
    assert all(s["review_status"] != "FROZEN_PRIMARY" for s in src["sources"])
    # Every parihara rule is disabled.
    par = json.loads((_NEW_PACK / "parihara.json").read_text())
    rules = par.get("rules", [])
    assert rules and all(r.get("enabled") is False for r in rules)


def test_old_draft_pack_preserved():
    # The prior draft pack must not be overwritten/deleted (deprecated evidence).
    assert (_RULE_PACK / "manifest.json").exists()


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

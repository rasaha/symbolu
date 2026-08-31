"""The documented public API equals the actual package surface (ADR §8, §20)."""

from __future__ import annotations

import dataclasses
import enum
import json
import pathlib

import ugence_policy_authority as g
from ugence_policy_authority import api

_PKG_ROOT = pathlib.Path(g.__file__).resolve().parent
_DIST_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PUBLIC_API_JSON = _DIST_ROOT / "public_api.json"


def _kind(obj) -> str:
    if isinstance(obj, type):
        if issubclass(obj, enum.Enum):
            return "enum"
        if issubclass(obj, Exception):
            return "exception"
        if dataclasses.is_dataclass(obj):
            return "dataclass"
        return "class"
    if callable(obj):
        return "function"
    return type(obj).__name__


def _actual_surface() -> tuple[dict, dict]:
    symbols: dict[str, dict] = {}
    constants: dict[str, str] = {}
    for name in sorted(api.__all__):
        if name == "__version__":
            continue
        obj = getattr(api, name)
        entry: dict = {"kind": _kind(obj)}
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            entry["values"] = [m.value for m in obj]
        elif isinstance(obj, type) and dataclasses.is_dataclass(obj):
            # Field ORDER is part of the snapshot, not merely the field set.
            entry["fields"] = [f.name for f in dataclasses.fields(obj)]
        elif isinstance(obj, str):
            entry["kind"] = "str_constant"
            entry["value"] = obj
            constants[name] = obj
        elif isinstance(obj, dict):
            entry["kind"] = "mapping_constant"
            entry["keys"] = sorted(
                k.value if isinstance(k, enum.Enum) else str(k) for k in obj
            )
        symbols[name] = entry
    return symbols, constants


def _documented() -> dict:
    return json.loads(_PUBLIC_API_JSON.read_text())


def test_documented_public_api_matches_actual():
    documented = _documented()
    symbols, constants = _actual_surface()
    assert documented["distribution"] == "ugence-policy-authority"
    assert documented["namespace"] == "ugence_policy_authority"
    assert documented["package_version"] == g.__version__ == "0.2.0"
    assert documented["curated_api_module"] == "ugence_policy_authority.api"
    assert documented["symbols"] == symbols
    assert documented["constants"] == constants


def test_curated_api_names_match_module_all():
    documented = _documented()
    expected = {n for n in api.__all__ if n != "__version__"}
    assert set(documented["symbols"]) == expected


def test_the_protocol_and_canonicalization_constants_are_snapshotted_exactly():
    documented = _documented()
    assert documented["authority_protocol"] == api.AUTHORITY_PROTOCOL == "ugence.policy-authority"
    assert documented["authority_protocol_version"] == api.AUTHORITY_PROTOCOL_VERSION == "v0.1"
    assert (
        documented["authority_protocol_id"]
        == api.AUTHORITY_PROTOCOL_ID
        == "ugence.policy-authority/v0.1"
    )
    assert (
        documented["canonicalization_version"]
        == api.CANONICALIZATION_VERSION
        == "ugence.policy-authority/canonicalization/v1"
    )
    assert documented["unicode_posture"] == "REJECT_NON_NFC"


def test_every_public_domain_constant_is_snapshotted():
    documented = _documented()
    for name in (
        "POLICY_BODY_DIGEST_DOMAIN",
        "ISSUANCE_SIGNING_DOMAIN",
        "REVOCATION_SIGNING_DOMAIN",
        "SUPERSESSION_REFERENCE_UNSUPPORTED",
        "GLOBAL_TENANT",
    ):
        assert name in documented["constants"], name
        assert documented["constants"][name] == getattr(api, name)


def test_top_level_and_curated_surfaces_agree():
    assert set(g.__all__) == set(api.__all__)
    for name in api.__all__:
        assert getattr(g, name) is getattr(api, name)


def test_py_typed_present():
    assert (_PKG_ROOT / "py.typed").is_file()


def test_obsolete_uvi_ownership_and_permissive_supersession_api_is_gone():
    for retired in (
        "SupersessionRule",
        "SUPPORTED_POLICY_FAMILIES",
        "UnsupportedPolicyFamilyError",
        "policy_family_of",
        "require_supported_policy",
        "canonical_policy_body_digest",
        "canonical_policy_body_bytes",
    ):
        assert retired not in api.__all__, retired
        assert not hasattr(api, retired), retired


def test_no_existing_package_version_was_bumped():
    import ugence_uvi_policy_contracts

    assert ugence_uvi_policy_contracts.__version__ == "0.1.0"


def test_no_symbol_shadows_a_contract_symbol():
    from ugence_uvi_policy_contracts import api as contracts_api

    overlap = set(api.__all__) & set(contracts_api.__all__)
    assert overlap == {"__version__"}


def test_the_adapter_seam_is_public():
    """A consumer can write and register a family adapter without internals."""

    for required in (
        "PolicyFamilyAdapter",
        "PolicyArtifactDescriptor",
        "PolicyCoordinate",
        "AdapterRegistry",
        "framed_body_digest",
        "framed_body_bytes",
        "canonical_bytes",
        "sha256_hex",
    ):
        assert required in api.__all__, required

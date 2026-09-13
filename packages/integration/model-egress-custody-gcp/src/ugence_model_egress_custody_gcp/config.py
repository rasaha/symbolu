"""Configuration this adapter accepts: references only, never material.

Every custody misconfiguration that ends in a leaked key looks the same at the start:
a field that was meant to hold a pointer was handed the thing it pointed at. So the
configuration is scanned before it is used, and a value that carries credential
material is refused whatever field it arrived in, with the field named and the value
never repeated.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

from ugence_model_egress_unit import looks_like_a_credential

from .identity import RuntimeIdentityAssertion
from .resource import parse_secret_version

__all__ = ["FORBIDDEN_CONFIG_KEYS", "ConfigRefused", "CustodyConfig", "refuse_credential_material"]

#: Keys that name credential MATERIAL rather than a reference to it. Matched on the
#: whole key, case-folded, with separators normalized, so ``privateKey``, ``private-key``
#: and ``PRIVATE_KEY`` are one name. A pointer field (``*_ref``, ``*_resource``,
#: ``*_path``, ``*_id``, ``*_digest``) is never on this list: pointers are the whole
#: point of the configuration.
FORBIDDEN_CONFIG_KEYS = frozenset({
    "privatekey", "privatekeyid", "clientsecret", "clientemail",
    "apikey", "openaiapikey", "openaikey", "vendorkey", "secret", "secretvalue",
    "secretpayload", "payload", "credentials", "credentialsjson", "credential",
    "serviceaccountkey", "serviceaccountjson", "sakey", "keydata", "keyfile",
    "password", "passphrase", "bearertoken", "accesstoken", "refreshtoken",
    "authorizationheader", "googleapplicationcredentials",
})


class ConfigRefused(ValueError):
    """Configuration this adapter will not accept. Names the field, never the value."""


def _normalize(key: str) -> str:
    return "".join(c for c in str(key).lower() if c.isalnum())


def _looks_like_a_service_account_key(value: str) -> bool:
    """A downloaded Google service-account key, inline or as a JSON string."""

    stripped = value.strip()
    if not stripped.startswith("{"):
        return False
    try:
        parsed = json.loads(stripped)
    except Exception:  # noqa: BLE001 - unparseable is not a key document
        return False
    if not isinstance(parsed, Mapping):
        return False
    return bool(parsed.get("private_key")) or parsed.get("type") == "service_account"


def refuse_credential_material(config: Any, *, path: str = "config") -> None:
    """Walk ``config`` and raise :class:`ConfigRefused` at the first credential.

    Three things are refused: a key that names material, a value carrying a credential
    shape (the unit's production detector), and a value that is a downloaded
    service-account key document. The refusal names the path and never the value.
    """

    if isinstance(config, Mapping):
        for key, value in config.items():
            if _normalize(key) in FORBIDDEN_CONFIG_KEYS:
                raise ConfigRefused(
                    f"{path}.{key}: this field names credential material; custody configuration carries "
                    f"references only (a resource name, an id, a digest), never the secret itself")
            refuse_credential_material(value, path=f"{path}.{key}")
        return
    if isinstance(config, (list, tuple)):
        for index, value in enumerate(config):
            refuse_credential_material(value, path=f"{path}[{index}]")
        return
    if isinstance(config, str):
        if looks_like_a_credential(config):
            raise ConfigRefused(
                f"{path}: the value carries a credential shape; custody configuration never holds a "
                f"provider key, a token or a secret payload")
        if _looks_like_a_service_account_key(config):
            raise ConfigRefused(
                f"{path}: the value is a downloaded service-account key document; the deployment runs as "
                f"its attached service account and holds no key file (LP-2)")


@dataclass(frozen=True)
class CustodyConfig:
    """Everything the production-form adapter needs, as references.

    Validated at construction: the resource is parsed and pinned, the identity source is
    checked, and every field is scanned for credential material.
    """

    custody_authority_id: str
    credential_profile: str
    vendor: str
    secret_version_resource: str
    identity: RuntimeIdentityAssertion
    lease_ttl_seconds: int = 300
    max_credential_age_days: int = 90
    environment: str = "non-production"

    def __post_init__(self) -> None:
        # The identity's type is checked first: every later step reads it as a record.
        if not isinstance(self.identity, RuntimeIdentityAssertion):
            raise ConfigRefused("config.identity: a RuntimeIdentityAssertion is required")
        refuse_credential_material(self.as_reference_record())
        for name in ("custody_authority_id", "credential_profile", "vendor"):
            if not str(getattr(self, name)).strip():
                raise ConfigRefused(f"config.{name}: required")
        parse_secret_version(self.secret_version_resource)
        if not (1 <= int(self.lease_ttl_seconds) <= 3600):
            raise ConfigRefused("config.lease_ttl_seconds: a lease lives between one second and one hour")
        if not (1 <= int(self.max_credential_age_days) <= 90):
            raise ConfigRefused("config.max_credential_age_days: rotation is at least every 90 days (LP-2)")
        if str(self.environment).strip().lower() != "non-production":
            raise ConfigRefused(
                "config.environment: this commissioning path is non-production only; production is a "
                "separate commissioning record (LP-7, LP-8)")

    def as_reference_record(self) -> dict:
        """The configuration as identifiers, for the scan and for a redacted report."""

        record = asdict(self)
        record["identity"] = dict(record["identity"])
        return record

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "CustodyConfig":
        if not isinstance(mapping, Mapping):
            raise ConfigRefused("config: a mapping is required")
        identity = mapping.get("identity")
        if not isinstance(identity, Mapping):
            raise ConfigRefused("config.identity: a mapping is required")
        unknown = set(identity) - {f for f in RuntimeIdentityAssertion.__dataclass_fields__}
        if unknown:
            raise ConfigRefused(f"config.identity: unknown field(s) {sorted(unknown)}")
        known = {f for f in cls.__dataclass_fields__}
        extra = set(mapping) - known
        if extra:
            raise ConfigRefused(f"config: unknown field(s) {sorted(extra)}")
        refuse_credential_material(mapping)
        return cls(**{**{k: v for k, v in mapping.items() if k != "identity"},
                      "identity": RuntimeIdentityAssertion(**dict(identity))})

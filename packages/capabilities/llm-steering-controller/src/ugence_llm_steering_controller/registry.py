"""Candidate registry — provider/model METADATA only.

The registry holds descriptive facts used to filter and score candidates. Constructing
or loading a registry performs **no** I/O: it never contacts a provider, queries a model
endpoint, reads environment credentials, opens a socket, or starts a background worker.

Secret-shaped keys are actively rejected at load time (fail-closed) so a registry can
never smuggle an API key, bearer token, or live client through its metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .contracts import ModelCandidate, ProviderCandidate, RegistryError

# Keys that must never appear anywhere in registry input (case-insensitive substring).
_FORBIDDEN_KEY_PATTERNS = (
    "api_key", "apikey", "secret", "token", "bearer", "password", "passwd",
    "credential", "private_key", "client_secret", "access_key", "aws_secret",
    "authorization", "auth_token", "session_token", "cert", "certificate",
)
_FORBIDDEN_RE = re.compile("|".join(re.escape(p) for p in _FORBIDDEN_KEY_PATTERNS), re.IGNORECASE)


def _scan_for_secrets(obj: Any, path: str = "") -> None:
    """Fail closed if any object key looks like a credential/secret."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _FORBIDDEN_RE.search(k):
                raise RegistryError(
                    f"forbidden secret-like key '{k}' at {path or '<root>'}; the registry "
                    "must contain metadata only, never credentials")
            _scan_for_secrets(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _scan_for_secrets(v, f"{path}[{i}]")


class CandidateRegistry:
    """An immutable-in-spirit snapshot of routable providers and models."""

    def __init__(self, providers: Iterable[ProviderCandidate], models: Iterable[ModelCandidate]):
        self._providers: Dict[str, ProviderCandidate] = {}
        for p in providers:
            if p.provider_id in self._providers:
                raise RegistryError(f"duplicate provider_id '{p.provider_id}'")
            self._providers[p.provider_id] = p

        self._models: Dict[str, ModelCandidate] = {}
        for m in models:
            if m.model_id in self._models:
                raise RegistryError(f"duplicate model_id '{m.model_id}'")
            if m.provider_id not in self._providers:
                raise RegistryError(
                    f"model '{m.model_id}' references unknown provider '{m.provider_id}'")
            self._models[m.model_id] = m

    # -- accessors (deterministic ordering) --------------------------------------------
    @property
    def providers(self) -> List[ProviderCandidate]:
        return [self._providers[k] for k in sorted(self._providers)]

    @property
    def models(self) -> List[ModelCandidate]:
        return [self._models[k] for k in sorted(self._models)]

    def provider(self, provider_id: str) -> ProviderCandidate:
        try:
            return self._providers[provider_id]
        except KeyError:
            raise RegistryError(f"no provider '{provider_id}'")

    def model(self, model_id: str) -> Optional[ModelCandidate]:
        return self._models.get(model_id)

    def __len__(self) -> int:
        return len(self._models)

    # -- construction ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CandidateRegistry":
        if not isinstance(d, dict):
            raise RegistryError("registry must be an object")
        _scan_for_secrets(d)
        providers = [ProviderCandidate.from_dict(p) for p in d.get("providers", [])]
        models = [ModelCandidate.from_dict(m) for m in d.get("models", [])]
        if not models:
            # An empty registry is legal but noted; discovery/recommend handle it as a
            # typed no-eligible-candidate outcome rather than an error.
            pass
        return cls(providers, models)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "providers": [p.to_dict() for p in self.providers],
            "models": [m.to_dict() for m in self.models],
        }

    # -- fingerprint (reproducibility) -------------------------------------------------
    def fingerprint(self) -> str:
        """Stable content hash of the registry snapshot (sorted, canonical JSON)."""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return "reg-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def validate_registry(d: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a raw registry payload. Returns ``(ok, problems)`` without raising for
    ordinary content problems; secret-like keys still fail closed."""
    problems: List[str] = []
    try:
        CandidateRegistry.from_dict(d)
    except RegistryError as exc:
        problems.append(str(exc))
    except Exception as exc:  # contract errors from candidate construction
        problems.append(f"{type(exc).__name__}: {exc}")
    return (not problems), problems


__all__ = ["CandidateRegistry", "validate_registry"]

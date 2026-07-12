"""Local session storage with retention + deletion, and separation of derived
features from raw telemetry.

At-rest protection: files are written 0600. If a passphrase is supplied, records are
encrypted with a **stdlib-only** stream cipher (PBKDF2-HMAC-SHA256 key derivation,
SHA-256 counter-mode keystream, HMAC-SHA256 integrity tag). This is honest
obfuscation-to-moderate protection, NOT an audited AEAD (no AES/libsodium available
here) — use full-disk encryption for real deployments. See PRIVACY_AND_ETHICS.md.

Layout:  <root>/<participant>/<session_id>/
    meta.json          session metadata (+ provenance)
    telemetry.jsonl    privacy-safe raw events           (raw lane)
    features.json      derived feature vectors           (derived lane, exported separately)
    quality.json       per-session quality summary
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# stdlib stream cipher (documented as non-audited)
# ---------------------------------------------------------------------------

_MAGIC = b"BBIOENC1"


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:n])


def encrypt_bytes(data: bytes, passphrase: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 200_000, dklen=32)
    ct = bytes(a ^ b for a, b in zip(data, _keystream(key, nonce, len(data))))
    tag = hmac.new(key, _MAGIC + salt + nonce + ct, hashlib.sha256).digest()
    return _MAGIC + salt + nonce + tag + ct


def decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    if blob[:8] != _MAGIC:
        raise ValueError("not an encrypted bbio blob")
    salt, nonce, tag, ct = blob[8:24], blob[24:40], blob[40:72], blob[72:]
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 200_000, dklen=32)
    expect = hmac.new(key, _MAGIC + salt + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expect):
        raise ValueError("integrity check failed (wrong passphrase or tampering)")
    return bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce, len(ct))))


def _write(path: Path, data: bytes, passphrase: Optional[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = encrypt_bytes(data, passphrase) if passphrase else data
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def _read(path: Path, passphrase: Optional[str]) -> bytes:
    raw = path.read_bytes()
    if raw[:8] == _MAGIC:
        if not passphrase:
            raise ValueError(f"{path} is encrypted; a passphrase is required")
        return decrypt_bytes(raw, passphrase)
    return raw


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

@dataclass
class SessionStore:
    root: Path
    passphrase: Optional[str] = None

    def __post_init__(self):
        self.root = Path(self.root)

    def _dir(self, participant: str, session_id: str) -> Path:
        return self.root / _safe(participant) / _safe(session_id)

    # ---- raw telemetry lane ----

    def save_session(self, session: Dict[str, Any]) -> Path:
        meta = session["session_meta"]
        d = self._dir(meta["participant_pseudonym"], meta["session_id"])
        _write(d / "meta.json", _json(meta), self.passphrase)
        lines = "\n".join(json.dumps(e, sort_keys=True) for e in session.get("events", []))
        _write(d / "telemetry.jsonl", lines.encode("utf-8"), self.passphrase)
        return d

    def load_session(self, participant: str, session_id: str) -> Dict[str, Any]:
        d = self._dir(participant, session_id)
        meta = json.loads(_read(d / "meta.json", self.passphrase))
        text = _read(d / "telemetry.jsonl", self.passphrase).decode("utf-8")
        events = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        return {"session_meta": meta, "events": events}

    # ---- derived-feature lane (SEPARATE file/command from raw telemetry) ----

    def save_features(self, participant: str, session_id: str, features: Dict[str, Any]) -> Path:
        d = self._dir(participant, session_id)
        _write(d / "features.json", _json(features), self.passphrase)
        return d / "features.json"

    def load_features(self, participant: str, session_id: str) -> Dict[str, Any]:
        d = self._dir(participant, session_id)
        return json.loads(_read(d / "features.json", self.passphrase))

    def save_quality(self, participant: str, session_id: str, quality: Dict[str, Any]) -> Path:
        d = self._dir(participant, session_id)
        _write(d / "quality.json", _json(quality), self.passphrase)
        return d / "quality.json"

    def load_quality(self, participant: str, session_id: str) -> Dict[str, Any]:
        d = self._dir(participant, session_id)
        return json.loads(_read(d / "quality.json", self.passphrase))

    def save_manifest(self, participant: str, session_id: str, manifest: Dict[str, Any]) -> Path:
        d = self._dir(participant, session_id)
        _write(d / "manifest.json", _json(manifest), self.passphrase)
        return d / "manifest.json"

    def load_manifest(self, participant: str, session_id: str) -> Dict[str, Any]:
        d = self._dir(participant, session_id)
        return json.loads(_read(d / "manifest.json", self.passphrase))

    def has_manifest(self, participant: str, session_id: str) -> bool:
        return (self._dir(participant, session_id) / "manifest.json").exists()

    # ---- enumeration / retention / deletion ----

    def list_sessions(self) -> List[Dict[str, str]]:
        out = []
        if not self.root.exists():
            return out
        for pdir in sorted(self.root.iterdir()):
            if not pdir.is_dir():
                continue
            for sdir in sorted(pdir.iterdir()):
                if (sdir / "meta.json").exists():
                    out.append({"participant": pdir.name, "session_id": sdir.name,
                                "path": str(sdir)})
        return out

    def delete_session(self, participant: str, session_id: str) -> bool:
        d = self._dir(participant, session_id)
        if not d.exists():
            return False
        for f in d.glob("*"):
            _shred(f)
        shutil.rmtree(d, ignore_errors=True)
        return True

    def purge_older_than(self, max_age_days: float, now_epoch: float) -> List[str]:
        """Retention control: delete sessions whose meta mtime is older than the
        retention window. ``now_epoch`` is passed in (no hidden clock)."""
        removed = []
        cutoff = now_epoch - max_age_days * 86400.0
        for s in self.list_sessions():
            meta_path = Path(s["path"]) / "meta.json"
            if meta_path.stat().st_mtime < cutoff:
                if self.delete_session(s["participant"], s["session_id"]):
                    removed.append(f'{s["participant"]}/{s["session_id"]}')
        return removed


def _shred(path: Path) -> None:
    """Best-effort overwrite before unlink (defense in depth; not a guarantee on
    copy-on-write / SSD-wear-leveled media — documented)."""
    try:
        size = path.stat().st_size
        with open(path, "r+b") as f:
            f.write(os.urandom(size))
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass


def _json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, indent=2).encode("utf-8")


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(name))

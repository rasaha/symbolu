"""Generic tool-adapter interface + mock adapters.

Adapters PROVE enforcement; they are not production integrations. Every adapter:

  * requires a broker-minted ``ScopedCredential`` and validates it *through the
    broker* before doing anything — so an adapter cannot execute directly, and a
    forged capability is rejected;
  * declares the permission its verb needs, so scope is checked at use time;
  * performs a mocked side-effect (the filesystem adapter alone touches disk, and
    only inside an explicit sandbox root).

No real cloud, Kubernetes, Terraform, shell, or network calls are made. Real
execution backends are OUT OF SCOPE (see README).
"""

from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING

from .errors import AdapterError
from .mapping import TOOL_PERMS

if TYPE_CHECKING:  # pragma: no cover
    from .broker import CredentialBroker, ScopedCredential
    from .mapping import ToolRequest


class ToolAdapter:
    """Interface every tool adapter implements."""

    name: str = "abstract"

    def needed_permission(self, verb: str) -> str:
        perms = TOOL_PERMS.get(self.name, {})
        if verb not in perms:
            raise AdapterError(f"{self.name}: unsupported verb {verb!r}")
        return perms[verb]

    def execute(self, req: "ToolRequest", credential: "ScopedCredential", *,
                broker: "CredentialBroker", now: str) -> dict:
        """Validate the capability through the broker, then perform the action."""
        needed = self.needed_permission(req.verb)
        # Enforcement chokepoint: no adapter runs without a valid broker capability.
        broker.validate(credential, needed_permission=needed, now=now)
        return self._perform(req)

    def _perform(self, req: "ToolRequest") -> dict:  # pragma: no cover - abstract
        raise NotImplementedError


class FilesystemTool(ToolAdapter):
    name = "filesystem"

    def __init__(self, sandbox_root: str):
        self.root = pathlib.Path(sandbox_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe(self, target: str) -> pathlib.Path:
        p = (self.root / target).resolve()
        if self.root not in p.parents and p != self.root:
            raise AdapterError(f"path escapes sandbox: {target!r}")
        return p

    def _perform(self, req: "ToolRequest") -> dict:
        rel = req.target[0].split("://", 1)[-1] if req.target else "out.txt"
        path = self._safe(rel)
        if req.verb == "write":
            path.parent.mkdir(parents=True, exist_ok=True)
            data = str(req.args.get("content", "")).encode("utf-8")
            path.write_bytes(data)
            return {"status": "ok", "verb": "write", "path": str(path),
                    "bytes_written": str(len(data))}
        if req.verb == "delete":
            existed = path.exists()
            if existed:
                os.remove(path)
            return {"status": "ok", "verb": "delete", "path": str(path),
                    "removed": "true" if existed else "false"}
        if req.verb == "read":
            return {"status": "ok", "verb": "read", "path": str(path),
                    "content": path.read_text() if path.exists() else ""}
        raise AdapterError(f"filesystem: unsupported verb {req.verb!r}")


class ShellCommandTool(ToolAdapter):
    name = "shell"

    def _perform(self, req: "ToolRequest") -> dict:
        # MOCK: never spawns a real process.
        return {"status": "ok", "verb": "run", "mocked": "true",
                "argv": req.args.get("argv", []), "exit_code": "0",
                "stdout": "[mock] command not actually executed"}


class HTTPTool(ToolAdapter):
    name = "http"

    def _perform(self, req: "ToolRequest") -> dict:
        # MOCK: no real network egress.
        return {"status": "ok", "verb": "request", "mocked": "true",
                "method": req.args.get("method", "GET"),
                "url": req.target[0] if req.target else "",
                "response_status": "200"}


class TerraformTool(ToolAdapter):
    name = "terraform"

    def _perform(self, req: "ToolRequest") -> dict:
        # MOCK: no real terraform binary or provider calls.
        return {"status": "ok", "verb": req.verb, "mocked": "true",
                "target": req.target, "resources_changed": req.args.get("changes", "0")}


class KubernetesTool(ToolAdapter):
    name = "kubernetes"

    def _perform(self, req: "ToolRequest") -> dict:
        # MOCK: no real cluster contact.
        return {"status": "ok", "verb": req.verb, "mocked": "true",
                "resource": req.target[0] if req.target else "",
                "namespace": req.args.get("namespace", "default")}


def default_adapters(sandbox_root: str) -> dict:
    return {
        "filesystem": FilesystemTool(sandbox_root),
        "shell": ShellCommandTool(),
        "http": HTTPTool(),
        "terraform": TerraformTool(),
        "kubernetes": KubernetesTool(),
    }

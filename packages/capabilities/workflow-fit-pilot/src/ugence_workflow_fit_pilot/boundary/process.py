"""§4.1 process start: the runner starts the boundary as a separate interpreter process with
the transport endpoint, the manifest digest and the provider-factory dotted path, and blocks on
the boundary's READY line. No clock and no polling. Unix-domain socket transport where
available, otherwise the pipe pair (the boundary's stdin/stdout)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Dict, Optional

from ..contracts.manifest import PilotStudyManifest
from ..errors import PilotError, PilotErrorCode
from .client import BoundaryConnection
from .transport import STDIO_ENDPOINT, UNIX_SOCKETS_AVAILABLE


class BoundaryProcess:
    def __init__(self, manifest: PilotStudyManifest, provider_factory: str, *, env: Optional[Dict[str, str]] = None, transport: Optional[str] = None) -> None:
        self.manifest = manifest
        self.transport = transport or ("unix" if UNIX_SOCKETS_AVAILABLE else "pipe")
        if self.transport == "unix":
            self.dir = tempfile.mkdtemp(prefix="wfp-boundary-")
            self.endpoint = os.path.join(self.dir, "boundary.sock")
        else:
            self.dir, self.endpoint = None, STDIO_ENDPOINT
        decl = manifest.capture_boundary
        args = [
            sys.executable, "-m", "ugence_workflow_fit_pilot.boundary.entry", "--endpoint", self.endpoint,
            "--manifest-digest", manifest.manifest_digest, "--provider-factory", provider_factory,
            "--declaration-json", json.dumps({
                "boundary_identity": decl.boundary_identity, "boundary_version": decl.boundary_version, "process_separation_ref": decl.process_separation_ref,
                "port_ref": decl.port_ref, "allowed_attested_fields": list(decl.allowed_attested_fields),
            }),
        ]
        pipes = subprocess.PIPE if self.transport == "pipe" else None
        self.proc = subprocess.Popen(args, env=env or os.environ.copy(), stdin=pipes, stdout=pipes, stderr=subprocess.PIPE)
        line = self.proc.stderr.readline()  # blocks until READY or process exit; no clock involved
        if line.strip() != b"READY":
            rest = self.proc.stderr.read().decode("utf-8", "replace") if self.proc.stderr else ""
            self.proc.wait()
            raise PilotError(PilotErrorCode.PROVIDER_FACTORY_INVALID, f"boundary process exited before serving: {(line.decode('utf-8', 'replace') + rest).strip()}")

    def connect(self) -> BoundaryConnection:
        if self.transport == "pipe":
            return BoundaryConnection(self.endpoint, pipes=(self.proc.stdout, self.proc.stdin))
        return BoundaryConnection(self.endpoint)

    def stop(self, conn: Optional[BoundaryConnection] = None) -> None:
        try:
            c = conn or (self.connect() if self.transport == "unix" else None)
            if c is not None:
                c.shutdown()
                if conn is None:
                    c.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=30)
        except Exception:
            self.proc.kill()


__all__ = ["BoundaryProcess"]

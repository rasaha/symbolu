"""§4.1 transport: newline-delimited JSON frames over a Unix-domain socket, or over a pipe
pair (the boundary process's stdin/stdout) where Unix-domain sockets are unavailable.
Both sides speak through a FrameStream; nothing else in the package touches a socket."""

from __future__ import annotations

import json
import socket
from typing import Any, BinaryIO, Dict, Optional

UNIX_SOCKETS_AVAILABLE = hasattr(socket, "AF_UNIX")
STDIO_ENDPOINT = "stdio"


class FrameStream:
    def __init__(self, reader: BinaryIO, writer: BinaryIO, closer=None) -> None:
        self._r, self._w, self._closer = reader, writer, closer

    def write(self, frame: Dict[str, Any]) -> None:
        self._w.write((json.dumps(frame) + "\n").encode("utf-8"))
        self._w.flush()

    def read(self) -> Optional[Dict[str, Any]]:
        line = self._r.readline()
        if not line:
            return None
        return json.loads(line.decode("utf-8"))

    def close(self) -> None:
        for f in (self._r, self._w):
            try:
                f.close()
            except Exception:
                pass
        if self._closer is not None:
            try:
                self._closer()
            except Exception:
                pass


def connect(endpoint: str, *, pipes=None) -> FrameStream:
    """Runner side. ``pipes`` = (boundary_stdout, boundary_stdin) for the pipe transport."""
    if endpoint == STDIO_ENDPOINT:
        if pipes is None:
            raise ValueError("pipe transport requires the boundary process's pipes")
        out, inp = pipes
        return FrameStream(out, inp)
    if not UNIX_SOCKETS_AVAILABLE:
        raise ValueError("Unix-domain sockets are unavailable; use the pipe transport")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(endpoint)
    return FrameStream(sock.makefile("rb"), sock.makefile("wb"), sock.close)


def serve(endpoint: str, handler, *, ready) -> None:
    """Boundary side. Calls ``ready()`` once the endpoint accepts frames, then serves one
    client at a time until a SHUTDOWN frame. ``handler(frame) -> reply``."""
    if endpoint == STDIO_ENDPOINT:
        import sys

        stream = FrameStream(sys.stdin.buffer, sys.stdout.buffer)
        ready()
        _serve_stream(stream, handler)
        return
    if not UNIX_SOCKETS_AVAILABLE:
        raise ValueError("Unix-domain sockets are unavailable; start the boundary with --endpoint stdio")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(endpoint)
    srv.listen(1)
    ready()
    try:
        while True:
            conn, _ = srv.accept()
            stream = FrameStream(conn.makefile("rb"), conn.makefile("wb"), conn.close)
            try:
                if _serve_stream(stream, handler):
                    return
            finally:
                stream.close()
    finally:
        srv.close()


def _serve_stream(stream: FrameStream, handler) -> bool:
    """Returns True on SHUTDOWN."""
    while True:
        frame = stream.read()
        if frame is None:
            return False
        if frame.get("kind") == "SHUTDOWN":
            stream.write({"ok": True})
            return True
        stream.write(handler(frame))


__all__ = ["UNIX_SOCKETS_AVAILABLE", "STDIO_ENDPOINT", "FrameStream", "connect", "serve"]

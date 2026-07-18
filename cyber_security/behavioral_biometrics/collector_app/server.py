"""Local, cloud-free collection server (Python stdlib only).

Serves the single-page collector app and a tiny JSON API, bound to 127.0.0.1. It
performs NO global monitoring — all telemetry originates in the page and is POSTed at
session completion, adapted through the frozen schema, quality-gated, and stored
locally. A REAL_PARTICIPANT session is rejected without recorded consent.

    python -m cyber_security.behavioral_biometrics.collector_app.server \
        --root /tmp/bbio-pilot --host 127.0.0.1 --port 8791
"""

from __future__ import annotations

import argparse
import html
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from cyber_security.behavioral_biometrics import privacy, storage
from cyber_security.behavioral_biometrics.collector_app import service

_STATIC = Path(__file__).resolve().parent / "static"
_ALLOWED_STATIC = {"index.html", "app.js", "keyclass.js", "tasks.js", "style.css"}
_CONTENT_TYPES = {".html": "text/html", ".js": "application/javascript", ".css": "text/css"}


def _consent_html() -> str:
    md = Path(__file__).resolve().parent / "CONSENT_SUMMARY.md"
    text = md.read_text() if md.exists() else _DEFAULT_CONSENT
    paras = [html.escape(p.strip()) for p in text.split("\n\n") if p.strip()
             and not p.strip().startswith("#")]
    return "".join(f"<p>{p}</p>" for p in paras[:8])


_DEFAULT_CONSENT = (
    "You are invited to take part in a behavioral instrumentation pilot. We record the "
    "TIMING of your keyboard and mouse activity inside this page only.\n\n"
    "We record key CATEGORIES (e.g. letter, space, backspace) and timing — never the "
    "actual characters or any text you type. We do not monitor anything outside this "
    "page and install no system-wide monitoring.\n\n"
    "Data is stored locally and pseudonymously. You may stop at any time and delete your "
    "session immediately after it ends. This phase measures recording quality only; no "
    "identity or biometric result is produced.\n\n"
    "Behavioral timing data can still be personal; we do not claim anonymity. "
    "Participation is voluntary.")


class Handler(BaseHTTPRequestHandler):
    store: storage.SessionStore = None
    salt: str = "study-salt"

    def _json(self, obj: Dict[str, Any], code: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, data: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            return self._text((_STATIC / "index.html").read_bytes(), "text/html")
        if path.startswith("/static/"):
            name = path[len("/static/"):]
            if name in _ALLOWED_STATIC and (_STATIC / name).exists():
                ct = _CONTENT_TYPES.get((_STATIC / name).suffix, "application/octet-stream")
                return self._text((_STATIC / name).read_bytes(), ct)
            return self._json({"error": "not_found"}, 404)
        if path == "/api/consent-summary":
            return self._json({"html": _consent_html()})
        if path == "/api/sessions":
            return self._json({"sessions": self.store.list_sessions()})
        return self._json({"error": "not_found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except json.JSONDecodeError:
            return self._json({"ok": False, "error": "bad_json"}, 400)
        path = self.path.split("?", 1)[0]
        if path == "/api/session":
            try:
                res = service.ingest_browser_session(self.store, payload, salt=self.salt,
                                                      policy=privacy.PrivacyPolicy())
            except Exception as e:  # noqa: BLE001  (adapter/consent errors -> 400)
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json(res, 200 if res.get("ok") else 400)
        if path == "/api/delete":
            ok = self.store.delete_session(payload.get("participant", ""),
                                           payload.get("session_id", ""))
            return self._json({"deleted": bool(ok)})
        return self._json({"error": "not_found"}, 404)

    def log_message(self, *args):  # keep quiet; never log request bodies
        return


def build_server(root: str, host: str = "127.0.0.1", port: int = 8791,
                 salt: str = "study-salt") -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("refusing to bind to a non-local host (local collection only)")
    Handler.store = storage.SessionStore(Path(root))
    Handler.salt = salt
    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/tmp/bbio-pilot")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--salt", default="study-salt")
    args = ap.parse_args(argv)
    srv = build_server(args.root, args.host, args.port, args.salt)
    print(json.dumps({"listening": f"http://{args.host}:{args.port}", "root": args.root,
                      "note": "local-only collection server; open the URL in a browser"}))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

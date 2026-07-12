"""Real-browser end-to-end: drive the actual page with REAL keyboard/pointer events
via the Chrome DevTools Protocol and verify privacy-safe capture + storage.

Skipped when node or a Chromium binary is unavailable — in that case the
event-adapter and server layers remain covered by the other tests, and the manual
browser checks in ACCEPTANCE_CHECKLIST.md apply.
"""

from __future__ import annotations

import glob
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from cyber_security.behavioral_biometrics.collector_app import server

_E2E = Path(__file__).resolve().parent / "browser_e2e.js"


def _chrome_path():
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/opt/pw-browsers/chromium-*/chrome-linux/headless_shell"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return shutil.which("chromium") or shutil.which("google-chrome")


_CHROME = _chrome_path()

pytestmark = pytest.mark.skipif(shutil.which("node") is None or not _CHROME,
                                reason="node or chromium unavailable for browser E2E")


def test_real_browser_capture_and_store(tmp_path):
    srv = server.build_server(str(tmp_path), "127.0.0.1", 0)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    try:
        proc = subprocess.run(["node", str(_E2E), f"http://127.0.0.1:{port}", _CHROME],
                              capture_output=True, text=True, timeout=90)
    finally:
        srv.shutdown()
    assert proc.stdout.strip(), proc.stderr[-800:]
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result.get("ok"), result
    assert result["captured_events"] > 20
    assert result["has_raw_content"] is False              # no raw characters captured
    assert result["server_result"]["leaks"] == []          # nothing leaked to storage
    # real keyboard AND pointer events flowed through the DOM
    mods = result["modalities"]
    assert mods.get("keydown", 0) > 0 and mods.get("pointermove", 0) > 0

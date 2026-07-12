"""The browser key-class mapping (keyclass.js) must match privacy.key_to_class exactly.
Runs the JS in node; skipped if node is unavailable."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cyber_security.behavioral_biometrics import privacy

_KEYCLASS_JS = Path(__file__).resolve().parents[1] / "static" / "keyclass.js"

_KEYS = ["a", "Z", "q", "5", "0", " ", "space", "Spacebar", "Backspace", "Delete", "Del",
         "Enter", "Return", "Tab", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp",
         "Shift", "Control", "Ctrl", "Alt", "Meta", "CapsLock", "Fn",
         "F1", "F12", "F24", "!", ".", "/", "\\", ";", "'", "\"", "€", "Unidentified", "Dead"]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available")


def test_keyclass_parity_js_vs_python():
    script = (f"const kc=require({json.dumps(str(_KEYCLASS_JS))});"
              f"const keys={json.dumps(_KEYS)};"
              f"console.log(JSON.stringify(keys.map(k=>kc.keyToClass(k))));")
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    js = json.loads(out.stdout.strip())
    py = [privacy.key_to_class(k) for k in _KEYS]
    mismatches = [(_KEYS[i], js[i], py[i]) for i in range(len(_KEYS)) if js[i] != py[i]]
    assert not mismatches, f"key-class mismatches (key, js, py): {mismatches}"

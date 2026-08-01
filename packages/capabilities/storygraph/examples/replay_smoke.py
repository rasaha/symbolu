#!/usr/bin/env python3
"""Replay smoke — deterministic historical-replay over the bundled fixture.

Runs the reference account-takeover Policy Pack against the synthetic replay
fixture shipped in the wheel and shows the deterministic replay report digest
(stable across runs and installs). Synthetic data only — NOT enterprise data,
no accuracy claim.

    python examples/replay_smoke.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ugence_storygraph.policypack import reference, replay


def _fixture_records():
    # The replay fixture ships as package data alongside the policypack.
    pp_dir = Path(reference.__file__).resolve().parent
    fixture = pp_dir / "fixtures" / "account_takeover_replay.json"
    return json.loads(fixture.read_text())["records"]


def main() -> int:
    records = _fixture_records()
    report = replay.run_replay(reference.account_takeover_pack(), records)

    print("records replayed:", len(records))
    print("report digest:   ", report["report_digest"])
    print("bundle digest:   ", report.get("bundle_digest"))

    # Deterministic: same input -> same report digest, matching the frozen value.
    assert report["report_digest"] == \
        "sha-256:0dcf2bc4730bf12a89e5e5e6b54b8a9442b59b105dc068659d8035033977923b"
    again = replay.run_replay(reference.account_takeover_pack(), records)
    assert again["report_digest"] == report["report_digest"]
    print("OK — replay is deterministic and reproduces the recorded digest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Render the canonical AP-3 acceptance report from the designation record.

    python deployment/governed-runtime-worker/ci/ap3_acceptance_report.py            # print
    python deployment/governed-runtime-worker/ci/ap3_acceptance_report.py --write    # write AP3_ACCEPTANCE_REPORT.md
    python deployment/governed-runtime-worker/ci/ap3_acceptance_report.py --check    # exit 1 if the committed report drifted

The report is a deterministic rendering of ``AP3_ENTERPRISE_ISSUER_VALIDATION.json``: it
holds no fact the record does not hold, and the worker's harness fails if the committed
report differs from what this script renders. Acceptance happens by the owner's statement,
recorded in the record's ``evidence.accepting_owner`` and ``evidence.ci_run_or_signed_report``
and then rendered here; the script never fills either. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
RECORD = PKG / "AP3_ENTERPRISE_ISSUER_VALIDATION.json"
REPORT = PKG / "AP3_ACCEPTANCE_REPORT.md"
ACCEPTOR = "Rakesh Mohan — Founder, Ugence Labs"


def render(record: dict) -> str:
    d, e = record["designation"], record["evidence"]
    rulings = record["rulings_applied"]
    lines: list[str] = []
    w = lines.append
    w("# AP-3 Enterprise Issuer Validation — acceptance report")
    w("")
    w("**Canonical acceptance artifact** for ruling AP-3 (`ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §18, §20, §20.7).")
    w("Rendered from `deployment/governed-runtime-worker/AP3_ENTERPRISE_ISSUER_VALIDATION.json` by")
    w("`ci/ap3_acceptance_report.py`; the worker's harness fails if this file drifts from the record.")
    w("It holds no token, cookie, secret, private key or authorization code.")
    w("")
    w(f"**Status:** `{record['ap3_status']}`")
    w("")
    w(f"**Designated acceptor:** {ACCEPTOR}")
    w("")
    accepted = e.get("accepting_owner")
    w(f"**Accepted:** {accepted if accepted else 'NOT ACCEPTED'}")
    w(f"**Signed or CI report:** {e.get('ci_run_or_signed_report') or 'none recorded'}")
    w("")
    w("## 1 — Designation")
    w("")
    w("| Term | Value |")
    w("|---|---|")
    w(f"| Issuer | `{d['issuer']}` |")
    w(f"| Audience | `{d['audience']}` |")
    w(f"| Validated application hostname | `{d['validated_application_hostname']}` |")
    w(f"| Planned custom hostname | {d['planned_custom_hostname']} |")
    w(f"| Production-validation scope | {d['production_validation_scope']} |")
    w(f"| Designated by / at | {d['designated_by']} / {d['designated_at']} |")
    w("")
    w("## 2 — Rulings applied")
    w("")
    for key in ("AP3-D1", "AP3-D2", "AP3-D3", "AP3-D4", "AP3-D5", "AP3-D6"):
        w(f"- **{key}** — {rulings[key]}")
    w("")
    w("## 3 — The sixteen rows")
    w("")
    w("| # | Scenario | Required | Result | Evidence class | Executed | Observed |")
    w("|---|---|---|---|---|---|---|")
    for n, row in enumerate(record["validation_matrix"], start=1):
        result = row["result"] if row["result"] is not None else "null"
        w(f"| {n} | {row['scenario']} | `{row['required']}` | `{result}` | `{row['evidence_class']}` | "
          f"{row.get('executed_at') or '—'} | {row.get('observed', '—')} |")
    w("")
    w("## 4 — Live evidence")
    w("")
    w(f"- JWKS: {e['jwks_probe_run']}")
    for k in e["jwks_key_identifiers"]:
        w(f"  - `{k['kid']}` ({k['kty']}, {k['alg']}, {k['use']})")
    w(f"  - document SHA-256 `{e['jwks_document_sha256']}`")
    cap = e["live_token_capture"]
    w(f"- Redacted capture ({cap['captured_at']}): alg `{cap['alg']}`, typ `{cap['typ']}`, kid `{cap['kid']}`, "
      f"payload keys {', '.join('`' + k + '`' for k in cap['payload_keys'])}, iss `{cap['iss']}`, "
      f"aud `{cap['aud'][0]}`, sub non-empty `{cap['sub_non_empty']}`, type `{cap['type']}`.")
    for run in e.get("live_verification_runs", []):
        w(f"- Live verification run at {run['ran_at']} by {run['ran_by']}: "
          f"PASS {run['summary']['PASS']}, FAIL {run['summary']['FAIL']}, BLOCKED {run['summary']['BLOCKED']}, "
          f"IN_PROCESS {run['summary']['IN_PROCESS']}; token fingerprint `{run['capture']['token_sha256']}`; "
          f"{run['capture']['token_status']}.")
    rev = e["exposed_token_revocation"]
    w(f"- Exposed token `{rev['fingerprint']}`: revocation attested by {rev['revoked_attested_by']} on "
      f"{rev['revoked_attested_at']}; status `{rev['status']}`; evidence: {rev['evidence'] or 'none recorded'}.")
    w("")
    w("## 5 — Remaining owner actions")
    w("")
    for action in e["required_owner_actions"]:
        if not action.startswith("DONE"):
            w(f"- {action}")
    w("")
    w("## 6 — Acceptance")
    w("")
    if accepted:
        w(f"Accepted by {accepted}. Report reference: `{e.get('ci_run_or_signed_report')}`.")
        w("")
        w("Statement as issued:")
        w("")
        w("> " + e["acceptance_statement"])
    else:
        w("Not accepted. The statement below is the one the designated acceptor issues once every")
        w("remaining action in section 5 is closed; on its issue the record's `accepting_owner` and")
        w("`ci_run_or_signed_report` are filled, this report is re-rendered, and `ap3_status` moves to `MET`.")
        w("")
        w("> I, Rakesh Mohan, Founder, Ugence Labs, accept the AP-3 Enterprise Issuer Validation for the")
        w(f"> Cloudflare Access issuer `{d['issuer']}`, audience `{d['audience']}`, validated on the")
        w(f"> application hostname `{d['validated_application_hostname']}`, scoped to human identities")
        w("> authenticated through the designated Google Workspace group, on the basis of")
        w("> `deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md` at commit `<hash>`: rows 1 to 4 and")
        w("> 8 to 12 by my live cryptographic run of 2026-09-11, rows 5 to 7 and 13 under AP3-D6 and rows 14 to")
        w("> 16 under AP3-D5 by in-process conformance evidence. The exposed token is revoked and evidenced.")
        w("> Set `ci_run_or_signed_report` to `deployment/governed-runtime-worker/AP3_ACCEPTANCE_REPORT.md@<hash>`,")
        w("> set `accepting_owner` to `Rakesh Mohan — Founder, Ugence Labs (2026-09-11)`, move `ap3_status` to")
        w("> `MET`, re-render the report, update draft PR #1748, and do not merge.")
    w("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render(json.loads(RECORD.read_text(encoding="utf-8")))
    if args.write:
        REPORT.write_text(text, encoding="utf-8")
        return 0
    if args.check:
        current = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        if current != text:
            print("AP3_ACCEPTANCE_REPORT.md drifted from the record; re-render with --write", file=sys.stderr)
            return 1
        print("AP3_ACCEPTANCE_REPORT.md matches the record")
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""AP-3 live verification, run entirely on the owner's machine (ADR section 20.7).

    py deployment\\governed-runtime-worker\\ci\\ap3_live_verify.py --app https://<application host> [--login]

Obtains one fresh Cloudflare Access token for the application through ``cloudflared``
(never through this terminal), verifies it with the repository's real adapter under the
``cloudflare-access`` profile against the LIVE designated JWKS, drives the matrix rows
that a single human login can drive, and prints ONLY: the redacted capture (as
``ap3_token_capture.py`` prints it), the JWKS key identifiers and digest, and one
PASS / FAIL / BLOCKED / IN_PROCESS line per matrix row.

    THE TOKEN IS NEVER PRINTED, WRITTEN OR RETAINED. Before anything is printed the
    output is checked against every segment of the token and the run aborts if one
    appears. ``--login`` runs ``cloudflared access login`` with its output captured and
    re-prints only the lines that carry no token, because the plain command prints the
    bearer token to the terminal.

This output is evidence for the owner to record; it declares nothing MET and changes no
file. Rows that need a token shape a human login cannot produce (a service token, a
token without email) are BLOCKED here, not faked. Rows 14 to 16 are the in-process
conformance rows of AP3-D5 and are reported as IN_PROCESS.

Requires on the machine: Python 3.10+, PyJWT[crypto], cryptography, SQLAlchemy (the
review-service package imports it), and ``cloudflared`` on the PATH for ``--app``.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parents[1]
RECORD = PKG / "AP3_ENTERPRISE_ISSUER_VALIDATION.json"
SOURCE_PATHS = (
    "packages/integration/approver-identity-jwt/src",
    "packages/integration/governed-review-service/src",
    "packages/integration/governed-review/src",
    "packages/integration/control-plane-root/src",
    "packages/integration/approval-workflow/src",
    "packages/integration/authority-directory/src",
    "packages/governance-contracts/src",
    "packages/integration/agent-runtime-governance/src",
    "packages/integration/risk-authority-runtime/src",
    "packages/integration/risk-authority-status-runtime/src",
    "packages/runtime/agent-runtime/src",
    "packages/risk_authority/src",
    "packages/capabilities/decision-authority/src",
    "packages/providers/actiongate/src",
    "packages/integration/durable-execution/src",
)
for _rel in SOURCE_PATHS:
    _p = str(REPO / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

TOKEN_SHAPE = re.compile(r"eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}")

MATRIX = (
    (1, "correct issuer, audience, tenant and human actor", "ACCEPTED"),
    (2, "wrong issuer", "REFUSED"),
    (3, "wrong audience", "REFUSED"),
    (4, "wrong tenant", "REFUSED"),
    (5, "missing tenant claim", "REFUSED"),
    (6, "workload identity presented as human", "REFUSED"),
    (7, "missing actor-type evidence", "REFUSED"),
    (8, "expired or not-yet-valid token", "REFUSED"),
    (9, "invalid signature", "REFUSED"),
    (10, "unknown signing-key id", "REFUSED"),
    (11, "malformed token", "REFUSED"),
    (12, "JWKS unavailable with no safely cached key", "REFUSED"),
    (13, "signing-key rotation", "NEW_VALID_KEY_ACCEPTED_AFTER_CONTROLLED_REFRESH"),
    (14, "valid identity without a directory grant", "AUTHENTICATED_BUT_UNAUTHORIZED"),
    (15, "valid identity with a wrong-tenant grant", "UNAUTHORIZED"),
    (16, "valid identity with the correct scoped grant", "WRITER_AUTHORIZER_PERMITS_ONLY_THE_NAMED_CAPABILITY"),
)


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def datetime(self) -> datetime:
        return self.now


def designation() -> tuple[dict, dict]:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    d = record["designation"]
    jwks = re.search(r"https://\S+/cdn-cgi/access/certs", d["jwks_trust"]).group(0)
    tenant = re.search(r"tenant_id = '([^']+)'", d["tenant_claim"]).group(1)
    domain = re.search(r"domain exactly '([^']+)'", d["tenant_claim"]).group(1)
    return {"issuer": d["issuer"], "audience": d["audience"], "jwks_url": jwks,
            "tenant": tenant, "domain": domain}, record


def _b64url_json(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _segment(text: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))


def rewrite_header(token: str, **changes: Any) -> str:
    """The same token with header fields changed (None deletes). The signature is left
    as it was, so a header the adapter admits would fail verification afterwards; the
    header checks come first and are what these rows exercise."""
    head, payload, sig = token.split(".")
    header = _segment(head)
    for key, value in changes.items():
        if value is None:
            header.pop(key, None)
        else:
            header[key] = value
    return ".".join((_b64url_json(header), payload, sig))


def tamper_signature(token: str) -> str:
    """One character in the middle of the signature changed (the final character can
    carry only base64url padding bits, so it is never the one flipped)."""
    head, payload, sig = token.split(".")
    i = len(sig) // 2
    replacement = "A" if sig[i] != "A" else "B"
    return ".".join((head, payload, sig[:i] + replacement + sig[i + 1:]))


def filtered_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        out.append("(a line carrying a token was suppressed)" if TOKEN_SHAPE.search(line) else line)
    return out


def obtain_token(app: str, login: bool) -> tuple[Optional[str], list[str]]:
    """Through cloudflared, captured; nothing it prints reaches the terminal unfiltered."""
    notes: list[str] = []
    if login:
        done = subprocess.run(["cloudflared", "access", "login", app], capture_output=True, text=True, check=False)
        notes += filtered_lines(done.stdout + done.stderr)
        if done.returncode != 0:
            return None, notes + [f"cloudflared access login exited {done.returncode}"]
    got = subprocess.run(["cloudflared", "access", "token", "--app", app], capture_output=True, text=True, check=False)
    token = got.stdout.strip()
    if got.returncode != 0 or not TOKEN_SHAPE.fullmatch(token):
        return None, notes + filtered_lines(got.stderr) + [f"cloudflared access token exited {got.returncode}"]
    return token, notes


def verify(token: str, cfg: dict, record: dict, *, jwks_url: Optional[str] = None,
           unavailable_jwks_url: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    from ugence_approver_identity_jwt import (
        CLOUDFLARE_ACCESS_PROFILE,
        AdapterConfig,
        JwksKeyCache,
        JwtApproverIdentityAdapter,
        KeyRetrievalFailed,
        __version__,
    )
    from ugence_governed_review_service import ActorKind

    spec = importlib.util.spec_from_file_location("ap3_token_capture", HERE / "ap3_token_capture.py")
    capture_mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(capture_mod)
    capture = capture_mod.capture(token)

    jwks = jwks_url or cfg["jwks_url"]
    loopback = jwks.startswith("http://")
    production = not loopback
    clock = Clock(now or datetime.now(timezone.utc))
    started = clock.now

    def config(**over) -> AdapterConfig:
        kwargs = dict(issuer=cfg["issuer"], audience=cfg["audience"], jwks_url=jwks,
                      issuer_profile=CLOUDFLARE_ACCESS_PROFILE, bound_tenant=cfg["tenant"],
                      verified_email_domain=cfg["domain"], production=production)
        kwargs.update(over)
        return AdapterConfig(**kwargs)

    keys = JwksKeyCache(config())
    adapter = JwtApproverIdentityAdapter(config(), clock=clock.datetime, keys=keys)

    def with_config(**over) -> JwtApproverIdentityAdapter:
        # the same live keys, a different expectation: rows 2 to 4
        return JwtApproverIdentityAdapter(config(**over), clock=clock.datetime, keys=keys)

    def answer(a, tok: str) -> str:
        try:
            got = a.authenticate(tok)
        except KeyRetrievalFailed as exc:
            return f"IDENTITY_UNAVAILABLE ({type(exc).__name__})"
        if got.authenticated:
            return f"ACCEPTED actor={got.actor_type.value} tenant={list(got.claims.tenant_claims)} profile={got.issuer_profile}"
        return f"REFUSED_{got.refusal}"

    rows: list[dict] = []

    def row(n: int, observed: str, status: str, note: str = "") -> None:
        number, scenario, required = MATRIX[n - 1]
        rows.append({"row": number, "scenario": scenario, "required": required,
                     "observed": observed, "status": status, **({"note": note} if note else {})})

    # row 1
    first = adapter.authenticate(token)
    accepted = (first.authenticated and first.actor_type is ActorKind.HUMAN
                and tuple(first.claims.tenant_claims) == (cfg["tenant"],))
    row(1, answer(adapter, token), "PASS" if accepted else "FAIL")
    kids_now = sorted(keys.known_kids)

    # rows 2 and 3: the same live keys, another expectation
    other_team = "https://not-the-designated-team.cloudflareaccess.com"
    obs = answer(with_config(issuer=other_team, jwks_url=other_team + "/cdn-cgi/access/certs"), token)
    row(2, obs, "PASS" if obs == "REFUSED_ISSUER_MISMATCH" else "FAIL")
    obs = answer(with_config(audience="0" * 64), token)
    row(3, obs, "PASS" if obs == "REFUSED_AUDIENCE_MISMATCH" else "FAIL")
    # row 4: the static binding is not corroborated by this email's domain
    obs = answer(with_config(bound_tenant="another-tenant", verified_email_domain="example.invalid"), token)
    row(4, obs, "PASS" if obs == "REFUSED_EMAIL_DOMAIN_MISMATCH" else "FAIL",
        "the live token's email is under the designated domain; a binding for another domain refuses it")
    row(5, "NOT_EXECUTABLE_WITH_A_HUMAN_LOGIN", "BLOCKED",
        "no tenant claim exists for this issuer (AP3-D2, confirmed by the capture's payload keys); the "
        "uncorroborated shape needs a token without email, which a human login never produces; proven in-process")
    row(6, "NOT_EXECUTABLE_WITH_A_HUMAN_LOGIN", "BLOCKED",
        "needs a live Cloudflare service token (common_name, empty sub); proven in-process")
    row(7, "NOT_EXECUTABLE_WITH_A_HUMAN_LOGIN", "BLOCKED",
        "needs a live token without email or without sub; proven in-process")

    # row 8: the real token, judged at instants past its exp and before its nbf
    payload = _segment(token.split(".")[1])
    parts = []
    clock.now = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc) + timedelta(seconds=1)
    parts.append(answer(adapter, token))
    if "nbf" in payload:
        clock.now = datetime.fromtimestamp(int(payload["nbf"]), tz=timezone.utc) - timedelta(seconds=1)
        parts.append(answer(adapter, token))
    else:
        parts.append("no nbf in this token")
    clock.now = started
    # before nbf the token is also before iat when the issuer sets them equal, and the
    # adapter refuses the earlier of the two first: either refusal is "not yet valid"
    ok8 = parts[0] == "REFUSED_EXPIRED" and parts[1] in ("REFUSED_NOT_YET_VALID", "REFUSED_ISSUED_IN_FUTURE",
                                                          "no nbf in this token")
    row(8, "; ".join(parts), "PASS" if ok8 else "FAIL",
        "judged by the injected clock at exp + 1s and, when nbf is present, at nbf - 1s")

    # row 9: the real key, a tampered signature
    obs = answer(adapter, tamper_signature(token))
    row(9, obs, "PASS" if obs == "REFUSED_SIGNATURE_INVALID" else "FAIL")
    # row 10: an unknown kid, one live refresh, then refusal
    obs = answer(adapter, rewrite_header(token, kid="ap3-verify-unknown-kid"))
    row(10, obs, "PASS" if obs == "REFUSED_KEY_UNKNOWN" else "FAIL", "the JWKS was refreshed once from the live endpoint")
    # row 11: malformed, plus the header substitutions the amended AP3-D1 must still refuse
    parts = {
        "not-a-token": answer(adapter, "not-a-token"),
        "two segments": answer(adapter, ".".join(token.split(".")[:2])),
        "alg none": answer(adapter, rewrite_header(token, alg="none")),
        "alg ES256": answer(adapter, rewrite_header(token, alg="ES256")),
        "typ at+jwt": answer(adapter, rewrite_header(token, typ="at+jwt")),
        "kid removed": answer(adapter, rewrite_header(token, kid=None)),
    }
    expected = {"not-a-token": "REFUSED_MALFORMED", "two segments": "REFUSED_MALFORMED",
                "alg none": "REFUSED_ALG_NOT_PERMITTED", "alg ES256": "REFUSED_ALG_NOT_PERMITTED",
                "typ at+jwt": "REFUSED_TYP_NOT_PROFILE_TYPE", "kid removed": "REFUSED_KID_MISSING"}
    row(11, "; ".join(f"{k}: {v}" for k, v in parts.items()), "PASS" if parts == expected else "FAIL")

    # row 12: a cache with no key and an endpoint that does not answer
    unavailable = unavailable_jwks_url or "https://no-such-team-for-ap3-row-12.cloudflareaccess.com/cdn-cgi/access/certs"
    unavailable_issuer = "https://no-such-team-for-ap3-row-12.cloudflareaccess.com"
    cold = JwksKeyCache(config(issuer=unavailable_issuer, jwks_url=unavailable,
                               production=not unavailable.startswith("http://")))
    obs = answer(JwtApproverIdentityAdapter(config(), clock=clock.datetime, keys=cold), token)
    row(12, obs, "PASS" if obs.startswith("IDENTITY_UNAVAILABLE") else "FAIL",
        "an exception, never an unauthenticated answer; the write gate turns it into REFUSED_IDENTITY_UNAVAILABLE")

    recorded = sorted(k["kid"] for k in record["evidence"].get("jwks_key_identifiers", []))
    if recorded and kids_now != recorded:
        row(13, f"KEY_SET_CHANGED since the record: now {kids_now}", "BLOCKED",
            "a rotation may have occurred; re-run the probe, re-record, and confirm a token under the new kid verifies")
    else:
        row(13, f"no rotation observed; published kids {kids_now}", "BLOCKED",
            "requires observing a Cloudflare rotation: a token under a kid absent from the cached set, accepted after one refresh")
    for n in (14, 15, 16):
        row(n, "in-process conformance evidence (tests/test_ap3_designation_conformance.py)", "IN_PROCESS",
            "AP3-D5: real adapter, real write gate, real directory, test-only authorizer")

    summary = {s: sum(1 for r in rows if r["status"] == s) for s in ("PASS", "FAIL", "BLOCKED", "IN_PROCESS")}
    return {
        "outcome": "LIVE_VERIFICATION",
        "verified_at": started.isoformat(),
        "adapter_version": __version__,
        "issuer_profile": CLOUDFLARE_ACCESS_PROFILE,
        "issuer": cfg["issuer"], "audience": cfg["audience"], "jwks_url": jwks,
        "jwks_kids_seen": kids_now,
        "capture": capture,
        "rows": rows,
        "summary": summary,
        "claims": "evidence for the owner to record; declares nothing MET; the token was neither printed nor retained",
    }


def emit(result: dict, token: str) -> str:
    text = json.dumps(result, indent=2)
    for segment in token.split("."):
        if segment and segment in text:
            raise SystemExit("refusing to print: a token segment reached the output")
    if TOKEN_SHAPE.search(text):
        raise SystemExit("refusing to print: something token-shaped reached the output")
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AP-3 live verification; never prints the token")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--app", help="the Access application URL; the token is obtained through cloudflared")
    source.add_argument("--token-stdin", action="store_true", help="read one token from standard input")
    parser.add_argument("--login", action="store_true", help="run cloudflared access login first, output filtered")
    parser.add_argument("--jwks-url", default=None, help="override the designated JWKS (loopback, harness only)")
    parser.add_argument("--unavailable-jwks-url", default=None, help="row 12 endpoint override (harness only)")
    args = parser.parse_args(argv)

    cfg, record = designation()
    if args.token_stdin:
        if sys.stdin.isatty():
            print(json.dumps({"outcome": "REFUSED", "reason": "pipe the token; never type or paste it"}), file=sys.stderr)
            return 2
        token, notes = sys.stdin.read().strip(), []
    else:
        token, notes = obtain_token(args.app, args.login)
    for line in notes:
        print(line, file=sys.stderr)
    if not token or not TOKEN_SHAPE.fullmatch(token):
        print(json.dumps({"outcome": "NO_TOKEN", "reason": "cloudflared did not hand over a token; run with --login"}))
        return 2
    try:
        result = verify(token, cfg, record, jwks_url=args.jwks_url, unavailable_jwks_url=args.unavailable_jwks_url)
    except Exception as exc:  # noqa: BLE001 - the message must not carry the token
        message = TOKEN_SHAPE.sub("<token suppressed>", str(exc))
        print(json.dumps({"outcome": "ERROR", "reason": type(exc).__name__, "message": message[:300]}))
        return 4
    print(emit(result, token))
    return 1 if result["summary"]["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())

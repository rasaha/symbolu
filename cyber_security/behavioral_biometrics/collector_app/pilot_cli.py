"""Researcher CLI for the instrumentation pilot. Machine-readable JSON output.
Never prints raw key content (there is none — keyboard is class-only).

    python -m cyber_security.behavioral_biometrics.collector_app.pilot_cli <cmd> [opts]

Commands: init · create-participant · start-session · list-sessions · quality ·
export · redact · delete · report · verify-integrity · serve · generate-demo · readiness
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

from cyber_security.behavioral_biometrics import (
    features,
    pilot,
    privacy,
    quality,
    storage,
    verdicts,
)
from cyber_security.behavioral_biometrics.collector_app import (
    fixtures,
    manifest,
    readiness,
    service,
)
from cyber_security.behavioral_biometrics.config import DEFAULT
from cyber_security.behavioral_biometrics.version import ORIGIN_DEMO, ORIGIN_REAL


def _out(obj: Any) -> int:
    print(json.dumps(obj, indent=2, default=str))
    return 0


def _store(args) -> storage.SessionStore:
    return storage.SessionStore(Path(args.root), passphrase=getattr(args, "passphrase", None))


def _participants_path(args) -> Path:
    return Path(args.root) / "participants.json"


def _load_participants(args) -> Dict[str, Any]:
    p = _participants_path(args)
    return json.loads(p.read_text()) if p.exists() else {}


def _save_participants(args, data: Dict[str, Any]):
    Path(args.root).mkdir(parents=True, exist_ok=True)
    _participants_path(args).write_text(json.dumps(data, indent=2))


def _load_sessions(store) -> List[Dict[str, Any]]:
    return [store.load_session(s["participant"], s["session_id"]) for s in store.list_sessions()]


# ---- commands ----

def cmd_init(args) -> int:
    Path(args.root).mkdir(parents=True, exist_ok=True)
    (Path(args.root) / "pilot_config.json").write_text(json.dumps({
        "root": args.root, "origin_default": ORIGIN_REAL if args.real else ORIGIN_DEMO,
        "phase": "instrumentation_feasibility_pilot"}, indent=2))
    return _out({"initialized": True, "root": args.root, "readiness": readiness.check()["verdict"]})


def cmd_create_participant(args) -> int:
    data = _load_participants(args)
    salt = args.salt
    pseudo = privacy.pseudonym(args.label or uuid.uuid4().hex, salt)
    data[pseudo] = {"created": True, "device_instance_hint": "assigned in-browser (localStorage)",
                    "sessions_expected": args.sessions}
    _save_participants(args, data)
    origin = ORIGIN_REAL if args.real else ORIGIN_DEMO
    return _out({"participant_pseudonym": pseudo, "origin": origin,
                 "launch_url": f"http://127.0.0.1:{args.port}/?origin={'real' if args.real else 'demo'}"
                               f"&participant={pseudo}",
                 "note": "start the server (pilot serve), open the URL in a browser"})


def cmd_start_session(args) -> int:
    origin = ORIGIN_REAL if args.real else ORIGIN_DEMO
    return _out({"participant": args.participant, "task": args.task, "origin": origin,
                 "launch_url": f"http://127.0.0.1:{args.port}/?origin={'real' if args.real else 'demo'}"
                               f"&participant={args.participant}",
                 "instructions": "Open the URL, confirm consent, run calibration, complete the "
                                 "task. The session is stored on completion."})


def cmd_list_sessions(args) -> int:
    store = _store(args)
    rows = []
    for s in store.list_sessions():
        q = store.load_quality(s["participant"], s["session_id"]) if _has(store, s, "quality.json") else {}
        man = store.load_manifest(s["participant"], s["session_id"]) if store.has_manifest(
            s["participant"], s["session_id"]) else {}
        rows.append({"participant": s["participant"], "session_id": s["session_id"],
                     "origin": man.get("data_origin"), "quality": q.get("verdict"),
                     "has_manifest": bool(man)})
    return _out({"sessions": rows})


def cmd_quality(args) -> int:
    store = _store(args)
    targets = ([{"participant": args.participant, "session_id": args.session}]
               if args.participant and args.session else store.list_sessions())
    out = []
    for s in targets:
        sess = store.load_session(s["participant"], s["session_id"])
        q = quality.analyze(sess)
        q["participant"] = s["participant"]
        q["session_id"] = s["session_id"]
        store.save_quality(s["participant"], s["session_id"], q)
        out.append({k: q[k] for k in ("participant", "session_id", "verdict", "reasons")})
    return _out({"quality": out,
                 "cohort": verdicts.instrumentation_verdict(
                     [quality.analyze(store.load_session(s["participant"], s["session_id"]))
                      for s in store.list_sessions()])})


def cmd_export(args) -> int:
    store = _store(args)
    sess = store.load_session(args.participant, args.session)
    rec = features.extract(sess)
    bundle = {"session": sess, "features": rec,
              "quality": quality.analyze(sess),
              "manifest": store.load_manifest(args.participant, args.session)
              if store.has_manifest(args.participant, args.session) else None}
    outp = Path(args.out or f"{args.participant}_{args.session}_export.json")
    outp.write_text(json.dumps(bundle, indent=2, default=str))
    return _out({"exported": str(outp), "raw_content_leaks": privacy.find_raw_content_leaks(sess)})


def cmd_redact(args) -> int:
    store = _store(args)
    sess = store.load_session(args.participant, args.session)
    pol = privacy.PrivacyPolicy(suppressed_regions=set(args.region or []),
                                suppressed_screens=set(args.screen or []))
    red = privacy.redact_session(sess, pol)
    store.save_session(red)
    return _out({"redacted": True, "raw_content_leaks": privacy.find_raw_content_leaks(red)})


def cmd_delete(args) -> int:
    store = _store(args)
    return _out({"deleted": store.delete_session(args.participant, args.session)})


def cmd_verify_integrity(args) -> int:
    store = _store(args)
    targets = ([{"participant": args.participant, "session_id": args.session}]
               if args.participant and args.session else store.list_sessions())
    out = []
    for s in targets:
        if not store.has_manifest(s["participant"], s["session_id"]):
            out.append({"session_id": s["session_id"], "intact": None, "reason": "no_manifest"})
            continue
        sess = store.load_session(s["participant"], s["session_id"])
        man = store.load_manifest(s["participant"], s["session_id"])
        v = manifest.verify(sess, man)
        out.append({"session_id": s["session_id"], "intact": v["intact"], "problems": v["problems"]})
    return _out({"integrity": out})


def cmd_report(args) -> int:
    store = _store(args)
    sessions = _load_sessions(store)
    if not sessions:
        return _out({"error": "no sessions; run 'generate-demo' or collect real sessions"})
    report = pilot.run_pilot(sessions, DEFAULT)
    origins = sorted({s["session_meta"].get("data_origin") for s in sessions})
    # explicit verdict locks for this instrumentation phase
    recs = [features.extract(s) for s in sessions]
    locks = _verdict_locks(recs, report, origins)
    return _out({"collection_quality": {
        "instrumentation_verdict": report["instrumentation_verdict"],
        "n_sessions": report["n_sessions"], "excluded_sessions": report["excluded_sessions"],
        "A_instrument_quality": report["A_instrument_quality"]},
        "data_origins": origins,
        "identity_and_coupling_LOCKED": locks,
        "marginal_signal_verdict": report["marginal_signal_verdict"]["verdict"],
        "coupling_verdict": report["coupling_verdict"]["verdict"],
        "collector_readiness": readiness.check()["verdict"]})


def _verdict_locks(recs, report, origins) -> Dict[str, Any]:
    reasons = []
    if any(o != ORIGIN_REAL for o in origins):
        reasons.append("non_real_origin_present (SYNTHETIC/DEMO cannot yield a biometric verdict)")
    mins = report.get("minimums", {})
    if not mins.get("met", False):
        reasons.append("minimum_sample_requirements_not_met")
    if report["instrumentation_verdict"]["verdict"] != quality.READY:
        reasons.append("cohort_instrumentation_not_ready")
    # same-task impostor presence
    has_impostor = any(r["meta"].get("condition") == "live_impostor" for r in recs)
    if not has_impostor:
        reasons.append("no_same_task_live_impostor_trials")
    return {"locked": bool(reasons), "reasons": reasons}


def cmd_serve(args) -> int:
    from cyber_security.behavioral_biometrics.collector_app import server
    srv = server.build_server(args.root, args.host, args.port, args.salt)
    print(json.dumps({"listening": f"http://{args.host}:{args.port}", "root": args.root}))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


def cmd_generate_demo(args) -> int:
    store = _store(args)
    n = 0
    for i in range(args.sessions):
        batch = fixtures.sample_browser_session(participant=f"demo_p{i % max(1, args.participants)}",
                                                session_id=f"demo_s{i}", origin=ORIGIN_DEMO)
        res = service.ingest_browser_session(store, batch)
        n += 1 if res.get("ok") else 0
    return _out({"generated_demo_sessions": n, "origin": ORIGIN_DEMO,
                 "note": "DEMO_ONLY — exercises the workflow; no biometric verdict possible"})


def cmd_readiness(args) -> int:
    return _out(readiness.check())


def _has(store, s, name):
    return (Path(s["path"]) / name).exists()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pilot")
    p.add_argument("--root", default="/tmp/bbio-pilot")
    p.add_argument("--salt", default="pilot-salt")
    p.add_argument("--port", type=int, default=8791)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--passphrase", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init"); sp.add_argument("--real", action="store_true")
    sp = sub.add_parser("create-participant")
    sp.add_argument("--label", default=None); sp.add_argument("--sessions", type=int, default=2)
    sp.add_argument("--real", action="store_true")
    sp = sub.add_parser("start-session")
    sp.add_argument("--participant", required=True); sp.add_argument("--task", default="mixed_workflow")
    sp.add_argument("--real", action="store_true")
    sub.add_parser("list-sessions")
    sp = sub.add_parser("quality")
    sp.add_argument("--participant", default=None); sp.add_argument("--session", default=None)
    sp = sub.add_parser("export")
    sp.add_argument("--participant", required=True); sp.add_argument("--session", required=True)
    sp.add_argument("--out", default=None)
    sp = sub.add_parser("redact")
    sp.add_argument("--participant", required=True); sp.add_argument("--session", required=True)
    sp.add_argument("--region", action="append"); sp.add_argument("--screen", action="append")
    sp = sub.add_parser("delete")
    sp.add_argument("--participant", required=True); sp.add_argument("--session", required=True)
    sp = sub.add_parser("verify-integrity")
    sp.add_argument("--participant", default=None); sp.add_argument("--session", default=None)
    sub.add_parser("report")
    sub.add_parser("serve")
    sp = sub.add_parser("generate-demo")
    sp.add_argument("--sessions", type=int, default=6); sp.add_argument("--participants", type=int, default=3)
    sub.add_parser("readiness")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {
        "init": cmd_init, "create-participant": cmd_create_participant,
        "start-session": cmd_start_session, "list-sessions": cmd_list_sessions,
        "quality": cmd_quality, "export": cmd_export, "redact": cmd_redact,
        "delete": cmd_delete, "verify-integrity": cmd_verify_integrity, "report": cmd_report,
        "serve": cmd_serve, "generate-demo": cmd_generate_demo, "readiness": cmd_readiness}
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

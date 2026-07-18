"""Researcher CLI. Machine-readable JSON output. Never prints raw input (keyboard is
class-only by construction).

    python -m cyber_security.behavioral_biometrics.cli <command> [options]

Commands:
    collector status|redact|delete-session
    tasks list|run
    quality analyze
    features extract
    splits create
    baseline train|evaluate
    pilot report
    synthetic generate-test-fixtures
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from cyber_security.behavioral_biometrics import (
    analysis,
    baselines,
    features,
    pilot,
    privacy,
    quality,
    splits,
    storage,
    synthetic,
    tasks,
    verdicts,
)
from cyber_security.behavioral_biometrics.config import DEFAULT


def _out(obj: Any) -> int:
    print(json.dumps(obj, indent=2, default=lambda o: getattr(o, "__dict__", str(o))))
    return 0


def _store(args) -> storage.SessionStore:
    return storage.SessionStore(Path(args.root), passphrase=args.passphrase)


def _load_sessions(store: storage.SessionStore) -> List[Dict[str, Any]]:
    return [store.load_session(s["participant"], s["session_id"]) for s in store.list_sessions()]


# ---- collector ----

def cmd_collector(args) -> int:
    store = _store(args)
    if args.sub == "status":
        return _out({"root": str(store.root), "sessions": store.list_sessions()})
    if args.sub == "redact":
        s = store.load_session(args.participant, args.session)
        pol = privacy.PrivacyPolicy(suppressed_regions=set(args.region or []),
                                    suppressed_screens=set(args.screen or []))
        red = privacy.redact_session(s, pol)
        store.save_session(red)
        return _out({"redacted": True, "participant": args.participant, "session": args.session,
                     "raw_leaks": privacy.find_raw_content_leaks(red)})
    if args.sub == "delete-session":
        ok = store.delete_session(args.participant, args.session)
        return _out({"deleted": ok})
    return _out({"error": "unknown collector subcommand"})


# ---- tasks ----

def cmd_tasks(args) -> int:
    if args.sub == "list":
        return _out(tasks.list_tasks())
    if args.sub == "run":
        s = tasks.run_synthetic_task(
            args.task, participant=args.participant, device=args.device,
            session_id=args.session or f"{args.participant}_{args.task}",
            trial_id=args.trial or f"{args.participant}_t", seed=args.seed,
            condition=args.condition, coupling_user_gain=args.coupling)
        store = _store(args)
        store.save_session(s)
        q = quality.analyze(s)
        return _out({"stored": True, "session_id": s["session_meta"]["session_id"],
                     "provenance": s["session_meta"]["data_provenance"],
                     "n_events": len(s["events"]), "instrumentation": q["verdict"]})
    return _out({"error": "unknown tasks subcommand"})


# ---- quality ----

def cmd_quality(args) -> int:
    store = _store(args)
    summaries = []
    for s in store.list_sessions():
        sess = store.load_session(s["participant"], s["session_id"])
        q = quality.analyze(sess)
        q["participant"] = s["participant"]
        q["session_id"] = s["session_id"]
        store.save_quality(s["participant"], s["session_id"], q)
        summaries.append({k: q[k] for k in ("participant", "session_id", "verdict", "reasons")})
    return _out({"cohort_verdict": verdicts.instrumentation_verdict(
        [quality.analyze(store.load_session(s["participant"], s["session_id"]))
         for s in store.list_sessions()]),
        "sessions": summaries})


# ---- features ----

def cmd_features(args) -> int:
    store = _store(args)
    n = 0
    for s in store.list_sessions():
        sess = store.load_session(s["participant"], s["session_id"])
        rec = features.extract(sess)
        store.save_features(s["participant"], s["session_id"], rec)
        n += 1
    return _out({"extracted": n, "extractor_version": rec["meta"]["extractor_version"] if n else None})


# ---- splits ----

def cmd_splits(args) -> int:
    store = _store(args)
    recs = [store.load_features(s["participant"], s["session_id"]) for s in store.list_sessions()]
    builder = {"session_disjoint": splits.session_disjoint,
               "live_impostor_only": splits.live_impostor_only,
               "task_disjoint": splits.task_disjoint,
               "device_instance": splits.device_instance,
               "participant_disjoint": splits.participant_disjoint}[args.type]
    plan = builder(recs)
    return _out({"split": plan.name, "leakage_violations": splits.check_leakage(plan, recs),
                 "n_enroll_participants": len(plan.enroll),
                 "n_test_rows": len(plan.labeled_test()), "notes": plan.notes})


# ---- baseline ----

def cmd_baseline(args) -> int:
    store = _store(args)
    recs = [store.load_features(s["participant"], s["session_id"]) for s in store.list_sessions()]
    plan = splits.session_disjoint(recs, seed=DEFAULT.master_seed)
    if args.sub == "train":
        leaks = splits.check_leakage(plan, recs)
        return _out({"trained_on_enroll_only": True, "leakage_violations": leaks,
                     "n_enroll_participants": len(plan.enroll)})
    if args.sub == "evaluate":
        res = analysis.marginal_identity(recs, plan, DEFAULT, model=args.model)
        return _out(res)
    return _out({"error": "unknown baseline subcommand"})


# ---- pilot ----

def cmd_pilot(args) -> int:
    store = _store(args)
    sessions = _load_sessions(store)
    if not sessions:
        return _out({"error": "no sessions in store; run 'tasks run' or "
                              "'synthetic generate-test-fixtures' first"})
    report = pilot.run_pilot(sessions, DEFAULT)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
    for line in pilot.summary_lines(report):
        print("# " + line, file=sys.stderr)
    return _out(report)


# ---- synthetic ----

def cmd_synthetic(args) -> int:
    coh = synthetic.generate_cohort(
        n_participants=args.participants, sessions_per=args.sessions,
        coupling_user_gain=args.coupling, coupling_task_gain=args.task_coupling,
        second_device=args.second_device)
    store = _store(args)
    for s in coh:
        store.save_session(s)
    return _out({"generated": len(coh), "marker": "SYNTHETIC_TEST_ONLY",
                 "root": str(store.root),
                 "note": "verdicts will refuse any identity/coupling claim from these"})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="behavioral_biometrics")
    p.add_argument("--root", default="/tmp/bbio-store", help="session store root")
    p.add_argument("--passphrase", default=None, help="at-rest encryption passphrase (optional)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collector")
    c.add_argument("sub", choices=["status", "redact", "delete-session"])
    c.add_argument("--participant")
    c.add_argument("--session")
    c.add_argument("--region", action="append")
    c.add_argument("--screen", action="append")

    t = sub.add_parser("tasks")
    t.add_argument("sub", choices=["list", "run"])
    t.add_argument("--task", default="mixed_workflow")
    t.add_argument("--participant", default="p_demo")
    t.add_argument("--device", default="dev_demo")
    t.add_argument("--session", default=None)
    t.add_argument("--trial", default=None)
    t.add_argument("--condition", default="genuine")
    t.add_argument("--seed", type=int, default=1)
    t.add_argument("--coupling", type=float, default=0.0)

    q = sub.add_parser("quality")
    q.add_argument("sub", nargs="?", default="analyze", choices=["analyze"])

    f = sub.add_parser("features")
    f.add_argument("sub", nargs="?", default="extract", choices=["extract"])

    s = sub.add_parser("splits")
    s.add_argument("sub", nargs="?", default="create", choices=["create"])
    s.add_argument("--type", default="session_disjoint",
                   choices=["session_disjoint", "live_impostor_only", "task_disjoint",
                            "device_instance", "participant_disjoint"])

    b = sub.add_parser("baseline")
    b.add_argument("sub", choices=["train", "evaluate"])
    b.add_argument("--model", default="prototype", choices=["prototype", "mahalanobis"])

    pl = sub.add_parser("pilot")
    pl.add_argument("sub", nargs="?", default="report", choices=["report"])
    pl.add_argument("--out", default=None)

    sy = sub.add_parser("synthetic")
    sy.add_argument("sub", nargs="?", default="generate-test-fixtures",
                    choices=["generate-test-fixtures"])
    sy.add_argument("--participants", type=int, default=12)
    sy.add_argument("--sessions", type=int, default=4)
    sy.add_argument("--coupling", type=float, default=0.0)
    sy.add_argument("--task-coupling", dest="task_coupling", type=float, default=0.0)
    sy.add_argument("--second-device", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {"collector": cmd_collector, "tasks": cmd_tasks, "quality": cmd_quality,
                "features": cmd_features, "splits": cmd_splits, "baseline": cmd_baseline,
                "pilot": cmd_pilot, "synthetic": cmd_synthetic}
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

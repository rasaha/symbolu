"""Leakage-safe split generation.

A split operates over a list of feature *records* (one per session). Splits are at
SESSION granularity and are session-disjoint by construction. Identifiers never enter
the model surface (features.vectorize excludes ``meta``); these split builders only
use ``meta`` to decide grouping and to attach ground-truth labels.

Split types:
  * session_disjoint       — enroll vs held-out genuine sessions of the same user;
                             impostors = live-impostor + zero-effort cross-user sessions.
  * live_impostor_only     — impostors restricted to same-task same-device live impostors.
  * task_disjoint          — enroll on one task, test on a different task (diagnostic).
  * device_instance        — enroll on device A, genuine test on device B (diagnostic).
  * participant_disjoint   — train users vs held-out users (a SEPARATE transfer claim).

``check_leakage`` verifies no session is shared between enroll and test for a user,
and (for participant_disjoint) that user sets are disjoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

GENUINE = ("genuine", "unspecified")


@dataclass
class SplitPlan:
    name: str
    enroll: Dict[str, List[int]] = field(default_factory=dict)          # pid -> record idxs
    genuine_test: Dict[str, List[int]] = field(default_factory=dict)
    impostor_test: Dict[str, List[int]] = field(default_factory=dict)
    train_participants: List[str] = field(default_factory=list)
    test_participants: List[str] = field(default_factory=list)
    notes: str = ""

    def all_train_indices(self) -> List[int]:
        out: List[int] = []
        for idxs in self.enroll.values():
            out.extend(idxs)
        return sorted(set(out))

    def labeled_test(self) -> List[Dict[str, Any]]:
        """Flat list of {pid, idx, label} for pooled scoring (1=genuine, 0=impostor)."""
        rows = []
        for pid, idxs in self.genuine_test.items():
            for i in idxs:
                rows.append({"pid": pid, "idx": i, "label": 1})
        for pid, idxs in self.impostor_test.items():
            for i in idxs:
                rows.append({"pid": pid, "idx": i, "label": 0})
        return rows


def _sid(rec) -> str:
    return rec["meta"]["session_id"]


def _pid(rec) -> str:
    return rec["meta"]["participant_pseudonym"]


def _by_participant(records) -> Dict[str, List[int]]:
    out: Dict[str, List[int]] = {}
    for i, r in enumerate(records):
        out.setdefault(_pid(r), []).append(i)
    return out


def session_disjoint(records: List[Dict[str, Any]], *, max_zero_effort: int = 4,
                     seed: int = 0) -> SplitPlan:
    plan = SplitPlan(name="session_disjoint")
    by_p = _by_participant(records)
    import numpy as np
    rng = np.random.default_rng(seed)
    for pid, idxs in by_p.items():
        genuine = [i for i in idxs if records[i]["meta"].get("condition") in GENUINE]
        impostor = [i for i in idxs if records[i]["meta"].get("condition") == "live_impostor"]
        if len(genuine) < 2:
            continue
        enroll = [i for i in genuine if records[i]["meta"].get("role") == "enrollment"]
        if not enroll:
            enroll = genuine[: max(1, len(genuine) // 2)]
        gtest = [i for i in genuine if i not in enroll]
        if not gtest:
            continue
        plan.enroll[pid] = enroll
        plan.genuine_test[pid] = gtest
        # impostors: same-task live impostors + zero-effort other-user genuine sessions
        zero = [j for other, jl in by_p.items() if other != pid for j in jl
                if records[j]["meta"].get("condition") in GENUINE]
        rng.shuffle(zero)
        plan.impostor_test[pid] = impostor + zero[:max_zero_effort]
    return plan


def live_impostor_only(records: List[Dict[str, Any]]) -> SplitPlan:
    base = session_disjoint(records)
    plan = SplitPlan(name="live_impostor_only", enroll=base.enroll,
                     genuine_test=base.genuine_test)
    for pid in base.enroll:
        plan.impostor_test[pid] = [i for i, r in enumerate(records)
                                   if _pid(r) == pid and r["meta"].get("condition") == "live_impostor"]
    return plan


def task_disjoint(records: List[Dict[str, Any]], *, enroll_task: Optional[str] = None) -> SplitPlan:
    plan = SplitPlan(name="task_disjoint")
    tasks = sorted({r["meta"].get("task_id", "") for r in records})
    if len(tasks) < 2:
        plan.notes = "insufficient_tasks"
        return plan
    et = enroll_task or tasks[0]
    for pid, idxs in _by_participant(records).items():
        genuine = [i for i in idxs if records[i]["meta"].get("condition") in GENUINE]
        enroll = [i for i in genuine if records[i]["meta"].get("task_id") == et]
        gtest = [i for i in genuine if records[i]["meta"].get("task_id") != et]
        if enroll and gtest:
            plan.enroll[pid] = enroll
            plan.genuine_test[pid] = gtest
    _add_zero_effort_impostors(records, plan)
    return plan


def device_instance(records: List[Dict[str, Any]]) -> SplitPlan:
    plan = SplitPlan(name="device_instance")
    for pid, idxs in _by_participant(records).items():
        genuine = [i for i in idxs if records[i]["meta"].get("condition") in GENUINE]
        devices = sorted({records[i]["meta"].get("device_id", "") for i in genuine})
        if len(devices) < 2:
            continue
        da = devices[0]
        enroll = [i for i in genuine if records[i]["meta"].get("device_id") == da]
        gtest = [i for i in genuine if records[i]["meta"].get("device_id") != da]
        if enroll and gtest:
            plan.enroll[pid] = enroll
            plan.genuine_test[pid] = gtest
    if not plan.enroll:
        plan.notes = "no_second_device"
    _add_zero_effort_impostors(records, plan)
    return plan


def participant_disjoint(records: List[Dict[str, Any]], *, train_frac: float = 0.6,
                         seed: int = 0) -> SplitPlan:
    import numpy as np
    rng = np.random.default_rng(seed)
    participants = sorted({_pid(r) for r in records})
    rng.shuffle(participants)
    n_train = max(1, int(len(participants) * train_frac))
    train_p = sorted(participants[:n_train])
    test_p = sorted(participants[n_train:])
    plan = SplitPlan(name="participant_disjoint", train_participants=train_p,
                     test_participants=test_p,
                     notes="SEPARATE transfer claim: train and test users are disjoint")
    # within the test users, an ordinary session-disjoint enroll/verify
    test_records = {i: r for i, r in enumerate(records) if _pid(r) in test_p}
    sub = session_disjoint([records[i] for i in sorted(test_records)])
    # remap sub indices back to original indexing
    order = sorted(test_records)
    remap = {j: order[j] for j in range(len(order))}
    plan.enroll = {p: [remap[i] for i in idxs] for p, idxs in sub.enroll.items()}
    plan.genuine_test = {p: [remap[i] for i in idxs] for p, idxs in sub.genuine_test.items()}
    plan.impostor_test = {p: [remap[i] for i in idxs] for p, idxs in sub.impostor_test.items()}
    return plan


def _add_zero_effort_impostors(records, plan, max_each: int = 4):
    for pid in list(plan.enroll):
        imp = [i for i, r in enumerate(records)
               if _pid(r) != pid and r["meta"].get("condition") in GENUINE]
        plan.impostor_test[pid] = imp[:max_each]


def check_leakage(plan: SplitPlan, records: List[Dict[str, Any]]) -> List[str]:
    """Return a list of leakage violations. Empty == leakage-safe."""
    problems: List[str] = []
    for pid in plan.enroll:
        enroll_sids = {_sid(records[i]) for i in plan.enroll[pid]}
        test_idx = plan.genuine_test.get(pid, []) + plan.impostor_test.get(pid, [])
        for i in test_idx:
            if _sid(records[i]) in enroll_sids:
                problems.append(f"{pid}: session {_sid(records[i])} in both enroll and test")
        # a genuine-test session must belong to the claimed identity
        for i in plan.genuine_test.get(pid, []):
            if _pid(records[i]) != pid:
                problems.append(f"{pid}: genuine_test idx {i} not this participant")
        # an impostor-test session must NOT be a genuine session of the claimed identity
        for i in plan.impostor_test.get(pid, []):
            r = records[i]
            if _pid(r) == pid and r["meta"].get("condition") in GENUINE:
                problems.append(f"{pid}: impostor_test idx {i} is a genuine session of the target")
    if plan.name == "participant_disjoint":
        overlap = set(plan.train_participants) & set(plan.test_participants)
        if overlap:
            problems.append(f"participant overlap: {sorted(overlap)}")
    return problems

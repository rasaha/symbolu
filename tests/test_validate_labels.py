"""CPU tests for validate_labels.py — the pre-flight label validator. Synthetic CSVs + a tiny keymap;
no traces, no evaluator run. No runtime change.
"""
import csv
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy")
from csr_match_filter import validate_labels as VL   # noqa: E402

_COLS = ["item_id", *VL.LABEL_FIELDS]


def _keymap(n):
    return {f"id{t}": {"source_id": f"s{t}", "arm": "base" if t % 2 else "framed",
                       "category": "x", "trace_index": t} for t in range(n)}


def _write(tmp, name, rows):
    p = tmp / name
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in _COLS})
    return str(p)


def _row(iid, rewrite, **kw):
    base = {"item_id": iid, "rewrite_needed": rewrite, "answer_acceptable": "no" if rewrite == "yes" else "yes",
            "clear_and_useful_1to5": 3, "factual_or_grounded_1to5": 4}
    base.update(kw)
    return base


# ---- clean file ----------------------------------------------------------------------------------
def test_clean_file_ok(tmp_path):
    km = _keymap(10)
    rows = [_row(f"id{t}", "yes" if t < 6 else "no") for t in range(10)]
    rep = VL.validate([_write(tmp_path, "a.csv", rows)], km, min_pos=5)
    assert rep["ok"] is True and rep["fatal"] == []
    assert rep["per_rater"][0]["n_rewrite_yes"] == 6
    assert rep["per_rater"][0]["n_rewrite_no"] == 4
    assert rep["ready_for_evaluation"] is True


# ---- fatal: unknown id ---------------------------------------------------------------------------
def test_unknown_item_id_is_fatal(tmp_path):
    km = _keymap(5)
    rows = [_row("id0", "yes"), _row("GHOST", "no")]
    rep = VL.validate([_write(tmp_path, "a.csv", rows)], km, min_pos=1)
    assert rep["ok"] is False
    assert any("not in keymap" in f for f in rep["fatal"])
    assert rep["per_rater"][0]["unknown_item_ids"] == ["GHOST"]


# ---- fatal: duplicate id -------------------------------------------------------------------------
def test_duplicate_item_id_is_fatal(tmp_path):
    km = _keymap(5)
    rows = [_row("id0", "yes"), _row("id0", "no")]
    rep = VL.validate([_write(tmp_path, "a.csv", rows)], km, min_pos=1)
    assert rep["ok"] is False
    assert any("duplicate" in f for f in rep["fatal"])
    assert rep["per_rater"][0]["duplicate_item_ids"] == ["id0"]


# ---- fatal: unparseable cell ---------------------------------------------------------------------
def test_unparseable_cell_is_fatal(tmp_path):
    km = _keymap(5)
    rows = [_row("id0", "maybe"), _row("id1", "yes", clear_and_useful_1to5=9)]
    rep = VL.validate([_write(tmp_path, "a.csv", rows)], km, min_pos=1)
    assert rep["ok"] is False
    assert any("unparseable" in f for f in rep["fatal"])
    pr = rep["per_rater"][0]
    assert "id0" in pr["unparseable_cells"] and "id1" in pr["unparseable_cells"]


# ---- warning: blank primary + partial coverage ---------------------------------------------------
def test_blank_primary_and_partial_coverage_warn(tmp_path):
    km = _keymap(10)
    rows = [_row("id0", ""), _row("id1", "yes")]        # blank primary, and only 2/10 labeled
    rep = VL.validate([_write(tmp_path, "a.csv", rows)], km, min_pos=1)
    assert rep["ok"] is True                            # not fatal
    assert rep["per_rater"][0]["blank_primary_label"] == ["id0"]
    assert any("unlabeled" in w for w in rep["warnings"])
    assert any("blank rewrite_needed" in w for w in rep["warnings"])


# ---- warning: low positive count -----------------------------------------------------------------
def test_low_power_warns(tmp_path):
    km = _keymap(30)
    rows = [_row(f"id{t}", "yes" if t < 3 else "no") for t in range(30)]
    rep = VL.validate([_write(tmp_path, "a.csv", rows)], km, min_pos=20)
    assert rep["ok"] is True
    assert any("SO_INSUFFICIENT_LABEL_POWER" in w for w in rep["warnings"])
    assert rep["ready_for_evaluation"] is False         # ok but not enough positives


# ---- two raters: kappa computed + low-agreement warning ------------------------------------------
def test_two_raters_kappa(tmp_path):
    km = _keymap(12)
    a = [_row(f"id{t}", "yes" if t < 6 else "no") for t in range(12)]
    b = [_row(f"id{t}", "yes" if t < 6 else "no") for t in range(12)]   # identical → κ=1
    rep = VL.validate([_write(tmp_path, "a.csv", a), _write(tmp_path, "b.csv", b)], km, min_pos=5)
    assert rep["n_raters"] == 2
    assert rep["agreement"]["overlap_n"] == 12
    assert rep["agreement"]["cohen_kappa"]["rewrite_needed"] == 1.0
    assert rep["ok"] is True


def test_two_raters_low_agreement_warns(tmp_path):
    km = _keymap(12)
    a = [_row(f"id{t}", "yes" if t % 2 == 0 else "no") for t in range(12)]
    b = [_row(f"id{t}", "no" if t % 2 == 0 else "yes") for t in range(12)]   # anti-correlated → κ<0
    rep = VL.validate([_write(tmp_path, "a.csv", a), _write(tmp_path, "b.csv", b)], km,
                      min_pos=5, kappa_min=0.4)
    assert any("SO_INSUFFICIENT_RATER_AGREEMENT" in w for w in rep["warnings"])


# ---- CLI exit code + report -----------------------------------------------------------------------
def test_main_exit_codes(tmp_path):
    import json
    km = _keymap(8)
    kmp = tmp_path / "km.json"
    kmp.write_text(json.dumps(km))
    good = _write(tmp_path, "good.csv", [_row(f"id{t}", "yes" if t < 5 else "no") for t in range(8)])
    bad = _write(tmp_path, "bad.csv", [_row("id0", "yes"), _row("NOPE", "no")])
    assert VL.main(["--labels", good, "--keymap", str(kmp), "--min-pos", "1"]) == 0
    assert VL.main(["--labels", bad, "--keymap", str(kmp), "--min-pos", "1"]) == 1

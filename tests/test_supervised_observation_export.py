"""CPU tests for the supervised-observation EXPORT packet (no evaluator, no runtime change).

Verifies the de-biasing contract from docs/CSR_SUPERVISED_OBSERVATION_PREREG.md: 220 rows, opaque ids,
no forbidden-field leakage, private keymap correctness, deterministic order, schema match, loud failures
on bad joins, JSONL round-trip, and CSV columns. Runs on the local stub trace + real eval-data (same
schema/ids as the pod's robustness_eval_v2.json) plus small synthetic dicts for the failure cases.
"""
import csv
import io
import json
import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

from csr_match_filter import export_supervised_observation_packet as EX   # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_TRACES = _ROOT / "runs" / "csr_phase2b" / "robustness_stub.json"
_EVAL = (_ROOT / "scripts" / "cg_wrapper_ablation" / "csr_match_filter" / "eval_data"
         / "framed_answer_eval_v2_rubricv2.jsonl")


def _load_real():
    data = json.load(open(_TRACES, encoding="utf-8"))
    backend = EX.select_backend(data)
    items = data["traces"][backend]
    prompts = EX.load_prompts(_EVAL)
    return items, prompts


def _synthetic(n=3, arms=("base", "framed")):
    items = [{"id": f"ord_{i:03d}", "category": "ordinary",
              "answers": {a: f"answer {i} {a}" for a in arms}} for i in range(n)]
    prompts = {f"ord_{i:03d}": f"prompt {i}?" for i in range(n)}
    return items, prompts


# ---- 1. row count --------------------------------------------------------------------------------
def test_row_count_220():
    items, prompts = _load_real()
    rows, keymap = EX.build_packet(items, prompts, seed=7)
    assert len(items) == 110
    assert len(rows) == 220 and len(keymap) == 220


# ---- 2. opaque ids unique + leak no source id / arm ----------------------------------------------
def test_opaque_ids_unique_and_opaque():
    items, prompts = _load_real()
    rows, keymap = EX.build_packet(items, prompts, seed=7)
    oids = [r["item_id"] for r in rows]
    assert len(set(oids)) == len(oids)                       # unique
    src_ids = {v["source_id"] for v in keymap.values()}
    for oid in oids:
        assert all(c in "0123456789abcdef" for c in oid)     # pure hex token
        assert oid not in src_ids                            # not a source id
        for s in src_ids:
            assert s not in oid
        assert "base" not in oid and "framed" not in oid


# ---- 3. no forbidden fields in public packet -----------------------------------------------------
def test_no_forbidden_fields_real():
    items, prompts = _load_real()
    rows, _ = EX.build_packet(items, prompts, seed=7)
    EX.assert_no_forbidden_fields(rows)   # would raise on any leak
    for r in rows:
        assert set(r) == set(EX.PUBLIC_ROW_KEYS)


def test_forbidden_leak_detected():
    items, prompts = _synthetic()
    rows, _ = EX.build_packet(items, prompts, seed=1)
    rows[0]["scores"] = {"primary_frame_correct": False}      # inject a leak -> hard fail
    with pytest.raises(AssertionError):
        EX.assert_no_forbidden_fields(rows)
    rows2, _ = EX.build_packet(items, prompts, seed=1)
    rows2[0]["human_labels"]["arm"] = "base"                  # nested leak -> hard fail
    with pytest.raises(AssertionError):
        EX.assert_no_forbidden_fields(rows2)


def test_scan_catches_nested_forbidden_key():
    # defense-in-depth: a forbidden key nested inside an otherwise-allowed value is still caught
    assert EX._scan_forbidden({"item_id": "x", "meta": {"arm": "base"}})
    assert EX._scan_forbidden({"a": [{"finding_types": []}]})
    assert EX._scan_forbidden({"item_id": "x", "prompt": "p", "answer": "a"}) == []


# ---- 4. private keymap carries source id + arm ---------------------------------------------------
def test_keymap_has_source_and_arm():
    items, prompts = _load_real()
    rows, keymap = EX.build_packet(items, prompts, seed=7)
    arms_seen, sids = set(), set()
    for oid, meta in keymap.items():
        assert set(meta) == {"source_id", "arm", "category", "trace_index"}
        assert meta["arm"] in ("base", "framed")
        arms_seen.add(meta["arm"])
        sids.add(meta["source_id"])
    assert arms_seen == {"base", "framed"}
    assert len(sids) == 110                                   # both arms map back to 110 source items
    # every public row resolves through the keymap
    assert {r["item_id"] for r in rows} == set(keymap)


# ---- 5. deterministic order with fixed seed ------------------------------------------------------
def test_deterministic_order():
    items, prompts = _load_real()
    a, ka = EX.build_packet(items, prompts, seed=42)
    b, kb = EX.build_packet(items, prompts, seed=42)
    assert [r["item_id"] for r in a] == [r["item_id"] for r in b]
    assert ka == kb
    c, _ = EX.build_packet(items, prompts, seed=43)
    assert [r["item_id"] for r in a] != [r["item_id"] for r in c]   # different seed -> different order/ids


# ---- 6. label schema matches pre-registration ----------------------------------------------------
def test_label_schema_exact():
    expected = {"rewrite_needed", "answer_acceptable", "primary_frame_correct", "rejected_domain_leak",
                "secondary_overpromoted", "generic_low_signal", "clear_and_useful_1to5",
                "factual_or_grounded_1to5", "overconfident_or_overstated", "frame_label_parroting",
                "needs_clarification", "short_reason"}
    assert set(EX.LABEL_FIELDS) == expected
    items, prompts = _synthetic()
    rows, _ = EX.build_packet(items, prompts, seed=1)
    for r in rows:
        assert set(r["human_labels"]) == expected
        assert all(v is None for v in r["human_labels"].values())


# ---- 7. missing prompt join fails loudly ---------------------------------------------------------
def test_missing_prompt_fails_loud():
    items, prompts = _synthetic()
    prompts.pop("ord_000")
    with pytest.raises(KeyError, match="no prompt join"):
        EX.build_packet(items, prompts, seed=1)


# ---- 8. missing/empty answer fails loudly --------------------------------------------------------
def test_missing_answer_fails_loud():
    items, prompts = _synthetic()
    del items[0]["answers"]["framed"]
    with pytest.raises(KeyError, match="missing answer for arm"):
        EX.build_packet(items, prompts, seed=1)
    items2, prompts2 = _synthetic()
    items2[0]["answers"]["base"] = "   "
    with pytest.raises(ValueError, match="empty/non-string answer"):
        EX.build_packet(items2, prompts2, seed=1)


# ---- 9. JSONL round-trips -------------------------------------------------------------------------
def test_jsonl_roundtrip(tmp_path):
    items, prompts = _load_real()
    rows, keymap = EX.build_packet(items, prompts, seed=7)
    packet, template, private = EX.write_outputs(rows, keymap, tmp_path)
    back = [json.loads(l) for l in open(packet, encoding="utf-8")]
    assert back == rows
    assert json.load(open(private, encoding="utf-8")) == keymap


# ---- 10. CSV template columns exact --------------------------------------------------------------
def test_csv_columns_exact(tmp_path):
    items, prompts = _synthetic()
    rows, keymap = EX.build_packet(items, prompts, seed=1)
    _, template, _ = EX.write_outputs(rows, keymap, tmp_path)
    with open(template, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        body = list(reader)
    assert header == list(EX.CSV_COLUMNS)
    assert header == ["item_id", *EX.LABEL_FIELDS]
    assert "prompt" not in header and "answer" not in header   # not duplicated into the CSV
    assert len(body) == len(rows)                              # one row per answer

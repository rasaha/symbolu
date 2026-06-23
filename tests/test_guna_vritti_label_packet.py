"""CPU tests for the de-biased Guna/Vritti human-labeling packet exporter.
Pre-reg: docs/CG_GUNA_VRITTI_HUMAN_LABELING_PREREG.md. No model, no training, no signal claim."""
import json
import sys
from pathlib import Path

import pytest

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation_training import export_guna_vritti_label_packet as EX   # noqa: E402


def _rows(n=6):
    # rows carry weak labels + source/metadata that MUST be stripped from rater rows
    return [{"id": f"src_{i}", "prompt": f"Question {i}?", "response": f"An answer number {i} here.",
             "labels": {"vritti": "pramana", "guna": [1, 0, 0, None, None, None]},
             "label_meta": {"source": "weak_heuristic"}, "metadata": {"model": "mistral"}}
            for i in range(n)]


def test_packet_debiased_no_forbidden_fields():
    public, keymap = EX.build_packet(_rows(8), seed=1)
    EX.assert_no_forbidden_fields(public)                    # would raise on any leak
    for r in public:
        assert set(r).issubset(set(EX.PUBLIC_ROW_KEYS))
        assert set(r["human_labels"]) == set(EX.LABEL_FIELDS)
        # no jargon/source/weak-label anywhere in the rater row
        blob = json.dumps(r).lower()
        for bad in ("guna", "vritti", "pramana", "sattva", "weak", "source", "model", "mistral", "labels\":"):
            assert bad not in blob or bad == "labels\":"      # only 'human_labels' allowed


def test_opaque_ids_and_keymap_holds_source_and_weak():
    public, keymap = EX.build_packet(_rows(6), seed=1)
    oids = [r["item_id"] for r in public]
    assert len(set(oids)) == len(oids)                       # unique
    src_ids = {v["source_id"] for v in keymap.values()}
    for o in oids:
        assert all(c in "0123456789abcdef" for c in o) and o not in src_ids
    # private keymap retains source + weak label (analyst-only, for later concordance)
    assert all("source_id" in v and "weak_label_for_concordance" in v for v in keymap.values())


def test_leak_detection_hard_fails():
    public, _ = EX.build_packet(_rows(3), seed=1)
    public[0]["labels"] = {"vritti": "pramana"}              # inject the construct
    with pytest.raises(AssertionError, match="FORBIDDEN FIELD LEAK|exceed allowed"):
        EX.assert_no_forbidden_fields(public)
    public2, _ = EX.build_packet(_rows(3), seed=1)
    public2[0]["human_labels"]["guna"] = 1                   # nested jargon key
    with pytest.raises(AssertionError):
        EX.assert_no_forbidden_fields(public2)


def test_missing_prompt_or_response_fails_loud():
    with pytest.raises(ValueError, match="missing/empty prompt"):
        EX.build_packet([{"id": "x", "prompt": "  ", "response": "ok answer here"}])
    with pytest.raises(ValueError, match="missing/empty response"):
        EX.build_packet([{"id": "x", "prompt": "ok?", "response": ""}])


def test_deterministic_shuffle():
    a, ka = EX.build_packet(_rows(8), seed=7)
    b, kb = EX.build_packet(_rows(8), seed=7)
    assert [r["item_id"] for r in a] == [r["item_id"] for r in b] and ka == kb
    c, _ = EX.build_packet(_rows(8), seed=8)
    assert [r["item_id"] for r in a] != [r["item_id"] for r in c]


def test_label_schema_matches_prereg():
    assert set(EX.LABEL_FIELDS) == {"response_kind", "clear_and_lucid", "energetic_actionable",
                                    "dull_confusing_lowsignal", "clarity_1to5", "short_reason"}
    assert set(EX.RESPONSE_KINDS) == {"grounded_factual", "factually_wrong", "speculative_imaginative",
                                      "evasive_nonanswer", "recall_of_context"}


def test_reference_passthrough_when_present():
    public, _ = EX.build_packet([{"id": "x", "prompt": "q?", "response": "an answer here ok",
                                  "reference": "ground truth note"}])
    assert public[0].get("reference") == "ground truth note"
    EX.assert_no_forbidden_fields(public)                    # 'reference' is allowed


def test_outputs_and_csv_columns(tmp_path):
    public, keymap = EX.build_packet(_rows(5), seed=1)
    packet, template, private = EX.write_outputs(public, keymap, tmp_path)
    back = [json.loads(l) for l in packet.read_text().splitlines()]
    assert back == public and json.loads(private.read_text()) == keymap
    import csv as _csv
    with open(template, newline="") as fh:
        header = next(_csv.reader(fh))
    assert header == list(EX.CSV_COLUMNS) and "prompt" not in header

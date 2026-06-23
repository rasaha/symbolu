"""CPU tests for the WEAK heuristic Guna/Vritti label deriver (torch-free, deterministic).
Pre-reg: docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md §5. No training, no GPU, no signal claim."""
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation_training import derive_weak_labels as D          # noqa: E402
from conscious_generation_training import surface_baseline as SB          # noqa: E402


# ---- Vritti routing -----------------------------------------------------------------------------
def test_vritti_nidra_on_refusal_or_empty():
    assert D.derive_vritti("q", "I don't know, I cannot help with that.") == "nidra"
    assert D.derive_vritti("q", "no.") == "nidra"                      # too short


def test_vritti_viparyaya_only_with_ground_truth():
    r = "The earth is flat and rests on a turtle for sure indeed."
    assert D.derive_vritti("q", r, false_claims=["earth is flat"], ground_truth_available=True) == "viparyaya"
    # without ground truth, cannot call it false -> not viparyaya
    assert D.derive_vritti("q", r) != "viparyaya"


def test_vritti_vikalpa_smriti_pramana():
    assert D.derive_vritti("q", "Imagine if a dragon could fly to the moon and back today.") == "vikalpa"
    assert D.derive_vritti("q", "As you mentioned earlier, the budget meeting was on Tuesday afternoon.") == "smriti"
    assert D.derive_vritti("q", "A doctor diagnoses and treats illness in patients with care.") == "pramana"


# ---- Guna multi-label ---------------------------------------------------------------------------
def test_guna_sattva_rajas_tamas_and_masked_dims():
    g_clear = D.derive_guna("q", "A doctor diagnoses and treats illness in patients with care.")
    assert g_clear[0] == 1 and g_clear[2] == 0                          # sattva, not tamas
    g_steps = D.derive_guna("q", "1. Book it.\n2. Bring records.\n3. Ask questions about the plan.")
    assert g_steps[1] == 1                                              # rajas (action/steps)
    g_hedge = D.derive_guna("q", "Well maybe perhaps it might possibly be unclear, i'm not sure really.")
    assert g_hedge[2] == 1                                              # tamas (hedge-heavy)
    for g in (g_clear, g_steps, g_hedge):
        assert g[3] is None and g[4] is None and g[5] is None           # dims 4-6 underdefined -> null


# ---- schema + provenance + honesty markers ------------------------------------------------------
def test_derive_row_schema_and_weak_marking():
    row = D.derive_row({"id": "x", "prompt": "What is a doctor?",
                        "response": "A doctor treats illness and keeps people healthy."})
    assert row["labels"]["vritti"] in ["pramana", "viparyaya", "vikalpa", "nidra", "smriti"]
    assert len(row["labels"]["guna"]) == 6 and row["labels"]["guna"][3] is None
    lm = row["label_meta"]
    assert lm["source"] == "weak_heuristic"
    assert "NEVER hidden states" in lm["derived_from"]
    assert "WARNING" in lm and "cannot validate" in lm["WARNING"]
    assert "bhava" not in str(row).lower()                             # Bhava not labelled


def test_deterministic():
    a = D.derive_row({"prompt": "p", "response": "Compare A and B; however the tradeoff is cost here."})
    b = D.derive_row({"prompt": "p", "response": "Compare A and B; however the tradeoff is cost here."})
    assert a == b


# ---- the honest point: weak labels ARE surface-derivable (guardrail confirms) -------------------
def test_weak_labels_are_surface_confounded_by_construction():
    # build varied prompt/response rows, derive weak labels, then run the surface baseline:
    # because the labels come from surface cues, the baseline should find them highly predictable.
    texts = [
        "I don't know, I cannot help.", "1. step one\n2. step two\n3. step three here",
        "Imagine if pigs could fly over the rainbow today.", "A cat is a small domesticated mammal kept as a pet.",
        "Well maybe perhaps it might be unclear, not sure.", "As you said earlier, the meeting was Tuesday.",
        "Run the script and then open the file to start.", "A doctor treats illness and helps patients heal.",
        "Suppose hypothetically the market crashed tomorrow morning.", "no.",
    ] * 4
    rows = [D.derive_row({"prompt": "q", "response": t}) for t in texts]
    rep = SB.surface_baseline(rows)
    # at least one weak label should be flagged surface-confounded (the whole point: they're not deep)
    assert rep["surface_confounded_labels"], "weak labels should be surface-confounded by construction"

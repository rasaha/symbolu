"""CPU tests for the optional Kosha depth/readiness inference layer (csr_match_filter/kosha.py).
Deterministic selector + byte-for-byte-unchanged-when-disabled prompt integration. No training,
no Guna/Vritti/Bhava, no model load.
"""
import sys
from pathlib import Path

_CSR = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_CSR) not in sys.path:
    sys.path.insert(0, str(_CSR))

from csr_match_filter import kosha as K          # noqa: E402
from csr_match_filter import prompts as P        # noqa: E402


def _lvl(q, **kw):
    return K.select_kosha_depth(q, **kw).level


# ---- 1. each level selectable -------------------------------------------------------------------
def test_each_level_selectable():
    assert _lvl("What is a doctor? Explain simply.") == K.KoshaLevel.ANNAMAYA
    assert _lvl("How do I prepare for a doctor appointment?") == K.KoshaLevel.PRANAMAYA
    assert _lvl("I am confused and worried about what the doctor said.") == K.KoshaLevel.MANOMAYA
    assert _lvl("Which is better, a generalist or specialist here?") == K.KoshaLevel.VIJNANAMAYA
    assert _lvl("Synthesize the deeper meaning of healing.") == K.KoshaLevel.ANANDAMAYA


# ---- 2. explicit simple / 5th grade forces ANNAMAYA ---------------------------------------------
def test_simple_forces_annamaya():
    # even with a reasoning cue present, an explicit simplicity request forces surface level
    assert _lvl("Compare these options but keep it simple.") == K.KoshaLevel.ANNAMAYA
    assert _lvl("Explain quantum computing for a 5th grade student.") == K.KoshaLevel.ANNAMAYA
    sel = K.select_kosha_depth("Explain simply please.")
    assert sel.features["source"] == "force_simple"


# ---- 3-6. cue routing ---------------------------------------------------------------------------
def test_pranamaya_cues():
    assert _lvl("Give me step by step instructions to configure nginx.") == K.KoshaLevel.PRANAMAYA
    assert _lvl("How to set up a backup checklist?") == K.KoshaLevel.PRANAMAYA


def test_manomaya_cues():
    assert _lvl("I am anxious and overwhelmed, can you reassure me?") == K.KoshaLevel.MANOMAYA


def test_vijnanamaya_cues():
    assert _lvl("Should I evaluate the tradeoffs and decide between A and B?") == K.KoshaLevel.VIJNANAMAYA
    assert _lvl("Compare the pros and cons of these designs.") == K.KoshaLevel.VIJNANAMAYA


def test_anandamaya_cues():
    assert _lvl("Synthesize the unifying principle and big picture.") == K.KoshaLevel.ANANDAMAYA


# ---- 7. high-stakes adds cautious wording -------------------------------------------------------
def test_high_stakes_adds_caution():
    sel = K.select_kosha_depth("Should I increase my medication dosage to treat this symptom?")
    assert sel.features["high_stakes"] is True
    assert "Be cautious" in sel.prompt_modifier and "factual grounding" in sel.prompt_modifier
    # a high-stakes 'simple' request is NOT force-downgraded to surface (safety precedence)
    assert K.select_kosha_depth("Explain my legal lawsuit options simply.").features["source"] != "force_simple"


# ---- 8. disabled leaves the framed prompt byte-for-byte unchanged --------------------------------
def test_disabled_prompt_unchanged():
    base = P.build_framed_prompt("q?", ["medicine"], ["care"], ["finance"], ex_id="x1")
    with_none = P.build_framed_prompt("q?", ["medicine"], ["care"], ["finance"], ex_id="x1", kosha=None)
    assert base == with_none
    assert "Depth/readiness instruction" not in base


# ---- 9. enabled inserts the modifier AFTER the frame instructions, BEFORE the user question ------
def test_enabled_inserts_modifier_in_order():
    sel = K.select_kosha_depth("Compare A and B and explain tradeoffs.")
    p = P.build_framed_prompt("Compare A and B?", ["technology"], [], [], kosha=sel)
    assert "Depth/readiness instruction:" in p
    i_instr = p.index("5. Preserve factual correctness.")
    i_depth = p.index("Depth/readiness instruction:")
    i_user = p.index("User question:")
    assert i_instr < i_depth < i_user                       # ordering preserved
    assert sel.prompt_modifier in p


# ---- 10. trace fields ---------------------------------------------------------------------------
def test_trace_enabled_and_disabled():
    sel = K.select_kosha_depth("Compare A and B.")
    en = K.kosha_trace(sel, enabled=True)
    assert en["enabled"] is True and en["level"] == "vijnanamaya" and "features" in en
    assert K.kosha_trace(sel, enabled=False) == {"enabled": False}
    assert K.kosha_trace(None, enabled=True) == {"enabled": False}


# ---- 11. no Guna/Vritti/Bhava fields ------------------------------------------------------------
def test_no_forbidden_fields():
    sel = K.select_kosha_depth("Compare A and B.")
    blob = repr(sel) + repr(K.kosha_trace(sel, enabled=True))
    for bad in ("guna", "vritti", "bhava", "kosha_state", "hidden"):
        assert bad not in blob.lower() or bad == "kosha_state" and False  # none present
    for bad in ("guna", "vritti", "bhava"):
        assert bad not in blob.lower()


# ---- default fallback is deterministic ----------------------------------------------------------
def test_default_when_no_cue():
    sel = K.select_kosha_depth("The doctor walked into the room.")
    assert sel.level == K.KoshaLevel.ANNAMAYA and sel.features["source"] == "default"
    assert sel.confidence == 0.4

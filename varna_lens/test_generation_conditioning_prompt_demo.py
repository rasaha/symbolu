"""Tests for the generation-conditioning PROMPT demo — NO MODEL, NO GENERATION, NO SCORING, NO NETWORK.

Hermetic: patches the g2p function so no nltk/cmudict is needed. Proves: no ML libs; all six arms
A/R/S/C/X/D printed; identical wrapper across arms; required banner present; no forbidden ontology/
Sanskrit/semantic-truth claims; no generated-answer field; dictionary-only arm is clearly separate
from the real resonance arm; no result files written.

    python3 varna_lens/test_generation_conditioning_prompt_demo.py
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                               # noqa: E402  (g2p lives here)
import sample_text_rule_harness as H                 # noqa: E402
import generation_conditioning_prompt_demo as G      # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


_FAKE = {
    "love": ([("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")], []),
    "mercy": ([("C", "ma", "M"), ("V", "a", "ER1"), ("C", "sa", "S"), ("V", "ii", "IY0")], []),
}


def _fake_cmudict(word):
    return _FAKE.get(word.lower(), ([], [f"'{word}' not in cmudict"]))


def _with_fake(fn):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake_cmudict            # harness g2p_units() calls V.phonemes_cmudict
    try:
        return fn()
    finally:
        V.phonemes_cmudict = orig


def test_all_six_arms_built():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    _check("all six arms A/R/S/C/X/D present", set(prompts) == set(G.ARMS))


def test_identical_wrapper_across_arms():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    for arm, p in prompts.items():
        _check(f"arm {arm} starts with wrapper header",
               p.startswith("[soft orientation — does not override the task]\n"))
        _check(f"arm {arm} ends with the same Task block", p.endswith("Task:\nWrite about love."))


def test_only_conditioning_slot_differs():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    # strip the shared wrapper head + task tail -> the middle (conditioning) must differ across arms
    mids = {arm: p.split("\n\nTask:\n")[0] for arm, p in prompts.items()}
    _check("conditioning texts differ across arms", len(set(mids.values())) == len(G.ARMS))


def test_banner_present():
    out = _with_fake(lambda: G.render_demo("Write about love.", "love"))
    _check("banner present (top + bottom)", out.count(G.BANNER) >= 2)


def test_no_forbidden_claims():
    for kw in ("love", "mercy"):
        out = _with_fake(lambda kw=kw: G.render_demo("Write about it.", kw)).lower()
        for bad in G.FORBIDDEN_CLAIMS:
            _check(f"{kw}: no forbidden claim {bad!r}", bad not in out)


def test_no_generated_answer_field():
    out = _with_fake(lambda: G.render_demo("Write about love.", "love")).lower()
    for tok in ("answer:", "response:", "generated text:", "completion:", "assistant:"):
        _check(f"no generated-answer marker {tok!r}", tok not in out)
    _check("explicit no-generation confirmation present", "no_generated_answer_produced: true" in out)


def test_dictionary_arm_distinct_from_resonance():
    prompts = _with_fake(lambda: G.build_prompts("Write about love.", "love"))
    _check("D arm marked dictionary/synonym field", "Dictionary/synonym field" in prompts["D"])
    _check("D arm says NOT resonance", "not resonance" in prompts["D"])
    _check("A arm is a latent-process reading", "latent-process reading" in prompts["A"])
    _check("A and D differ", prompts["A"] != prompts["D"])


def test_g2p_unavailable_arms_marked_not_crash():
    # 'zznotword' is not in the fake dict -> g2p empty -> A/S/C marked unavailable; R/X/D still built
    prompts = _with_fake(lambda: G.build_prompts("Write.", "zznotword"))
    _check("arm A marked G2P_UNAVAILABLE", "G2P_UNAVAILABLE" in prompts["A"])
    _check("arm X still constructed", "no additional symbolic orientation" in prompts["X"])
    _check("arm D still constructed (frozen table fallback)", "Dictionary/synonym field" in prompts["D"])


def test_no_result_files_written(tmp=pathlib.Path(HERE)):
    before = set(p.name for p in tmp.iterdir())
    _with_fake(lambda: G.render_demo("Write about mercy.", "mercy"))
    after = set(p.name for p in tmp.iterdir())
    _check("demo writes no files", before == after)


def test_no_ml_libs_imported():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def main():
    print("generation_conditioning_prompt_demo — prompt-construction tests (no model, no generation)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll generation-conditioning prompt-demo tests passed.")


if __name__ == "__main__":
    main()

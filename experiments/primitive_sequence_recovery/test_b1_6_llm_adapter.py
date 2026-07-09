"""Tests for the B1.6 local LLM adapter. Uses ONLY the deterministic FakeAdapter — NO model,
NO external API call. Real backends are never instantiated here."""
import pytest
import b1_6_llm_adapter as A


def _well_formed():
    return A.FakeAdapter().generate("some prompt")


# ---- output-format validation --------------------------------------------------------
def test_fake_wellformed_validates():
    ok, reasons = A.validate_output_format(_well_formed())
    assert ok, reasons


def test_fake_malformed_fails_validation():
    ok, reasons = A.validate_output_format(A.FakeAdapter(malformed=True).generate("p"))
    assert not ok and reasons


def test_missing_section_detected():
    ok, reasons = A.validate_output_format("Title: x\nInterpretation: a b c\nCaution: y")
    assert not ok and any("Practical reflection" in r for r in reasons)


def test_out_of_order_detected():
    txt = "Interpretation: a\nTitle: x\nPractical reflection:\n- a\nCaution: y"
    ok, reasons = A.validate_output_format(txt)
    assert not ok


def test_empty_output_rejected():
    ok, reasons = A.validate_output_format("")
    assert not ok


# ---- retry + validation --------------------------------------------------------------
def test_retry_returns_ok_for_wellformed():
    text, status, reasons = A.generate_with_retry(A.FakeAdapter(), "p",
                                                  A.GenerationSettings(max_attempts=2), sleep=lambda s: None)
    assert status == "ok" and text and not reasons


def test_retry_format_invalid_after_attempts_no_edit():
    text, status, reasons = A.generate_with_retry(A.FakeAdapter(malformed=True), "p",
                                                  A.GenerationSettings(max_attempts=3), sleep=lambda s: None)
    assert status == "format_invalid" and text is None and reasons  # never edited to "fix" it


def test_retry_on_exception_then_error():
    class Boom:
        backend = "boom"
        def generate(self, prompt, settings=None):
            raise RuntimeError("backend down")
    text, status, reasons = A.generate_with_retry(Boom(), "p",
                                                  A.GenerationSettings(max_attempts=2), sleep=lambda s: None)
    assert text is None and status == "error" and any("RuntimeError" in r for r in reasons)


def test_no_validation_returns_raw():
    text, status, _ = A.generate_with_retry(A.FakeAdapter(malformed=True), "p",
                                            A.GenerationSettings(max_attempts=1), validate=False,
                                            sleep=lambda s: None)
    assert status == "ok" and text is not None


# ---- backend readiness / settings ----------------------------------------------------
def test_backend_readiness_no_network():
    r = A.model_backend_readiness()
    assert "cuda_available" in r and "transformers_version" in r and "note" in r
    assert isinstance(r["cuda_available"], bool)


def test_settings_metadata_excludes_base_url():
    s = A.GenerationSettings(model_id="m", base_url="http://localhost:8000", temperature=0.5)
    md = s.metadata()
    assert "base_url" not in md and md["model_id"] == "m" and md["temperature"] == 0.5


def test_build_adapter_fake():
    a = A.build_adapter(A.GenerationSettings(backend="fake"))
    assert isinstance(a, A.FakeAdapter) and a.is_real is False


def test_build_adapter_unknown_backend():
    with pytest.raises(ValueError):
        A.build_adapter(A.GenerationSettings(backend="nope"))


def test_openai_compat_requires_base_url():
    with pytest.raises(ValueError):
        A.OpenAICompatLocalAdapter(A.GenerationSettings(backend="openai_compat_local"))

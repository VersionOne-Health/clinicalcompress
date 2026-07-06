"""Tests for the deterministic compression layer."""

import sys
import types

from clinicalcompress.compress import compress_deterministic, compress_llm
from clinicalcompress.protect import protect
from tests.fixtures import CLEAN_NOTE, REDUNDANT_NOTE


def test_protected_spans_never_altered():
    spans = protect(CLEAN_NOTE)
    compressed, _trace = compress_deterministic(CLEAN_NOTE, spans, target_reduction=0.3)
    for span in spans:
        assert span.text in compressed, f"Protected span '{span.text}' was altered or dropped"


def test_duplicate_sentences_removed():
    spans = protect(REDUNDANT_NOTE)
    compressed, trace = compress_deterministic(REDUNDANT_NOTE, spans, target_reduction=0.2)
    assert compressed.count("Patient came in today") <= 1 or len(trace.removed_duplicate_sentences) > 0


def test_filler_phrases_removed():
    text = "As previously discussed, patient will continue lisinopril 10 mg daily."
    spans = protect(text)
    compressed, trace = compress_deterministic(text, spans, target_reduction=0.2)
    assert "as previously discussed" not in compressed.lower()
    assert "10 mg" in compressed


def test_reduction_achieved_on_redundant_text():
    spans = protect(REDUNDANT_NOTE)
    compressed, _trace = compress_deterministic(REDUNDANT_NOTE, spans, target_reduction=0.3)
    assert len(compressed) < len(REDUNDANT_NOTE)


def test_dense_single_encounter_note_still_compresses():
    """Regression test: a dense note where every sentence carries some
    protected span (so no whole sentence/phrase can be dropped) must still
    achieve non-zero reduction via filler/connector-word trimming, not
    silently return the input unchanged."""
    text = (
        "57M with history of HTN and T2DM. Denies chest pain, shortness of "
        "breath, or fever. No known drug allergies except penicillin. "
        "BP 120/80. Left knee pain. Continue lisinopril 10 mg daily."
    )
    spans = protect(text)
    compressed, trace = compress_deterministic(text, spans, target_reduction=0.7)

    assert compressed != text
    assert len(compressed) < len(text)
    assert trace.removed_filler_words
    for span in spans:
        assert span.text in compressed, f"Protected span '{span.text}' was altered or dropped"


def test_sentence_pruning_never_drops_a_value_after_earlier_mutation():
    """Regression test: on a longer note, filler-word removal shrinks
    `working` before sentence-level pruning runs. If sentence pruning
    checks overlap using stale offsets (computed against the original,
    unmutated text) instead of re-detecting spans on the current
    `working` text, it can misjudge a sentence that genuinely contains a
    protected value as droppable and silently discard it -- which then
    fails `values_intact` in verify() and, under strict mode, wipes out
    the entire compression gain. This must never happen."""
    text = (
        "Emergency Department admission note for an elderly patient with "
        "multiple chronic conditions including COPD, heart failure, and "
        "diabetes who presented after several days of worsening symptoms "
        "at home despite following the usual home care routine carefully. "
        "The patient normally ambulates independently with a walker but "
        "today required assistance to get out of bed. Home pulse oximetry "
        "reportedly showed oxygen saturations between 82% and 86% despite "
        "her baseline oxygen therapy at home. She denies chest pain but "
        "reports chest tightness associated with coughing today. No "
        "hemoptysis. No recent travel. Mild bilateral lower extremity "
        "swelling has increased over the past week at home."
    )
    spans = protect(text)
    value_spans = [s for s in spans if s.category.value == "value"]
    assert value_spans, "fixture must contain at least one detected value span"

    compressed, _trace = compress_deterministic(text, spans, target_reduction=0.7)

    for span in value_spans:
        assert span.text in compressed, (
            f"Protected value '{span.text}' was dropped by sentence-level "
            "pruning due to stale offsets"
        )
    assert compressed != text
    assert len(compressed) < len(text)


def test_filler_words_removed_outside_protected_spans():
    text = "Patient presented with a history of HTN and T2DM."
    spans = protect(text)
    compressed, trace = compress_deterministic(text, spans, target_reduction=0.2)
    assert "with" not in compressed.lower().split()
    assert "history of" in compressed
    assert "HTN" in compressed and "T2DM" in compressed
    assert trace.removed_filler_words


def test_never_splits_a_protected_span():
    text = "Patient has BP 120/80 and denies chest pain and shortness of breath today only."
    spans = protect(text)
    compressed, _trace = compress_deterministic(text, spans, target_reduction=0.6)
    for span in spans:
        assert span.text in compressed


class _FakeAnthropicClient:
    """A stand-in for anthropic.Anthropic that records every prompt it is
    sent, so tests can assert protected clinical content was never
    forwarded to the (fake) LLM."""

    def __init__(self, api_key=None):
        self.sent_prompts: list[str] = []
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, model, max_tokens, messages):
        prompt = messages[0]["content"]
        self.sent_prompts.append(prompt)
        fragment = prompt.rsplit("\n\n", 1)[-1]
        shortened = fragment.strip().split(".")[0].strip()
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=shortened or fragment)])


def test_compress_llm_never_sends_protected_content(monkeypatch):
    """Regression test: `compress_llm` must be called with spans whose
    offsets are valid for the text it is actually segmenting (i.e. spans
    re-derived against post-deterministic-compression text, not stale
    offsets from the original). If offsets were stale, protected text
    could end up in an "unprotected" segment and get sent to the LLM."""
    fake_module = types.ModuleType("anthropic")
    created_clients: list[_FakeAnthropicClient] = []

    def _fake_anthropic_factory(api_key=None):
        client = _FakeAnthropicClient(api_key=api_key)
        created_clients.append(client)
        return client

    fake_module.Anthropic = _fake_anthropic_factory
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    text = (
        "As previously discussed, patient came in today. "
        "Patient denies chest pain, shortness of breath, or fever. "
        "No history of MI. BP 120/80, HR 76 bpm. "
        "Allergic to penicillin. Left knee pain, stable."
    )
    original_spans = protect(text)
    compressed_text, _trace = compress_deterministic(text, original_spans, target_reduction=0.3)
    assert compressed_text != text

    llm_spans = protect(compressed_text)
    result_text, used_llm = compress_llm(compressed_text, llm_spans, {"api_key": "fake-key"})

    assert used_llm is True
    assert created_clients, "expected the fake Anthropic client to be constructed"
    sent_prompts = created_clients[0].sent_prompts

    for span in llm_spans:
        for prompt in sent_prompts:
            assert span.text not in prompt, (
                f"Protected span '{span.text}' leaked into an LLM prompt — "
                "offsets used for segmentation must be valid for the text "
                "being segmented."
            )

    for span in llm_spans:
        assert span.text in result_text, f"Protected span '{span.text}' missing from LLM-compressed output"

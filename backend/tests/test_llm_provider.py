import pytest
from pydantic import BaseModel

from agent import llm, settings


class Probe(BaseModel):
    answer: str


def configure(monkeypatch, openai=False, openrouter=False):
    monkeypatch.setattr(settings, "OPENAI_CONFIGURED", openai)
    monkeypatch.setattr(settings, "OPENROUTER_CONFIGURED", openrouter)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-test-key")


def fallback_count(runnable):
    return len(getattr(runnable, "fallbacks", ()) or ())


def test_openai_leads_and_openrouter_backs_it_up(monkeypatch):
    configure(monkeypatch, openai=True, openrouter=True)

    assert llm.provider_chain_description() == "openai, falling back to openrouter"
    assert fallback_count(llm.get_llm()) == 1


def test_openrouter_serves_alone_when_the_openai_key_is_missing(monkeypatch):
    configure(monkeypatch, openai=False, openrouter=True)

    assert llm.provider_chain_description() == "openrouter (no fallback configured)"
    assert llm.get_llm().model_name == settings.OPENROUTER_MODEL


def test_no_configured_provider_fails_loudly(monkeypatch):
    configure(monkeypatch, openai=False, openrouter=False)

    with pytest.raises(llm.NoModelConfigured):
        llm.get_llm()


def test_structured_output_degrades_to_function_calling_per_provider(monkeypatch):
    configure(monkeypatch, openai=True, openrouter=True)

    assert fallback_count(llm.get_structured_llm(Probe)) == 3


def test_temperature_is_omitted_when_the_model_rejects_it(monkeypatch):
    configure(monkeypatch, openai=False, openrouter=True)
    monkeypatch.setattr(settings, "MODEL_TEMPERATURE", "")

    assert llm.default_temperature() is None
    assert llm.temperature_kwargs(None) == {}

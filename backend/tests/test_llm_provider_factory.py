from app.core.config import get_settings
from app.intent.llm_parser import GroqClient, build_llm_parser


def test_build_llm_parser_uses_groq_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GROQ_MODEL", "llama-test")
    get_settings.cache_clear()

    try:
        parser = build_llm_parser()
        assert parser is not None
        assert isinstance(parser.client, GroqClient)
        assert parser.client.api_key == "gsk-test"
        assert parser.client.model == "llama-test"
    finally:
        get_settings.cache_clear()

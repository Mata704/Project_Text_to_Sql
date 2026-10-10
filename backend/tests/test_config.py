from text_to_sql.config import Settings
from text_to_sql.embeddings.constants import DEFAULT_EMBEDDING_MODEL
from text_to_sql.llms.llm_selector.constants import DEFAULT_LLM_MODEL


def test_model_settings_use_defaults_when_environment_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.openai_model == DEFAULT_LLM_MODEL
    assert settings.openai_embedding_model == DEFAULT_EMBEDDING_MODEL


def test_model_settings_read_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "custom-chat-model")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "custom-embedding-model")

    settings = Settings(_env_file=None)

    assert settings.openai_model == "custom-chat-model"
    assert settings.openai_embedding_model == "custom-embedding-model"

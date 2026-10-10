from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from text_to_sql.embeddings.constants import DEFAULT_EMBEDDING_MODEL
from text_to_sql.llms.llm_selector.constants import DEFAULT_LLM_MODEL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openai_model: str = DEFAULT_LLM_MODEL
    openai_embedding_model: str = DEFAULT_EMBEDDING_MODEL

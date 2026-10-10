import sys

from text_to_sql.config import Settings
from text_to_sql.errors import ConfigurationError, TextToSQLError
from text_to_sql.llms import LLMSelectorService


def main() -> int:
    try:
        question = input("Pergunta sobre viagens de comboio: ").strip()
        if not question:
            raise ValueError("The question cannot be empty.")

        settings = Settings()
        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is missing. Set it in .env or in the environment."
            )

        LLMSelectorService(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
        ).run(question)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except TextToSQLError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

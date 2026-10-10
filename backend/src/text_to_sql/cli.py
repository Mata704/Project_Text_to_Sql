import sys

from text_to_sql.config import Settings
from text_to_sql.document_ingestion import DocumentIngestionService
from text_to_sql.errors import ConfigurationError, TextToSQLError
from text_to_sql.llms import LLMSelectorService


def main() -> int:
    try:
        settings = Settings()
        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is missing. Set it in .env or in the environment."
            )
        api_key = settings.openai_api_key.get_secret_value()

        ingestion_result = DocumentIngestionService(api_key=api_key).run()
        if ingestion_result.skipped:
            print("Documentação já está sincronizada na ChromaDB.")
        else:
            print(
                "Documentação processada: "
                f"{ingestion_result.chunk_count} chunks indexados na ChromaDB."
            )

        question = input("Pergunta sobre viagens de comboio: ").strip()
        if not question:
            raise ValueError("The question cannot be empty.")

        LLMSelectorService(
            api_key=api_key,
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

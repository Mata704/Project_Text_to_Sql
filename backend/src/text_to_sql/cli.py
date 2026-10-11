import json
import sys

from text_to_sql.config import Settings
from text_to_sql.document_ingestion import DocumentIngestionConfig, DocumentIngestionService
from text_to_sql.embeddings import EmbeddingConfig
from text_to_sql.errors import ConfigurationError, TextToSQLError
from text_to_sql.llms import LLMSelectorService, LLMSQLGeneratorService
from text_to_sql.retrieval import RetrievalConfig, RetrievalService
from text_to_sql.sample_database import SampleDatabaseService
from text_to_sql.sqlite_db import SQLiteService


def main() -> int:
    try:
        settings = Settings()
        database_changed = SampleDatabaseService().ensure_current()
        if database_changed:
            print("Base de dados SQLite de demonstração criada ou atualizada.")
        else:
            print("Base de dados SQLite de demonstração já está atualizada.")

        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is missing. Set it in .env or in the environment."
            )
        api_key = settings.openai_api_key.get_secret_value()

        ingestion_config = DocumentIngestionConfig(
            embedding=EmbeddingConfig(model=settings.openai_embedding_model)
        )
        ingestion_result = DocumentIngestionService(
            api_key=api_key,
            config=ingestion_config,
        ).run()
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

        classification = LLMSelectorService(
            api_key=api_key,
            model=settings.openai_model,
        ).run(question)

        if classification.status == "relevant":
            retrieval_config = RetrievalConfig(
                embedding=ingestion_config.embedding,
                vector_store=ingestion_config.vector_store,
            )
            retrieved_chunks = RetrievalService(
                api_key=api_key,
                config=retrieval_config,
            ).retrieve(classification.normalized_query)
            if retrieved_chunks:
                print("Chunks recuperados:")
                for rank, result in enumerate(retrieved_chunks, start=1):
                    source = result.chunk.metadata.get("source", "Fonte desconhecida")
                    print(
                        f"\n{rank}. ID: {result.chunk.chunk_id} | "
                        f"score: {result.score:.3f} | fonte: {source}"
                    )
                    print(result.chunk.content)
            else:
                print("Não foram encontradas evidências relevantes na documentação.")

            sqlite_service = SQLiteService()
            generation = LLMSQLGeneratorService(
                api_key=api_key,
                model=settings.openai_model,
                sqlite_service=sqlite_service,
            ).generate(classification.normalized_query, retrieved_chunks)
            print("\nQuery SQL gerada:")
            print(generation.explanation)
            if generation.sql is not None:
                print(generation.sql)
                parameters = {
                    parameter.name: parameter.value for parameter in generation.parameters
                }
                print("Parâmetros: " + json.dumps(parameters, ensure_ascii=False, sort_keys=True))
                rows = sqlite_service.fetch_all(generation.sql, parameters)
                print("\nResultado:")
                if rows:
                    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
                else:
                    print("A query não devolveu resultados.")
            for citation in generation.citations:
                print(f"- {citation.source} / {citation.chunk_id}: {citation.quote}")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except TextToSQLError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

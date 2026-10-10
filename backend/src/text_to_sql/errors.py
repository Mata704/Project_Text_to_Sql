class TextToSQLError(Exception):
    """Base class for errors that can be reported cleanly by the CLI."""


class ConfigurationError(TextToSQLError):
    """Raised when required application configuration is missing."""


class LLMError(TextToSQLError):
    """Raised when the language model cannot produce a usable result."""


class EmbeddingError(TextToSQLError):
    """Raised when text embeddings cannot be created or validated."""


class VectorStoreError(TextToSQLError):
    """Raised when vector documents cannot be stored or retrieved."""

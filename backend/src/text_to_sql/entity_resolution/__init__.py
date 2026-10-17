"""Normalização de nomes de entidades contra a base de dados."""

from text_to_sql.entity_resolution.entity_resolution_model import (
    EntityResolutionResult,
    EntitySuggestion,
    ResolvedEntity,
)
from text_to_sql.entity_resolution.entity_resolution_service import (
    EntityResolutionService,
    normalize_text,
)

__all__ = [
    "EntityResolutionResult",
    "EntityResolutionService",
    "EntitySuggestion",
    "ResolvedEntity",
    "normalize_text",
]

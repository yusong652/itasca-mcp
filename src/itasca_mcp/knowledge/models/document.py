"""Unified document model for Itasca documentation search system.

This module provides a unified representation of different document types
(commands, model properties, Python API) to enable consistent search operations
across the entire Itasca documentation system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentType(Enum):
    """Document type enumeration.

    Defines the types of searchable documents in the Itasca system:
    - COMMAND: Itasca command documentation (e.g., "ball create", "contact property")
    - MODEL_PROPERTY: Contact model property documentation (e.g., "linear", "hertz")
    - PYTHON_API: Python SDK API documentation (e.g., "itasca.ball.create")
    - FISH: FISH intrinsic functions (e.g., "ball.pos", "math.sqrt")

    Search Strategy:
    - COMMAND + MODEL_PROPERTY: Unified search via CommandSearch
    - PYTHON_API: Independent search via PythonAPISearch
    """

    COMMAND = "command"
    MODEL_PROPERTY = "model_property"
    PYTHON_API = "python_api"
    FISH = "fish"
    REFERENCE = "reference"


@dataclass
class SearchDocument:
    """Unified search document model.

    This class provides a common interface for all searchable documents,
    abstracting away differences between commands, APIs, and model properties.

    Design Goals:
    - Unified search: Same search algorithms work for all document types
    - Extensible: Easy to add new document types via metadata
    - Type-safe: Explicit typing prevents errors

    Attributes:
        name: Unique document name/identifier
            Examples:
            - COMMAND: "ball create", "contact property"
            - MODEL_PROPERTY: "linear", "hertz"
            - PYTHON_API: "itasca.ball.create", "Ball.vel"
        doc_type: Type of document (COMMAND/MODEL_PROPERTY/PYTHON_API)
        title: Display title for search results
        description: Full text description for BM25 search
        keywords: Human-curated search keywords for exact/partial matching
        category: Document category for filtering
            Examples: "ball" (commands), "contact" (model), "itasca.ball" (API)
        syntax: Command/function syntax for display
        examples: Usage examples list
        metadata: Extensible metadata dictionary for custom fields
            Common fields:
            - python_available (bool): Python SDK alternative exists
            - file_path (str): Source JSON file path
            - priority (str): "high", "medium", "low" for ranking
            - property_count (int): Number of properties (model docs)

    Usage:
        >>> # Command document
        >>> cmd_doc = SearchDocument(
        ...     name="ball create",
        ...     doc_type=DocumentType.COMMAND,
        ...     title="ball create",
        ...     description="Create a new ball object...",
        ...     keywords=["create", "ball", "generate"],
        ...     category="ball",
        ...     syntax="ball create <keyword> ..."
        ... )

        >>> # Model property document
        >>> model_doc = SearchDocument(
        ...     name="linear",
        ...     doc_type=DocumentType.MODEL_PROPERTY,
        ...     title="Linear Contact Model",
        ...     description="Linear elastic contact model...",
        ...     keywords=["linear", "contact model", "stiffness"],
        ...     category="contact",
        ...     metadata={"priority": "high", "property_count": 8}
        ... )
    """

    # Required fields
    name: str
    doc_type: DocumentType
    title: str
    description: str
    keywords: list[str]

    # Optional fields (with defaults)
    category: str | None = None
    syntax: str | None = None
    examples: list[dict[str, str]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and normalize fields after initialization."""
        # Ensure metadata is initialized
        if self.metadata is None:
            self.metadata = {}

        # Ensure examples is initialized
        if self.examples is None:
            self.examples = []

        # Normalize keywords (lowercase for consistent matching)
        self.keywords = [k.lower() for k in self.keywords]

    def matches_filters(self, filters: dict[str, Any]) -> bool:
        """Check if document matches filter criteria.

        Args:
            filters: Dictionary of filter conditions
                Supported keys:
                - category: Filter by category (e.g., "ball", "contact")
                - doc_type: Filter by document type
                - Any metadata key: Filter by metadata values

        Returns:
            True if document matches all filters, False otherwise

        Example:
            >>> doc.matches_filters({"category": "ball"})
            True
            >>> doc.matches_filters({"doc_type": DocumentType.MODEL_PROPERTY})
            False
            >>> doc.matches_filters({"metadata.priority": "high"})
            True
        """
        for key, value in filters.items():
            if key == "category" and self.category != value:
                return False
            if key == "doc_type" and self.doc_type != value:
                return False
            # Check metadata (support nested keys like "metadata.priority")
            if key.startswith("metadata."):
                meta_key = key.replace("metadata.", "")
                if self.metadata.get(meta_key) != value:
                    return False
            # Direct metadata check
            elif key in self.metadata and self.metadata[key] != value:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert document to dictionary representation.

        Useful for serialization, logging, and API responses.

        Returns:
            Dictionary with all document fields
        """
        return {
            "name": self.name,
            "doc_type": self.doc_type.value,
            "title": self.title,
            "description": self.description,
            "keywords": self.keywords,
            "category": self.category,
            "syntax": self.syntax,
            "examples": self.examples,
            "metadata": self.metadata,
        }

"""High-level command search interface.

This module provides a simple, user-friendly API for searching Itasca commands.
Model properties are handled separately via itasca_browse_doc(source='reference') tool.
"""

from typing import Any

from itasca_mcp.knowledge.adapters.command_adapter import CommandDocumentAdapter
from itasca_mcp.knowledge.commands.loader import CommandLoader
from itasca_mcp.knowledge.models.search_result import SearchResult
from itasca_mcp.knowledge.search.engines.bm25_engine import BM25SearchEngine


class CommandSearch:
    """Command search interface for Itasca documentation.

    This class provides a high-level API for searching Itasca commands
    using BM25 algorithm with multi-field scoring.

    Features:
    - Automatic index initialization (lazy loading)
    - Singleton pattern for efficient memory usage
    - Support for filtering by category
    - BM25 with multi-field scoring (name=0.5, keywords=0.3, description=0.2)

    Note: For contact model properties, use itasca_browse_doc(source='reference') tool directly.

    Usage:
        >>> # Basic search
        >>> results = CommandSearch.search("ball create", top_k=5)
        >>> results[0].document.title
        "ball create"

        >>> # With category filter
        >>> results = CommandSearch.search("create", category="ball")
        >>> results[0].document.category
        "ball"
    """

    # Singleton instances keyed by (software, version)
    _engines: dict[tuple[str, str], BM25SearchEngine] = {}

    @classmethod
    def _get_engine(cls, version: str = CommandLoader.DEFAULT_VERSION, *, software: str) -> BM25SearchEngine:
        """Get or create a (software, version)-specific BM25 search engine.

        Returns:
            BM25SearchEngine instance (shared across all calls for the same key)
        """
        key = (software, version)
        if key not in cls._engines:
            cls._engines[key] = BM25SearchEngine(
                document_loader=lambda: CommandDocumentAdapter.load_commands(version=version, software=software)
            )
            cls._engines[key].build()

        return cls._engines[key]

    @classmethod
    def search(
        cls,
        query: str,
        top_k: int = 10,
        category: str | None = None,
        min_score: float | None = None,
        version: str = CommandLoader.DEFAULT_VERSION,
        *,
        software: str,
    ) -> list[SearchResult]:
        """Search for Itasca commands.

        Args:
            query: Search query string
                  Examples: "ball create", "contact property", "model solve"
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter
                     Examples: "ball", "contact", "model"
            min_score: Optional minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> results = CommandSearch.search("ball create")
            >>> results[0].document.title
            "ball create"

            >>> results = CommandSearch.search("create", category="ball")
            >>> results[0].document.category
            "ball"
        """
        engine = cls._get_engine(version, software=software)

        # Build filter dictionary
        filters: dict[str, Any] = {}

        if category is not None:
            filters["category"] = category

        if min_score is not None:
            filters["min_score"] = min_score

        # Execute search
        results = engine.search(query=query, top_k=top_k, filters=filters if filters else None)

        return results

    @classmethod
    def search_commands_only(
        cls,
        query: str,
        top_k: int = 10,
        category: str | None = None,
        version: str = CommandLoader.DEFAULT_VERSION,
        *,
        software: str,
    ) -> list[SearchResult]:
        """Search for commands (alias for search method).

        Kept for backward compatibility.

        Args:
            query: Search query string
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter

        Returns:
            List of SearchResult objects
        """
        return cls.search(query=query, top_k=top_k, category=category, version=version, software=software)

    @classmethod
    def get_by_category(
        cls,
        category: str,
        top_k: int = 20,
        version: str = CommandLoader.DEFAULT_VERSION,
        *,
        software: str,
    ) -> list[SearchResult]:
        """Get all commands in a specific category.

        Args:
            category: Category name (e.g., "ball", "contact", "model")
            top_k: Maximum number of results (default: 20)

        Returns:
            List of SearchResult objects in the category

        Example:
            >>> results = CommandSearch.get_by_category("ball")
            >>> all(r.document.category == "ball" for r in results)
            True
        """
        return cls.search(query=category, top_k=top_k, category=category, version=version, software=software)

    @classmethod
    def rebuild_index(cls, software: str | None = None, version: str | None = None) -> None:
        """Rebuild search index(es) from scratch.

        With no arguments, rebuilds every cached (software, version) engine.
        When both ``software`` and ``version`` are given, rebuilds only that key.

        Use this when:
        - Documentation files have been updated
        - Index parameters need to be changed
        - Troubleshooting index issues
        """
        if software is not None and version is not None:
            engine = cls._engines.get((software, version))
            if engine is not None:
                engine.rebuild()
            return

        for engine in cls._engines.values():
            engine.rebuild()

    @classmethod
    def get_index_stats(cls, version: str = CommandLoader.DEFAULT_VERSION, *, software: str) -> dict[str, Any]:
        """Get search index statistics.

        Returns:
            Dictionary with index statistics:
            - doc_count: Number of indexed documents
            - name_field: Name field statistics
            - description_field: Description field statistics
            - keywords_field: Keywords field statistics
        """
        engine = cls._get_engine(version, software=software)
        return engine.get_index_stats()

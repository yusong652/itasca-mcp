"""High-level Python API search interface.

This module provides a simple, user-friendly API for searching Itasca Python SDK
documentation using BM25 algorithm with multi-field scoring.

Features:
- Natural language queries (e.g., "ball velocity", "contact force")
- API path queries (e.g., "Ball.vel", "BallBallContact.gap") via tokenization
- Fresh index built per search (~240ms) for consistency
- Abbreviation support through partial matching
- Contact API consolidation (5 types → 1 result with metadata)
- Component API consolidation (x/y/z variants → base method with metadata)
"""

from typing import Any

from itasca_mcp.knowledge.adapters.api_adapter import APIDocumentAdapter
from itasca_mcp.knowledge.models.search_result import SearchResult
from itasca_mcp.knowledge.search.engines.bm25_engine import BM25SearchEngine
from itasca_mcp.knowledge.search.postprocessing import consolidate_component_apis, consolidate_contact_apis


class APISearch:
    """Python SDK API search interface.

    This class provides a high-level API for searching Itasca Python SDK
    documentation using BM25 algorithm with multi-field scoring.

    Search Scope:
    - Module functions: itasca.ball.create, itasca.wall.create, etc.
    - Object methods: itasca.ball.Ball.vel, itasca.wall.Wall.pos, etc.
    - Contact types: itasca.BallBallContact.gap, itasca.BallFacetContact.gap, etc.
    - All 1006 API documents in unified index

    Features:
    - Unified BM25 search for all API types
    - Fresh index per search (~240ms) for consistency
    - Smart tokenization handles API paths (Ball.vel → ["ball", "vel"])
    - Technical single-char preservation (x, y, z, r, n, t)
    - Abbreviation support through partial matching (pos → position)
    - Contact API consolidation (5 types → 1 result)
    - Component API consolidation (x/y/z variants → base method)

    Design Decisions:
    - Multi-field BM25: name (0.5), keywords (0.3), description (0.2)
    - Single search() method handles all query types
    - Category filter for module-specific searches
    - No caching: ensures fresh results, acceptable ~240ms overhead

    Usage:
        >>> # Natural language search
        >>> results = APISearch.search("ball create", top_k=5)
        >>> results[0].document.title
        "itasca.ball.create"

        >>> # API path search (handled by tokenizer + name boost)
        >>> results = APISearch.search("Ball.vel", top_k=5)
        >>> results[0].document.title
        "itasca.ball.Ball.vel"

        >>> # Contact type search
        >>> results = APISearch.search("contact gap", top_k=5)
        >>> any("Contact" in r.document.title for r in results)
        True

        >>> # With category filter
        >>> results = APISearch.search(
        ...     "position",
        ...     top_k=10,
        ...     category="ball"
        ... )

        >>> # Abbreviations (partial matching)
        >>> results = APISearch.search("pos")  # Matches "position"
    """

    @classmethod
    def search(
        cls,
        query: str,
        top_k: int = 10,
        category: str | None = None,
        min_score: float | None = None,
        *,
        software: str,
    ) -> list[SearchResult]:
        """Search for Python SDK APIs using BM25 algorithm.

        This method uses BM25 with smart tokenization to handle both
        natural language queries and API path queries:
        - Natural language: "ball velocity", "contact gap"
        - API paths: "Ball.vel", "BallBallContact.gap" (tokenized by dots/underscores)

        Args:
            query: Search query string
                  Examples: "ball create", "Ball.vel", "contact gap", "position"
            top_k: Maximum number of results to return (default: 10)
            category: Optional category filter
                     Examples: "ball", "wall", "contact"
            min_score: Optional minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)
            Empty list if no matches found

        Example:
            >>> # Natural language query
            >>> results = APISearch.search("ball position")
            >>> results[0].document.name
            "itasca.ball.Ball.pos"

            >>> # API path query (handled by tokenizer)
            >>> results = APISearch.search("Ball.vel")
            >>> results[0].document.name
            "itasca.ball.Ball.vel"

            >>> # Contact type query
            >>> results = APISearch.search("BallBallContact.gap")
            >>> "Contact" in results[0].document.name
            True

            >>> # With filters
            >>> results = APISearch.search(
            ...     "velocity",
            ...     category="ball",
            ...     min_score=5.0
            ... )
        """
        # Create and build BM25 search engine (no caching)
        # Each search builds a fresh index (~240ms overhead)
        # This ensures consistency and avoids stale cache issues in development
        engine = BM25SearchEngine(document_loader=lambda: APIDocumentAdapter.load_all(software=software))
        engine.build()

        # Build filter dictionary
        filters: dict[str, Any] = {}

        if category is not None:
            filters["category"] = category

        if min_score is not None:
            filters["min_score"] = min_score

        # Execute BM25 search with over-fetching to account for consolidation
        # Two-stage consolidation can reduce result count significantly:
        # - Contact consolidation: 5 contact types → 1 result (5:1 ratio)
        # - Component consolidation: base + _x/_y/_z → 1 result (4:1 ratio)
        # - Combined worst case: 5 × 4 = 20:1 compression ratio
        #
        # Strategy: Fetch 10x top_k results, consolidate twice, then return top_k
        # Example: top_k=8 → search 80 → after consolidation ≈ 4-8 results
        #
        # This balances performance (single search call) with accuracy (enough diverse results)

        # Calculate search limit: 10x for two-stage consolidation, capped at 100
        search_limit = min(top_k * 10, 100)

        results = engine.search(query=query, top_k=search_limit, filters=filters if filters else None)

        # Consolidate Contact API duplicates
        # This reduces redundancy (e.g., BallBallContact.gap, BallFacetContact.gap → single result)
        # while preserving type information in metadata['all_contact_types']
        consolidated = consolidate_contact_apis(results)

        # Consolidate component APIs (_x, _y, _z variants)
        # This reduces redundancy (e.g., force_global, force_global_x/y/z → single result)
        # while preserving component information in metadata['has_components']
        consolidated = consolidate_component_apis(consolidated)

        # Consolidation drops entries, so renumber before returning the final top_k
        final = consolidated[:top_k]
        for rank, result in enumerate(final, start=1):
            result.rank = rank
        return final

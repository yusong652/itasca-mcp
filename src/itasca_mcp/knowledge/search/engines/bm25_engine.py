"""BM25-based search engine for Itasca documentation with multi-field support.

This module implements a complete search engine using BM25 algorithm with
multi-field scoring, providing a high-level interface for document search.
"""

from collections.abc import Callable
from typing import Any

from itasca_mcp.knowledge.models.document import SearchDocument
from itasca_mcp.knowledge.models.search_result import SearchResult
from itasca_mcp.knowledge.search.engines.base_engine import BaseSearchEngine
from itasca_mcp.knowledge.search.indexing.bm25_indexer import BM25Indexer
from itasca_mcp.knowledge.search.scoring.bm25_scorer import BM25Scorer


class BM25SearchEngine(BaseSearchEngine):
    """BM25 search engine with multi-field scoring.

    This engine provides a complete search solution using BM25 algorithm:
    - Multi-field indexing (name, description, keywords)
    - Field-specific BM25 scoring with weighted combination
    - Automatic index building on first query
    - Partial matching support (abbreviations)

    Features:
    - Pure Python implementation (no NumPy dependency)
    - Optimized for ~1000 documents (commands + APIs)
    - Fast indexing (<200ms) and query (<15ms)
    - Automatic result ranking and filtering

    Algorithm Details:
    - BM25 parameters: K1=1.5, B=0.75
    - Field weights: name=0.5, keywords=0.3, description=0.2
    - IDF formula: Robertson-Spärck Jones (field-specific)
    - Real document lengths (no artificial boosting)

    Usage:
        >>> from itasca_mcp.knowledge.adapters.command_adapter import CommandDocumentAdapter
        >>> engine = BM25SearchEngine(document_loader=CommandDocumentAdapter.load_all)
        >>> engine.build()
        >>> results = engine.search("Ball.vel", top_k=5)
        >>> for result in results:
        ...     print(f"{result.document.name}: {result.score:.3f}")
        ...     print(f"  Field scores: {result.match_info['field_scores']}")
    """

    def __init__(self, document_loader: Callable[[], list[SearchDocument]]):
        """Initialize BM25 search engine with multi-field support.

        Args:
            document_loader: Callable that returns list of SearchDocument objects

        Example:
            >>> engine = BM25SearchEngine(
            ...     document_loader=CommandDocumentAdapter.load_all
            ... )
        """
        super().__init__(document_loader)
        self.indexer = BM25Indexer()
        self.scorer: BM25Scorer | None = None

    def build(self) -> None:
        """Build multi-field BM25 index from loaded documents.

        This method:
        1. Loads documents using document_loader()
        2. Builds separate BM25 indexes for name/description/keywords fields
        3. Creates multi-field BM25 scorer with weighted combination

        Raises:
            Exception: If document loading or indexing fails

        Example:
            >>> engine.build()
            >>> stats = engine.indexer.get_stats()
            >>> stats['doc_count']
            1006
            >>> stats['name_field']['avg_doc_len']
            4.2
        """
        # Load documents
        self.documents = self.document_loader()

        if not self.documents:
            raise ValueError("Document loader returned empty list")

        # Build multi-field BM25 index
        self.indexer.build(self.documents)

        # Create multi-field scorer
        self.scorer = BM25Scorer(self.indexer)

        # Mark as built
        self._is_built = True

    def search(self, query: str, top_k: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        """Execute BM25 search with optional filtering.

        Args:
            query: Search query string
                  Examples: "ball porosity", "contact gap", "pos"
            top_k: Maximum number of results to return (default: 10)
            filters: Optional filters:
                    - doc_type: Filter by DocumentType
                    - category: Filter by category
                    - min_score: Minimum score threshold

        Returns:
            List of SearchResult objects sorted by score (highest first)

        Raises:
            ValueError: If engine not built (call build() first)

        Example:
            >>> engine.build()
            >>> results = engine.search("ball create", top_k=5)
            >>> results[0].document.title
            "ball create"
            >>> results[0].score
            15.234

            >>> # With filters
            >>> results = engine.search(
            ...     "contact",
            ...     top_k=10,
            ...     filters={"doc_type": "command", "min_score": 5.0}
            ... )
        """
        # Auto-build on first query
        if not self._is_built:
            self.build()

        # Validate query
        query = query.strip()
        if not query:
            return []

        # Score all documents using BM25
        assert self.scorer is not None
        scored_results = self.scorer.batch_score(query, self.documents)

        search_results = [
            SearchResult(document=document, score=score, match_info=match_info, rank=0)
            for document, score, match_info in scored_results
        ]

        # Apply filters if provided
        if filters:
            search_results = self._apply_filters(search_results, filters)

        # Sort by score (descending); ranks are 1-based positions in that order
        search_results.sort(key=lambda r: r.score, reverse=True)
        for rank, result in enumerate(search_results, start=1):
            result.rank = rank

        return search_results[:top_k]

    def get_index_stats(self) -> dict[str, Any]:
        """Get multi-field BM25 index statistics.

        Returns:
            Dictionary with index statistics for each field:
            - doc_count: Number of indexed documents
            - name_field: Statistics for name field (avg_doc_len, vocab_size, total_terms)
            - description_field: Statistics for description field
            - keywords_field: Statistics for keywords field

        Raises:
            ValueError: If engine not built

        Example:
            >>> engine.build()
            >>> stats = engine.get_index_stats()
            >>> stats
            {
                'doc_count': 1006,
                'name_field': {
                    'avg_doc_len': 4.2,
                    'vocab_size': 245,
                    'total_terms': 4242
                },
                'description_field': {
                    'avg_doc_len': 18.7,
                    'vocab_size': 1543,
                    'total_terms': 18802
                },
                'keywords_field': {
                    'avg_doc_len': 8.1,
                    'vocab_size': 654,
                    'total_terms': 8146
                }
            }
        """
        if not self._is_built:
            raise ValueError("Engine not built. Call build() first.")

        return self.indexer.get_stats()

    def set_field_weights(
        self, weight_name: float | None = None, weight_desc: float | None = None, weight_kw: float | None = None
    ) -> None:
        """Update field weights for scoring.

        Field weights control the relative importance of each field in the final score.
        Weights should sum to 1.0 for proper normalization.

        Args:
            weight_name: Name field weight (default: 0.5)
            weight_desc: Description field weight (default: 0.2)
            weight_kw: Keywords field weight (default: 0.3)

        Example:
            >>> # Increase name field importance for API path queries
            >>> engine.set_field_weights(weight_name=0.6, weight_desc=0.15, weight_kw=0.25)
            >>>
            >>> # Balance keywords and description more evenly
            >>> engine.set_field_weights(weight_name=0.5, weight_desc=0.25, weight_kw=0.25)
        """
        BM25Scorer.set_parameters(weight_name=weight_name, weight_desc=weight_desc, weight_kw=weight_kw)

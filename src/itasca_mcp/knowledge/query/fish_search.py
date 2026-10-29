"""High-level FISH intrinsic search interface (BM25 over the ``fish_docs`` corpus)."""

from __future__ import annotations

from itasca_mcp.knowledge.adapters.fish_adapter import FishDocumentAdapter, expand_query
from itasca_mcp.knowledge.models.search_result import SearchResult
from itasca_mcp.knowledge.search.engines.bm25_engine import BM25SearchEngine


class FishSearch:
    """Search FISH intrinsics by keywords or dotted fragments.

    One BM25 index per (software, version) so a 6.0 query never surfaces 9.x-only
    names; indexes are built lazily and kept for the process lifetime.
    """

    _engines: dict[tuple[str, str], BM25SearchEngine] = {}

    @classmethod
    def _get_engine(cls, *, software: str, version: str) -> BM25SearchEngine:
        key = (software, version)
        if key not in cls._engines:
            engine = BM25SearchEngine(
                document_loader=lambda: FishDocumentAdapter.load_all(software=software, version=version)
            )
            engine.build()
            cls._engines[key] = engine
        return cls._engines[key]

    @classmethod
    def search(
        cls,
        query: str,
        top_k: int = 10,
        *,
        software: str,
        version: str,
        category: str | None = None,
        min_score: float | None = None,
    ) -> list[SearchResult]:
        engine = cls._get_engine(software=software, version=version)
        filters: dict[str, object] = {}
        if category:
            filters["category"] = category
        if min_score is not None:
            filters["min_score"] = min_score
        return engine.search(expand_query(query), top_k=top_k, filters=filters or None)

    @classmethod
    def clear_cache(cls) -> None:
        cls._engines.clear()

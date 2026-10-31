"""High-level reference search interface (BM25 over reference items and sub-items)."""

from __future__ import annotations

from itasca_mcp.knowledge.adapters.reference_adapter import ReferenceDocumentAdapter
from itasca_mcp.knowledge.models.search_result import SearchResult
from itasca_mcp.knowledge.search.engines.bm25_engine import BM25SearchEngine


class ReferenceSearch:
    """Search reference docs (model properties, range elements, plot items) by keywords.

    One BM25 index per (software, version), built lazily, so version-gated
    items (PFC contact models) only surface where they exist.
    """

    _engines: dict[tuple[str, str], BM25SearchEngine] = {}

    @classmethod
    def _get_engine(cls, *, software: str, version: str) -> BM25SearchEngine:
        key = (software, version)
        if key not in cls._engines:
            engine = BM25SearchEngine(
                document_loader=lambda: ReferenceDocumentAdapter.load_all(software=software, version=version)
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
    ) -> list[SearchResult]:
        engine = cls._get_engine(software=software, version=version)
        filters = {"category": category} if category else None
        return engine.search(query, top_k=top_k, filters=filters)

    @classmethod
    def clear_cache(cls) -> None:
        cls._engines.clear()

"""BM25 inverted index builder for Itasca documentation search system with multi-field support.

This module implements BM25 indexing using only Python standard library
(no NumPy dependency), optimized for technical documentation search.

Multi-Field Design:
- Separate BM25 indexes for name, description, and keywords fields
- Each field maintains its own term frequencies, document frequencies, and lengths
- Enables field-specific scoring and flexible weighting at query time
"""

import math
from collections import Counter
from typing import Any

from itasca_mcp.knowledge.models.document import SearchDocument
from itasca_mcp.knowledge.search.preprocessing.tokenizer import TextTokenizer


class BM25Indexer:
    """BM25 inverted index builder with multi-field support.

    Builds and maintains separate BM25 index structures for each field:
    - Name field: API paths, command names (highest semantic importance)
    - Description field: Detailed explanations (medium importance)
    - Keywords field: Curated search terms (high importance)

    Each field has independent:
    - Document tokens (real lengths, no artificial boosting)
    - Term frequencies per document
    - Document frequencies per term
    - Average document length

    Advantages over single-field approach:
    - Real document lengths (no inflation from boosting)
    - Field-specific IDF values reflect true term distribution
    - Can distinguish name matches from description matches
    - Flexible field weighting at query time

    Design:
    - Pure Python implementation (no NumPy)
    - Optimized for ~1000 documents (commands + APIs)
    - Three independent indexes (simple, no over-engineering)

    Usage:
        >>> indexer = BM25Indexer()
        >>> indexer.build(documents)
        >>>
        >>> # Get IDF for a term in the name field
        >>> name_idf = indexer.get_idf("ball", field="name")
        >>>
        >>> # Get term frequency in description field
        >>> desc_tf = indexer.get_term_freq("itasca.ball.Ball.vel", "velocity", field="description")
    """

    def __init__(self) -> None:
        """Initialize empty multi-field BM25 index."""
        # Name field index
        self.name_documents: dict[str, list[str]] = {}  # doc_id → tokens
        self.name_term_freq: dict[str, dict[str, int]] = {}  # doc_id → {term → count}
        self.name_term_doc_freq: dict[str, int] = {}  # term → document frequency
        self.name_avg_doc_len: float = 0.0

        # Description field index
        self.desc_documents: dict[str, list[str]] = {}
        self.desc_term_freq: dict[str, dict[str, int]] = {}
        self.desc_term_doc_freq: dict[str, int] = {}
        self.desc_avg_doc_len: float = 0.0

        # Keywords field index
        self.kw_documents: dict[str, list[str]] = {}
        self.kw_term_freq: dict[str, dict[str, int]] = {}
        self.kw_term_doc_freq: dict[str, int] = {}
        self.kw_avg_doc_len: float = 0.0

        # Common
        self.doc_count: int = 0
        self.tokenizer = TextTokenizer()

    def build(self, documents: list[SearchDocument]) -> None:
        """Build multi-field BM25 index from documents.

        Each field is indexed independently with its real token counts:
        - Name field: Tokenize document name (API path or command name)
        - Description field: Tokenize description text
        - Keywords field: Tokenize and concatenate keywords list

        No artificial boosting - field importance is handled at scoring time.

        Args:
            documents: List of SearchDocument instances to index

        Example:
            >>> indexer = BM25Indexer()
            >>> indexer.build([doc1, doc2, doc3])
            >>> indexer.doc_count
            3
            >>> indexer.name_avg_doc_len  # Real length
            4.2
            >>> indexer.desc_avg_doc_len
            18.7
        """
        # Clear existing indexes
        self.clear()

        # Process each document
        for doc in documents:
            doc_id = doc.name

            # 1. Index name field
            name_tokens = self.tokenizer.tokenize(doc.name)
            self.name_documents[doc_id] = name_tokens
            self.name_term_freq[doc_id] = dict(Counter(name_tokens))
            for term in set(name_tokens):
                self.name_term_doc_freq[term] = self.name_term_doc_freq.get(term, 0) + 1

            # 2. Index description field (plus any metadata index_terms, e.g. keyword names)
            extra = " ".join(doc.metadata.get("index_terms", []))
            desc_tokens = self.tokenizer.tokenize(f"{doc.description} {extra}" if extra else doc.description)
            self.desc_documents[doc_id] = desc_tokens
            self.desc_term_freq[doc_id] = dict(Counter(desc_tokens))
            for term in set(desc_tokens):
                self.desc_term_doc_freq[term] = self.desc_term_doc_freq.get(term, 0) + 1

            # 3. Index keywords field
            kw_tokens = self.tokenizer.tokenize(" ".join(doc.keywords))
            self.kw_documents[doc_id] = kw_tokens
            self.kw_term_freq[doc_id] = dict(Counter(kw_tokens))
            for term in set(kw_tokens):
                self.kw_term_doc_freq[term] = self.kw_term_doc_freq.get(term, 0) + 1

        # Calculate statistics
        self.doc_count = len(documents)

        if self.doc_count > 0:
            # Name field stats
            name_total_len = sum(len(tokens) for tokens in self.name_documents.values())
            self.name_avg_doc_len = name_total_len / self.doc_count

            # Description field stats
            desc_total_len = sum(len(tokens) for tokens in self.desc_documents.values())
            self.desc_avg_doc_len = desc_total_len / self.doc_count

            # Keywords field stats
            kw_total_len = sum(len(tokens) for tokens in self.kw_documents.values())
            self.kw_avg_doc_len = kw_total_len / self.doc_count
        else:
            self.name_avg_doc_len = 0.0
            self.desc_avg_doc_len = 0.0
            self.kw_avg_doc_len = 0.0

    def get_idf(self, term: str, field: str = "name") -> float:
        """Calculate IDF (Inverse Document Frequency) for a term in a specific field.

        Uses BM25 IDF formula (Robertson-Spärck Jones):
        IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)

        Args:
            term: Term to calculate IDF for
            field: Field name ("name", "description", or "keywords")

        Returns:
            IDF score (>= 0)

        Example:
            >>> indexer.get_idf("ball", field="name")
            2.456  # "ball" is rare in name field
            >>> indexer.get_idf("ball", field="description")
            0.823  # "ball" is common in description field
        """
        # Select appropriate term_doc_freq dict
        if field == "name":
            term_doc_freq = self.name_term_doc_freq
        elif field == "description":
            term_doc_freq = self.desc_term_doc_freq
        elif field == "keywords":
            term_doc_freq = self.kw_term_doc_freq
        else:
            raise ValueError(f"Unknown field: {field}. Must be 'name', 'description', or 'keywords'")

        df = term_doc_freq.get(term, 0)
        N = self.doc_count

        if N == 0 or df == 0:
            return 0.0

        # BM25 IDF formula
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
        return max(0.0, idf)

    def get_term_freq(self, doc_id: str, term: str, field: str = "name") -> int:
        """Get term frequency in a specific document and field.

        Args:
            doc_id: Document ID
            term: Term to look up
            field: Field name ("name", "description", or "keywords")

        Returns:
            Term frequency (0 if not found)

        Example:
            >>> indexer.get_term_freq("itasca.ball.Ball.vel", "ball", field="name")
            2  # "ball" appears twice in name
            >>> indexer.get_term_freq("itasca.ball.Ball.vel", "velocity", field="description")
            3  # "velocity" appears 3 times in description
        """
        if field == "name":
            term_freq = self.name_term_freq
        elif field == "description":
            term_freq = self.desc_term_freq
        elif field == "keywords":
            term_freq = self.kw_term_freq
        else:
            raise ValueError(f"Unknown field: {field}")

        return term_freq.get(doc_id, {}).get(term, 0)

    def get_doc_length(self, doc_id: str, field: str = "name") -> int:
        """Get document length (number of tokens) for a specific field.

        Args:
            doc_id: Document ID
            field: Field name ("name", "description", or "keywords")

        Returns:
            Document length

        Example:
            >>> indexer.get_doc_length("itasca.ball.Ball.vel", field="name")
            4  # Real token count in name
            >>> indexer.get_doc_length("itasca.ball.Ball.vel", field="description")
            18  # Real token count in description
        """
        if field == "name":
            documents = self.name_documents
        elif field == "description":
            documents = self.desc_documents
        elif field == "keywords":
            documents = self.kw_documents
        else:
            raise ValueError(f"Unknown field: {field}")

        return len(documents.get(doc_id, []))

    def get_avg_doc_length(self, field: str = "name") -> float:
        """Get average document length for a specific field.

        Args:
            field: Field name ("name", "description", or "keywords")

        Returns:
            Average document length

        Example:
            >>> indexer.get_avg_doc_length(field="name")
            4.2
            >>> indexer.get_avg_doc_length(field="description")
            18.7
        """
        if field == "name":
            return self.name_avg_doc_len
        elif field == "description":
            return self.desc_avg_doc_len
        elif field == "keywords":
            return self.kw_avg_doc_len
        else:
            raise ValueError(f"Unknown field: {field}")

    def get_field_tokens(self, doc_id: str, field: str = "name") -> list[str]:
        """Get tokenized content for a specific field.

        Args:
            doc_id: Document ID
            field: Field name ("name", "description", or "keywords")

        Returns:
            List of tokens (empty list if not found)

        Example:
            >>> indexer.get_field_tokens("itasca.ball.Ball.vel", field="name")
            ['itasca', 'ball', 'ball', 'vel']
        """
        if field == "name":
            return self.name_documents.get(doc_id, [])
        elif field == "description":
            return self.desc_documents.get(doc_id, [])
        elif field == "keywords":
            return self.kw_documents.get(doc_id, [])
        else:
            raise ValueError(f"Unknown field: {field}")

    def get_all_doc_ids(self) -> set[str]:
        """Get all document IDs in the index.

        Returns:
            Set of document IDs

        Example:
            >>> indexer.get_all_doc_ids()
            {'itasca.ball.Ball.vel', 'itasca.wall.create', ...}
        """
        return set(self.name_documents.keys())

    def clear(self) -> None:
        """Clear all index data for all fields.

        Example:
            >>> indexer.clear()
            >>> indexer.doc_count
            0
        """
        # Clear name field
        self.name_documents.clear()
        self.name_term_freq.clear()
        self.name_term_doc_freq.clear()
        self.name_avg_doc_len = 0.0

        # Clear description field
        self.desc_documents.clear()
        self.desc_term_freq.clear()
        self.desc_term_doc_freq.clear()
        self.desc_avg_doc_len = 0.0

        # Clear keywords field
        self.kw_documents.clear()
        self.kw_term_freq.clear()
        self.kw_term_doc_freq.clear()
        self.kw_avg_doc_len = 0.0

        # Clear common
        self.doc_count = 0

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics for debugging.

        Returns:
            Dictionary with multi-field index statistics

        Example:
            >>> stats = indexer.get_stats()
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
        return {
            "doc_count": self.doc_count,
            "name_field": {
                "avg_doc_len": round(self.name_avg_doc_len, 2),
                "vocab_size": len(self.name_term_doc_freq),
                "total_terms": sum(len(tokens) for tokens in self.name_documents.values()),
            },
            "description_field": {
                "avg_doc_len": round(self.desc_avg_doc_len, 2),
                "vocab_size": len(self.desc_term_doc_freq),
                "total_terms": sum(len(tokens) for tokens in self.desc_documents.values()),
            },
            "keywords_field": {
                "avg_doc_len": round(self.kw_avg_doc_len, 2),
                "vocab_size": len(self.kw_term_doc_freq),
                "total_terms": sum(len(tokens) for tokens in self.kw_documents.values()),
            },
        }

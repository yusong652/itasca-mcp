"""BM25 scoring algorithm for Itasca documentation search system with multi-field support.

This module implements BM25 ranking with multi-field scoring and weighted combination,
using only Python standard library (no NumPy dependency).
"""

from typing import Any

from itasca_mcp.knowledge.models.document import DocumentType, SearchDocument
from itasca_mcp.knowledge.search.indexing.bm25_indexer import BM25Indexer
from itasca_mcp.knowledge.search.keyword_matcher import find_partial_matches
from itasca_mcp.knowledge.search.preprocessing.tokenizer import TextTokenizer


class BM25Scorer:
    """BM25 scoring algorithm implementation with multi-field support.

    Implements BM25 ranking function with configurable parameters:
    - K1: Term frequency saturation parameter
    - B: Document length normalization parameter
    - Field weights: Relative importance of name/description/keywords

    Multi-Field Scoring Strategy:
    1. Score each field (name, description, keywords) independently using BM25
    2. Combine scores using weighted average: score = w_name*s_name + w_desc*s_desc + w_kw*s_kw
    3. Field weights default to: name=0.5, keywords=0.3, description=0.2

    Advantages:
    - Can distinguish name matches from description matches
    - Flexible field weighting for different use cases
    - Real document lengths prevent BM25 saturation issues

    Design:
    - Pure Python (no NumPy)
    - Optimized for ~1000 documents
    - Supports partial matching for abbreviations

    Usage:
        >>> indexer = BM25Indexer()
        >>> indexer.build(documents)
        >>> scorer = BM25Scorer(indexer)
        >>> score, info = scorer.score("Ball.vel", doc)
        >>> score
        15.8  # High score for exact name match
        >>> info
        {
            'field_scores': {'name': 12.5, 'description': 2.1, 'keywords': 1.2},
            'total_score': 15.8,
            'matched_terms': ['ball', 'vel'],
            ...
        }
    """

    # BM25 hyperparameters (tunable)
    K1 = 1.5  # Term frequency saturation (1.2-2.0 recommended)
    B = 0.75  # Document length normalization (0.5-0.8 recommended); used for the name field
    # Length normalization is per field, because length means different things:
    # - name: extra tokens in a command/API name are extra distance from the
    #   query ("fracture delete" vs "fracture template-delete"), so the short
    #   name bonus is a real relevance signal and stays at the default B.
    # - description: ranges from one curated sentence to a full official
    #   paragraph plus live-behaviour notes, and that length says nothing about
    #   relevance, so the short-document bonus is kept mild.
    B_DESCRIPTION = 0.5
    # The keywords field is a curated tag list, not prose. A document tagged with
    # more concepts is not "longer" in the BM25 sense, and a tag repeated across
    # phrase-style entries is not "more about" that concept, so a keywords hit is
    # scored as plain presence: IDF only, no length normalization, no tf saturation.
    B_KEYWORDS = 0.0

    # Field weights (tunable) - must sum to 1.0
    # These define relative importance of each field in final score
    WEIGHT_NAME = 0.5  # 50% - API paths have highest importance
    WEIGHT_KEYWORDS = 0.3  # 30% - Curated terms are highly relevant
    WEIGHT_DESCRIPTION = 0.2  # 20% - Descriptions provide context

    def __init__(self, indexer: BM25Indexer):
        """Initialize BM25 scorer with multi-field indexer.

        Args:
            indexer: Built multi-field BM25 index
        """
        self.indexer = indexer
        self.tokenizer = TextTokenizer()

    def score(self, query: str, document: SearchDocument) -> tuple[float, dict[str, Any]]:
        """Calculate multi-field BM25 score for a query-document pair.

        Process:
        1. Score query against name field
        2. Score query against description field
        3. Score query against keywords field
        4. Combine using field weights: total = w_name*s_name + w_desc*s_desc + w_kw*s_kw

        Args:
            query: User query string
            document: Document to score

        Returns:
            Tuple of (total_score, match_info) where:
            - total_score: Weighted combination of field scores
            - match_info: Dict with field-specific scores and matched terms

        Example:
            >>> score, info = scorer.score("Ball.contacts", doc)
            >>> score
            18.5
            >>> info['field_scores']
            {'name': 15.2, 'description': 2.1, 'keywords': 1.2}
        """
        # 1. Tokenize query
        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return 0.0, {}

        doc_id = document.name
        query_set = set(query_tokens)

        # 2. Score each field independently
        name_score, name_info = self._score_field(query_set, doc_id, field="name")
        desc_score, desc_info = self._score_field(query_set, doc_id, field="description")
        kw_score, kw_info = self._score_field(query_set, doc_id, field="keywords")

        # 3. Combine scores using field weights
        total_score = (
            self.WEIGHT_NAME * name_score + self.WEIGHT_DESCRIPTION * desc_score + self.WEIGHT_KEYWORDS * kw_score
        )

        # 4. Boost exact name matches (e.g., query "BallBallContact" → itasca.BallBallContact)
        doc_name_lower = document.name.rsplit(".", 1)[-1].lower() if "." in document.name else document.name.lower()
        if doc_name_lower in query_set:
            total_score *= 2.0
        # Graded version of the same rule for multi-token command names. The
        # factor runs from 1 (name shares nothing with the query) to 2 (query
        # spells out exactly the name) as the product of two ratios:
        # - name precision |name ∩ query| / |name|: a longer sibling
        #   ("zone export-data" for "zone export") carries tokens the query
        #   never asked for, so it earns less than the exact name;
        # - query coverage |name ∩ query| / |query|: a shorter name
        #   ("zone initialize" for "zone initialize stress") ignores query
        #   words another command's name answers, so it earns less than that
        #   command. Query tokens include stems, which deflates coverage the
        #   same way for every document, so ranking is unaffected.
        elif document.doc_type == DocumentType.COMMAND:
            name_tokens = set(self.indexer.get_field_tokens(doc_id, field="name"))
            shared = len(name_tokens & query_set)
            if shared:
                total_score *= 1.0 + (shared / len(name_tokens)) * (shared / len(query_set))

        # 4. Collect all matched terms (union across fields)
        all_matched_terms = set()
        all_matched_terms.update(name_info["exact_matches"])
        all_matched_terms.update(desc_info["exact_matches"])
        all_matched_terms.update(kw_info["exact_matches"])

        # 5. Build comprehensive match info
        match_info = {
            "total_score": round(total_score, 3),
            "field_scores": {
                "name": round(name_score, 3),
                "description": round(desc_score, 3),
                "keywords": round(kw_score, 3),
            },
            "field_weights": {
                "name": self.WEIGHT_NAME,
                "description": self.WEIGHT_DESCRIPTION,
                "keywords": self.WEIGHT_KEYWORDS,
            },
            "matched_terms": list(all_matched_terms),
            "field_details": {"name": name_info, "description": desc_info, "keywords": kw_info},
        }

        return total_score, match_info

    def _score_field(self, query_tokens: set[str], doc_id: str, field: str) -> tuple[float, dict[str, Any]]:
        """Score query against a specific document field.

        Args:
            query_tokens: Set of query tokens
            doc_id: Document ID
            field: Field name ("name", "description", or "keywords")

        Returns:
            Tuple of (field_score, field_match_info)

        Example:
            >>> score, info = scorer._score_field({'ball', 'vel'}, doc_id, field="name")
            >>> score
            8.5
            >>> info['exact_matches']
            ['ball', 'vel']
        """
        # 1. Get document tokens for this field
        doc_tokens = set(self.indexer.get_field_tokens(doc_id, field=field))

        if not doc_tokens:
            return 0.0, {"exact_matches": [], "partial_matches": [], "term_scores": {}}

        # 2. Find exact matches
        exact_matches = query_tokens & doc_tokens

        # 3. Find partial matches for unmatched query terms
        # Note: Name field requires exact matching only (no partial matches for API paths)
        if field == "name":
            # Disable partial matching for name field (API paths should match exactly)
            partial_matches: set[tuple[str, str]] = set()
            quality = 1.0
        else:
            # Enable partial matching for description and keywords fields
            unmatched_query = query_tokens - exact_matches
            unmatched_doc = doc_tokens - exact_matches
            partial_matches, quality = find_partial_matches(unmatched_query, unmatched_doc)

        # 4. Score exact matches
        term_scores = {}
        for term in exact_matches:
            term_score = self._score_term(term, doc_id, field=field)
            term_scores[term] = round(term_score, 3)

        # 5. Score partial matches (with quality discount)
        for q_term, d_term in partial_matches:
            term_score = self._score_term(d_term, doc_id, field=field) * quality
            term_scores[f"{d_term}←{q_term}"] = round(term_score, 3)

        # 6. Sum all term scores for this field
        field_score = sum(term_scores.values())

        # 7. Build field match info
        field_info = {
            "exact_matches": list(exact_matches),
            "partial_matches": [{"query": q, "doc": d, "quality": quality} for q, d in partial_matches],
            "term_scores": term_scores,
        }

        return field_score, field_info

    def _score_term(self, term: str, doc_id: str, field: str = "name") -> float:
        """Calculate BM25 score contribution for a single term in a specific field.

        BM25 formula:
        score(t, D, f) = IDF(t, f) × (TF(t, D, f) × (k1 + 1)) / (TF(t, D, f) + k1 × (1 - b + b × |D_f| / avgdl_f))

        where:
        - IDF(t, f): Inverse document frequency of term t in field f
        - TF(t, D, f): Frequency of term t in document D's field f
        - |D_f|: Length of document D's field f
        - avgdl_f: Average document length for field f
        - k1, b: Tuning parameters (b is per field: B for name, B_DESCRIPTION
          for description)

        The keywords field short-circuits to IDF(t, f) alone (tag presence).

        Args:
            term: Term to score
            doc_id: Document ID
            field: Field name ("name", "description", or "keywords")

        Returns:
            BM25 score contribution for this term in this field

        Example:
            >>> scorer._score_term("ball", doc_id, field="name")
            4.5  # High IDF in name field
            >>> scorer._score_term("ball", doc_id, field="description")
            1.2  # Lower IDF in description field
        """
        # 1. Get field-specific IDF
        idf = self.indexer.get_idf(term, field=field)

        # 2. Get field-specific term frequency
        tf = self.indexer.get_term_freq(doc_id, term, field=field)

        if tf == 0:
            return 0.0

        # Tag semantics for the keywords field: presence only (see B_KEYWORDS).
        if field == "keywords":
            return idf

        # 3. Get field-specific document length and average
        doc_len = self.indexer.get_doc_length(doc_id, field=field)
        avg_len = self.indexer.get_avg_doc_length(field=field)

        b = self.B_DESCRIPTION if field == "description" else self.B
        if avg_len == 0:
            norm_factor = 1.0
        else:
            norm_factor = 1 - b + b * (doc_len / avg_len)

        # 4. Calculate saturated term frequency
        saturated_tf = (tf * (self.K1 + 1)) / (tf + self.K1 * norm_factor)

        # 5. Final BM25 score for this term in this field
        score = idf * saturated_tf

        return score

    def batch_score(
        self, query: str, documents: list[SearchDocument]
    ) -> list[tuple[SearchDocument, float, dict[str, Any]]]:
        """Score multiple documents for a query using multi-field BM25.

        Args:
            query: User query
            documents: List of documents to score

        Returns:
            List of (document, score, match_info) tuples for documents with score > 0

        Example:
            >>> results = scorer.batch_score("Ball.vel", documents)
            >>> len(results)
            15  # 15 documents matched
            >>> results[0][1]  # Top score
            18.5
        """
        results = []

        for doc in documents:
            score, match_info = self.score(query, doc)
            if score > 0:
                results.append((doc, score, match_info))

        return results

    @classmethod
    def set_parameters(
        cls,
        k1: float | None = None,
        b: float | None = None,
        weight_name: float | None = None,
        weight_desc: float | None = None,
        weight_kw: float | None = None,
    ) -> None:
        """Set BM25 hyperparameters and field weights.

        Args:
            k1: Term frequency saturation (default: 1.5, range: 1.2-2.0)
            b: Length normalization for the name field (default: 0.75, range: 0.5-0.8)
            weight_name: Name field weight (default: 0.5)
            weight_desc: Description field weight (default: 0.2)
            weight_kw: Keywords field weight (default: 0.3)

        Note: Field weights should sum to 1.0 for proper normalization

        Example:
            >>> # Increase name field importance
            >>> BM25Scorer.set_parameters(weight_name=0.6, weight_desc=0.15, weight_kw=0.25)
            >>>
            >>> # Adjust BM25 parameters
            >>> BM25Scorer.set_parameters(k1=2.0, b=0.5)
        """
        # Update BM25 parameters
        if k1 is not None:
            cls.K1 = k1
        if b is not None:
            cls.B = b

        # Update field weights
        if weight_name is not None:
            cls.WEIGHT_NAME = weight_name
        if weight_desc is not None:
            cls.WEIGHT_DESCRIPTION = weight_desc
        if weight_kw is not None:
            cls.WEIGHT_KEYWORDS = weight_kw

        # Validate weights sum to 1.0 (with tolerance for floating point errors)
        total_weight = cls.WEIGHT_NAME + cls.WEIGHT_DESCRIPTION + cls.WEIGHT_KEYWORDS
        if abs(total_weight - 1.0) > 0.01:
            print(f"Warning: Field weights sum to {total_weight:.3f}, not 1.0. Consider adjusting.")

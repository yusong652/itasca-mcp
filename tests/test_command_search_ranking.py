"""Ranking regressions for command search.

These lock in rankings that an agent (or a paper's worked example) relies on.
The recurring shape: a command with a generic name (``ball attribute``,
``contact model``, ``model solve``) whose real vocabulary lives in its keyword
table must surface for "<category> <keyword>" queries ahead of commands that
merely mention the keyword in a short description.
"""

import pytest

from itasca_mcp.knowledge.query import APISearch, CommandSearch
from itasca_mcp.knowledge.search.keyword_matcher import word_match_quality
from itasca_mcp.knowledge.search.scoring.bm25_scorer import BM25Scorer


def _top(query: str, *, software: str = "pfc", version: str = "7.0", k: int = 5) -> list[str]:
    return [r.document.name for r in CommandSearch.search(query, top_k=k, version=version, software=software)]


@pytest.mark.parametrize("version", ["6.0", "7.0", "9.0"])
def test_ball_velocity_ranks_ball_attribute_first(version: str) -> None:
    assert _top("ball velocity", version=version)[0] == "ball attribute"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # piece attribute setters
        ("ball density", "ball attribute"),
        ("ball spin", "ball attribute"),
        ("ball displacement", "ball attribute"),
        ("clump velocity", "clump attribute"),
        ("clump density", "clump attribute"),
        ("wall displacement", "wall attribute"),
        ("rblock density", "rblock attribute"),
        ("rblock velocity", "rblock attribute"),
        # contact model names are the vocabulary of `contact model`
        ("contact hertz", "contact model"),
        ("contact flatjoint", "contact model"),
        ("contact linearpbond", "contact model"),
        # solve limits / calculation modes
        ("model ratio", "model solve"),
        ("model convergence", "model solve"),
        ("model cfd", "model configure"),
        # recorded quantities
        ("contact force", "contact history"),
        ("ball history velocity", "ball history"),
    ],
)
def test_keyword_vocabulary_queries_rank_owner_first(query: str, expected: str) -> None:
    assert _top(query)[0] == expected


@pytest.mark.parametrize(
    "query",
    ["ball create", "ball fix", "ball generate", "ball delete", "contact property", "model solve", "model cycle"],
)
def test_exact_name_queries_still_rank_first(query: str) -> None:
    assert _top(query)[0] == query


@pytest.mark.parametrize(
    ("query", "expected", "software"),
    [
        ("zone create", "zone create", "flac"),
        ("zone property", "zone property", "flac"),
        # exact name beats a longer sibling ("zone export-data") ...
        ("zone export", "zone export", "flac"),
        ("mpoint initialize", "mpoint initialize", "mpoint"),
        # ... but a query with more words is not hijacked by the shorter name
        ("block face apply remove", "block face-apply-remove", "3dec"),
        ("block create", "block create", "3dec"),
        ("mpoint create", "mpoint create", "mpoint"),
    ],
)
def test_other_engines_name_queries(query: str, expected: str, software: str) -> None:
    assert _top(query, software=software, version="9.0")[0] == expected


@pytest.mark.parametrize(
    ("query", "software"),
    [("zone initialize stress", "flac"), ("mpoint initialize stress", "mpoint")],
)
def test_initialize_stress_keeps_both_setters_on_top(query: str, software: str) -> None:
    """`<x> initialize` carries stress in its keyword vocabulary (stress-xx ...), so both the
    component setter and `<x> initialize-stresses` are correct answers; neither may drop out."""
    prefix = query.rsplit(" ", 1)[0]
    assert set(_top(query, software=software, version="9.0", k=2)) == {prefix, f"{prefix}-stresses"}


@pytest.mark.parametrize(
    ("query", "expected", "software"),
    [
        # zone-level setters, recorders and model/property assignment
        ("zone mohr-coulomb", "zone cmodel", "flac"),
        ("zone cohesion", "zone property", "flac"),
        ("zone fastflow", "zone fluid", "flac"),
        ("zone history displacement", "zone history", "flac"),
        # 3DEC block family
        ("block velocity", "block initialize", "3dec"),
        ("block mohr-coulomb", "block zone-cmodel", "3dec"),
        ("block cohesion", "block property", "3dec"),
        ("block history displacement", "block history", "3dec"),
    ],
)
def test_flac_3dec_keyword_vocabulary_queries_rank_owner_first(query: str, expected: str, software: str) -> None:
    assert _top(query, software=software, version="9.0")[0] == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # `mpoint initialize` is MPoint's attribute setter (no `mpoint attribute`)
        ("mpoint velocity", "mpoint initialize"),
        ("mpoint density", "mpoint initialize"),
        ("mpoint pore pressure", "mpoint initialize"),
        ("mpoint stress", "mpoint initialize"),
        # constitutive model names belong to `mpoint cmodel`, property names to `mpoint property`
        ("mpoint mohr-coulomb", "mpoint cmodel"),
        ("mpoint elastic", "mpoint cmodel"),
        ("mpoint young", "mpoint property"),
        ("mpoint cohesion", "mpoint property"),
        # recorded quantities
        ("mpoint history displacement", "mpoint history"),
        ("node history", "mpoint node-history"),
    ],
)
def test_mpoint_keyword_vocabulary_queries_rank_owner_first(query: str, expected: str) -> None:
    assert _top(query, software="mpoint", version="9.0")[0] == expected


def test_rank_is_position_in_returned_order() -> None:
    results = CommandSearch.search("mpoint velocity", top_k=5, version="9.0", software="mpoint")
    assert [r.rank for r in results] == list(range(1, len(results) + 1))


def test_keywords_field_scores_tag_presence_only() -> None:
    """Keywords are a tag list: a hit is IDF alone, no length or tf effects."""
    assert BM25Scorer.B_KEYWORDS == 0.0
    # description normalization is milder than the name field's
    assert 0.0 < BM25Scorer.B_DESCRIPTION < BM25Scorer.B


def test_partial_matching_direction() -> None:
    """Abbreviations (query shorter) and short inflections only."""
    assert word_match_quality("pos", "position") == 0.8
    assert word_match_quality("balls", "ball") == 0.8
    assert word_match_quality("fixed", "fix") == 0.8
    assert word_match_quality("loc", "velocity") == 0.6
    # a doc token that merely sits inside a long query word is not a hit
    assert word_match_quality("definitelynonexistentkeyword", "defin") == 0.0
    assert word_match_quality("nonexistent", "one") == 0.0


def test_nonsense_query_yields_no_api_results() -> None:
    assert APISearch.search("definitelynonexistentkeyword", top_k=5, software="pfc") == []

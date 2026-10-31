"""Keyword extraction of the shared command-page parser (scripts/corpus/parse_pfc600.py).

Options nested in a keyword's <dd> used to replace the keyword: 'zone create' lost
'point' to its last option 'gridpoint <s>', 'model solve' lost 'mechanical' and
'fish-call'. Nothing downstream notices, so the shape is pinned here.
"""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "corpus" / "parse_pfc600.py"
_spec = importlib.util.spec_from_file_location("parse_pfc600", _SCRIPT)
assert _spec and _spec.loader
parse_pfc600 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parse_pfc600)


def _kwd(kid: str, text: str, body: str) -> str:
    return (
        f'<dl><dt class="sig sig-object fish" id="kwd:{kid}">'
        f'<span class="cmdkey"><span class="pre">{text}</span></span></dt><dd>{body}</dd></dl>'
    )


_PAGE = (
    '<dl><dt class="sig sig-object fish" id="command:zone.create">'
    '<span class="cmdname"><span class="pre">zone create keyword</span></span></dt>'
    "<dd><p>Create zones.</p></dd></dl>"
    + _kwd("zone.create.merge", "merge", "<p>Merge gridpoints.</p>")
    + _kwd(
        "zone.create.point",
        "point keyword",
        "<p>Reference points.</p>"
        + _kwd("zone.create.point.adummy", "v", "<p>Given as a vector.</p>")
        + _kwd("zone.create.point.gridpoint", "gridpoint", "<p>A named gridpoint.</p>"),
    )
    + _kwd("zone.create.size", "size", "<p>Zone counts.</p>")
)


def _keywords() -> list[dict]:
    parser = parse_pfc600.CommandHTMLParser()
    parser.feed(_PAGE)
    return parser.keywords


def test_nested_options_fold_into_their_keyword() -> None:
    keywords = _keywords()
    assert [k["name"] for k in keywords] == ["merge", "point", "size"]
    point = keywords[1]
    assert point["syntax"] == "point {v | gridpoint}"
    assert point["description"] == "Reference points. Options: v: Given as a vector.; gridpoint: A named gridpoint."


def test_plain_keywords_keep_their_shape() -> None:
    keywords = _keywords()
    assert keywords[0] == {"name": "merge", "syntax": "merge", "description": "Merge gridpoints."}
    assert keywords[2] == {"name": "size", "syntax": "size", "description": "Zone counts."}

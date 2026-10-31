"""Generate the 3DEC ``joint-models`` reference category.

Joint (sub-contact) constitutive models are 3DEC's defining reference — the
property vocabulary for ``block contact jmodel assign`` + ``block contact
property``. They have no FLAC/PFC equivalent (FLAC ``constitutive-models`` and
PFC ``contact-models`` cover different physics), so this is authored fresh.

Sources, in order of authority:
- The model list + display names come from the running 3DEC engine
  (``block contact jmodel list``) and the "Constitutive Models in 3DEC" catalog.
- Per-model property keywords come from each model's theory page property table
  (header ``[Parameter, Description, Keyword]``) under
  ``3dec/docproject/source/theory/<dir>/<page>.html``.
- ``elastic`` (no yield, stiffness only), ``power`` (creep page uses a different
  table shape) and ``ratestate`` (not documented in the 9.0 manual) are filled
  from FALLBACK below — only with keywords that are actually documented or are
  the universal joint stiffness terms; nothing is invented. Their ``notes``
  flag the limitation and point at the source.

Output (mirrors flac/references/constitutive-models):
    3dec/references/index.json                      (top index, category entry)
    3dec/references/joint-models/index.json         (category index)
    3dec/references/joint-models/<keyword>.json     (one per model)

Usage:
    uv run python scripts/corpus/generate_3dec_joint_models.py
"""

import json
import re
from pathlib import Path
from typing import Any

DOC = Path("C:/Program Files/Itasca/ItascaSoftware900/exe64/doc/3dec/docproject/source/theory")
SRC_BASE = "https://docs.itascacg.com/itasca900/3dec/docproject/source/theory"
OUT = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/3dec/references")
CAT_DIR = OUT / "joint-models"

# keyword (as `block contact jmodel assign <keyword>`) -> spec.
# ``page`` is the theory page (dir/stem) or None; ``fallback`` supplies property
# rows when the page has no standard [Parameter, Description, Keyword] table.
MODELS: dict[str, dict[str, Any]] = {
    "elastic": {
        "full_name": "Elastic Joint Model",
        "page": "elastic/elastic",
        "fallback": [
            {
                "keyword": "stiffness-normal",
                "symbol": "k_n",
                "description": "joint normal stiffness (STRESS/LENGTH)",
                "type": "FLT",
            },
            {
                "keyword": "stiffness-shear",
                "symbol": "k_s",
                "description": "joint shear stiffness (STRESS/LENGTH)",
                "type": "FLT",
            },
        ],
        "note": "Elastic joints have no yield (infinitely strong); the only properties are the normal and shear stiffnesses.",
    },
    "mohr": {"full_name": "Mohr-Coulomb Joint Model", "page": "mohrcoulomb/mohrcoulomb"},
    "bilinear-mohr": {"full_name": "Bilinear Mohr-Coulomb Joint Model", "page": "bilinear/bilinearmc"},
    "softening-mohr": {"full_name": "Softening-Healing Mohr-Coulomb Joint Model", "page": "softhealmc/softhealmc"},
    "cyjm": {"full_name": "Continuously Yielding Joint Model", "page": "cyjoint/cyjoint"},
    "nonlinear": {"full_name": "Nonlinear Joint Model", "page": "nonlinear/nonlinear"},
    "power": {
        "full_name": "Power-Law Creeping Joint Model",
        "page": "creep/creep",
        "fallback": [
            {
                "keyword": "stiffness-normal",
                "symbol": "k_n",
                "description": "joint normal stiffness (STRESS/LENGTH)",
                "type": "FLT",
            },
            {
                "keyword": "stiffness-shear",
                "symbol": "k_s",
                "description": "joint shear stiffness (STRESS/LENGTH)",
                "type": "FLT",
            },
        ],
        "note": "Power-law (Norton) creep joint model. The creep page documents the rheology rather than a flat property-keyword table; only the universal stiffness terms are listed here — see the source page and 'block contact property' for the full creep parameter set.",
    },
    "ratestate": {
        "full_name": "Rate-State Joint Model",
        "page": None,
        "description": "Rate- and state-dependent friction joint model (laboratory rate-state friction law), available via 'block contact jmodel assign ratestate'.",
        "fallback": [
            {
                "keyword": "stiffness-normal",
                "symbol": "k_n",
                "description": "joint normal stiffness (STRESS/LENGTH)",
                "type": "FLT",
            },
            {
                "keyword": "stiffness-shear",
                "symbol": "k_s",
                "description": "joint shear stiffness (STRESS/LENGTH)",
                "type": "FLT",
            },
        ],
        "note": "Detailed property documentation is not present in the local 9.0 manual; only the universal joint stiffness terms are listed. Use 'block contact property' against the running engine for the full rate-state parameter set.",
    },
}


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", fragment)).strip()


_GREEK = {
    r"\phi": "φ",
    r"\psi": "ψ",
    r"\sigma": "σ",
    r"\tau": "τ",
    r"\Delta": "Δ",
    r"\delta": "δ",
    r"\gamma": "γ",
    r"\beta": "β",
    r"\alpha": "α",
    r"\mu": "μ",
    r"\nu": "ν",
    r"\rho": "ρ",
    r"\theta": "θ",
    r"\lambda": "λ",
    r"\epsilon": "ε",
    r"\eta": "η",
    r"\kappa": "κ",
}


def _strip_latex(s: str) -> str:
    """Render a LaTeX symbol (``\\(\\phi_{res}\\)``) to a readable plain symbol (``φ_res``)."""
    s = s.replace(r"\(", "").replace(r"\)", "").replace("$", "")
    for cmd, ch in _GREEK.items():
        s = s.replace(cmd, ch)
    s = s.replace("{", "").replace("}", "")  # u_{cs} -> u_cs, _{res} -> _res
    s = re.sub(r"\\[a-zA-Z]+", " ", s)  # drop any remaining LaTeX commands
    return re.sub(r"\s+", " ", s).strip()


def _intro(html_text: str) -> str:
    m = re.search(r"<h1>.*?</h1>\s*<p[^>]*>(.*?)</p>", html_text, re.S)
    return _text(m.group(1)) if m else ""


def _property_table(html_text: str) -> list[dict[str, Any]]:
    """Parse the standard [Parameter, Description, Keyword] joint property table."""
    for tbl in re.findall(r"<table.*?</table>", html_text, re.S):
        rows = re.findall(r"<tr.*?</tr>", tbl, re.S)
        if not rows:
            continue
        hdr = [_text(c) for c in re.findall(r"<t[dh].*?</t[dh]>", rows[0], re.S)]
        if hdr[:1] != ["Parameter"] or "Keyword" not in hdr:
            continue
        ki = hdr.index("Keyword")
        di = hdr.index("Description") if "Description" in hdr else 1
        props = []
        for row in rows[1:]:
            cells = [_text(c) for c in re.findall(r"<t[dh].*?</t[dh]>", row, re.S)]
            if len(cells) <= ki or not cells[ki]:
                continue
            props.append(
                {
                    "keyword": cells[ki],
                    "symbol": _strip_latex(cells[0]),
                    "description": cells[di],
                    "type": "FLT",
                }
            )
        return props
    return []


def _search_keywords(model: str, full_name: str, props: list[dict[str, Any]]) -> list[str]:
    toks: list[str] = []
    for t in re.split(r"[\s\-]+", f"{model} {full_name}".lower()):
        t = t.strip()
        if t and t not in toks and t not in {"model", "joint"}:
            toks.append(t)
    toks += ["joint", "constitutive", "jmodel", "subcontact"]
    for p in props:
        if p["keyword"] not in toks:
            toks.append(p["keyword"])
    return toks


def main() -> None:
    CAT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = []

    for keyword, spec in MODELS.items():
        page = spec.get("page")
        description = spec.get("description", "")
        props: list[dict[str, Any]] = []
        source = ""
        if page:
            html_text = (DOC / f"{page}.html").read_text(encoding="utf-8")
            source = f"{SRC_BASE}/{page}.html"
            if not description:
                description = _intro(html_text)
            props = _property_table(html_text)
        if not props:
            props = spec.get("fallback", [])

        group_desc = (
            f"Joint properties for the '{keyword}' joint constitutive model. Assign the model with "
            f"'block contact jmodel assign {keyword} [range ...]', then set these with "
            f"'block contact property <keyword> <value> [range jmodel {keyword}]'."
        )
        item: dict[str, Any] = {
            "model": keyword,
            "full_name": spec["full_name"],
            "search_keywords": _search_keywords(keyword, spec["full_name"], props),
            "description": description,
            "property_groups": [{"name": "Properties", "description": group_desc, "properties": props}],
        }
        if source:
            item["source"] = source
        if spec.get("note"):
            item["note"] = spec["note"]
        item["usage"] = (
            f"block contact jmodel assign {keyword} ; block contact property <prop> <value> [range jmodel {keyword}]"
        )

        (CAT_DIR / f"{keyword}.json").write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", "utf-8")
        catalog.append(
            {
                "name": keyword,
                "file": f"{keyword}.json",
                "full_name": spec["full_name"],
                "description": description[:160],
                "property_count": len(props),
            }
        )
        print(
            f"  {keyword:<16} {spec['full_name']:<42} props={len(props)}{'  (fallback)' if not page or not _property_table_cached(page) else ''}"
        )

    cat_index = {
        "type": "joint_constitutive_model_properties",
        "description": (
            "Reference documentation for 3DEC joint (sub-contact) constitutive model properties — the "
            "property vocabulary for 'block contact jmodel assign' and 'block contact property'."
        ),
        "usage_contexts": [
            "block contact jmodel assign <name> [range ...]",
            "block contact property <prop> <value> [range jmodel <name>]",
            "Python: subcontact.set_model('<name>') ; subcontact.set_prop('<prop>', value)",
        ],
        "property_metadata_fields": {
            "keyword": "Property name used in 'block contact property' commands",
            "symbol": "Mathematical symbol used in the model documentation",
            "description": "Description including physical meaning and units",
            "type": "Coarse data type (FLT=float, BOOL=boolean) — heuristic",
        },
        "models": catalog,
    }
    (CAT_DIR / "index.json").write_text(json.dumps(cat_index, indent=2, ensure_ascii=False) + "\n", "utf-8")

    top = {
        "type": "3dec_references",
        "description": "3DEC reference documentation: syntax elements (property vocabularies) used within commands.",
        "categories": {
            "joint-models": {
                "name": "Joint Constitutive Models",
                "description": (
                    "3DEC joint (sub-contact) constitutive model properties — elastic, mohr, bilinear-mohr, "
                    "softening-mohr, cyjm, nonlinear, power, ratestate. Property vocabulary for "
                    "'block contact jmodel' / 'block contact property'."
                ),
                "directory": "joint-models",
                "index_file": "joint-models/index.json",
                "summary": f"{len(catalog)} 3DEC joint constitutive models — the keywords for 'block contact jmodel assign' + 'block contact property'",
                "usage": "block contact jmodel assign <name> ; block contact property <prop> <value> [range jmodel <name>]",
            }
        },
        "navigation": {
            "root": "List all reference categories",
            "category": "List items in category (e.g., 'joint-models')",
            "item": "Full documentation (e.g., 'joint-models mohr')",
        },
        "notes": [
            "References are syntax elements used within commands, not standalone commands",
            "Use itasca_browse_doc(source='commands', software='3dec') for command syntax",
            "Use itasca_browse_doc(source='reference', software='3dec') for reference documentation",
        ],
    }
    OUT.joinpath("index.json").write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"\nWrote {OUT / 'index.json'} and {CAT_DIR}  ({len(catalog)} models)")


# tiny helper so the print line can note fallback usage without re-reading files
_PT_CACHE: dict[str, bool] = {}


def _property_table_cached(page: str) -> bool:
    if page not in _PT_CACHE:
        html_text = (DOC / f"{page}.html").read_text(encoding="utf-8")
        _PT_CACHE[page] = bool(_property_table(html_text))
    return _PT_CACHE[page]


if __name__ == "__main__":
    main()

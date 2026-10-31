"""FISH intrinsic document adapter for the documentation search system.

Turns ``fish_docs`` entries into :class:`SearchDocument` instances so the
BM25 engine indexes FISH intrinsics exactly like commands and Python APIs.
"""

from __future__ import annotations

from itasca_mcp.knowledge.fish.loader import FishLoader
from itasca_mcp.knowledge.models.document import DocumentType, SearchDocument

# FISH names are abbreviations with no prose around them, so a query written in
# words ("ball position") would otherwise only match on the namespace token.
# Expansions are indexed as keywords; the name field itself stays verbatim.
ABBREVIATIONS: dict[str, tuple[str, ...]] = {
    "pos": ("position",),
    "vel": ("velocity",),
    "disp": ("displacement",),
    "rvel": ("angular", "velocity", "rotational"),
    "spin": ("angular", "velocity"),
    "rdisp": ("rotation", "displacement"),
    "accel": ("acceleration",),
    "num": ("number", "count"),
    "maxid": ("max", "id"),
    "fric": ("friction",),
    "coh": ("cohesion",),
    "ten": ("tension", "tensile", "tensor"),
    "temp": ("temperature",),
    "unbal": ("unbalanced",),
    "app": ("applied",),
    "moi": ("moment", "inertia"),
    "rad": ("radius",),
    "vol": ("volume",),
    "prop": ("property",),
    "extra": ("extra", "variable"),
    "grp": ("group",),
    "isgroup": ("group", "member"),
    "cmodel": ("constitutive", "model", "contact"),
    "gp": ("gridpoint",),
    "dfn": ("fracture", "network"),
    "pp": ("pore", "pressure"),
    "sat": ("saturation",),
    "perm": ("permeability",),
    "stress": ("stress",),
    "strain": ("strain",),
    "str": ("string",),
    "flt": ("float",),
    "int": ("integer",),
    "mat": ("matrix",),
    "min": ("minimum",),
    "max": ("maximum",),
    "inc": ("increment",),
    "tot": ("total",),
    "fos": ("factor", "safety"),
    "comp": ("component",),
}


_REVERSE: dict[str, set[str]] = {}
for _abbr, _words in ABBREVIATIONS.items():
    for _w in _words:
        _REVERSE.setdefault(_w, set()).add(_abbr)


def expand_query(query: str) -> str:
    """Append the FISH abbreviations of any spelled-out query words.

    The scorer doubles a document's score when its last name segment is a query
    token, so "ball position" must also carry "pos" for ``ball.pos`` to receive
    the same boost as ``ball.zone.ball.ball`` gets from "ball".
    """
    words = query.lower().split()
    extra = [a for w in words for a in sorted(_REVERSE.get(w, ())) if a not in words]
    return " ".join(words + extra)


class FishDocumentAdapter:
    """Adapter for FISH intrinsics (one document per dotted name)."""

    @staticmethod
    def load_all(*, software: str, version: str | None = None) -> list[SearchDocument]:
        """Every intrinsic the engine lists, optionally only those present in ``version``."""
        documents: list[SearchDocument] = []
        for name, entry in FishLoader.entries(software=software).items():
            if version is not None and not FishLoader.available(entry, version):
                continue
            parts = name.split(".")
            # Signature and return type are display-only (``syntax`` / metadata): indexed,
            # their ``ball_pnt`` tokens repeat the name and let ``ball.zone.ball.ball``
            # outrank ``ball.pos`` on a "ball position" query.
            bits: list[str] = []
            if entry.get("description"):  # the manual's one-liner: lets prose queries reach abbreviated names
                bits.append(entry["description"])
            if entry.get("family"):
                bits.append(entry["family"])
            if entry.get("settable"):
                bits.append("assignable")
            expansions = [w for p in parts for w in ABBREVIATIONS.get(p, ())]
            family = [entry["family"]] if entry.get("family") else []
            keywords = list(dict.fromkeys(parts + expansions + family))
            documents.append(
                SearchDocument(
                    name=name,
                    doc_type=DocumentType.FISH,
                    title=name,
                    description="; ".join(bits),
                    keywords=keywords,
                    category=entry["namespace"],
                    syntax=entry.get("signature") or name,
                    examples=[],
                    metadata={
                        "returns": entry.get("returns"),
                        "args": entry.get("args", []),
                        "settable": entry.get("settable"),
                        "versions": entry.get("versions", {}),
                        "doc": entry.get("doc"),
                        "scope": entry.get("scope"),
                        "description": entry.get("description"),
                    },
                )
            )
        return documents

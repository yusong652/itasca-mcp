"""Loader for the ``fish_docs`` corpus (FISH intrinsic trees).

FISH intrinsics form a purely lexical tree: ``ball`` is a namespace (not a
symbol), ``ball.pos`` is a function that is also the prefix of ``ball.pos.x``.
The corpus stores one flat file per top-level namespace (see
``scripts/corpus/generate_fish_docs.py``); this loader rebuilds the tree from
the dotted names and answers "what is at this prefix" for browsing and "every
entry of this engine" for search.

Per-engine ``fish_docs/index.json`` files hold RESOURCES-root-relative file
pointers, so kernel namespaces live once under ``_common/fish_docs`` and each
engine's index decides whether it lists them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, cast

from itasca_mcp.knowledge.config import fish_index_path, resolve


class FishLoader:
    """Cached access to the FISH intrinsic corpus of one engine."""

    @staticmethod
    @lru_cache(maxsize=8)
    def load_index(*, software: str) -> dict[str, Any]:
        path = fish_index_path(software)
        if not path.exists():
            raise FileNotFoundError(f"FISH index not found: {path}")
        with open(path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    @lru_cache(maxsize=128)
    def _load_file(rel_path: str) -> dict[str, Any]:
        with open(resolve(rel_path), encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    @lru_cache(maxsize=8)
    def entries(*, software: str) -> dict[str, dict[str, Any]]:
        """name -> entry for every namespace the engine's index lists.

        Each entry is tagged with its ``namespace`` and ``scope`` ("common" or the
        owning engine) so callers never need the index again.
        """
        index = FishLoader.load_index(software=software)
        out: dict[str, dict[str, Any]] = {}
        for ns, meta in index.get("namespaces", {}).items():
            data = FishLoader._load_file(meta["file"])
            for raw in data.get("entries", []):
                entry = dict(raw)
                entry["namespace"] = ns
                entry["scope"] = meta.get("scope", "common")
                out[entry["name"]] = entry
        return out

    @staticmethod
    @lru_cache(maxsize=8)
    def _children(*, software: str) -> dict[str, tuple[str, ...]]:
        """prefix -> direct child node names; the empty prefix is the root."""
        kids: dict[str, set[str]] = {}
        for name in FishLoader.entries(software=software):
            parts = name.split(".")
            for i in range(len(parts)):
                parent = ".".join(parts[:i])
                kids.setdefault(parent, set()).add(".".join(parts[: i + 1]))
        return {k: tuple(sorted(v)) for k, v in kids.items()}

    # -- node queries ---------------------------------------------------------

    @staticmethod
    def get(name: str, *, software: str) -> dict[str, Any] | None:
        return FishLoader.entries(software=software).get(name)

    @staticmethod
    def children(prefix: str, *, software: str) -> list[str]:
        return list(FishLoader._children(software=software).get(prefix, ()))

    @staticmethod
    def is_node(name: str, *, software: str) -> bool:
        """True when ``name`` is an intrinsic or a prefix of one."""
        return name in FishLoader.entries(software=software) or name in FishLoader._children(software=software)

    @staticmethod
    def available(entry: dict[str, Any], version: str | None) -> bool:
        """Version gate; kernel entries carry the union view across engines."""
        if version is None:
            return True
        return bool(entry.get("versions", {}).get(version, False))

    @staticmethod
    def available_in(entry: dict[str, Any]) -> list[str]:
        return [v for v, ok in entry.get("versions", {}).items() if ok]

    @staticmethod
    def has_available_descendant(prefix: str, version: str | None, *, software: str) -> bool:
        """Whether anything at or below ``prefix`` exists in ``version``."""
        if version is None:
            return FishLoader.is_node(prefix, software=software)
        stack = [prefix]
        while stack:
            node = stack.pop()
            entry = FishLoader.get(node, software=software)
            if entry is not None and FishLoader.available(entry, version):
                return True
            stack.extend(FishLoader.children(node, software=software))
        return False

    @staticmethod
    def count_available(prefix: str, version: str | None, *, software: str) -> int:
        """Number of intrinsics at or below ``prefix`` that exist in ``version``."""
        total = 0
        stack = [prefix]
        while stack:
            node = stack.pop()
            entry = FishLoader.get(node, software=software)
            if entry is not None and FishLoader.available(entry, version):
                total += 1
            stack.extend(FishLoader.children(node, software=software))
        return total

    @staticmethod
    def namespaces(*, software: str, version: str | None = None) -> list[dict[str, Any]]:
        """Top-level namespaces from the engine index, dropping ones empty in ``version``."""
        index = FishLoader.load_index(software=software)
        out = []
        for ns, meta in index.get("namespaces", {}).items():
            count = meta.get("available", {}).get(version, meta.get("count", 0)) if version else meta.get("count", 0)
            if version and not count:
                continue
            out.append({"name": ns, "scope": meta.get("scope", "common"), "count": count})
        return out

    @staticmethod
    def suggest(name: str, *, software: str, limit: int = 8) -> list[str]:
        """Names sharing the longest known prefix with ``name``; for not-found errors."""
        parts = name.split(".")
        while parts:
            prefix = ".".join(parts)
            if FishLoader.is_node(prefix, software=software):
                kids = FishLoader.children(prefix, software=software)
                return ([prefix] if FishLoader.get(prefix, software=software) else []) + kids[:limit]
            parts.pop()
        return [ns["name"] for ns in FishLoader.namespaces(software=software)][:limit]

    @staticmethod
    def clear_cache() -> None:
        FishLoader.load_index.cache_clear()
        FishLoader._load_file.cache_clear()
        FishLoader.entries.cache_clear()
        FishLoader._children.cache_clear()

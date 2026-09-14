"""Data loading layer for Itasca reference documentation.

This module loads reference documentation from JSON files with caching
for performance.

Supports two item layouts:
- File-based: {category}/{item}.json (2-level: category → item)
- Directory-based: {category}/{item}/index.json (3-level: category → item → sub-item)

Responsibilities:
- Load references index (categories: contact-models, range-elements, plot-items)
- Load individual reference item documentation
- Load sub-item documentation for directory-based items
- Cache loaded data to avoid repeated I/O
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from itasca_mcp.knowledge.config import SUPPORTED_SOFTWARE, references_root, resolve


class ReferenceLoader:
    """Loads and caches Itasca reference documentation.

    This class provides static methods for loading reference docs
    (contact models, range elements). All methods use caching
    to avoid repeated file I/O.
    """

    @staticmethod
    @lru_cache(maxsize=8)
    def load_index(*, software: str) -> dict[str, Any]:
        """Load the main references index file.

        Returns:
            References index with:
                - categories: Available reference categories
                - navigation: Navigation hints
                - notes: Usage notes

        Example:
            >>> index = ReferenceLoader.load_index()
            >>> categories = index["categories"]
            >>> "contact-models" in categories
            True
        """
        index_path = references_root(software) / "index.json"
        if not index_path.exists():
            return {}

        with open(index_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    def load_category_index(category: str, *, software: str) -> dict[str, Any] | None:
        """Load index for a specific reference category.

        Args:
            category: Category name (e.g., "contact-models", "range-elements")

        Returns:
            Category index dict or None if not found

        Example:
            >>> index = ReferenceLoader.load_category_index("contact-models")
            >>> len(index["models"])
            5
            >>> index = ReferenceLoader.load_category_index("range-elements")
            >>> len(index["elements"])
            24
        """
        refs_index = ReferenceLoader.load_index(software=software)
        categories = refs_index.get("categories", {})

        if category not in categories:
            return None

        cat_data = categories[category]
        index_file = cat_data.get("index_file")
        if not index_file:
            return None

        index_path = references_root(software) / index_file
        if not index_path.exists():
            return None

        with open(index_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    def load_item_doc(category: str, item_name: str, *, software: str) -> dict[str, Any] | None:
        """Load documentation for a specific reference item.

        Args:
            category: Category name (e.g., "contact-models", "range-elements")
            item_name: Item name (e.g., "linear", "cylinder", "group")

        Returns:
            Item documentation dict or None if not found

        Example:
            >>> doc = ReferenceLoader.load_item_doc("contact-models", "linear")
            >>> doc["full_name"]
            "Linear Model"
            >>> doc = ReferenceLoader.load_item_doc("range-elements", "cylinder")
            >>> doc["name"]
            "cylinder"
        """
        refs_index = ReferenceLoader.load_index(software=software)
        categories = refs_index.get("categories", {})

        if category not in categories:
            return None

        cat_data = categories[category]
        directory = cat_data.get("directory", category)

        # Shared-content borrow: if the category index gives this item a
        # RESOURCES-root-relative ``file`` pointer (e.g. into ``_common/``),
        # resolve it there. This lets engines that share a kernel reference set
        # (FLAC/3DEC zone constitutive models) point at one copy instead of
        # duplicating it, mirroring how command docs borrow ``_common``.
        pointer = ReferenceLoader._item_file_pointer(category, item_name, software=software)
        if pointer:
            with open(pointer, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))

        # Try file-based item first: {category}/{item}.json
        doc_path = references_root(software) / directory / f"{item_name}.json"
        if doc_path.exists():
            with open(doc_path, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))

        # Try directory-based item: {category}/{item}/index.json
        dir_index = references_root(software) / directory / item_name / "index.json"
        if dir_index.exists():
            with open(dir_index, encoding="utf-8") as f:
                return cast(dict[str, Any], json.load(f))

        return None

    # RESOURCES-root prefixes that mark a ``file`` pointer as cross-root (vs a
    # bare filename relative to the category directory).
    _ROOT_PREFIXES = ("_common/", *(f"{sw}/" for sw in SUPPORTED_SOFTWARE))

    @staticmethod
    def _item_file_pointer(category: str, item_name: str, *, software: str) -> Path | None:
        """RESOURCES-root-relative ``file`` for an item, resolved to a real path.

        Looks the item up in the category index and, if its ``file`` is a
        cross-root pointer (starts with ``_common/`` or ``<software>/``),
        resolves it against the RESOURCES root. Returns None when there is no
        such pointer (the caller then uses the legacy directory-based layout).
        """
        cat_index = ReferenceLoader.load_category_index(category, software=software)
        if not cat_index:
            return None
        for value in cat_index.values():
            if not isinstance(value, list):
                continue
            for entry in value:
                if not isinstance(entry, dict):
                    continue
                if item_name in (entry.get("name"), entry.get("model"), entry.get("element")):
                    file_ref = entry.get("file")
                    if isinstance(file_ref, str) and file_ref.startswith(ReferenceLoader._ROOT_PREFIXES):
                        path = resolve(file_ref)
                        return path if path.exists() else None
                    return None
        return None

    @staticmethod
    def is_directory_item(category: str, item_name: str, *, software: str) -> bool:
        """Check if an item uses directory-based layout (supports sub-items).

        Returns:
            True if {category}/{item}/index.json exists, False otherwise.
        """
        refs_index = ReferenceLoader.load_index(software=software)
        categories = refs_index.get("categories", {})
        if category not in categories:
            return False
        category_meta = categories[category]
        raw_directory = category_meta.get("directory") if isinstance(category_meta, dict) else None
        directory = raw_directory if isinstance(raw_directory, str) and raw_directory else category
        return (references_root(software) / directory / item_name / "index.json").exists()

    @staticmethod
    def load_sub_item_doc(category: str, item_name: str, sub_item: str, *, software: str) -> dict[str, Any] | None:
        """Load documentation for a sub-item within a directory-based item.

        Args:
            category: Category name (e.g., "plot-items")
            item_name: Item name (e.g., "ball")
            sub_item: Sub-item name (e.g., "color-by")

        Returns:
            Sub-item documentation dict or None if not found.

        Example:
            >>> doc = ReferenceLoader.load_sub_item_doc("plot-items", "ball", "color-by")
            >>> doc["name"]
            "color-by"
        """
        refs_index = ReferenceLoader.load_index(software=software)
        categories = refs_index.get("categories", {})
        if category not in categories:
            return None
        directory = categories[category].get("directory", category)

        doc_path = references_root(software) / directory / item_name / f"{sub_item}.json"
        if not doc_path.exists():
            return None

        with open(doc_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    def _entry_available(entry: dict[str, Any], version: str | None) -> bool:
        """Whether an index entry is available in the requested version.

        Entries without an ``availability`` map are version-agnostic and
        treated as available in every version (backward compatible).
        """
        if version is None:
            return True
        availability = entry.get("availability")
        if not isinstance(availability, dict):
            return True
        return bool(availability.get(version, False))

    @staticmethod
    def get_item_list(category: str, version: str | None = None, *, software: str) -> list[dict[str, Any]]:
        """Get list of items in a reference category.

        Args:
            category: Category name (e.g., "contact-models", "range-elements")
            version: Optional engine version (e.g. "6.0"). When given, items
                whose ``availability`` map excludes that version are filtered
                out. Items without an ``availability`` map are kept.

        Returns:
            List of item metadata dicts

        Example:
            >>> items = ReferenceLoader.get_item_list("contact-models")
            >>> len(items) >= 5
            True
            >>> items = ReferenceLoader.get_item_list("range-elements")
            >>> len(items)
            24
        """
        index = ReferenceLoader.load_category_index(category, software=software)
        if not index:
            return []

        # Each category uses its own list key: "models", "elements", "items".
        # Match those by name. The old code took whichever list-of-dicts came
        # first in the file, so any sibling list added later -- a set of shared
        # properties, a table of traps -- silently became "the items" and the
        # real list disappeared from browse output.
        items: list[dict[str, Any]] = []
        for key in ("models", "elements", "items"):
            value = index.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                items = cast(list[dict[str, Any]], value)
                break
        else:  # unknown category shape: fall back to the first list of dicts
            for _key, value in index.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    items = cast(list[dict[str, Any]], value)
                    break

        if version is None:
            return items
        return [i for i in items if ReferenceLoader._entry_available(i, version)]

    @staticmethod
    def item_availability(category: str, item_name: str, *, software: str) -> dict[str, bool] | None:
        """Return an item's availability map, or None if version-agnostic.

        Used by the browse tool to gate a model behind a requested version.
        """
        doc = ReferenceLoader.load_item_doc(category, item_name, software=software)
        if not doc:
            return None
        availability = doc.get("availability")
        if isinstance(availability, dict):
            return cast(dict[str, bool], availability)
        return None

    @staticmethod
    def clear_cache() -> None:
        """Clear all cached data.

        Useful for testing or when documentation files are updated.
        """
        ReferenceLoader.load_index.cache_clear()

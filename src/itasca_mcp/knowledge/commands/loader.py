"""Data loading layer for Itasca command documentation.

This module loads command documentation from JSON files with caching
for performance.

Responsibilities:
- Load index.json (command catalog metadata)
- Load individual command documentation files
- Resolve versioned command schemas into a stable runtime shape
- Cache loaded data to avoid repeated I/O
"""

import json
from functools import lru_cache
from typing import Any, cast

from itasca_mcp.knowledge.config import command_index_path, resolve
from itasca_mcp.utils import supported_doc_versions


class CommandLoader:
    """Loads and caches Itasca command documentation.

    This class provides static methods for loading command docs.
    All methods use caching to avoid repeated file I/O.
    """

    DEFAULT_VERSION = "7.0"

    @staticmethod
    @lru_cache(maxsize=8)
    def load_index(*, software: str) -> dict[str, Any]:
        """Load the main command index file with caching.

        The index file contains:
        - categories: command categories with metadata
        - commands: command catalog entries with summary metadata
        - python_sdk_alternatives: Command to Python SDK mappings
        - command_patterns: Common command patterns

        Returns:
            Dict containing index data structure

        Raises:
            FileNotFoundError: If index.json doesn't exist

        Example:
            >>> index = CommandLoader.load_index()
            >>> categories = index["categories"]
            >>> len(categories)
            7
            >>> "ball" in categories
            True
        """
        index_path = command_index_path(software)
        if not index_path.exists():
            raise FileNotFoundError(f"Command index file not found: {index_path}")

        with open(index_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    @lru_cache(maxsize=256)
    def _load_doc_file(command_file: str) -> dict[str, Any] | None:
        """Load a raw command documentation file by RESOURCES-root-relative path."""
        doc_path = resolve(command_file)
        if not doc_path.exists():
            return None

        with open(doc_path, encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    VERSION_LABELS = ("6.0", "7.0", "9.0")

    @staticmethod
    def _is_version_map(value: Any) -> bool:
        """A value keyed purely by version labels varies by version."""
        return isinstance(value, dict) and bool(value) and set(value) <= set(CommandLoader.VERSION_LABELS)

    @staticmethod
    def _home_versions(command_file: str) -> list[str]:
        """Versions a doc covers when it carries no availability: its home tree's set."""
        home = command_file.split("/", 1)[0]
        if home == "_common":
            return list(CommandLoader.VERSION_LABELS)
        return sorted(supported_doc_versions(home))

    @staticmethod
    def _filter_entries(entries: list[Any], version: str) -> list[Any]:
        """Keep the keyword/example entries this version has; resolve their maps.

        An entry's ``availability.versions`` is consumed here (it is routing, like
        the engines tag); any other availability content stays on the entry.
        """
        served = []
        for entry in entries:
            if not isinstance(entry, dict):
                served.append(entry)
                continue
            availability = entry.get("availability")
            versions = availability.get("versions") if isinstance(availability, dict) else None
            if isinstance(versions, list) and version not in versions:
                continue
            resolved: dict[str, Any] = {}
            for key, value in entry.items():
                if key == "availability":
                    rest = {k: v for k, v in value.items() if k != "versions"}
                    if rest:
                        resolved[key] = rest
                    continue
                if CommandLoader._is_version_map(value):
                    if version in value:
                        resolved[key] = value[version]
                    continue
                resolved[key] = value
            served.append(resolved)
        return served

    @staticmethod
    def _resolve_versioned_doc(
        doc: dict[str, Any],
        version: str,
        allowed_versions: frozenset[str] | None,
        home_versions: list[str],
    ) -> dict[str, Any]:
        """Resolve a merged command doc to the stable runtime shape for one version.

        The doc's ``availability.versions`` (or its home tree's version set) says
        where it exists; ``allowed_versions`` restricts the advertised list to the
        requesting engine's corpus. Version-mapped field values resolve to this
        version's text, or drop out when the version has none. A top-level
        ``available: false`` doc (documented but engine-rejected) serves as
        negative knowledge for every version.
        """
        availability = doc.get("availability")
        doc_versions = availability.get("versions", home_versions) if isinstance(availability, dict) else home_versions
        advertised = [v for v in doc_versions if allowed_versions is None or v in allowed_versions]

        if doc.get("available") is False:
            resolved = {k: v for k, v in doc.items() if k != "availability"}
            resolved["versions"] = []  # documented but engine-rejected: no available version
            return resolved

        # A version the doc documents resolves even when the requesting engine's
        # corpus does not cover it (the tools coerce versions upstream); the
        # advertised list stays the engine's own.
        if version not in doc_versions:
            raise KeyError(version)

        resolved = {}
        for key, value in doc.items():
            if key == "availability":
                resolved["versions"] = advertised
                continue
            if CommandLoader._is_version_map(value):
                if version in value:
                    resolved[key] = value[version]
                continue
            resolved[key] = value
        resolved.setdefault("versions", advertised)
        for field in ("keywords", "examples"):
            if isinstance(resolved.get(field), list):
                resolved[field] = CommandLoader._filter_entries(resolved[field], version)
        return resolved

    @staticmethod
    def load_command_doc(
        category: str,
        command_name: str,
        version: str = DEFAULT_VERSION,
        *,
        software: str,
    ) -> dict[str, Any] | None:
        """Load documentation for a specific command.

        Args:
            category: Command category (e.g., "ball", "contact", "model")
            command_name: Command name (e.g., "create", "property", "cycle")
            version: engine version string to resolve (defaults to 7.0)

        Returns:
            Command documentation dict with fields:
                - command: Full command name
                - syntax: Command syntax
                - description: Detailed description
                - parameters: Parameter definitions
                - examples: Usage examples
                - notes: Additional notes
                - related_commands: Related commands
                - python_alternative: Python SDK alternative (if available)

                - versions: Available version strings

            Returns None if command/category not found.

        Raises:
            KeyError: If the requested version is not present in the command doc

        Example:
            >>> doc = CommandLoader.load_command_doc("ball", "create")
            >>> doc["syntax"]
            "ball create <keyword> ..."
            >>> "description" in doc
            True
        """
        index = CommandLoader.load_index(software=software)

        # Find command file path from index
        categories = index.get("categories", {})
        if category not in categories:
            return None

        category_data = categories[category]
        commands = category_data.get("commands", [])

        # Find matching command
        command_file = None
        for cmd in commands:
            if cmd["name"] == command_name:
                command_file = cmd.get("file")
                break

        if not command_file:
            return None

        # Load and resolve command documentation
        raw_doc = CommandLoader._load_doc_file(command_file)
        if raw_doc is None:
            return None

        resolved = CommandLoader._resolve_versioned_doc(
            raw_doc, version, supported_doc_versions(software), CommandLoader._home_versions(command_file)
        )
        return CommandLoader._scope_keywords(resolved, software)

    @staticmethod
    def _keyword_engines(keyword: Any) -> list[str] | None:
        if not isinstance(keyword, dict):
            return None
        availability = keyword.get("availability")
        engines = availability.get("engines") if isinstance(availability, dict) else None
        return engines if isinstance(engines, list) else None

    @staticmethod
    def _scope_keywords(doc: dict[str, Any], software: str) -> dict[str, Any]:
        """Keep only the keywords a shared doc tags for this engine.

        A ``_common`` doc lists every product's variants (``fish callback`` names zone,
        block and ball events alike); a keyword carrying ``availability.engines`` is
        served to those engines only, untagged keywords to all. The engines tag is
        consumed here: the served entry keeps any other availability content.
        """
        keywords = doc.get("keywords")
        if not isinstance(keywords, list) or not any(CommandLoader._keyword_engines(k) for k in keywords):
            return doc
        scoped = []
        for keyword in keywords:
            engines = CommandLoader._keyword_engines(keyword)
            if engines is None:
                scoped.append(keyword)
                continue
            if software not in engines:
                continue
            availability = {key: value for key, value in keyword["availability"].items() if key != "engines"}
            served = {key: value for key, value in keyword.items() if key != "availability"}
            if availability:
                served["availability"] = availability
            scoped.append(served)
        return {**doc, "keywords": scoped}

    @staticmethod
    def get_all_commands(*, software: str) -> list[dict[str, Any]]:
        """Get all commands from all categories.

        Returns:
            List of command metadata dicts, each containing:
                - name: Command name
                - category: Category name
                - file: File path
                - short_description: Brief description
                - syntax: Command syntax
                - python_available: Python SDK availability

        Example:
            >>> commands = CommandLoader.get_all_commands()
            >>> len(commands)
            115
            >>> commands[0]["category"] in ["ball", "wall", "clump", ...]
            True
        """
        index = CommandLoader.load_index(software=software)
        categories = index.get("categories", {})

        all_commands = []
        for category_name, category_data in categories.items():
            for cmd in category_data.get("commands", []):
                all_commands.append({**cmd, "category": category_name})

        return all_commands

    @staticmethod
    def clear_cache() -> None:
        """Clear all cached data.

        Useful for testing or when documentation files are updated.
        """
        CommandLoader.load_index.cache_clear()
        CommandLoader._load_doc_file.cache_clear()

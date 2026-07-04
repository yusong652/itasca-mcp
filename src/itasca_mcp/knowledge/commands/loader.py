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

    @staticmethod
    def _resolve_versioned_doc(
        doc: dict[str, Any], version: str, allowed_versions: frozenset[str] | None = None
    ) -> dict[str, Any]:
        """Resolve a possibly-versioned command doc to a stable runtime shape.

        ``allowed_versions`` restricts the advertised ``versions`` list to what the
        requesting engine's docs cover — shared ``_common`` docs carry keys for
        every engine (e.g. 6.0 for PFC) that must not leak into engines whose
        corpus does not include that version (e.g. FLAC).
        """
        versions = doc.get("versions")
        if not isinstance(versions, dict):
            if version != CommandLoader.DEFAULT_VERSION:
                raise KeyError(version)

            resolved = dict(doc)
            resolved["versions"] = [CommandLoader.DEFAULT_VERSION]
            return resolved

        if version not in versions:
            raise KeyError(version)

        resolved = {k: v for k, v in doc.items() if k != "versions"}
        resolved["versions"] = [v for v in versions if allowed_versions is None or v in allowed_versions]

        version_doc = versions[version]
        if version_doc.get("available") is False:
            resolved["available"] = False
            return resolved

        resolved.update(version_doc)
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

        return CommandLoader._resolve_versioned_doc(raw_doc, version, supported_doc_versions(software))

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

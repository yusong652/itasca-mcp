"""Command document adapter for Itasca documentation search system.

This module converts Itasca command documentation from the CommandLoader format
into unified SearchDocument models for search.

Note: Model properties are handled separately via itasca_browse_doc(source='reference') tool.
"""

from itasca_mcp.knowledge.commands.loader import CommandLoader
from itasca_mcp.knowledge.models import DocumentType, SearchDocument


class CommandDocumentAdapter:
    """Adapter for Itasca command documentation.

    Converts command data from CommandLoader into unified SearchDocument format.
    This enables:
    - Consistent interface for search engines
    - Separation of data loading and search logic

    Note: For contact model properties, use itasca_browse_doc(source='reference') tool directly.

    Usage:
        >>> documents = CommandDocumentAdapter.load_commands()
        >>> len(documents)
        115  # 115 commands across 7 categories
    """

    @staticmethod
    def load_commands(version: str = CommandLoader.DEFAULT_VERSION, *, software: str) -> list[SearchDocument]:
        """Load all Itasca command documents.

        Returns:
            List of SearchDocument instances for all commands

        Example:
            >>> docs = CommandDocumentAdapter.load_commands()
            >>> doc = docs[0]
            >>> doc.name
            'ball create'
            >>> doc.doc_type
            <DocumentType.COMMAND: 'command'>
        """
        documents = []
        all_commands = CommandLoader.get_all_commands(software=software)

        for cmd_meta in all_commands:
            category = cmd_meta["category"]
            cmd_name = cmd_meta["name"]

            # Load full command documentation. A KeyError means this command's
            # doc has no entry for the requested version (some engines, e.g. FLAC,
            # omit older-version keys entirely rather than marking available=False),
            # so it is simply not part of this version's corpus.
            try:
                cmd_doc = CommandLoader.load_command_doc(category, cmd_name, version, software=software)
            except KeyError:
                continue
            if not cmd_doc or cmd_doc.get("available") is False:
                continue

            # Convert to SearchDocument
            doc = SearchDocument(
                name=f"{category} {cmd_name}",
                doc_type=DocumentType.COMMAND,
                title=cmd_doc.get("command", f"{category} {cmd_name}"),
                description=cmd_doc.get("description", ""),
                keywords=cmd_doc.get("search_keywords", []),
                category=category,
                syntax=cmd_doc.get("syntax"),
                examples=cmd_doc.get("examples", []),
                metadata={
                    "python_available": cmd_doc.get("python_sdk_alternative", {}).get("available", False),
                    "file": cmd_meta.get("file"),
                    "short_description": cmd_meta.get("short_description", ""),
                    "version": version,
                },
            )
            documents.append(doc)

        return documents

    # Alias for backward compatibility
    load_all = load_commands

    @staticmethod
    def load_by_id(
        doc_id: str, version: str = CommandLoader.DEFAULT_VERSION, *, software: str
    ) -> SearchDocument | None:
        """Load a specific command document by ID.

        Args:
            doc_id: Document ID in "category command" format (e.g., "ball create")

        Returns:
            SearchDocument instance or None if not found

        Example:
            >>> doc = CommandDocumentAdapter.load_by_id("ball create")
            >>> doc.title
            'ball create'
        """
        if " " not in doc_id:
            return None

        category, cmd_name = doc_id.split(" ", 1)
        try:
            cmd_doc = CommandLoader.load_command_doc(category, cmd_name, version, software=software)
        except KeyError:
            return None

        if not cmd_doc or cmd_doc.get("available") is False:
            return None

        return SearchDocument(
            name=doc_id,
            doc_type=DocumentType.COMMAND,
            title=cmd_doc.get("command", doc_id),
            description=cmd_doc.get("description", ""),
            keywords=cmd_doc.get("search_keywords", []),
            category=category,
            syntax=cmd_doc.get("syntax"),
            examples=cmd_doc.get("examples", []),
            metadata={
                "python_available": cmd_doc.get("python_sdk_alternative", {}).get("available", False),
                "version": version,
            },
        )

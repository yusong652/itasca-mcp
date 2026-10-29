"""Python API document adapter for Itasca documentation search system.

This module converts Python SDK API documentation from the PythonAPILoader
format into unified SearchDocument models for search.
"""

from itasca_mcp.knowledge.models.document import DocumentType, SearchDocument
from itasca_mcp.knowledge.python_api.loader import PythonAPILoader


class PythonAPIDocumentAdapter:
    """Adapter for Python API documentation.

    Converts Python SDK API data from PythonAPILoader into unified
    SearchDocument format. This enables:
    - Independent search for Python APIs
    - Consistent interface with command search
    - Separation of data loading and search logic

    Design:
    - Only function/method APIs (not module-level docs)
    - DocumentType.PYTHON_API for all entries
    - Metadata preserves signature and parameter info

    Usage:
        >>> # Load all API documents
        >>> documents = PythonAPIDocumentAdapter.load_all()
        >>> len(documents)
        100  # Approximate count

        >>> # Example document
        >>> doc = documents[0]
        >>> doc.name
        'itasca.ball.create'
        >>> doc.doc_type
        <DocumentType.PYTHON_API: 'python_api'>
    """

    @staticmethod
    def load_all(*, software: str) -> list[SearchDocument]:
        """Load all Python API documents.

        Returns:
            List of SearchDocument instances for all APIs

        Note:
            This loads function/method APIs only, not module-level docs.
            Module queries are handled separately by PythonAPILoader.

        Example:
            >>> docs = PythonAPIDocumentAdapter.load_all()
            >>> api_doc = docs[0]
            >>> api_doc.name
            'itasca.ball.create'
            >>> api_doc.syntax
            'itasca.ball.create(radius, pos=None)'
        """
        documents = []
        index = PythonAPILoader.load_index(software=software)
        quick_ref = index.get("quick_ref", {})
        all_keywords = PythonAPILoader.load_all_keywords(software=software)

        # Iterate through all API entries in quick_ref
        for api_name, file_ref in quick_ref.items():
            # Load the API documentation
            api_doc = PythonAPILoader.load_api_doc(api_name, software=software)

            if not api_doc:
                continue

            # Skip module-level docs (they have "type": "module")
            if api_doc.get("type") == "module":
                continue

            # Extract category from API name
            # Examples:
            # - "itasca.ball.create" → category = "itasca.ball"
            # - "itasca.ball.Ball.vel" → category = "itasca.ball"
            # - "itasca.BallBallContact.gap" → category = "itasca.contact"
            category = PythonAPIDocumentAdapter._extract_category(api_name)

            # Build description from API doc
            description = api_doc.get("description", "")

            # Add parameter information to description for better search
            parameters = api_doc.get("parameters", [])
            if parameters:
                param_names = [p.get("name", "") for p in parameters]
                description += f"\n\nParameters: {', '.join(param_names)}"

            # Get keywords from the keywords index (loaded once above)
            keywords = []
            for keyword, api_list in all_keywords.items():
                if api_name in api_list:
                    keywords.append(keyword)

            # Convert to SearchDocument
            doc = SearchDocument(
                name=api_name,
                doc_type=DocumentType.PYTHON_API,
                title=api_name,
                description=description,
                keywords=keywords,
                category=category,
                syntax=api_doc.get("signature", api_name),
                examples=[{"code": ex} if isinstance(ex, str) else ex for ex in api_doc.get("examples", [])],
                metadata={
                    "file_ref": file_ref,
                    "returns": api_doc.get("returns", ""),
                    "limitations": api_doc.get("limitations", []),
                    "fallback_commands": api_doc.get("fallback_commands", []),
                    "see_also": api_doc.get("see_also", []),
                },
            )
            documents.append(doc)

        return documents

    @staticmethod
    def _extract_category(api_name: str) -> str:
        """Extract category from API name.

        Args:
            api_name: Full API path (e.g., "itasca.ball.create", "Ball.vel")

        Returns:
            Category string (e.g., "itasca.ball", "itasca.contact")

        Examples:
            >>> PythonAPIDocumentAdapter._extract_category("itasca.ball.create")
            'itasca.ball'
            >>> PythonAPIDocumentAdapter._extract_category("itasca.ball.Ball.vel")
            'itasca.ball'
            >>> PythonAPIDocumentAdapter._extract_category("itasca.BallBallContact.gap")
            'itasca.contact'
        """
        # Import contact types for mapping
        try:
            from itasca_mcp.knowledge.python_api.types.contact import ALL_CONTACT_TYPES
        except ImportError:
            ALL_CONTACT_TYPES = []

        # Check if it's a Contact type (e.g., BallBallContact, BallFacetContact)
        parts = api_name.split(".")
        if len(parts) >= 2:
            # Check if second part is a Contact type
            if parts[1] in ALL_CONTACT_TYPES:
                return "itasca.contact"

        # Standard module function: itasca.ball.create → itasca.ball
        if api_name.startswith("itasca.") and len(parts) >= 3:
            return ".".join(parts[:2])  # itasca.ball, itasca.wall, etc.

        # Object method: Ball.vel → itasca.ball
        # (This should rarely happen after index expansion, but handle it)
        if len(parts) == 2:
            # Try to map class name to module
            try:
                from itasca_mcp.knowledge.python_api.types.mappings import CLASS_TO_MODULE

                class_name = parts[0]
                if class_name in CLASS_TO_MODULE:
                    return f"itasca.{CLASS_TO_MODULE[class_name]}"
            except ImportError:
                pass

        # Fallback: use first two parts or first part
        if len(parts) >= 2:
            return ".".join(parts[:2])
        return parts[0] if parts else "unknown"

    @staticmethod
    def load_by_id(doc_id: str, *, software: str) -> SearchDocument | None:
        """Load a specific API document by ID.

        Args:
            doc_id: API name (e.g., "itasca.ball.create", "Ball.vel")

        Returns:
            SearchDocument instance or None if not found

        Example:
            >>> doc = PythonAPIDocumentAdapter.load_by_id("itasca.ball.create")
            >>> doc.title
            'itasca.ball.create'
            >>> doc.syntax
            'itasca.ball.create(radius, pos=None)'
        """
        api_doc = PythonAPILoader.load_api_doc(doc_id, software=software)

        if not api_doc or api_doc.get("type") == "module":
            return None

        # Extract category
        category = PythonAPIDocumentAdapter._extract_category(doc_id)

        # Build description
        description = api_doc.get("description", "")
        parameters = api_doc.get("parameters", [])
        if parameters:
            param_names = [p.get("name", "") for p in parameters]
            description += f"\n\nParameters: {', '.join(param_names)}"

        # Get keywords
        all_keywords = PythonAPILoader.load_all_keywords(software=software)
        keywords = []
        for keyword, api_list in all_keywords.items():
            if doc_id in api_list:
                keywords.append(keyword)

        return SearchDocument(
            name=doc_id,
            doc_type=DocumentType.PYTHON_API,
            title=doc_id,
            description=description,
            keywords=keywords,
            category=category,
            syntax=api_doc.get("signature", doc_id),
            examples=[{"code": ex} if isinstance(ex, str) else ex for ex in api_doc.get("examples", [])],
            metadata={
                "returns": api_doc.get("returns", ""),
                "limitations": api_doc.get("limitations", []),
                "see_also": api_doc.get("see_also", []),
            },
        )

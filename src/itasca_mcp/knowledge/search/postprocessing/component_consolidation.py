"""Component API consolidation for search results.

This module handles deduplication of component APIs (_x, _y, _z) by consolidating
them into their base vector method, reducing redundancy while preserving component
information in metadata.
"""

import re

from itasca_mcp.knowledge.models.search_result import SearchResult


def consolidate_component_apis(results: list[SearchResult]) -> list[SearchResult]:
    """Consolidate component APIs (_x, _y, _z) into base vector methods.

    When a base method and its components (method_x, method_y, method_z) appear
    in results, keep only the base method and add metadata indicating available
    components. This reduces redundancy while informing LLM about component access.

    Design Philosophy:
    - **Pure function**: Doesn't modify input results
    - **Component detection**: Uses regex to match _x, _y, _z suffixes
    - **Metadata enrichment**: Adds 'has_components' to base method's metadata
    - **Preserves order**: Maintains score-based ranking from search engine

    Args:
        results: List of SearchResult objects (should be sorted by score, descending)

    Returns:
        New list with component methods consolidated into base methods

    Example:
        Before consolidation (15 results):
            1. itasca.BallBallContact.force_global (score: 3.89)
            2. itasca.BallBallContact.force_local (score: 3.63)
            3. itasca.BallBallContact.force_global_x (score: 3.44)
            4. itasca.BallBallContact.force_global_y (score: 3.44)
            5. itasca.BallBallContact.force_global_z (score: 3.44)
            6. itasca.wall.Wall.force_contact (score: 3.90)
            7. itasca.wall.Wall.force_contact_x (score: 3.64)
            8. itasca.wall.Wall.force_contact_y (score: 3.64)
            9. itasca.wall.Wall.force_contact_z (score: 3.64)
            ...

        After consolidation (6 results):
            1. itasca.BallBallContact.force_global (score: 3.89)
               metadata['has_components'] = ['x', 'y', 'z']
            2. itasca.BallBallContact.force_local (score: 3.63)
               (no metadata - no components in results)
            3. itasca.wall.Wall.force_contact (score: 3.90)
               metadata['has_components'] = ['x', 'y', 'z']
            ...

    Usage:
        >>> from itasca_mcp.knowledge.query import PythonAPISearch
        >>> from itasca_mcp.knowledge.search.postprocessing import (
        ...     consolidate_contact_apis,
        ...     consolidate_component_apis
        ... )
        >>>
        >>> results = PythonAPISearch.search("contact force", top_k=30)
        >>> len(results)
        30  # May contain many component APIs
        >>>
        >>> consolidated = consolidate_contact_apis(results)
        >>> consolidated = consolidate_component_apis(consolidated)
        >>> len(consolidated)
        10  # Much cleaner! Only base methods
        >>>
        >>> # Check metadata
        >>> consolidated[0].document.metadata.get('has_components')
        ['x', 'y', 'z']
    """
    # Component pattern: matches method names ending with _x, _y, or _z
    COMPONENT_PATTERN = re.compile(r"^(.+)_(x|y|z)$")

    # Pass 1: Identify all base methods and their components
    base_methods: dict[str, set[str]] = {}
    # {base_api_name: set of components ('x', 'y', 'z')}

    for result in results:
        doc_name = result.document.name
        method_name = doc_name.split(".")[-1]

        # Check if this is a component method
        match = COMPONENT_PATTERN.match(method_name)

        if match:
            # This is a component method (e.g., force_global_x)
            base_method = match.group(1)
            component = match.group(2)

            # Reconstruct base API name
            prefix = ".".join(doc_name.split(".")[:-1])
            base_api_name = f"{prefix}.{base_method}"

            # Track this component
            if base_api_name not in base_methods:
                base_methods[base_api_name] = set()
            base_methods[base_api_name].add(component)

    # Pass 2: Build consolidated list, skipping components and adding metadata
    consolidated = []

    for result in results:
        doc_name = result.document.name
        method_name = doc_name.split(".")[-1]

        # Skip component methods
        if COMPONENT_PATTERN.match(method_name):
            continue

        # Check if this base method has components
        if doc_name in base_methods:
            components = base_methods[doc_name]
            # Add metadata to result
            result.document.metadata["has_components"] = sorted(components)

        # Add to consolidated list
        consolidated.append(result)

    return consolidated

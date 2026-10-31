"""High-level query interfaces for Itasca documentation search.

This module provides user-facing search APIs that abstract away
the complexity of search engines and adapters.
"""

from itasca_mcp.knowledge.query.command_search import CommandSearch
from itasca_mcp.knowledge.query.fish_search import FishSearch
from itasca_mcp.knowledge.query.python_api_search import PythonAPISearch
from itasca_mcp.knowledge.query.reference_search import ReferenceSearch

__all__ = [
    "CommandSearch",
    "PythonAPISearch",
    "FishSearch",
    "ReferenceSearch",
]

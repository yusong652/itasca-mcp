"""High-level query interfaces for Itasca documentation search.

This module provides user-facing search APIs that abstract away
the complexity of search engines and adapters.
"""

from itasca_mcp.knowledge.query.api_search import APISearch
from itasca_mcp.knowledge.query.command_search import CommandSearch
from itasca_mcp.knowledge.query.fish_search import FishSearch
from itasca_mcp.knowledge.query.reference_search import ReferenceSearch

__all__ = [
    "CommandSearch",
    "APISearch",
    "FishSearch",
    "ReferenceSearch",
]

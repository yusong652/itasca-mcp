"""Itasca Python SDK documentation: loader, formatter and data models.

Search lives in the unified search system (``itasca_mcp.knowledge.query.PythonAPISearch``);
this package only loads and formats the per-engine ``python_sdk_docs`` corpus.
"""

from itasca_mcp.knowledge.python_api.formatter import PythonAPIFormatter
from itasca_mcp.knowledge.python_api.loader import PythonAPILoader
from itasca_mcp.knowledge.python_api.models import PythonAPIDocumentation, SearchResult, SearchStrategy

__all__ = [
    "PythonAPILoader",
    "PythonAPIFormatter",
    "SearchResult",
    "PythonAPIDocumentation",
    "SearchStrategy",
]

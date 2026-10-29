"""``itasca_browse_doc``: one browse tool over the four documentation trees."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.tools._docs_common import VERSION_DESCRIPTION, resolve_doc_version, stamp_summary
from itasca_mcp.tools.browse_commands import browse as browse_commands_tree
from itasca_mcp.tools.browse_fish import browse as browse_fish_tree
from itasca_mcp.tools.browse_python_api import browse as browse_python_api_tree
from itasca_mcp.tools.browse_reference import browse as browse_reference_tree
from itasca_mcp.utils import (
    CommandDocVersion,
    DocSourceParam,
    SoftwareParam,
    normalize_doc_source,
    normalize_software_value,
)

_BROWSERS = {
    "commands": browse_commands_tree,
    "python_api": browse_python_api_tree,
    "fish": browse_fish_tree,
    "reference": browse_reference_tree,
}

PATH_DESCRIPTION = (
    "Path inside the selected tree; omit for the top level.\n"
    "- commands: space-separated ('ball' lists ball commands, 'ball create' is the full doc)\n"
    "- python_api: dotted from itasca ('itasca.ball', 'itasca.ball.create', 'itasca.ball.Ball.pos')\n"
    "- fish: dotted intrinsic name ('ball' lists the namespace, 'ball.pos' shows its signature "
    "plus ball.pos.x/y/z)\n"
    "- reference: 'category item sub' ('contact-models linear', 'range-elements cylinder', "
    "'plot-items zone contour')"
)


def register(mcp: FastMCP) -> None:
    """Register itasca_browse_doc with the MCP server."""

    @mcp.tool()
    def itasca_browse_doc(
        software: SoftwareParam,
        source: DocSourceParam,
        path: str | None = Field(None, description=PATH_DESCRIPTION),
        version: CommandDocVersion = Field(CommandDocVersion.V9_0, description=VERSION_DESCRIPTION),
    ) -> dict[str, Any]:
        """Browse ITASCA documentation by path, like ls + cat over one documentation tree.

        source picks the tree: commands (Itasca command syntax and keywords), python_api
        (the itasca Python SDK), fish (FISH intrinsic functions: name, signature, which
        versions have it), reference (contact/constitutive/joint model properties, range
        elements, plot items). Each level lists what is below it, so start at the top of
        a tree when unsure and descend.

        Use itasca_query_doc when you only have keywords; its results are paths for this tool.
        """
        sw = normalize_software_value(software)
        version_value, error = resolve_doc_version(sw, version)
        if error is not None or version_value is None:
            return error or {}
        envelope = _BROWSERS[normalize_doc_source(source)](sw, path, version_value)
        return stamp_summary(envelope, software=sw, version=version_value)

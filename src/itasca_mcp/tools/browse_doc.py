"""``itasca_browse_doc``: one browse tool over the four documentation trees."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.tools.docs import commands, fish, python_api, reference
from itasca_mcp.tools.docs._common import VERSION_DESCRIPTION, resolve_doc_version, stamp_summary
from itasca_mcp.utils import (
    CommandDocVersion,
    DocSourceParam,
    SoftwareParam,
    normalize_doc_source,
    normalize_software_value,
)

_BROWSERS = {
    "commands": commands.browse,
    "python_api": python_api.browse,
    "fish": fish.browse,
    "reference": reference.browse,
}

PATH_DESCRIPTION = (
    "Path inside the selected tree; omit for the top level.\n"
    "- commands: space-separated ('ball' lists ball commands, 'ball create' is the full doc, "
    "'ball create radius' one keyword or section; a word group such as 'block contact' or "
    "'structure beam' lists its commands, summary.groups names them)\n"
    "- python_api: dotted from itasca ('itasca.ball', 'itasca.ball.create', 'itasca.ball.Ball.pos')\n"
    "- fish: dotted intrinsic name ('ball' lists the namespace, 'ball.pos' shows its signature "
    "plus ball.pos.x/y/z)\n"
    "- reference: 'category item sub' ('contact-models linear', 'range-elements cylinder', "
    "'plot-items zone contour', 'contact-models linearpbond pb_ten' one property or section)\n"
    "A page too large for one response leaves parts out (summary.omitted_sections / "
    "summary.compacted); summary.hint gives the path to read them."
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

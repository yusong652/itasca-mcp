"""ITASCA documentation path configuration (multi-engine).

The corpus is organized into per-engine layers plus a shared ``_common`` layer
that holds the Itasca 9.0 unified-kernel docs shared across engines::

    resources/_common/{command_docs,python_sdk_docs}/   # shared kernel
    resources/<software>/{command_docs,python_sdk_docs,references}/

``command_docs`` and ``python_sdk_docs`` index ``file`` pointers are
RESOURCES-root-relative -- they may point into ``_common/`` or ``<software>/``
-- and are resolved with :func:`resolve`. References are engine-only and are
resolved against :func:`references_root`.
"""

from pathlib import Path

# Root of all bundled documentation resources.
RESOURCES_DIR = Path(__file__).parent / "resources"

# Engines exposed through the (required) ``software`` parameter on the
# documentation tools. There is deliberately no default engine: a unified
# itasca-mcp must not silently bias toward one product.
SUPPORTED_SOFTWARE = ("pfc", "flac", "3dec", "mpoint", "massflow")


def normalize_software(software: str) -> str:
    """Validate/normalize a required software selector.

    Raises:
        ValueError: if ``software`` is missing or not a supported engine.
    """
    value = (software or "").strip().lower()
    if value not in SUPPORTED_SOFTWARE:
        raise ValueError(f"Unsupported software {software!r}; expected one of {', '.join(SUPPORTED_SOFTWARE)}")
    return value


def resolve(rel_path: str) -> Path:
    """Resolve a RESOURCES-root-relative file pointer from a command/python index."""
    return RESOURCES_DIR / rel_path


def command_index_path(software: str) -> Path:
    return RESOURCES_DIR / software / "command_docs" / "index.json"


def python_index_path(software: str) -> Path:
    return RESOURCES_DIR / software / "python_sdk_docs" / "index.json"


def python_docs_root(software: str) -> Path:
    return RESOURCES_DIR / software / "python_sdk_docs"


def python_keywords_path(software: str) -> Path:
    return RESOURCES_DIR / software / "python_sdk_docs" / "itasca_keywords.json"


def references_root(software: str) -> Path:
    return RESOURCES_DIR / software / "references"


def fish_index_path(software: str) -> Path:
    return RESOURCES_DIR / software / "fish_docs" / "index.json"


def fish_docs_root(software: str) -> Path:
    return RESOURCES_DIR / software / "fish_docs"

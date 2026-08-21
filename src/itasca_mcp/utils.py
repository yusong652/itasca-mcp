"""Validation models and utilities for Itasca MCP tools."""

from enum import Enum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated

from pydantic import Field
from pydantic.functional_validators import AfterValidator

# Search limits
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 20

# Task/output pagination
DEFAULT_OUTPUT_LINES = 64
MAX_OUTPUT_LINES = 200
DEFAULT_TASK_LIST_LIMIT = 32
MAX_TASK_LIST_LIMIT = 100

# Timeout constraints (seconds)
MIN_TIMEOUT_S = 1
MAX_TIMEOUT_S = 600

# Wait constraints (seconds)
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 3600

# Description constraints
DESCRIPTION_MAX_LENGTH = 200


class CommandDocVersion(str, Enum):
    """Supported Itasca documentation versions for command tools."""

    V6_0 = "6.0"
    V7_0 = "7.0"
    V9_0 = "9.0"


def normalize_command_doc_version(value: CommandDocVersion | str) -> str:
    """Return the plain string value for a command-doc version enum."""
    if isinstance(value, CommandDocVersion):
        return value.value
    return str(value)


class Software(str, Enum):
    """Supported ITASCA engines selected by the documentation tools' ``software`` arg."""

    PFC = "pfc"
    FLAC = "flac"
    THREE_DEC = "3dec"
    MPOINT = "mpoint"
    MASSFLOW = "massflow"


def normalize_software_value(value: "Software | str") -> str:
    """Return the plain lowercase string value for a software enum/string."""
    if isinstance(value, Software):
        return value.value
    return str(value).strip().lower()


# Engines that ship only the Itasca 9.x unified kernel: their command/reference
# docs carry a single "9.0" key. The documentation tools' version selector
# defaults to 7.0 (a PFC-era leftover), which would otherwise make every
# 9.0-only command resolve as "unavailable", so the effective version is coerced
# to 9.0 for these engines. PFC (6.0/7.0/9.0), FLAC (7.0/9.0) and 3DEC
# (7.0/9.0) keep their multi-version behavior.
NINE_ZERO_ONLY_SOFTWARE = frozenset({"mpoint", "massflow"})

# Doc versions each engine's corpus covers.
SUPPORTED_DOC_VERSIONS: dict[str, frozenset[str]] = {
    "pfc": frozenset({"6.0", "7.0", "9.0"}),
    "flac": frozenset({"7.0", "9.0"}),
    "3dec": frozenset({"7.0", "9.0"}),
}

_NINE_ZERO_ONLY_VERSIONS = frozenset({"9.0"})


def supported_doc_versions(software: str) -> frozenset[str]:
    """Return the doc versions available for a normalized software value."""
    return SUPPORTED_DOC_VERSIONS.get(software, _NINE_ZERO_ONLY_VERSIONS)


def effective_doc_version(software: str, version: str) -> str:
    """Return the doc version to use, coercing 9.0-only engines to 9.0.

    ``software`` must already be normalized (see :func:`normalize_software_value`).
    """
    if software in NINE_ZERO_ONLY_SOFTWARE:
        return "9.0"
    return version


def normalize_input(value: str | None, lowercase: bool = False) -> str:
    """Normalize user input: collapse whitespace, optionally lowercase."""
    if value is None:
        return ""
    normalized = " ".join(value.split())
    return normalized.lower() if lowercase else normalized


def validate_non_empty_string(value: str) -> str:
    """Validate that a string is not empty after stripping whitespace."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("Value cannot be empty or whitespace only")
    return stripped


def validate_script_path(value: str) -> str:
    """Validate entry script path."""
    stripped = validate_non_empty_string(value)
    if not (PurePosixPath(stripped).is_absolute() or PureWindowsPath(stripped).is_absolute()):
        raise ValueError("entry_script must be an absolute path")
    return stripped


def validate_task_description(value: str) -> str:
    """Validate task description text."""
    stripped = validate_non_empty_string(value)
    if len(stripped) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(f"description is too long (max {DESCRIPTION_MAX_LENGTH} chars)")
    return stripped


# Search query for commands
SearchQuery = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(
        ...,
        min_length=1,
        description=(
            "Search keywords for Itasca commands. Examples: 'ball create', "
            "'contact property', 'model solve'. Case-insensitive."
        ),
    ),
]

# Python API search query
PythonAPISearchQuery = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(
        ...,
        min_length=1,
        description=(
            "Search keywords for Itasca Python SDK API. Examples: 'ball pos', "
            "'contact force', 'model solve'. Case-insensitive."
        ),
    ),
]

# Software / engine selector (required, no default — itasca-mcp must not bias to one engine)
SoftwareParam = Annotated[
    Software,
    Field(
        ...,
        description="ITASCA engine to query: 'pfc', 'flac', '3dec', 'mpoint', or 'massflow'. Required — there is no default engine.",
    ),
]

# Search limit
SearchLimit = Annotated[
    int,
    Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description=f"Maximum number of results (1-{MAX_SEARCH_LIMIT}).",
    ),
]

TaskId = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(..., description="Task ID returned by itasca_execute_task"),
]

ScriptPath = Annotated[
    str,
    AfterValidator(validate_script_path),
    Field(..., description="Absolute path to entry Python script in the Itasca engine workspace"),
]

TaskDescription = Annotated[
    str,
    AfterValidator(validate_task_description),
    Field(..., min_length=1, max_length=DESCRIPTION_MAX_LENGTH, description="Brief task purpose"),
]

SkipNewestTasks = Annotated[
    int,
    Field(default=0, ge=0, description="Skip N most recent tasks before listing"),
]

TaskListLimit = Annotated[
    int,
    Field(default=DEFAULT_TASK_LIST_LIMIT, ge=1, le=MAX_TASK_LIST_LIMIT, description="Max tasks to return"),
]

SkipNewestLines = Annotated[
    int,
    Field(default=0, ge=0, description="Skip N newest output lines before pagination"),
]

OutputLimit = Annotated[
    int,
    Field(default=DEFAULT_OUTPUT_LINES, ge=1, le=MAX_OUTPUT_LINES, description="Output lines per page"),
]

FilterText = Annotated[
    str | None,
    Field(default=None, description="Only keep output lines containing this text"),
]

WaitSeconds = Annotated[
    float,
    Field(
        default=MIN_WAIT_SECONDS,
        ge=MIN_WAIT_SECONDS,
        le=MAX_WAIT_SECONDS,
        description="Wait time before querying status",
    ),
]

ConsoleCode = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(..., min_length=1, description="Python code to execute in the Itasca engine user console"),
]

ConsoleTimeoutSeconds = Annotated[
    int,
    Field(default=120, ge=MIN_TIMEOUT_S, le=MAX_TIMEOUT_S, description="Console execution timeout in seconds"),
]

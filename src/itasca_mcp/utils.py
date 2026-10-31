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

# Blocking parameters stay under the shortest MCP client request timeout
# seen in practice (OpenCode 30 s), so the bridge answers before the
# client drops the result.
HARNESS_TIMEOUT_FLOOR_S = 20

# Timeout constraints (seconds)
MIN_TIMEOUT_S = 1
MAX_TIMEOUT_S = HARNESS_TIMEOUT_FLOOR_S

# Wait constraints (seconds)
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = HARNESS_TIMEOUT_FLOOR_S

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


class DocSource(str, Enum):
    """Documentation trees served by itasca_browse_doc / itasca_query_doc."""

    COMMANDS = "commands"
    PYTHON_API = "python_api"
    FISH = "fish"
    REFERENCE = "reference"


def normalize_doc_source(value: "DocSource | str") -> str:
    """Return the plain lowercase string value for a doc-source enum/string."""
    if isinstance(value, DocSource):
        return value.value
    return str(value).strip().lower()


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


# Software / engine selector (required, no default — itasca-mcp must not bias to one engine)
SoftwareParam = Annotated[
    Software,
    Field(
        ...,
        description="ITASCA engine to query: 'pfc', 'flac', '3dec', 'mpoint', or 'massflow'. Required — there is no default engine.",
    ),
]

# Documentation tree selector for itasca_browse_doc (required there; optional on itasca_query_doc)
DocSourceParam = Annotated[
    DocSource,
    Field(
        ...,
        description=(
            "Documentation tree: 'commands' (Itasca command syntax), 'python_api' (itasca Python SDK), "
            "'fish' (FISH intrinsic functions), 'reference' (model properties, range elements, plot items)."
        ),
    ),
]

# Keyword query for itasca_query_doc
DocQuery = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(
        ...,
        min_length=1,
        description=(
            "Search keywords or a name fragment. Examples: 'ball create', 'contact force', "
            "'ball.pos', 'mohr-coulomb', 'zone pore pressure'. Case-insensitive."
        ),
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
    Field(..., description="Task ID returned by itasca_execute_task or listed by itasca_list_tasks"),
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
        description="Long-poll: return when the task changes state or after this many seconds.",
    ),
]

ConsoleCode = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(..., min_length=1, description="Python code to execute in the Itasca engine user console"),
]

ConsoleTimeoutSeconds = Annotated[
    int,
    Field(
        default=10,
        ge=MIN_TIMEOUT_S,
        le=MAX_TIMEOUT_S,
        description="Seconds before the bridge aborts the snippet; longer work belongs in itasca_execute_task.",
    ),
]

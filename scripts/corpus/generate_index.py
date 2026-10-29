#!/usr/bin/env python3
"""Generate index.json from individual command documentation files.

This script scans the commands/ directory and extracts metadata from each
command JSON file to build the index. Category-level metadata is defined
in CATEGORY_METADATA below.

Usage:
    python generate_index.py

The script will overwrite index.json with the generated content.
"""

import json
from pathlib import Path
from typing import Any

DEFAULT_VERSION = "7.0"

# Category-level metadata (cannot be extracted from command files)
CATEGORY_METADATA: dict[str, dict[str, Any]] = {
    "ball": {
        "full_name": "Ball Commands",
        "description": "Commands for creating, modifying, and managing ball objects in PFC discrete element simulations",
        "command_prefix": "ball",
        "python_module": "itasca.ball",
        "python_object_class": "Ball",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/ball/ball.html",
        "related_categories": ["wall", "clump", "contact", "model"],
        "notes": [
            "Ball commands typically operate on ranges (groups, spatial regions, or all balls)",
            "Use Python SDK for fine-grained control and complex logic",
            "Use commands for batch operations and initial model setup",
            "Ball generation with packing patterns requires commands (not available in Python SDK)",
        ],
    },
    "wall": {
        "full_name": "Wall Commands",
        "description": "Commands for creating, modifying, and managing wall objects (faceted boundaries) in PFC",
        "command_prefix": "wall",
        "python_module": "itasca.wall",
        "python_object_class": "Wall",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/wall/wall.html",
        "related_categories": ["ball", "clump", "contact", "model"],
        "notes": [
            "Walls are composed of triangular facets (Facet objects)",
            "Wall generation commands (box, cylinder) are not available in Python SDK",
            "Use Python SDK for programmatic wall manipulation",
            "Walls can be moved via velocity or displacement attributes",
        ],
    },
    "clump": {
        "full_name": "Clump Commands",
        "description": "Clump object creation, modification, and template management commands. Clumps are rigid aggregates of overlapping or touching balls (pebbles) that behave as single rigid bodies.",
        "command_prefix": "clump",
        "python_module": "itasca.clump",
        "python_object_class": "Clump",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/clump/clump.html",
        "related_categories": ["ball", "wall", "contact", "model"],
        "notes": [
            "Clumps are rigid bodies composed of pebbles (component balls)",
            "Clump templates enable efficient replication of complex shapes",
            "clump generate creates non-overlapping clumps; clump distribute allows overlaps for target porosity",
            "Most clump operations (template, generate, distribute) not available in Python SDK",
        ],
    },
    "contact": {
        "full_name": "Contact Commands",
        "description": "Commands for configuring contact models and managing contact properties between objects",
        "command_prefix": "contact",
        "python_module": "itasca.contact",
        "python_object_class": "Contact (BallBallContact, BallFacetContact, etc.)",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/contact/contact.html",
        "related_categories": ["ball", "wall", "clump", "model"],
        "notes": [
            "Contact models define mechanical behavior at contact points",
            "Common contact models: linear, linearpbond, linearcbond, hertz",
            "Contact properties are model-specific (e.g., 'kn' for normal stiffness)",
            "Use 'contact model' commands to assign and configure models",
        ],
    },
    "model": {
        "full_name": "Model Commands",
        "description": "System-level commands for controlling simulation execution, configuration, and state management",
        "command_prefix": "model",
        "python_module": "itasca",
        "python_functions": ["itasca.cycle()", "itasca.timestep()", "itasca.set_timestep()"],
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/model/model.html",
        "common_keywords": {
            "solve": ["ratio", "ratio-average", "force-max", "moment-max", "cycles"],
            "cycle": ["number of cycles"],
            "domain": ["extent", "condition", "periodic", "destroy"],
            "configure": ["threads", "dynamic"],
        },
        "related_categories": ["ball", "wall", "contact", "set"],
        "notes": [
            "'model solve' is preferred for reaching equilibrium (not available in Python SDK)",
            "'model cycle' is equivalent to itasca.cycle() in Python",
            "Model state can be saved/restored for checkpointing",
            "Domain settings must be configured before generating objects",
            "Use 'model solve' with ratio criteria for automatic convergence",
        ],
    },
    "fragment": {
        "full_name": "Fragment Commands",
        "description": "Fragment tracking and analysis commands for connected component detection in contact networks. Fragments identify groups of connected bodies based on contact connectivity.",
        "command_prefix": "fragment",
        "python_module": None,
        "python_functions": ["ball.fragment()", "clump.fragment()"],
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/fragment/fragment.html",
        "typical_workflow": [
            "1. Register fragments: fragment register",
            "2. Compute or activate: fragment compute OR fragment activate cycles 100",
            "3. Query fragment IDs: ball.fragment() or clump.fragment() in Python",
            "4. Clear when done: fragment clear",
        ],
        "related_categories": ["ball", "clump", "contact", "model"],
        "notes": [
            "Fragment registration (fragment register) is required before any computation",
            "By default, only bonded contacts contribute to fragment connectivity (use ignorebond for all contacts)",
            "Fragment ID 0 indicates isolated body (no contacts)",
            "fragment activate enables automatic periodic computation; fragment compute is one-time",
            "After computation, query fragment IDs via ball.fragment() or clump.fragment() in Python",
        ],
    },
    "measure": {
        "full_name": "Measurement Commands",
        "description": "Measurement region creation and property analysis commands. Measurement regions calculate porosity, stress, strain, coordination number, and particle size distributions within spherical (3D) or circular (2D) regions.",
        "command_prefix": "measure",
        "python_module": "itasca.measure",
        "python_object_class": "Measurement",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/measure/measure.html",
        "measured_quantities": ["porosity", "coordination_number", "stress", "strain", "particle_size_distribution"],
        "typical_workflow": [
            "1. Create measurement region: measure create radius 5.0",
            "2. Trigger calculation: model clean",
            "3. View results: measure list",
            "4. Export if needed: measure dump",
        ],
        "related_categories": ["ball", "clump", "model"],
        "notes": [
            "Measurement regions are disks (2D) or spheres (3D)",
            "Measurements calculated when 'model clean' is called or when FISH intrinsic queries measurement",
            "Can measure: porosity, coordination number, stress, strain, size distribution",
            "Use 'bins' keyword in create to enable particle size distribution calculation",
            "Tolerance parameter controls accuracy vs. speed trade-off for porosity calculation",
        ],
    },
    "plot": {
        "full_name": "Plot Commands",
        "description": "Commands for creating, modifying, and exporting visualization plots. Controls plot items, camera views, and image export.",
        "command_prefix": "plot",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/plot/plot.html",
        "related_categories": ["ball", "wall", "clump", "contact", "zone", "geometry"],
        "notes": [
            "Plot commands control visualization, not simulation",
            "Use 'plot export bitmap' to save plot images",
            "Plot item keywords are extensive; use 'plot export datafile' to inspect syntax",
            "Camera view controlled via center, eye, magnification, projection keywords",
        ],
    },
    "brick": {
        "full_name": "Brick Commands",
        "description": "Commands for creating, importing, assembling, and managing brick-based geometry and inlets used by rigid-body workflows.",
        "command_prefix": "brick",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/brick/brick.html",
        "related_categories": ["rblock", "ball", "clump", "model"],
        "notes": [
            "Brick commands manage reusable geometry definitions and inlets rather than simulation pieces directly",
            "Use brick inlets to generate balls, clumps, or rblocks during cycling",
            "Most brick operations currently rely on the command interface via itasca.command()",
        ],
    },
    "rblock": {
        "full_name": "RBlock Commands",
        "description": "Commands for creating, configuring, and managing rigid blocks (rblocks) and their template-driven workflows.",
        "command_prefix": "rblock",
        "python_module": "itasca.rblock",
        "python_object_class": "RBlock",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/rblock/rblock.html",
        "related_categories": ["brick", "ball", "clump", "contact", "model"],
        "notes": [
            "RBlocks are rigid polyhedral bodies with dedicated creation, cutting, and surface-management commands",
            "Template-based workflows are common for rblock generation and replication",
            "Python SDK supports querying and manipulating existing rblocks, while many creation workflows still require commands",
        ],
    },
    "program": {
        "full_name": "Program Commands",
        "description": "Program-level commands controlling the PFC executable: license, threads, working directory, logging, encryption, undo, system shell, and lifecycle (quit/exit/stop/return/continue).",
        "command_prefix": "program",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/program/program.html",
        "related_categories": ["model", "history", "fish"],
        "notes": [
            "These commands manage the executable itself, not the model state",
            "program list and program license print to stdout - useful for environment diagnostics under itasca.command()",
            "program log redirects subsequent command output to a file",
            "program quit / exit / stop terminate execution; rarely used from MCP workflows",
            "program threads controls multi-threaded solve parallelism",
        ],
    },
    "history": {
        "full_name": "History Commands",
        "description": "Commands for managing model histories: time-series recordings of scalar quantities sampled during cycling. Used for monitoring convergence, plotting trends, and exporting tabular data.",
        "command_prefix": "history",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/history/history.html",
        "related_categories": ["model", "ball", "wall", "clump"],
        "notes": [
            "Histories are created by domain-specific commands (e.g., 'ball history', 'model history'), then managed here",
            "history list and history results print samples to stdout - capturable via log",
            "history export writes tabular data to a file; history interval controls sampling cadence",
            "history label / rename adjust display metadata; history delete / purge remove entries",
        ],
    },
    "fish": {
        "full_name": "FISH Commands",
        "description": "Commands controlling the FISH embedded scripting language: function definition, callbacks, debugging, tracing, and runtime configuration.",
        "command_prefix": "fish",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/fish/fish.html",
        "related_categories": ["model", "program", "history"],
        "notes": [
            "FISH is PFC's in-process scripting language; these commands manage its runtime",
            "fish define introduces a function; fish list prints all symbols (loggable)",
            "fish callback registers per-cycle FISH execution; fish-halt in 'model solve' is a stop-condition callback",
            "fish trace / debug emit diagnostic output capturable via log",
            "Prefer Python SDK for new scripting; FISH remains required for callbacks and in-cycle hooks",
        ],
    },
    "geometry": {
        "full_name": "Geometry Commands",
        "description": "Commands for managing geometry sets — nodes, edges, polygons — used as boundaries, wall sources, and reference shapes. Includes import/export, refinement, tessellation, and group/extra metadata.",
        "command_prefix": "geometry",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/geometry/geometry.html",
        "related_categories": ["wall", "fracture", "model"],
        "notes": [
            "geometry sets are containers of nodes/edges/polygons addressed via 'geometry set <name>'",
            "geometry import / export are the primary I/O paths (STL, DXF, geometry-set format)",
            "Sub-namespaces (edge / node / polygon) operate on individual element types within a set",
            "Use 'wall import from-geometry' or 'fracture import' to convert geometry into simulation entities",
        ],
    },
    "fracture": {
        "full_name": "Fracture (DFN) Commands",
        "description": "Discrete Fracture Network commands for creating, importing, and analyzing planar discontinuities (fractures) and their intersections. Drives Smooth-Joint and similar contact models.",
        "command_prefix": "fracture",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/dfn/dfn.html",
        "related_categories": ["geometry", "contact", "ball"],
        "notes": [
            "DFN module: command verb is 'fracture' even though docs call it 'dfn'",
            "fracture generate creates statistical DFNs; fracture import reads explicit fracture files",
            "fracture template defines reusable fracture geometries (fracture template create / delete / modify-default)",
            "fracture intersections compute / scanline produces connectivity data for joint-set analysis",
            "Use 'contact model smoothjoint' (or similar) to wire fractures into mechanical behavior",
        ],
    },
    "table": {
        "full_name": "Table Commands",
        "description": "Commands for managing numerical tables — paired x/y data used as input for time-varying boundary conditions, property curves, and history post-processing.",
        "command_prefix": "table",
        "python_module": "itasca.table",
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/table/table.html",
        "related_categories": ["history", "model"],
        "notes": [
            "Tables are indexed by name (string) or numeric ID; created by 'table add' / 'table import'",
            "'history export ... table <s>' pushes history data into a table for downstream use",
            "table export / list dump current contents to stdout/file",
            "Python SDK (itasca.table) exposes read/write for runtime queries; commands handle batch I/O",
        ],
    },
    "group": {
        "full_name": "Group Commands",
        "description": "Commands for creating and renaming named groups across all object types (balls, walls, contacts, etc.). Groups occupy named slots and act as range filters in subsequent commands.",
        "command_prefix": "group",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/group/group.html",
        "related_categories": ["ball", "wall", "clump", "contact"],
        "notes": [
            "Group membership is set by object-specific commands ('ball group X', 'wall group Y'), not by 'group' commands",
            "'group slot' assigns/renames a slot (group categories that don't conflict — e.g., material slot, region slot)",
            "'group list' enumerates known group names across slots (loggable output)",
            "Use 'range group <name>' in any range-accepting command to filter by group",
        ],
    },
    "trace": {
        "full_name": "Trace Commands",
        "description": "Commands for managing particle traces — recordings of per-object scalar/vector quantities sampled during cycling, used for path visualization and post-hoc analysis.",
        "command_prefix": "trace",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/trace/trace.html",
        "related_categories": ["history", "ball", "clump", "wall"],
        "notes": [
            "Traces are created by object-specific commands ('ball trace', 'wall trace'); these commands manage lifecycle",
            "Similar to histories but record per-object trajectories instead of scalar time-series",
            "trace list / export prints sample data; trace interval controls cadence; trace purge erases samples but keeps definitions",
        ],
    },
    "project": {
        "full_name": "Project Commands",
        "description": "Commands for managing PFC project containers — bundles of model save states, data files, and plugins maintained by the GUI project view.",
        "command_prefix": "project",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/project/project.html",
        "related_categories": ["program", "model"],
        "notes": [
            "Project files (.prj) bundle multiple model saves + data files for a related study",
            "project new / save / restore manage the active project; project list enumerates contents",
            "project execute runs a data file in the project context",
            "Mostly a GUI-oriented concept; scripted workflows usually skip projects and use 'model save'/'model restore' directly",
        ],
    },
    "data": {
        "full_name": "Data Commands",
        "description": "Commands for creating user-defined data containers — labels, scalars, vectors, and tensors — attached to model objects. Used for visualizing imported field data or computed quantities.",
        "command_prefix": "data",
        "python_module": None,
        "doc_url": "https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/data/data.html",
        "related_categories": ["ball", "geometry", "plot"],
        "notes": [
            "Four sub-namespaces: data label / scalar / vector / tensor — each with create/delete/list/import/export/group/results",
            "Useful for piping external CSV / field data into the model for visualization or sampling",
            "Sub-namespace is part of the JSON key: 'data scalar create' → commands/data/scalar-create.json",
            "Plot items can color/size objects by data values stored in these containers",
        ],
    },
}

# Python SDK alternatives (command-level, kept in index for quick reference)
PYTHON_SDK_ALTERNATIVES: dict[str, dict[str, Any]] = {
    "ball generate": {
        "command": "ball generate",
        "reason": "Python SDK doesn't support packing patterns for batch ball creation",
        "python_alternative": "itasca.ball.create() - can create individual balls only",
        "python_workaround": "Use itasca.ball.create() in a loop with manual positioning logic",
        "recommendation": "use_command",
    },
    "wall generate": {
        "command": "wall generate",
        "reason": "Python SDK doesn't support geometric wall generation (box, cylinder, etc.)",
        "python_alternative": "Manual wall creation using Python SDK requires vertex-by-vertex construction",
        "python_workaround": "Calculate vertices manually and use itasca.wall module",
        "recommendation": "use_command",
    },
    "clump template": {
        "command": "clump template",
        "reason": "Python SDK does not provide clump template management",
        "python_alternative": "itasca.command('clump template ...') - must use command interface",
        "python_workaround": "Use command interface via itasca.command()",
        "recommendation": "use_command",
    },
    "clump generate": {
        "command": "clump generate",
        "reason": "Python SDK cannot generate clumps with templates and packing patterns",
        "python_alternative": "itasca.command('clump generate ...') - must use command interface",
        "python_workaround": "Use command interface via itasca.command()",
        "recommendation": "use_command",
    },
    "model solve": {
        "command": "model solve",
        "reason": "Python SDK doesn't have automatic equilibrium detection",
        "python_alternative": "itasca.cycle() - requires manual termination logic",
        "python_workaround": "Use itasca.cycle() with manual ratio checking in a loop",
        "recommendation": "use_command",
    },
    "fragment register": {
        "command": "fragment register",
        "reason": "Fragment registration is a global initialization operation",
        "python_alternative": "itasca.command('fragment register ...') - no direct SDK method",
        "python_workaround": "Use command interface via itasca.command()",
        "recommendation": "use_command",
    },
}

# Command patterns metadata
COMMAND_PATTERNS: dict[str, list[str]] = {
    "object_commands": ["ball", "wall", "clump", "measure", "brick", "rblock"],
    "system_commands": ["model", "contact", "program", "project"],
    "analysis_commands": ["fragment", "measure", "history", "trace"],
    "geometry_commands": ["geometry", "fracture"],
    "data_commands": ["table", "data", "group"],
    "visualization_commands": ["plot"],
    "scripting_commands": ["fish"],
    "common_subcommands": ["generate", "create", "delete", "attribute", "property", "group", "result", "history"],
}

# Global notes
GLOBAL_NOTES: list[str] = [
    "Commands are preferred over Python SDK for batch operations and specialized geometries",
    "Python SDK is preferred for fine-grained control and programmatic logic",
    "Use 'itasca.command()' to execute any PFC command from Python",
    "Commands return no value; use 'result' subcommands to query results",
    "Most commands operate on ranges (groups, spatial regions, all objects)",
]


def _resolve_index_fields(cmd_data: dict[str, Any]) -> dict[str, Any]:
    """Flatten versioned command docs so index metadata stays populated."""
    versions = cmd_data.get("versions")
    if not isinstance(versions, dict):
        return cmd_data

    preferred_order = [DEFAULT_VERSION, *[v for v in versions if v != DEFAULT_VERSION]]
    for version in preferred_order:
        version_data = versions.get(version)
        if isinstance(version_data, dict) and version_data.get("available") is not False:
            resolved = dict(cmd_data)
            resolved.update(version_data)
            return resolved

    return dict(cmd_data)


def extract_command_metadata(cmd_path: Path, category: str, category_dir: Path) -> dict[str, Any]:
    """Extract metadata from a command JSON file."""
    with open(cmd_path, encoding="utf-8") as f:
        cmd_data = json.load(f)

    cmd_data = _resolve_index_fields(cmd_data)

    # Extract command name from filename (without .json)
    name = cmd_path.stem

    # Handle nested commands (e.g., contact/cmat/add.json -> "cmat add")
    rel_path = cmd_path.relative_to(category_dir)
    if len(rel_path.parts) > 1:
        # Nested command like cmat/add.json
        name = " ".join(rel_path.parts[:-1]) + " " + rel_path.stem
        name = name.replace("/", " ")

    # Build relative file path from command_docs root
    file_path = f"commands/{category}/{'/'.join(rel_path.parts)}"

    # Extract short_description (first sentence or first 100 chars of description)
    description = cmd_data.get("description", "")
    short_desc = description.split(".")[0] if description else ""
    if len(short_desc) > 100:
        short_desc = short_desc[:97] + "..."

    # Extract python_available from python_sdk_alternative
    python_alt = cmd_data.get("python_sdk_alternative", {})
    python_available = python_alt.get("available", False)
    python_alternative = python_alt.get("workaround", "")

    return {
        "name": name,
        "file": file_path,
        "short_description": short_desc,
        "syntax": cmd_data.get("syntax", ""),
        "python_available": python_available,
        "python_alternative": python_alternative,
    }


def scan_category_commands(category_dir: Path, category: str) -> list[dict[str, Any]]:
    """Scan a category directory and extract all command metadata."""
    commands = []

    # Get all JSON files recursively (for nested commands like contact/cmat/)
    for cmd_path in sorted(category_dir.rglob("*.json")):
        # Skip non-command files
        if cmd_path.name.startswith("_") or cmd_path.name == "category.json":
            continue

        try:
            cmd_meta = extract_command_metadata(cmd_path, category, category_dir)
            commands.append(cmd_meta)
        except Exception as e:
            print(f"Warning: Failed to process {cmd_path}: {e}")

    return commands


def generate_index(commands_dir: Path) -> dict[str, Any]:
    """Generate the complete index structure."""
    categories = {}

    for category_dir in sorted(commands_dir.iterdir()):
        if not category_dir.is_dir():
            continue

        category_name = category_dir.name

        # Get category metadata
        if category_name not in CATEGORY_METADATA:
            print(f"Warning: No metadata defined for category '{category_name}'")
            category_meta: dict[str, Any] = {
                "full_name": f"{category_name.title()} Commands",
                "description": f"Commands for {category_name}",
                "command_prefix": category_name,
            }
        else:
            category_meta = CATEGORY_METADATA[category_name].copy()

        # Scan commands
        commands = scan_category_commands(category_dir, category_name)
        category_meta["commands"] = commands

        categories[category_name] = category_meta

    # Build final index
    index = {
        "version": "1.0",
        "description": "PFC command documentation index for quick lookup and LLM-assisted command discovery",
        "categories": categories,
        "python_sdk_alternatives": PYTHON_SDK_ALTERNATIVES,
        "command_patterns": COMMAND_PATTERNS,
        "notes": GLOBAL_NOTES,
    }

    return index


def main() -> int:
    """Main entry point."""
    script_dir = Path(__file__).parent
    commands_dir = script_dir / "commands"
    index_path = script_dir / "index.json"

    if not commands_dir.exists():
        print(f"Error: Commands directory not found: {commands_dir}")
        return 1

    print(f"Scanning commands in: {commands_dir}")
    index = generate_index(commands_dir)

    # Count commands
    total_commands = sum(len(cat.get("commands", [])) for cat in index["categories"].values())

    print(f"Found {len(index['categories'])} categories, {total_commands} commands")

    # Write index
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"Generated: {index_path}")
    return 0


if __name__ == "__main__":
    exit(main())

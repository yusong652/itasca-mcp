"""One-shot bootstrap for missing PFC command JSON files.

Generates skeleton JSON files for commands that are present in installed
PFC HTML documentation (6.0 / 7.0 / 9.0) but not yet captured in the
repository's `commands/` tree. Two cases are handled:

* Partial scopes (existing JSON dir, missing some commands):
    model, contact, fragment

* New scopes (no JSON dir yet):
    program, history, fish

For each missing command, the script parses the HTML in all three PFC
versions and writes a complete file matching the existing schema:
    {
      "category": <scope>,
      "search_keywords": [...],
      "description": <from 7.0 HTML>,
      "notes": [],
      "python_sdk_alternative": {"available": false, "workaround": ""},
      "versions": {"6.0": {...}, "7.0": {...}, "9.0": {...}}
    }

After running this script, run `generate_index.py` to refresh `index.json`.

Usage:
    uv run python src/itasca_mcp/knowledge/resources/command_docs/bootstrap_missing.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from parse_pfc600 import CommandHTMLParser, normalize_syntax
except ModuleNotFoundError:
    from .parse_pfc600 import CommandHTMLParser, normalize_syntax


PFC600_DOC = Path("C:/Program Files/Itasca/PFC600/exe64/doc")
PFC700_DOC = Path("C:/Program Files/Itasca/PFC700/exe64/doc")
PFC900_DOC = Path("C:/Program Files/Itasca/ItascaSoftware900/exe64/doc")

COMMANDS_DIR = Path(__file__).parent / "commands"


# ---------------------------------------------------------------------------
# Scope configuration
# ---------------------------------------------------------------------------
#
# Each entry describes one scope: where its HTML lives in each PFC version,
# and which command stems (filename without prefix and .html) we want to
# bootstrap.
#
# For partial scopes the `stems` list is the explicit gap. For new scopes
# `stems` is None which means "bootstrap every HTML file found".


def _kernel_dir(root: Path, scope: str) -> Path:
    # Most kernel docs live under <scope>/commands, history under <scope>_manual/<scope>_commands.
    if scope == "history":
        return root / "common/kernel/doc/manual/history_manual/history_commands"
    return root / "common/kernel/doc/manual" / scope / "commands"


SCOPE_CONFIG: dict[str, dict[str, Any]] = {
    "model": {
        "html_dirs": {
            "6.0": _kernel_dir(PFC600_DOC, "model"),
            "7.0": _kernel_dir(PFC700_DOC, "model"),
            "9.0": _kernel_dir(PFC900_DOC, "model"),
        },
        "file_prefix": "cmd_model.",
        "stems": [
            "creep",
            "dynamic",
            "energy",
            "factor-of-safety",
            "fluid",
            "list",
            "precision",
            "step",
            "title",
        ],
    },
    "contact": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/contact/doc/contact_manual/contact_commands",
            "7.0": PFC700_DOC / "common/contact/doc/contact_manual/contact_commands",
            "9.0": PFC900_DOC / "common/contact/doc/contact_manual/contact_commands",
        },
        "file_prefix": "cmd_contact.",
        "stems": ["extra", "history", "list"],
    },
    "fragment": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/contact/doc/fragment_manual/fragment_commands",
            "7.0": PFC700_DOC / "common/contact/doc/fragment_manual/fragment_commands",
            "9.0": PFC900_DOC / "common/contact/doc/fragment_manual/fragment_commands",
        },
        "file_prefix": "cmd_fragment.",
        "stems": ["groupisolated", "groupslot", "map"],
    },
    "program": {
        "html_dirs": {
            "6.0": _kernel_dir(PFC600_DOC, "program"),
            "7.0": _kernel_dir(PFC700_DOC, "program"),
            "9.0": _kernel_dir(PFC900_DOC, "program"),
        },
        "file_prefix": "cmd_program.",
        "stems": None,  # bootstrap every HTML found
    },
    "history": {
        "html_dirs": {
            "6.0": _kernel_dir(PFC600_DOC, "history"),
            "7.0": _kernel_dir(PFC700_DOC, "history"),
            "9.0": _kernel_dir(PFC900_DOC, "history"),
        },
        "file_prefix": "cmd_history.",
        "stems": None,
    },
    "fish": {
        "html_dirs": {
            "6.0": _kernel_dir(PFC600_DOC, "fish"),
            "7.0": _kernel_dir(PFC700_DOC, "fish"),
            "9.0": _kernel_dir(PFC900_DOC, "fish"),
        },
        "file_prefix": "cmd_fish.",
        "stems": None,
    },
    # ---- Batch 2 ----
    "geometry": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/geometry/doc/manual/commands",
            "7.0": PFC700_DOC / "common/geometry/doc/manual/commands",
            "9.0": PFC900_DOC / "common/geometry/doc/manual/commands",
        },
        "file_prefix": "cmd_geometry.",
        "stems": None,
    },
    # The "dfn" docs module documents commands prefixed `fracture` — keep the
    # scope name aligned with the actual command verb users type.
    "fracture": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/dfn/doc/dfn_manual/dfn_commands",
            "7.0": PFC700_DOC / "common/dfn/doc/dfn_manual/dfn_commands",
            "9.0": PFC900_DOC / "common/dfn/doc/dfn_manual/dfn_commands",
        },
        "file_prefix": "cmd_fracture_",
        "stems": None,
    },
    "table": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/kernel/doc/manual/table_manual/table_commands",
            "7.0": PFC700_DOC / "common/kernel/doc/manual/table_manual/table_commands",
            "9.0": PFC900_DOC / "common/kernel/doc/manual/table_manual/table_commands",
        },
        "file_prefix": "cmd_table.",
        "stems": None,
    },
    "group": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/module/doc/manual/group_manual/group_commands",
            "7.0": PFC700_DOC / "common/module/doc/manual/group_manual/group_commands",
            "9.0": PFC900_DOC / "common/module/doc/manual/group_manual/group_commands",
        },
        "file_prefix": "cmd_group.",
        "stems": None,
    },
    "trace": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/kernel/doc/manual/trace_manual/trace_commands",
            "7.0": PFC700_DOC / "common/kernel/doc/manual/trace_manual/trace_commands",
            "9.0": PFC900_DOC / "common/kernel/doc/manual/trace_manual/trace_commands",
        },
        "file_prefix": "cmd_trace.",
        "stems": None,
    },
    "project": {
        "html_dirs": {
            "6.0": _kernel_dir(PFC600_DOC, "project"),
            "7.0": _kernel_dir(PFC700_DOC, "project"),
            "9.0": _kernel_dir(PFC900_DOC, "project"),
        },
        "file_prefix": "cmd_project.",
        "stems": None,
    },
    "data": {
        "html_dirs": {
            "6.0": _kernel_dir(PFC600_DOC, "data"),
            "7.0": _kernel_dir(PFC700_DOC, "data"),
            "9.0": _kernel_dir(PFC900_DOC, "data"),
        },
        "file_prefix": "cmd_data.",
        "stems": None,
    },
    "domain": {
        "html_dirs": {
            "6.0": PFC600_DOC / "common/kernel/doc/manual/domain_manual/command_reference/cmd_domain",
            "7.0": PFC700_DOC / "common/kernel/doc/manual/domain_manual/command_reference/cmd_domain",
            "9.0": PFC900_DOC / "common/kernel/doc/manual/domain_manual/command_reference/cmd_domain",
        },
        "file_prefix": "cmd_domain.",
        "stems": None,
        # 'model domain <x>' commands: filed under model as domain-<x>.json
        "json_scope": "model",
        "json_prefix": "domain-",
    },
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def parse_html_file(html_path: Path) -> dict[str, Any]:
    content = html_path.read_text(encoding="utf-8", errors="replace")
    parser = CommandHTMLParser()
    parser.feed(content)
    return {
        "command": parser.command_name,
        "syntax": parser.command_syntax,
        "keywords": parser.keywords,
        "description": parser.description,
    }


def build_version_entry(html_path: Path | None) -> dict[str, Any]:
    """Return version block for one PFC version."""
    if html_path is None or not html_path.exists():
        return {"available": False}
    parsed = parse_html_file(html_path)
    return {
        "command": parsed["command"],
        "syntax": normalize_syntax(parsed["syntax"]),
        "keywords": parsed["keywords"],
        "examples": [],
    }


def discover_stems(html_dir: Path, file_prefix: str) -> list[tuple[str, str]]:
    """Return [(json_key, raw_html_stem), ...] sorted by json_key.

    Dotted HTML stems (e.g. cmd_geometry.edge.create.html) are mapped to
    dash-separated JSON keys (edge-create), matching the rblock convention.
    The raw stem (with dots) is kept to reconstruct the HTML filename.
    """
    if not html_dir.exists():
        return []
    pairs: list[tuple[str, str]] = []
    for html_file in html_dir.glob("*.html"):
        name = html_file.stem
        if name.startswith(file_prefix):
            raw = name[len(file_prefix) :]
            json_key = raw.replace(".", "-")
            pairs.append((json_key, raw))
    return sorted(pairs)


def make_skeleton(scope: str, stem: str, html_paths: dict[str, Path]) -> dict[str, Any]:
    """Build a complete JSON document for one command."""
    # Use 7.0 as the canonical source for top-level description.
    description = ""
    if html_paths.get("7.0") and html_paths["7.0"].exists():
        description = parse_html_file(html_paths["7.0"])["description"]

    versions: dict[str, Any] = {}
    for version, path in html_paths.items():
        versions[version] = build_version_entry(path)

    return {
        "category": scope,
        "search_keywords": [stem],
        "description": description,
        "notes": [],
        "python_sdk_alternative": {
            "available": False,
            "workaround": "",
        },
        "versions": versions,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def process_scope(scope: str, config: dict[str, Any]) -> tuple[int, int]:
    """Process one scope. Returns (created, skipped)."""
    html_dirs: dict[str, Path] = config["html_dirs"]
    file_prefix: str = config["file_prefix"]
    declared_stems: list[str] | None = config["stems"]

    # Reference dir = 7.0 (newest with full coverage relative to 6.0)
    ref_dir = html_dirs["7.0"]
    if declared_stems is None:
        pairs = discover_stems(ref_dir, file_prefix)
    else:
        # Manual list: stems are already JSON keys (no dots).
        pairs = [(s, s) for s in declared_stems]

    json_scope: str = config.get("json_scope", scope)
    json_prefix: str = config.get("json_prefix", "")
    scope_dir = COMMANDS_DIR / json_scope
    scope_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0

    for json_key, raw_stem in pairs:
        json_key = json_prefix + json_key
        target = scope_dir / f"{json_key}.json"
        if target.exists():
            print(f"  [SKIP] exists: {target.name}")
            skipped += 1
            continue

        html_paths: dict[str, Path] = {}
        for version, html_dir in html_dirs.items():
            html_paths[version] = html_dir / f"{file_prefix}{raw_stem}.html"

        doc = make_skeleton(json_scope, json_key, html_paths)
        target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        kw_count = len(doc["versions"].get("7.0", {}).get("keywords", []) or [])
        print(f"  [NEW] {target.name} ({kw_count} keywords)")
        created += 1

    return created, skipped


def main() -> int:
    print("=" * 72)
    print("Bootstrapping missing PFC command JSON files")
    print("=" * 72)

    total_created = 0
    total_skipped = 0
    for scope, config in SCOPE_CONFIG.items():
        print(f"\n[{scope}]")
        created, skipped = process_scope(scope, config)
        print(f"  => {created} created, {skipped} skipped")
        total_created += created
        total_skipped += skipped

    print()
    print("=" * 72)
    print(f"Done. {total_created} files created, {total_skipped} skipped.")
    print("Next step: run generate_index.py to refresh index.json")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

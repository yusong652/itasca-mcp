"""
Parse PFC 7.0 HTML documentation and refresh "7.0" version data in command JSON files.

Rules:
- Commands present in JSON but absent in 7.0 HTML -> {"available": false}
- If HTML provides keyword sections, replace the stored 7.0 keywords
- If HTML has no keyword sections, keep existing 7.0 keywords as curated fallback

Usage:
    uv run python src/itasca_mcp/knowledge/resources/command_docs/parse_pfc700.py
"""

import json
from pathlib import Path

try:
    from parse_pfc600 import CommandHTMLParser as SharedCommandHTMLParser
    from parse_pfc600 import normalize_syntax as shared_normalize_syntax
except ModuleNotFoundError:
    from .parse_pfc600 import CommandHTMLParser as SharedCommandHTMLParser
    from .parse_pfc600 import normalize_syntax as shared_normalize_syntax


PFC700_DOC = Path("C:/Program Files/Itasca/PFC700/exe64/doc")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/command_docs/commands")


CATEGORY_CONFIG = {
    "ball": {
        "html_dir": PFC700_DOC / "pfc/pfcmodule/doc/manual/ball_manual/ball_commands",
        "file_prefix": "cmd_ball.",
        "dt_id_prefix": "kwd:",
        "json_to_html": {
            "results": "result",
        },
    },
    "clump": {
        "html_dir": PFC700_DOC / "pfc/pfcmodule/doc/manual/clump_manual/clump_commands",
        "file_prefix": "cmd_clump_",
        "dt_id_prefix": "kwd:",
        "extra_prefixes": ["cmd_clump."],
        "json_to_html": {
            "results": "result",
        },
    },
    "contact": {
        "html_dir": PFC700_DOC / "common/contact/doc/contact_manual/contact_commands",
        "file_prefix": "cmd_contact.",
        "dt_id_prefix": "kwd:",
        "extra_prefixes": ["cmd_cmat."],
    },
    "fragment": {
        "html_dir": PFC700_DOC / "common/contact/doc/fragment_manual/fragment_commands",
        "file_prefix": "cmd_fragment.",
        "dt_id_prefix": "kwd:",
    },
    "measure": {
        "html_dir": PFC700_DOC / "pfc/pfcmodule/doc/manual/measure_manual/command_reference/cmd_measure",
        "file_prefix": "cmd_measure.",
        "dt_id_prefix": "kwd:",
    },
    "model": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/model/commands",
        "file_prefix": "cmd_model.",
        "dt_id_prefix": "kwd:",
        "json_to_html": {
            "large-strain": "largestrain",
        },
        # 'model domain condition' is filed as model/domain-condition.json; its page
        # lives in the kernel's domain manual as cmd_domain.condition.html
        "also": [
            {
                "html_dir": PFC700_DOC / "common/kernel/doc/manual/domain_manual/command_reference/cmd_domain",
                "file_prefix": "cmd_domain.",
                "key_prefix": "domain-",
            }
        ],
    },
    "program": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/program/commands",
        "file_prefix": "cmd_program.",
        "dt_id_prefix": "kwd:",
    },
    "history": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/history_manual/history_commands",
        "file_prefix": "cmd_history.",
        "dt_id_prefix": "kwd:",
    },
    "fish": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/fish/commands",
        "file_prefix": "cmd_fish.",
        "dt_id_prefix": "kwd:",
    },
    "plot": {
        "html_dir": PFC700_DOC / "common/guimodule/doc/manual/plot",
        "file_prefix": "cmd_plot.",
        "dt_id_prefix": "kwd:",
    },
    "wall": {
        "html_dir": PFC700_DOC / "pfc/pfcmodule/doc/manual/wall_manual/wall_commands",
        "file_prefix": "cmd_wall_",
        "dt_id_prefix": "kwd:",
        "extra_prefixes": ["cmd_wall."],
        "json_to_html": {
            "results": "result",
            "active-sides": "activeside",
        },
    },
    "geometry": {
        "html_dir": PFC700_DOC / "common/geometry/doc/manual/commands",
        "file_prefix": "cmd_geometry.",
        "dt_id_prefix": "kwd:",
    },
    "fracture": {
        "html_dir": PFC700_DOC / "common/dfn/doc/dfn_manual/dfn_commands",
        "file_prefix": "cmd_fracture_",
        "dt_id_prefix": "kwd:",
    },
    "table": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/table_manual/table_commands",
        "file_prefix": "cmd_table.",
        "dt_id_prefix": "kwd:",
    },
    "group": {
        "html_dir": PFC700_DOC / "common/module/doc/manual/group_manual/group_commands",
        "file_prefix": "cmd_group.",
        "dt_id_prefix": "kwd:",
    },
    "trace": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/trace_manual/trace_commands",
        "file_prefix": "cmd_trace.",
        "dt_id_prefix": "kwd:",
    },
    "project": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/project/commands",
        "file_prefix": "cmd_project.",
        "dt_id_prefix": "kwd:",
    },
    "data": {
        "html_dir": PFC700_DOC / "common/kernel/doc/manual/data/commands",
        "file_prefix": "cmd_data.",
        "dt_id_prefix": "kwd:",
    },
}


def parse_html_file(html_path: Path) -> dict:
    """Parse a single command HTML file and return extracted data."""
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"error": str(exc)}

    parser = SharedCommandHTMLParser()
    parser.feed(content)

    return {
        "command": parser.command_name,
        "syntax": parser.command_syntax,
        "keywords": parser.keywords,
        "description": parser.description,
    }


def normalize_syntax(s: str) -> str:
    """Normalize whitespace in syntax string for comparison."""
    return shared_normalize_syntax(s)


def build_html_map(category: str, config: dict) -> dict:
    """Return dict mapping subcommand_name -> Path to HTML file."""
    html_dir = config["html_dir"]
    if not html_dir.exists():
        print(f"  [WARN] HTML dir not found: {html_dir}")
        return {}

    mapping = {}
    prefixes = [config["file_prefix"]]
    prefixes += config.get("extra_prefixes", [])

    for extra in config.get("also", []):
        for html_file in extra["html_dir"].glob("*.html"):
            if html_file.stem.startswith(extra["file_prefix"]):
                sub = html_file.stem[len(extra["file_prefix"]) :].replace(".", "-")
                mapping[extra["key_prefix"] + sub] = html_file

    for html_file in html_dir.glob("*.html"):
        name = html_file.stem
        for prefix in prefixes:
            if name.startswith(prefix):
                # Dotted HTML stems (e.g. cmd_geometry.edge.create) map to
                # dash-separated JSON keys (edge-create); flat stems pass through.
                sub = name[len(prefix) :].replace(".", "-")
                mapping[sub] = html_file
                break

    if category == "contact":
        for html_file in html_dir.glob("cmd_cmat.*.html"):
            sub_raw = html_file.stem[len("cmd_cmat.") :]
            json_key = f"cmat-{sub_raw}"
            mapping[json_key] = html_file

    return mapping


def process_category(category: str, config: dict):
    cat_dir = COMMANDS_DIR / category
    if not cat_dir.exists():
        print(f"  [SKIP] JSON dir not found: {cat_dir}")
        return

    html_map = build_html_map(category, config)
    json_to_html = config.get("json_to_html", {})
    for json_key, html_suffix in json_to_html.items():
        if html_suffix in html_map and json_key not in html_map:
            html_map[json_key] = html_map[html_suffix]

    print(f"  HTML files found: {sorted(html_map.keys())}")

    json_files = list(cat_dir.glob("*.json"))
    updated = 0
    skipped = 0

    for json_path in sorted(json_files):
        subcommand = json_path.stem
        data = json.loads(json_path.read_text(encoding="utf-8"))
        versions = data.setdefault("versions", {})
        existing_v70 = versions.get("7.0", {})

        html_path = html_map.get(subcommand)
        if html_path is None:
            versions["7.0"] = {"available": False}
            print(f"    {json_path.name}: NOT in 7.0 -> available=false")
        else:
            parsed = parse_html_file(html_path)
            if "error" in parsed:
                print(f"    {json_path.name}: PARSE ERROR: {parsed['error']}")
                skipped += 1
                continue

            v70 = {}
            v70["command"] = parsed["command"] or existing_v70.get("command", "")
            v70["syntax"] = normalize_syntax(parsed["syntax"]) or existing_v70.get("syntax", "")
            v70["keywords"] = parsed["keywords"] if parsed["keywords"] else existing_v70.get("keywords", [])
            if existing_v70.get("examples"):
                v70["examples"] = existing_v70["examples"]
            versions["7.0"] = v70
            print(f"    {json_path.name}: OK ({len(v70['keywords'])} keywords)")

        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        updated += 1

    print(f"  => {updated} files updated, {skipped} skipped")


def main():
    print("=" * 72)
    print("Refreshing 7.0 command docs from installed PFC700 HTML")
    print("=" * 72)
    for category, config in CATEGORY_CONFIG.items():
        print(f"\n[{category}]")
        process_category(category, config)


if __name__ == "__main__":
    main()

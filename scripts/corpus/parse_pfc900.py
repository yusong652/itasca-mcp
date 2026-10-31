"""
Parse PFC 9.0 HTML documentation and inject "9.0" version data into command JSON files.

Rules:
- Commands present in JSON (from 7.0) but absent in 9.0 HTML -> {"available": false}
- Commands present in 9.0 HTML but absent in JSON (new in 9.0)  -> skipped (no new entries)

Usage:
    uv run python src/itasca_mcp/knowledge/resources/command_docs/parse_pfc900.py
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

try:
    from parse_pfc600 import CommandHTMLParser as SharedCommandHTMLParser
    from parse_pfc600 import normalize_syntax as shared_normalize_syntax
except ModuleNotFoundError:
    from .parse_pfc600 import CommandHTMLParser as SharedCommandHTMLParser
    from .parse_pfc600 import normalize_syntax as shared_normalize_syntax

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------

PFC900_DOC = Path("C:/Program Files/Itasca/ItascaSoftware900/exe64/doc")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/command_docs/commands")

# Map category -> (html_dir, filename_pattern, id_prefix)
#   html_dir: absolute Path to the folder containing HTML command files
#   file_prefix: prefix of HTML stem, e.g. "cmd_ball."
#   dt_id_prefix: prefix used in dt id attributes
#
# Special overrides:
#   json_to_html: dict mapping JSON subcommand name -> HTML stem suffix
#     when the HTML filename does not follow the default pattern.
CATEGORY_CONFIG = {
    "ball": {
        "html_dir": PFC900_DOC / "pfc/pfcmodule/doc/manual/ball_manual/ball_commands",
        "file_prefix": "cmd_ball.",
        "dt_id_prefix": "kwd:",
        # ball/results.json -> cmd_ball.result.html (9.0 dropped the 's')
        "json_to_html": {
            "results": "result",
        },
    },
    "clump": {
        "html_dir": PFC900_DOC / "pfc/pfcmodule/doc/manual/clump_manual/clump_commands",
        "file_prefix": "cmd_clump_",
        "dt_id_prefix": "kwd:",
        # clump has mixed naming: cmd_clump.accumulate-stress.html and cmd_clump_create.html
        "extra_prefixes": ["cmd_clump."],
        "json_to_html": {
            "results": "result",
        },
    },
    "contact": {
        "html_dir": PFC900_DOC / "common/contact/doc/contact_manual/contact_commands",
        "file_prefix": "cmd_contact.",
        "dt_id_prefix": "kwd:",
        "extra_prefixes": ["cmd_cmat."],
    },
    "fragment": {
        "html_dir": PFC900_DOC / "common/contact/doc/fragment_manual/fragment_commands",
        "file_prefix": "cmd_fragment.",
        "dt_id_prefix": "kwd:",
    },
    "measure": {
        "html_dir": PFC900_DOC / "pfc/pfcmodule/doc/manual/measure_manual/command_reference/cmd_measure",
        "file_prefix": "cmd_measure.",
        "dt_id_prefix": "kwd:",
    },
    "model": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/model/commands",
        "file_prefix": "cmd_model.",
        "dt_id_prefix": "kwd:",
        # model/large-strain.json -> cmd_model.largestrain.html
        "json_to_html": {
            "large-strain": "largestrain",
        },
        # 'model domain condition' is filed as model/domain-condition.json; its page
        # lives in the kernel's domain manual as cmd_domain.condition.html
        "also": [
            {
                "html_dir": PFC900_DOC / "common/kernel/doc/manual/domain_manual/command_reference/cmd_domain",
                "file_prefix": "cmd_domain.",
                "key_prefix": "domain-",
            }
        ],
    },
    "program": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/program/commands",
        "file_prefix": "cmd_program.",
        "dt_id_prefix": "kwd:",
    },
    "history": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/history_manual/history_commands",
        "file_prefix": "cmd_history.",
        "dt_id_prefix": "kwd:",
    },
    "fish": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/fish/commands",
        "file_prefix": "cmd_fish.",
        "dt_id_prefix": "kwd:",
    },
    "plot": {
        "html_dir": PFC900_DOC / "common/guimodule/doc/manual/plot",
        "file_prefix": "cmd_plot.",
        "dt_id_prefix": "kwd:",
    },
    "wall": {
        "html_dir": PFC900_DOC / "pfc/pfcmodule/doc/manual/wall_manual/wall_commands",
        "file_prefix": "cmd_wall_",
        "dt_id_prefix": "kwd:",
        "extra_prefixes": ["cmd_wall."],
        "json_to_html": {
            "results": "result",
            "active-sides": "activeside",
        },
    },
    "geometry": {
        "html_dir": PFC900_DOC / "common/geometry/doc/manual/commands",
        "file_prefix": "cmd_geometry.",
        "dt_id_prefix": "kwd:",
    },
    "fracture": {
        "html_dir": PFC900_DOC / "common/dfn/doc/dfn_manual/dfn_commands",
        "file_prefix": "cmd_fracture_",
        "dt_id_prefix": "kwd:",
    },
    "table": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/table_manual/table_commands",
        "file_prefix": "cmd_table.",
        "dt_id_prefix": "kwd:",
    },
    "group": {
        "html_dir": PFC900_DOC / "common/module/doc/manual/group_manual/group_commands",
        "file_prefix": "cmd_group.",
        "dt_id_prefix": "kwd:",
    },
    "trace": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/trace_manual/trace_commands",
        "file_prefix": "cmd_trace.",
        "dt_id_prefix": "kwd:",
    },
    "project": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/project/commands",
        "file_prefix": "cmd_project.",
        "dt_id_prefix": "kwd:",
    },
    "data": {
        "html_dir": PFC900_DOC / "common/kernel/doc/manual/data/commands",
        "file_prefix": "cmd_data.",
        "dt_id_prefix": "kwd:",
    },
}

# ---------------------------------------------------------------------------
# HTML parser (same as parse_pfc600.py)
# ---------------------------------------------------------------------------


class CommandHTMLParser(HTMLParser):
    """Stateful parser for PFC command HTML files."""

    def __init__(self):
        super().__init__()
        # Result fields
        self.command_name = ""  # e.g. "ball create"
        self.command_syntax = ""  # full syntax string
        self.keywords = []  # list of {name, syntax, description}
        self.description = ""  # main command description

        # Internal state
        self._in_h1 = False
        self._in_fishcmd = False
        self._h1_text = ""

        # Main DT parsing (command-level)
        self._in_main_dt = False
        self._main_dt_depth = 0
        self._main_dt_text_parts = []

        # Main DD parsing (command description)
        self._in_main_dd = False
        self._main_dd_depth = 0
        self._main_desc_parts = []
        self._in_main_desc_p = False
        self._main_desc_done = False  # first <p> in main dd
        self._admonition_depth = 0  # skip admonition blocks

        # Keyword DT parsing
        self._current_kwd_id = None
        self._in_kwd_dt = False
        self._kwd_dt_depth = 0
        self._kwd_dt_parts = []

        # Keyword DD parsing
        self._in_kwd_dd = False
        self._kwd_dd_depth = 0
        self._kwd_desc_parts = []
        self._in_kwd_desc_p = False
        self._pending_kwd = None  # {name, syntax} waiting for description

        # Depth tracking
        self._global_depth = 0

        # Type class mapping
        self._type_map = {
            "varintfloat": lambda t: f"<{t.strip()}>",
            "varstringbool": lambda t: f"<{t.strip()}>",
            "varstring": lambda t: f"<{t.strip()}>",
            "token": lambda t: t,  # range token - keep as-is
        }

        # Whether we are inside a <span class="cmdopt">
        self._cmdopt_depth = 0
        self._cmdopt_open = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_type_text(self, tag, attrs):
        """Return formatted type placeholder or None."""
        cls = dict(attrs).get("class", "")
        if cls in self._type_map:
            return cls  # marker - actual text collected in handle_data
        return None

    def _is_type_span(self, cls):
        return cls in ("varintfloat", "varstringbool", "varstring")

    def _is_cmdopt_span(self, cls):
        return cls == "cmdopt"

    # ------------------------------------------------------------------
    # Feed helpers
    # ------------------------------------------------------------------

    def _dt_text(self, parts):
        """Join dt text parts into clean syntax string."""
        raw = "".join(parts)
        # Collapse multiple spaces
        raw = re.sub(r"  +", " ", raw)
        return raw.strip()

    def _dd_text(self, parts):
        raw = " ".join(p.strip() for p in parts if p.strip())
        return re.sub(r"\s+", " ", raw).strip()

    # ------------------------------------------------------------------
    # HTMLParser overrides
    # ------------------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        self._global_depth += 1
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")
        id_ = attr_dict.get("id", "")

        # --- h1 ---
        if tag == "h1":
            self._in_h1 = True
            self._h1_text = ""

        # --- fishcmd span inside h1 ---
        if self._in_h1 and tag == "span" and cls == "fishcmd":
            self._in_fishcmd = True

        # --- Main command DT ---
        # <dl class="ball command"> or <dl class="model command"> etc.
        if tag == "dl" and "command" in cls and not self._in_main_dt and not self.command_syntax:
            # This is the top-level command DL
            self._waiting_main_dl = True

        if tag == "dt" and id_.startswith("command:") and not self.command_syntax:
            self._in_main_dt = True
            self._main_dt_depth = self._global_depth
            self._main_dt_text_parts = []
            self._cmdopt_depth = 0

        # --- Main command DD (description) ---
        if (
            tag == "dd"
            and self._in_main_dt is False
            and self.command_syntax
            and not self._in_main_dd
            and not self._main_desc_done
        ):
            self._in_main_dd = True
            self._main_dd_depth = self._global_depth
            self._admonition_depth = 0

        # --- Keyword DT ---
        if tag == "dt" and (id_.startswith("kwd:") or id_.startswith("keyword:")):
            # Extract keyword name from id, e.g. "kwd:ball.create.radius" -> "radius"
            kwd_name = id_.split(".")[-1]
            self._current_kwd_id = kwd_name
            self._in_kwd_dt = True
            self._kwd_dt_depth = self._global_depth
            self._kwd_dt_parts = []
            self._cmdopt_depth = 0

        # --- Keyword DD ---
        if tag == "dd" and self._in_kwd_dt is False and self._current_kwd_id and not self._in_kwd_dd:
            self._in_kwd_dd = True
            self._kwd_dd_depth = self._global_depth
            self._kwd_desc_parts = []
            self._in_kwd_desc_p = False

        # --- Track cmdopt spans ---
        if tag == "span" and cls == "cmdopt":
            self._cmdopt_depth += 1
            if self._in_main_dt:
                self._main_dt_text_parts.append("[")
            if self._in_kwd_dt:
                self._kwd_dt_parts.append("[")

        # --- Track type spans (varintfloat etc.) ---
        if tag == "span" and self._is_type_span(cls):
            if self._in_main_dt or self._in_kwd_dt:
                # We'll wrap text in <> when we see it
                self._current_type_span = cls
            else:
                self._current_type_span = None
        else:
            if not (tag == "span" and cls == "cmdopt"):
                pass  # clear only on non-cmdopt, non-type spans is handled below

        # Track type span state
        if tag == "span":
            self._span_class_stack = getattr(self, "_span_class_stack", [])
            self._span_class_stack.append(cls)

        # p inside keyword dd
        if tag == "p" and self._in_kwd_dd:
            self._in_kwd_desc_p = True

        # p inside main dd (first non-admonition p)
        if tag == "p" and self._in_main_dd and not self._main_desc_done:
            if self._admonition_depth == 0:
                self._in_main_desc_p = True

        # admonition tracking (skip primary keywords list etc.)
        if tag == "div" and "admonition" in cls:
            if self._in_main_dd:
                self._admonition_depth += 1

    def handle_endtag(self, tag):
        cls_stack = getattr(self, "_span_class_stack", [])

        # --- h1 ---
        if tag == "h1":
            self._in_h1 = False
            self._in_fishcmd = False
            if self._h1_text:
                self.command_name = self._h1_text.strip()

        # --- fishcmd span ---
        if tag == "span" and self._in_fishcmd and self._in_h1:
            self._in_fishcmd = False

        # --- cmdopt tracking ---
        if tag == "span" and cls_stack and cls_stack[-1] == "cmdopt":
            if self._cmdopt_depth > 0:
                self._cmdopt_depth -= 1
                if self._in_main_dt:
                    self._main_dt_text_parts.append("]")
                if self._in_kwd_dt:
                    self._kwd_dt_parts.append("]")

        # --- Main DT end ---
        if tag == "dt" and self._in_main_dt and self._global_depth == self._main_dt_depth:
            self._in_main_dt = False
            self.command_syntax = self._dt_text(self._main_dt_text_parts)

        # --- Main DD end ---
        if tag == "dd" and self._in_main_dd and self._global_depth == self._main_dd_depth:
            self._in_main_dd = False

        # --- Main desc p end ---
        if tag == "p" and self._in_main_desc_p:
            self._in_main_desc_p = False
            self._main_desc_done = True
            self.description = self._dd_text(self._main_desc_parts)

        # --- Admonition end ---
        if tag == "div" and self._admonition_depth > 0 and self._in_main_dd:
            self._admonition_depth -= 1

        # --- Keyword DT end ---
        if tag == "dt" and self._in_kwd_dt and self._global_depth == self._kwd_dt_depth:
            self._in_kwd_dt = False
            kwd_syntax = self._dt_text(self._kwd_dt_parts)
            self._pending_kwd = {
                "name": self._current_kwd_id,
                "syntax": kwd_syntax,
            }

        # --- Keyword DD end ---
        if tag == "dd" and self._in_kwd_dd and self._global_depth == self._kwd_dd_depth:
            self._in_kwd_dd = False
            if self._pending_kwd:
                desc = self._dd_text(self._kwd_desc_parts)
                self.keywords.append(
                    {
                        "name": self._pending_kwd["name"],
                        "syntax": self._pending_kwd["syntax"],
                        "description": desc,
                    }
                )
                self._pending_kwd = None
                self._current_kwd_id = None

        # --- Keyword desc p end ---
        if tag == "p" and self._in_kwd_desc_p:
            self._in_kwd_desc_p = False

        # span stack pop
        if tag == "span" and cls_stack:
            cls_stack.pop()

        self._global_depth -= 1

    def _in_type_span(self, span_stack):
        """Return True if any ancestor span is a type-variable span."""
        return any(c in ("varintfloat", "varstringbool", "varstring") for c in span_stack)

    def handle_data(self, data):
        span_stack = getattr(self, "_span_class_stack", [])
        top_cls = span_stack[-1] if span_stack else ""

        # h1 fishcmd text
        if self._in_h1 and self._in_fishcmd:
            self._h1_text += data
            return

        # Main DT text collection
        if self._in_main_dt:
            if self._in_type_span(span_stack):
                # We're inside a type-variable span (possibly nested in null)
                t = data.strip()
                if t:
                    self._main_dt_text_parts.append(f"<{t}>")
            elif top_cls in ("cmdname", "cmdkey", "pref", "null", "token"):
                self._main_dt_text_parts.append(data)
            elif top_cls == "cmdopt":
                pass  # brackets already added on open/close
            return

        # Keyword DT text collection
        if self._in_kwd_dt:
            if self._in_type_span(span_stack):
                t = data.strip()
                if t:
                    self._kwd_dt_parts.append(f"<{t}>")
            elif top_cls in ("cmdname", "cmdkey", "pref", "null", "token"):
                self._kwd_dt_parts.append(data)
            elif top_cls == "cmdopt":
                pass
            return

        # Main description p text
        if self._in_main_desc_p:
            self._main_desc_parts.append(data)
            return

        # Keyword description p text
        if self._in_kwd_desc_p:
            self._kwd_desc_parts.append(data)
            return


# ---------------------------------------------------------------------------
# Parsing logic
# ---------------------------------------------------------------------------


def parse_html_file(html_path: Path) -> dict:
    """Parse a single command HTML file and return extracted data."""
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e)}

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
    normalized = shared_normalize_syntax(s)
    return normalized.replace("[:bool:b]", "[<b>]")


# ---------------------------------------------------------------------------
# File mapping: map JSON subcommand name -> HTML file path
# ---------------------------------------------------------------------------


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
        name = html_file.stem  # e.g. "cmd_ball.create"
        for prefix in prefixes:
            if name.startswith(prefix):
                # Dotted HTML stems (e.g. cmd_geometry.edge.create) map to
                # dash-separated JSON keys (edge-create); flat stems pass through.
                sub = name[len(prefix) :].replace(".", "-")
                mapping[sub] = html_file
                break

    # Special: contact also has cmat commands
    # cmat commands: cmd_cmat.add.html -> "cmat-add" in JSON
    if category == "contact":
        for html_file in html_dir.glob("cmd_cmat.*.html"):
            sub_raw = html_file.stem[len("cmd_cmat.") :]  # e.g. "add"
            json_key = f"cmat-{sub_raw}"
            mapping[json_key] = html_file

    return mapping


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------


def process_category(category: str, config: dict):
    cat_dir = COMMANDS_DIR / category
    if not cat_dir.exists():
        print(f"  [SKIP] JSON dir not found: {cat_dir}")
        return

    html_map = build_html_map(category, config)
    # Apply json_to_html overrides: add alias entries into html_map
    # so that e.g. "results" maps to the same Path as "result"
    json_to_html = config.get("json_to_html", {})
    for json_key, html_suffix in json_to_html.items():
        if html_suffix in html_map and json_key not in html_map:
            html_map[json_key] = html_map[html_suffix]

    print(f"  HTML files found: {sorted(html_map.keys())}")

    json_files = list(cat_dir.glob("*.json"))
    updated = 0
    skipped = 0

    for json_path in sorted(json_files):
        subcommand = json_path.stem  # e.g. "create", "cmat-add"

        # Load existing JSON
        data = json.loads(json_path.read_text(encoding="utf-8"))
        versions = data.setdefault("versions", {})
        v70 = versions.get("7.0", {})

        # Find matching HTML
        html_path = html_map.get(subcommand)

        if html_path is None:
            # 9.0 does not have this command
            versions["9.0"] = {"available": False}
            print(f"    {json_path.name}: NOT in 9.0 -> available=false")
        else:
            parsed = parse_html_file(html_path)
            if "error" in parsed:
                print(f"    {json_path.name}: PARSE ERROR: {parsed['error']}")
                skipped += 1
                continue

            # Build 9.0 version entry
            v90 = {}
            v90["command"] = parsed["command"] or v70.get("command", "")
            v90["syntax"] = normalize_syntax(parsed["syntax"]) or v70.get("syntax", "")
            v90["keywords"] = parsed["keywords"] if parsed["keywords"] else v70.get("keywords", [])

            # Copy examples from 7.0 (9.0 HTML doesn't have structured examples)
            v90["examples"] = v70.get("examples", [])

            versions["9.0"] = v90
            print(f"    {json_path.name}: OK ({len(v90['keywords'])} keywords)")

        # Write back
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        updated += 1

    print(f"  => {updated} files updated, {skipped} skipped")


def main():
    print("=== PFC 9.0 documentation parser ===\n")
    for category, config in CATEGORY_CONFIG.items():
        print(f"[{category}]")
        if not config["html_dir"].exists():
            print(f"  [SKIP] HTML directory not found: {config['html_dir']}")
            continue
        process_category(category, config)
        print()
    print("Done.")


if __name__ == "__main__":
    main()

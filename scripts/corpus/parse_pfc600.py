"""
Parse PFC 6.0 HTML documentation and inject "6.0" version data into command JSON files.

Usage:
    uv run python src/itasca_mcp/knowledge/resources/command_docs/parse_pfc600.py
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------

PFC600_DOC = Path("C:/Program Files/Itasca/PFC600/exe64/doc")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/command_docs/commands")

# Map category -> (html_dir, filename_pattern, id_prefix)
#   html_dir: absolute Path to the folder containing HTML command files
#   filename_pattern: glob pattern relative to html_dir
#   id_prefix: prefix used in dt id attributes, e.g. "kwd:" or "keyword:"
CATEGORY_CONFIG = {
    "ball": {
        "html_dir": PFC600_DOC / "pfc/pfcmodule/doc/manual/ball_manual/ball_commands",
        "file_prefix": "cmd_ball.",
        "dt_id_prefix": "kwd:",
    },
    "clump": {
        "html_dir": PFC600_DOC / "pfc/pfcmodule/doc/manual/clump_manual/clump_commands",
        "file_prefix": "cmd_clump_",
        "dt_id_prefix": "kwd:",
    },
    "contact": {
        "html_dir": PFC600_DOC / "common/contact/doc/contact_manual/contact_commands",
        "file_prefix": "cmd_contact.",
        "dt_id_prefix": "kwd:",
        "extra_prefixes": ["cmd_cmat."],
    },
    "fragment": {
        "html_dir": PFC600_DOC / "common/contact/doc/fragment_manual/fragment_commands",
        "file_prefix": "cmd_fragment.",
        "dt_id_prefix": "kwd:",
    },
    "measure": {
        "html_dir": PFC600_DOC / "pfc/pfcmodule/doc/manual/measure_manual/command_reference/cmd_measure",
        "file_prefix": "cmd_measure.",
        "dt_id_prefix": "kwd:",
    },
    "model": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/model/commands",
        "file_prefix": "cmd_model.",
        "dt_id_prefix": "kwd:",
        "json_to_html": {
            "large-strain": "largestrain",
        },
        # 'model domain condition' is filed as model/domain-condition.json; its page
        # lives in the kernel's domain manual as cmd_domain.condition.html
        "also": [
            {
                "html_dir": PFC600_DOC / "common/kernel/doc/manual/domain_manual/command_reference/cmd_domain",
                "file_prefix": "cmd_domain.",
                "key_prefix": "domain-",
            }
        ],
    },
    "program": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/program/commands",
        "file_prefix": "cmd_program.",
        "dt_id_prefix": "kwd:",
    },
    "history": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/history_manual/history_commands",
        "file_prefix": "cmd_history.",
        "dt_id_prefix": "kwd:",
    },
    "fish": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/fish/commands",
        "file_prefix": "cmd_fish.",
        "dt_id_prefix": "kwd:",
    },
    "plot": {
        "html_dir": PFC600_DOC / "common/guimodule/doc/manual/plot",
        "file_prefix": "cmd_plot.",
        "dt_id_prefix": "kwd:",
    },
    "wall": {
        "html_dir": PFC600_DOC / "pfc/pfcmodule/doc/manual/wall_manual/wall_commands",
        "file_prefix": "cmd_wall_",
        "dt_id_prefix": "kwd:",
    },
    "geometry": {
        "html_dir": PFC600_DOC / "common/geometry/doc/manual/commands",
        "file_prefix": "cmd_geometry.",
        "dt_id_prefix": "kwd:",
    },
    "fracture": {
        "html_dir": PFC600_DOC / "common/dfn/doc/dfn_manual/dfn_commands",
        "file_prefix": "cmd_fracture_",
        "dt_id_prefix": "kwd:",
    },
    "table": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/table_manual/table_commands",
        "file_prefix": "cmd_table.",
        "dt_id_prefix": "kwd:",
    },
    "group": {
        "html_dir": PFC600_DOC / "common/module/doc/manual/group_manual/group_commands",
        "file_prefix": "cmd_group.",
        "dt_id_prefix": "kwd:",
    },
    "trace": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/trace_manual/trace_commands",
        "file_prefix": "cmd_trace.",
        "dt_id_prefix": "kwd:",
    },
    "project": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/project/commands",
        "file_prefix": "cmd_project.",
        "dt_id_prefix": "kwd:",
    },
    "data": {
        "html_dir": PFC600_DOC / "common/kernel/doc/manual/data/commands",
        "file_prefix": "cmd_data.",
        "dt_id_prefix": "kwd:",
    },
}

# ---------------------------------------------------------------------------
# HTML parser
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

        # Keyword DD parsing. A keyword's <dd> may hold a nested <dl> of its own
        # options (dt id "kwd:point.gridpoint" inside the dd of "kwd:point"), so
        # open dds form a stack; a closing option is folded into its parent.
        self._kwd_stack = []  # [{name, syntax, depth, parts, children}]
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
        if self._has_type_class(cls):
            return cls  # marker - actual text collected in handle_data
        return None

    def _is_type_span(self, cls):
        return self._has_type_class(cls)

    def _is_cmdopt_span(self, cls):
        return self._has_class(cls, "cmdopt")

    def _class_tokens(self, cls):
        return [token for token in str(cls).split() if token]

    def _has_class(self, cls, token):
        return token in self._class_tokens(cls)

    def _has_type_class(self, cls):
        return any(token.startswith("var") for token in self._class_tokens(cls))

    def _is_syntax_span(self, cls):
        tokens = self._class_tokens(cls)
        if not tokens:
            return False
        if any(token.startswith("var") for token in tokens):
            return True
        return any(token in {"cmdname", "cmdkey", "pref", "null", "token", "cmdopt", "pre"} for token in tokens)

    def _should_collect_syntax_text(self, span_stack):
        return any(self._is_syntax_span(cls) for cls in span_stack)

    # ------------------------------------------------------------------
    # Feed helpers
    # ------------------------------------------------------------------

    def _dt_text(self, parts):
        """Join dt text parts into clean syntax string."""
        raw = "".join(parts)
        # Collapse multiple spaces
        raw = re.sub(r"  +", " ", raw)
        return raw.strip()

    def _fold_keyword(self, frame):
        """One keyword entry; nested options become alternatives in its syntax.

        'point <i> keyword' with options '<v> [add]' and 'gridpoint <s>' reads
        'point <i> {<v> [add] | gridpoint <s>}'; each option's text follows the
        keyword's own description.
        """
        syntax = frame["syntax"]
        description = self._dd_text(frame["parts"])
        children = frame["children"]
        if children:
            alternatives = "{" + " | ".join(c["syntax"] for c in children) + "}"
            placeholder = r"\bkeywo?rd\b"  # the manual misspells it 'keywrd' once (zone interface node)
            if re.search(placeholder, syntax):
                syntax = re.sub(placeholder, lambda _: alternatives, syntax, count=1)
            else:
                syntax = f"{syntax} {alternatives}"
            options = "; ".join(
                f"{c['syntax']}: {c['description']}" if c["description"] else c["syntax"] for c in children
            )
            description = f"{description} Options: {options}" if description else f"Options: {options}"
        return {"name": frame["name"], "syntax": syntax, "description": description}

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
        if tag == "dd" and self._in_kwd_dt is False and self._pending_kwd:
            self._kwd_stack.append({**self._pending_kwd, "depth": self._global_depth, "parts": [], "children": []})
            self._pending_kwd = None
            self._in_kwd_desc_p = False

        # --- Track cmdopt spans ---
        if tag == "span" and self._is_cmdopt_span(cls):
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
            if not (tag == "span" and self._is_cmdopt_span(cls)):
                pass  # clear only on non-cmdopt, non-type spans is handled below

        # Track type span state
        if tag == "span":
            self._span_class_stack = getattr(self, "_span_class_stack", [])
            self._span_class_stack.append(cls)

        # p inside keyword dd
        if tag == "p" and self._kwd_stack:
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
                self.command_name = re.sub(
                    r"\s+command\s*$",
                    "",
                    self._h1_text.strip(),
                    flags=re.IGNORECASE,
                ).strip()

        # --- fishcmd span ---
        if tag == "span" and self._in_fishcmd and self._in_h1:
            self._in_fishcmd = False

        # --- cmdopt tracking ---
        if tag == "span" and cls_stack and self._is_cmdopt_span(cls_stack[-1]):
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
        if tag == "dd" and self._kwd_stack and self._global_depth == self._kwd_stack[-1]["depth"]:
            entry = self._fold_keyword(self._kwd_stack.pop())
            if self._kwd_stack:
                self._kwd_stack[-1]["children"].append(entry)
            else:
                self.keywords.append(entry)
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
        return any(token.startswith("var") for c in span_stack for token in self._class_tokens(c))

    def handle_data(self, data):
        span_stack = getattr(self, "_span_class_stack", [])

        # h1 fishcmd text
        if self._in_h1:
            self._h1_text += data
            return

        # Main DT text collection
        if self._in_main_dt:
            if self._in_type_span(span_stack):
                t = data.strip()
                if t:
                    self._main_dt_text_parts.append(f"<{t}>")
            elif self._should_collect_syntax_text(span_stack):
                t = data.strip()
                if t in {"<", ">"}:
                    return
                self._main_dt_text_parts.append(data)
            return

        # Keyword DT text collection
        if self._in_kwd_dt:
            if self._in_type_span(span_stack):
                t = data.strip()
                if t:
                    self._kwd_dt_parts.append(f"<{t}>")
            elif self._should_collect_syntax_text(span_stack):
                t = data.strip()
                if t in {"<", ">"}:
                    return
                self._kwd_dt_parts.append(data)
            return

        # Main description p text
        if self._in_main_desc_p:
            self._main_desc_parts.append(data)
            return

        # Keyword description p text
        if self._in_kwd_desc_p and self._kwd_stack:
            self._kwd_stack[-1]["parts"].append(data)
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

    parser = CommandHTMLParser()
    parser.feed(content)

    return {
        "command": parser.command_name,
        "syntax": parser.command_syntax,
        "keywords": parser.keywords,
        "description": parser.description,
    }


def normalize_syntax(s: str) -> str:
    """Normalize whitespace in syntax string for comparison."""
    return re.sub(r"\s+", " ", s).strip()


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
            # 6.0 does not have this command
            versions["6.0"] = {"available": False}
            print(f"    {json_path.name}: NOT in 6.0 -> available=false")
        else:
            parsed = parse_html_file(html_path)
            if "error" in parsed:
                print(f"    {json_path.name}: PARSE ERROR: {parsed['error']}")
                skipped += 1
                continue

            # Build 6.0 version entry
            v60 = {}
            v60["command"] = parsed["command"] or v70.get("command", "")
            v60["syntax"] = normalize_syntax(parsed["syntax"]) or v70.get("syntax", "")
            v60["keywords"] = parsed["keywords"] if parsed["keywords"] else v70.get("keywords", [])

            # Copy examples from 7.0 (6.0 HTML doesn't have them)
            v60["examples"] = v70.get("examples", [])

            versions["6.0"] = v60
            print(f"    {json_path.name}: OK ({len(v60['keywords'])} keywords)")

        # Write back
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        updated += 1

    print(f"  => {updated} files updated, {skipped} skipped")


def main():
    print("=== PFC 6.0 documentation parser ===\n")
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

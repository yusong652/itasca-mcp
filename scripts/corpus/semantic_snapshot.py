"""Dump the resolved (served) view of all four doc trees for diffing.

Workflow for a corpus format migration (docs/development/corpus-spec.md):

    uv run python scripts/corpus/semantic_snapshot.py SNAP_DIR/before
    ... run the migration script ...
    uv run python scripts/corpus/semantic_snapshot.py SNAP_DIR/after
    git diff --no-index SNAP_DIR/before SNAP_DIR/after

Commands and fish are dumped through the loaders'/tools' *resolution* path, so
a purely mechanical format change (version blocks -> availability, bool maps ->
version lists) produces zero diff there; only real content changes show.
references and python_api are dumped as loaded docs, so shape conversions do
show — as uniform, reviewable diffs.

tests/test_corpus_sweep.py is the structural guard; this is the content guard.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from itasca_mcp.knowledge.commands.loader import CommandLoader  # noqa: E402
from itasca_mcp.knowledge.config import SUPPORTED_SOFTWARE, references_root  # noqa: E402
from itasca_mcp.knowledge.fish import FishLoader  # noqa: E402
from itasca_mcp.knowledge.python_api import PythonAPILoader  # noqa: E402
from itasca_mcp.knowledge.references.loader import ReferenceLoader  # noqa: E402
from itasca_mcp.tools.docs import fish as fish_tool  # noqa: E402
from itasca_mcp.utils import supported_doc_versions  # noqa: E402


def snapshot_commands(software: str) -> dict:
    out: dict = {}
    for version in sorted(supported_doc_versions(software)):
        view = out.setdefault(version, {})
        for cmd_meta in CommandLoader.get_all_commands(software=software):
            category, name = cmd_meta["category"], cmd_meta["name"]
            try:
                doc = CommandLoader.load_command_doc(category, name, version, software=software)
            except KeyError:
                continue
            if doc is not None:
                view[f"{category}/{name}"] = doc
    return out


def snapshot_references(software: str) -> dict:
    out: dict = {}
    for category in ReferenceLoader.load_index(software=software).get("categories", {}):
        view = out.setdefault(category, {})
        for entry in ReferenceLoader.get_item_list(category, None, software=software):
            item = entry.get("name") or entry.get("model") or entry.get("element")
            if not isinstance(item, str) or not item:
                continue
            view[item] = ReferenceLoader.load_item_doc(category, item, software=software)
            if ReferenceLoader.is_directory_item(category, item, software=software):
                directory = (
                    ReferenceLoader.load_index(software=software)["categories"][category].get("directory") or category
                )
                for sub in sorted((references_root(software) / directory / item).glob("*.json")):
                    if sub.name != "index.json":
                        view[f"{item}/{sub.stem}"] = ReferenceLoader.load_sub_item_doc(
                            category, item, sub.stem, software=software
                        )
    return out


def snapshot_python_api(software: str) -> dict:
    index = PythonAPILoader.load_index(software=software)
    return {
        "modules": {key: PythonAPILoader.load_module(key, software=software) for key in index.get("modules", {})},
        "objects": {key: PythonAPILoader.load_object(key, software=software) for key in index.get("objects", {})},
    }


def snapshot_fish(software: str) -> dict:
    out: dict = {}
    versions = sorted(supported_doc_versions(software))
    for name in FishLoader.entries(software=software):
        record: dict = {}
        for version in versions:
            envelope = fish_tool.browse(software, name, version)
            if envelope["ok"]:
                record[version] = envelope["data"]["entries"][0]
            else:
                record[version] = {"error": envelope["error"]["code"]}
        out[name] = record
    return out


TREES = {
    "commands": snapshot_commands,
    "references": snapshot_references,
    "python_api": snapshot_python_api,
    "fish": snapshot_fish,
}


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} OUT_DIR")
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for software in SUPPORTED_SOFTWARE:
        for tree, fn in TREES.items():
            path = out_dir / f"{software}_{tree}.json"
            text = json.dumps(fn(software), ensure_ascii=False, sort_keys=True, indent=1)
            path.write_text(text, encoding="utf-8")
            manifest[path.name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            print(f"{path.name}: {len(text):>10,} chars  {manifest[path.name][:12]}")
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

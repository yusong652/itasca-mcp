"""Every documentation page fits one response.

A page past the envelope size limit used to come back as a bare ``_truncated`` stub
with nothing to page through, which hid ``itasca.ball.Ball``, ``measure create`` and the
whole 3DEC python_api root. Pages now trim themselves and name a deeper path for what
they leave out; the sweep below walks every browse path so corpus growth cannot bring
the stub back unnoticed.
"""

from collections.abc import Iterator
from typing import Any

from itasca_mcp.knowledge.commands import CommandLoader
from itasca_mcp.tools.docs import commands, python_api, reference

ENGINE_VERSIONS = {
    "pfc": ("6.0", "7.0", "9.0"),
    "flac": ("7.0", "9.0"),
    "3dec": ("7.0", "9.0"),
    "mpoint": ("9.0",),
    "massflow": ("9.0",),
}


def _entries(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    return (envelope.get("data") or {}).get("entries", []) if envelope.get("ok") else []


def _all_pages() -> Iterator[tuple[str, dict[str, Any]]]:
    for software, versions in ENGINE_VERSIONS.items():
        categories = CommandLoader.load_index(software=software).get("categories", {})
        for version in versions:
            yield f"{software} {version} commands", commands.browse(software, None, version)
            for category, category_data in categories.items():
                yield f"{software} {version} commands {category}", commands.browse(software, category, version)
                for command in category_data.get("commands", []):
                    path = f"{category} {command['name']}"
                    yield f"{software} {version} commands {path}", commands.browse(software, path, version)

            root = reference.browse(software, None, version)
            yield f"{software} {version} reference", root
            for category in _entries(root):
                listing = reference.browse(software, category["name"], version)
                yield f"{software} {version} reference {category['name']}", listing
                for item in _entries(listing):
                    path = f"{category['name']} {item.get('name')}"
                    page = reference.browse(software, path, version)
                    yield f"{software} {version} reference {path}", page
                    for sub in (_entries(page) or [{}])[0].get("sub_items", []):
                        sub_path = f"{path} {sub['name']}"
                        yield (
                            f"{software} {version} reference {sub_path}",
                            reference.browse(software, sub_path, version),
                        )

        root = python_api.browse(software, None, "9.0")
        yield f"{software} python_api", root
        for module in _entries(root):
            if module.get("entry_type") != "module":
                continue
            page = python_api.browse(software, module["path"], "9.0")
            yield f"{software} python_api {module['path']}", page
            for obj in (page.get("data") or {}).get("summary", {}).get("related_objects", []):
                path = f"{module['path']}.{obj}"
                yield f"{software} python_api {path}", python_api.browse(software, path, "9.0")


def test_no_documentation_page_is_blanked() -> None:
    blanked = [label for label, envelope in _all_pages() if (envelope.get("data") or {}).get("_truncated")]
    assert not blanked


def test_trimmed_command_page_keeps_its_parts_reachable() -> None:
    page = commands.browse("pfc", "measure create", "9.0")["data"]
    omitted = page["summary"]["omitted_sections"]
    assert omitted and "measure create <name>" in page["summary"]["hint"]

    section = commands.browse("pfc", f"measure create {omitted[0]}", "9.0")["data"]["entries"][0]
    assert section["section"] == omitted[0] and section["content"]
    keyword = commands.browse("pfc", "measure create position", "9.0")["data"]["entries"][0]["keyword"]
    assert keyword["name"] == "position" and keyword["description"]
    # 'kwd:' event keywords are addressed by their bare name
    event = commands.browse("pfc", "fish callback bond_break", "9.0")["data"]["entries"][0]["keyword"]
    assert event["name"] == "kwd:bond_break"
    # a real three-word command still wins over the section lookup
    assert commands.browse("flac", "structure beam apply", "9.0")["data"]["entries"][0]["command"] == "beam apply"

    missing = commands.browse("pfc", "measure create bogus", "9.0")
    assert missing["error"]["code"] == "section_not_found"
    assert "position" in missing["error"]["details"]["available_keywords"]


def test_trimmed_object_page_lists_method_signatures() -> None:
    page = python_api.browse("pfc", "itasca.ball.Ball", "9.0")["data"]
    assert page["summary"]["compacted"] == ["methods"]
    methods = {m["name"]: m["signature"] for m in page["entries"][0]["doc"]["methods"]}
    assert "in_group" in methods and methods["in_group"]
    method = python_api.browse("pfc", "itasca.ball.Ball.in_group", "9.0")["data"]["entries"][0]
    assert method["doc"]["name"] == "in_group"


def test_object_page_section_reachable_by_path() -> None:
    entry = python_api.browse("pfc", "itasca.measure.Measure.usage_examples", "9.0")["data"]["entries"][0]
    assert entry["section"] == "usage_examples" and entry["content"]


def test_trimmed_reference_item_keeps_its_parts_reachable() -> None:
    page = reference.browse("pfc", "contact-models linearpbond", "9.0")["data"]
    assert "callback_events" in page["summary"]["omitted_sections"]
    events = reference.browse("pfc", "contact-models linearpbond callback_events", "9.0")["data"]["entries"][0]
    assert events["content"]["events"][0]["name"] == "bond_break"
    prop = reference.browse("pfc", "contact-models linearpbond pb_ten", "9.0")["data"]["entries"][0]["property"]
    assert prop["keyword"] == "pb_ten"
    missing = reference.browse("pfc", "contact-models linearpbond bogus", "9.0")
    assert missing["error"]["code"] == "section_not_found"

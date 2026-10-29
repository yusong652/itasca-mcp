"""Tests for the figure_reference corpus-flagging pipeline (v2).

`scripts/corpus/extract_figure_refs.py` mines the source HTML for the reference
figures the text corpus dropped and writes `figure_manifest.json`;
`scripts/corpus/flag_figure_defined.py` joins that manifest onto every command
doc and adds a structured `figure_reference` flag with two independent signals:

* `figures`  -- neutral fact: the figures exist at these verified doc_paths.
* `text_incomplete` / `deferrals` -- the text itself explicitly defers to a
  figure (the "do not guess" sub-signal).

These tests guard the detection/assembly logic, the manifest shape, idempotency,
and end-to-end surfacing through the loader (the `itasca_browse_doc` commands path).
"""

import importlib.util
import json
from pathlib import Path

import pytest

from itasca_mcp.knowledge.commands.loader import CommandLoader

# Load the pipeline script as a module (it lives under scripts/, not the package).
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "corpus" / "flag_figure_defined.py"
_spec = importlib.util.spec_from_file_location("flag_figure_defined", _SCRIPT)
assert _spec and _spec.loader
ffd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ffd)

# A figure list shaped like the manifest, for unit tests.
_FIGS = [{"name": "sector-quad.png", "doc_path": "_images/sector-quad.png"}]


class TestDeferralDetection:
    """Text deferral phrase detection."""

    def test_detects_reference_image_idiom(self):
        assert ffd._find_deferrals("The points are illustrated in the reference images.")

    def test_detects_figures_above_idiom(self):
        assert ffd._find_deferrals("Refer to the figures above for entries and dimensions.")

    def test_detects_thumbnail_idiom(self):
        assert ffd._find_deferrals("Click on any thumbnail above to access the enlargement.")

    def test_ignores_plain_prose(self):
        assert ffd._find_deferrals("Create a ball at the given position with the given radius.") == []


class TestBuildFlag:
    """The two signals assemble independently."""

    def test_figures_only_is_neutral(self):
        flag = ffd._build_flag(_FIGS, [])
        assert flag is not None
        assert flag["figures"] == _FIGS
        assert "text_incomplete" not in flag
        assert flag["note"] == ffd.NOTE_NEUTRAL

    def test_deferrals_only_has_no_figures(self):
        flag = ffd._build_flag(None, ["Refer to the figures above."])
        assert flag is not None
        assert "figures" not in flag
        assert flag["text_incomplete"] is True
        assert flag["note"] == ffd.NOTE_INCOMPLETE

    def test_both_signals_use_incomplete_note(self):
        flag = ffd._build_flag(_FIGS, ["Refer to the figures above."])
        assert flag["figures"] == _FIGS
        assert flag["text_incomplete"] is True
        assert flag["note"] == ffd.NOTE_INCOMPLETE

    def test_neither_is_none(self):
        assert ffd._build_flag(None, []) is None

    def test_deferrals_are_capped_and_deduped_upstream(self):
        flag = ffd._build_flag(None, ["a."] * 10)
        assert len(flag["deferrals"]) == ffd.MAX_DEFERRALS


class TestApply:
    """_apply_to_doc joins the manifest and the text signal."""

    MANIFEST = {"zone create2d": _FIGS}

    def test_figures_attached_from_manifest(self):
        doc = {"versions": {"9.0": {"command": "zone create2d", "keywords": []}}}
        assert ffd._apply_to_doc(doc, self.MANIFEST) is True
        assert doc["versions"]["9.0"]["figure_reference"]["figures"] == _FIGS

    def test_deferral_text_sets_incomplete(self):
        doc = {
            "versions": {
                "9.0": {
                    "command": "zone create2d",
                    "keywords": [{"name": "size", "description": "shown in the reference images above."}],
                }
            }
        }
        ffd._apply_to_doc(doc, self.MANIFEST)
        fr = doc["versions"]["9.0"]["figure_reference"]
        assert fr["text_incomplete"] is True and fr["figures"] == _FIGS

    def test_no_match_no_flag(self):
        doc = {"versions": {"9.0": {"command": "model solve", "keywords": []}}}
        assert ffd._apply_to_doc(doc, self.MANIFEST) is False
        assert "figure_reference" not in doc["versions"]["9.0"]

    def test_idempotent(self):
        doc = {"versions": {"9.0": {"command": "zone create2d", "keywords": []}}}
        assert ffd._apply_to_doc(doc, self.MANIFEST) is True
        assert ffd._apply_to_doc(doc, self.MANIFEST) is False

    def test_stale_flag_removed(self):
        doc = {
            "versions": {
                "9.0": {
                    "command": "model solve",
                    "keywords": [],
                    "figure_reference": {"figures": _FIGS, "note": "old"},
                }
            }
        }
        assert ffd._apply_to_doc(doc, self.MANIFEST) is True
        assert "figure_reference" not in doc["versions"]["9.0"]

    def test_unavailable_version_never_flagged(self):
        doc = {"versions": {"6.0": {"available": False}}}
        ffd._apply_to_doc(doc, self.MANIFEST)
        assert "figure_reference" not in doc["versions"]["6.0"]


class TestManifest:
    """The committed manifest is well-formed and covers the key commands."""

    def test_manifest_shape(self):
        manifest = ffd.load_manifest()
        assert manifest, "manifest is empty"
        for command, figs in manifest.items():
            assert isinstance(command, str) and command
            for f in figs:
                assert f["doc_path"] == f"_images/{f['name']}"
                assert f["name"].lower().endswith((".png", ".svg", ".gif"))

    def test_manifest_has_primitive_creators(self):
        manifest = ffd.load_manifest()
        assert "zone create2d" in manifest
        assert "zone create" in manifest
        assert any(f["name"] == "sector-quad.png" for f in manifest["zone create2d"])


class TestCorpusUpToDate:
    """Committed corpus must match the pass output (CI guard == --check)."""

    def test_committed_corpus_is_not_stale(self):
        manifest = ffd.load_manifest()
        stale = []
        for path in ffd.iter_command_docs():
            doc = json.loads(path.read_text(encoding="utf-8"))
            if ffd._apply_to_doc(doc, manifest):
                stale.append(path.name)
        assert not stale, f"Run flag_figure_defined.py; stale: {stale}"


class TestFlagSurfacesThroughLoader:
    """End-to-end: the flag reaches the doc the browse tool returns."""

    def setup_method(self):
        CommandLoader.clear_cache()

    def test_create2d_carries_figures_and_incomplete(self):
        doc = CommandLoader.load_command_doc("zone", "create2d", "9.0", software="flac")
        fr = doc.get("figure_reference")
        assert fr is not None
        assert len(fr["figures"]) >= 7
        assert all(f["doc_path"].startswith("_images/") for f in fr["figures"])
        assert fr["text_incomplete"] is True

    def test_illustrative_command_has_figures_but_not_incomplete(self):
        # ball generate has figures but the text does not defer -> neutral.
        doc = CommandLoader.load_command_doc("ball", "generate", "9.0", software="pfc")
        fr = doc.get("figure_reference")
        assert fr is not None and fr.get("figures")
        assert "text_incomplete" not in fr

    def test_plain_command_has_no_figure_reference(self):
        doc = CommandLoader.load_command_doc("model", "solve", "7.0", software="pfc")
        assert doc is not None
        assert "figure_reference" not in doc


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

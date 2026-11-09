# Corpus field spec

Status: **decided 2026-11-09, nothing migrated yet.** This document defines
one canonical format for the four documentation trees under
`src/itasca_mcp/knowledge/resources/`. Each section states the divergence
found by the 2026-11-09 field inventory and the rule that replaces it. The
open questions were settled by the maintainer on 2026-11-09.

Inventory scope: 2,345 JSON files (command_docs 989, python_sdk_docs 334,
fish_docs 75, references 314, including indexes) across `_common` + 5 engines.

## Guiding rules

1. One meaning, one field name, one value shape — across all four trees.
2. Structured facts live in structured fields; prose lives in `notes`.
   No new top-level section names per file.
3. A field that is absent means "no restriction / nothing to say", never
   "unknown". Restrictions are stated only where they bind.
4. Migrations are mechanical JSON-to-JSON scripts with `--dry-run`/`--write`
   (model: `normalize_command_syntax.py`). The HTML parsers are never rerun
   wholesale; generators (fish) must be updated to emit the same shape and
   verified by regenerate-and-diff.

## A. Availability and versions

Today the same fact — "this exists in these versions, for these engines" —
has four shapes:

| tree | shape today |
| --- | --- |
| command_docs | `versions: {"6.0": {...whole block...}, "7.0": {...}}` + `available: false` blocks + keyword-level `engines: [...]` |
| python_sdk_docs | `availability: {"versions": ["9.0"]}` (802 uses) + stragglers `available_in_3dec_97` (12), top-level `versions: [...]` (17) |
| fish_docs | per-entry bool map `versions: {"6.0": false, "7.0": true, "9.0": true}` (4,501 entries) |
| references | bool map `availability: {"7.0": false, "9.0": true}` (112) + `since: "7.0"` (2) + suffix keys (`available_types_flac3d_97`, `flac2d_only_keywords`, ...) |

**Canonical form** — allowed on any object (file top level, keyword, method,
function, fish entry, example):

```json
"availability": {"versions": ["7.0", "9.0"], "engines": ["pfc", "flac"]}
```

- Both subfields optional; an omitted subfield means no restriction within
  what the file's placement already implies (`_common` vs engine directory,
  the tree's covered versions).
- An omitted `availability` means available everywhere the file is served.
- Version labels stay `6.0 / 7.0 / 9.0`, with `9.0` meaning the 9.8 baseline
  (decided 2026-10-28). No bool maps, no `since`, no per-build suffix keys.
- Keyword-level `engines: [...]` in `_common` command docs merges into
  `availability.engines`; the loader's `_scope_keywords` filter reads the new
  field, same semantics.

**command_docs restructure** (maintainer direction, 2026-11-05): drop the
per-version whole-block duplication. Of 961 command files, 778 are
multi-version, 196 have byte-identical blocks across versions, and 3,490 of
10,987 keyword entries (31.8%) are identical in another version's block.

New file shape: one body, availability where it binds —

```json
{
  "category": "ball",
  "search_keywords": ["..."],
  "description": "...",
  "python_sdk_alternative": {"available": false, "workaround": "..."},
  "availability": {"versions": ["7.0", "9.0"]},
  "command": "ball accumulate-stress",
  "syntax": "ball accumulate-stress <b>",
  "keywords": [
    {"name": "...", "syntax": "...", "description": "...",
     "availability": {"versions": ["9.0"]}}
  ],
  "examples": [{"command": "...", "description": "..."}],
  "notes": ["..."]
}
```

- A field whose text genuinely differs between versions uses a version map as
  the value: `"syntax": {"7.0": "...", "9.0": "..."}`. Allowed for `syntax`,
  `description`, keyword `syntax`/`description`. The loader resolves the map
  at request time. (fish `signature_7.0` ×19 becomes the same map form.)
- The 6.0 removed-command apparatus (`legacy_documentation`, `reason`,
  `target_version`, `source_urls`) folds into `notes` (decided): one note per
  removed version stating when it existed, why it went away and what replaced
  it, with the legacy URL in the text.
- Loader work: `_resolve_versioned_doc` becomes an availability filter +
  version-map resolver; the browse payload's advertised `versions` list is
  derived from `availability`. Tool response shape does not change.

## B. Dimension (2D/3D)

Today: fish has structured `dimension: "2D" | "3D"` (842 entries);
python_sdk_docs has 263 prose notes "2D builds only." / "3D builds only.";
references has free-text `dimension` (88 files — values include `"3D"`,
`"mixed"`, whole sentences) plus `dimension_differences` (16),
`dimension_caveat`, `dimension_note`, `by_dimension`, `dimension-differences`,
and parallel list fields (`keywords_3d_only`, `mpoint2d_only_keywords`,
`flac2d_only_keywords`, `3d_only_keywords`, ...).

**Canonical form:**

- `dimension: "2D" | "3D"` — structured, allowed on any entry, present only
  when the thing is restricted to one build dimension. Omitted = both.
- All prose about *how* the dimensions differ goes in `dimension_notes:
  list[str]` (one canonical name; `dimension_differences`/`_caveat`/`_note`
  all fold in).
- Parallel "X-only keyword" list fields dissolve: each keyword entry carries
  its own `dimension` tag inside the structured `keywords` list.
- python_sdk_docs: the 263 "2D/3D builds only." notes convert to
  `dimension` on the method/function entry (mechanical: exact-string match),
  keeping any surrounding prose in `notes`.
- references `"mixed"` means per-member differences: the file loses its
  top-level `dimension` and tags members instead.

## C. Notes and ad-hoc sections (done 2026-11-09)

Today: `note` (str) and `notes` (str or list) coexist in every tree;
command_docs additionally has **190 distinct ad-hoc top-level keys** that
appear in ≤5 files each (`activate_vs_inhibit`, `catalog_concept`,
`when_to_use_measure`, ... — early hand-curated PFC files), references has a
similar ~60-key tail, and PFC has `warnings` (27), `warning` (5), `tips`,
`troubleshooting`, `common_use_cases`, `typical_workflow`,
`performance_considerations`. These sections are served (browse passes the
whole doc through) but are invisible to search and get trimmed first when a
response is too large (`_COMMAND_CORE_FIELDS`).

**Canonical form:**

- `notes: list[str]` is the only free-prose field, valid at any level.
  Scalar `note`, string-valued `notes` → one-element list. Mechanical.
- `warnings`/`warning`/`tips`/`caveat` fold into `notes` entries, prefixed
  `Warning:` where the label carried meaning (decided).
- Ad-hoc sections are **curated during the fold** (decided): content worth
  keeping becomes a `"<Title>: <content>"` note; sections that restate
  `keywords`/`description` or add no operative fact are deleted. Done tree by
  tree with dry-run diffs reviewed before `--write`.
- Outcome (`scripts/corpus/migrate_notes.py`, decision table inside): of 401
  command_docs section instances, 333 dropped, 64 folded by renderers
  (related/important_notes/keyword-shaped lists), 33 files got hand-condensed
  engine-fact notes, 4 left for later concerns (`plot_items`,
  `dimension_differences`, `independent_dimensions`, `live_verification`).
  `flag_figure_defined.py` now writes `figure_reference.notes`.
- The related-item fields (`related_commands`, `related_models`,
  `related_modules`, `see_also`, `related`) fold into `notes` too (decided);
  entries that are not genuinely useful cross-references are dropped outright
  rather than kept.

## D. Naming and provenance

| meaning | today | canonical |
| --- | --- | --- |
| manual origin | `source`, `source_url`, `source_urls`, `official_documentation` | `source` (str or list[str]) |
| live-test provenance | `verification`, `verified`, `evidence`, `live_verification[_flac3d_97/...]`, `live_enumeration_9_7`, `binary_validated_*`, `live_notes`, `validation_notes` | `verification: list[str]`, each entry naming the build and the fact ("FLAC3D 9.8.54 console: ...") |
| hierarchy | `parent` (16), `parent_item` (16) | `parent` |
| display title | `full_name` vs `name` | keep both: `name` = engine spelling / path token, `full_name` = human title |
| syntax line | `syntax`, `base_syntax`, `documented_syntax`, `alt_syntax` | `syntax`; a manual-vs-engine discrepancy becomes a `verification` + the engine-true string in `syntax` |
| example entry | `{command, description}` + stragglers `use_case` (386), `model` (66), `output_example` (9), and a few legacy bare-string examples | `{command, description}`; `use_case` merges into `description`, `model` becomes an `availability`-style tag only if load-bearing, else description text; bare strings become `{command}` |

## E. Keywords

- Structured keyword entry (command_docs and references alike):
  `{name, syntax, description, availability?, dimension?, optional?}`.
  `verified` (16) → `verification` note on the file. `kwd:` prefixes stay
  (path addressing strips them).
- The dozens of `*_keywords` list fields in references
  (`basic_keywords`, `top_level_keywords`, `management_keywords`,
  `beam_family_keywords`, ...) dissolve into the structured `keywords` list,
  using `group` on the entry if the grouping mattered:
  `{name, ..., group: "management"}`.
- `search_keywords` stays as-is (it is the curated search field), and stays
  manually maintained — remember new keywords do not index themselves
  (`command_adapter._keyword_names` fallback only covers uncurated files).

## F. references tree archetypes

The tree is really four page kinds; the spec names them so new files copy the
right shape (`spec-first`, 2026-11-07):

1. **model** (constitutive-models, contact-models, joint-models):
   `model, full_name, search_keywords, description, property_groups,
   availability, source, usage, notes, verification`.
2. **range-element**: `name, syntax, description, search_keywords, category,
   category_name, parameters?, sub_keywords?, supports_extent?, examples,
   notes, source`.
3. **plot/data item** (ball, clump, wall, block, zone, mpoint, marker, ...):
   `name, parent, description, syntax, keywords, modes?, attributes?,
   notes, verification`.
4. **topic page** (boundary-conditions, initial-conditions,
   histories-and-results, structural-properties, file-formats, workflows,
   ...): `name, full_name, description, dimension?, primary_commands,
   keywords?, examples?, notes, verification, source`.

Everything a current file carries outside its archetype folds per sections
C–E.

## G. fish tree (reference model — minimal change)

fish_docs is already closest to spec: keep
`{namespace, scope, engines, count, undocumented, entries}` /
entry `{name, signature, returns, args, settable, description, doc,
dimension?, family?}`. Changes: bool-map `versions` → `availability` (A,
done 2026-11-09), the per-engine index's `available` per-version count map →
`counts` (same change — the old name read as an availability field),
`signature_7.0` → version map (A, with the command restructure), `note` →
`notes` (C). Generators updated to emit the new shape; regenerate must
reproduce the corpus byte-for-byte before and after the format change
(established check).

## H. python_sdk tree

Already uses the canonical `availability`. Changes: kill
`available_in_3dec_97`-style keys (12) and top-level `versions` duplicates
(17) → `availability`; `note` → `notes` (C); dimension notes → `dimension`
(B); `source_url` → `source` (D).

## Guard rails (in place before any migration)

- `tests/test_corpus_sweep.py` — structural guard. Resolves every command,
  reference item and Python API entry for every engine and version through
  the loaders and browse tools, asserting the served shape, and names the
  exact path that breaks. It pins the *resolved* view, not the raw JSON, so
  the migration can rewrite files freely without touching these tests.
  (fish has its own full-reachability tests in `test_doc_tools_merged.py`.)
- `scripts/corpus/semantic_snapshot.py OUT_DIR` — content guard. Dumps the
  resolved view of all four trees (~22 MB over 20 files). Run before and
  after each migration script and diff; commands/fish must diff only where
  the fold intended, references/python_api shape conversions must diff
  uniformly.

## Migration order

1. Snapshot a `before/` baseline with `semantic_snapshot.py`.
2. One mechanical script per concern, not per tree (availability, notes,
   naming), each dry-run/--write, run over all trees; command version-block
   restructure is its own script and lands together with the loader change.
   After each script: sweep tests green + snapshot diff reviewed.
3. Loader/adapter updates keep the tool response contract: same envelope,
   same `data` keys; the only visible change is formerly ad-hoc fields now
   appearing under `notes`.
4. Added tests per policy (silent-and-costly only): loader availability
   resolution, version-map resolution, keyword engine-scoping, alongside the
   existing envelope suites (`test_phase2_tools.py`, `test_tool_contracts.py`,
   `test_doc_tools_merged.py`).
5. The deferred keyword batches (PFC thermal 33 + cfd 33, MPoint/MassFlow
   scans) are written directly in the new format afterwards.

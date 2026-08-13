# FLAC Corpus Verification Checklist

Live target: **FLAC3D 9.7** (`Itasca Software Subscription`, GUI + bridge).
Static baselines: FLAC3D 7.0 doc tree (`C:\Program Files\Itasca\FLAC3D700\exe64\doc`),
Itasca 9.7 doc tree (`...\Itasca Software Subscription\exe64\doc`).
Corpus size at scan time (2026-08-13): 333 command JSONs (body 55 / domain 3 /
extruder 71 / group 4 / model 1 / structure 131 / zone 68), 12 Python module
units, 44 reference files.

Status legend: `[x]` done (PR merged) · `[~]` partially done · `[ ]` open.
Evidence grades per docs/verification/README.md: static / syntax / state.

## Verified & fixed

### Batch 1 — zone boundary-condition family + scan P0s (2026-08-13)

- [x] Demo cap measured: 1000 zones, enforced at `zone create` (incremental
  creation counts toward the total); error text is a misleading license
  failure. (state)
- [x] `zone gridpoint fix` / `free`: 9.0 blocks were missing `saturation`
  (engine-enumerated; requires fluid configure; absent from official 9.x
  HTML). Added. (state: fixed value holds and reads back via `gp.sat()`)
- [x] `zone face apply`: 9.0 block was missing `head-saturation <f>`,
  `pore-pressure-maximum [<f>]`, `pore-pressure-saturation <v2>` (all absent
  from official 9.x HTML — live-engine-only discoveries), plus the `table`
  and `servo` apply-block modifiers. Added. `pore-pressure-maximum` semantics
  are syntax-grade only (see Open). (syntax)
- [x] `zone apply`: 9.0 block carried two parse artifacts — `thermal` and
  `upper-multiplier` (truncations of `table-thermal` / `servo-upper-multiplier`;
  engine rejects both). Removed; added real `table` + `servo` entries. (syntax)
- [x] Servo grammar change 7.0→9.x documented: hyphenated `servo-*` keywords
  are rejected by 9.x; the 9.x form is `servo` + sub-keywords (latency,
  lower-bound, lower-multiplier >1, maximum, minimum, ramp,
  ratio average|convergence|global|local|maximum, reduce, upper-bound,
  upper-multiplier <1). Multiplier bounds are state-checked (out-of-range
  values rejected by the parser). (syntax/state)
- [x] Quoting asymmetry documented: `table 'name'` requires a quoted string;
  `fish funcname` requires an unquoted FISH symbol. (syntax)
- [x] `update-direction`: accepted after gridpoint-based vector conditions,
  rejected after face-based stress conditions. Annotated. (syntax)
- [x] `zone face apply-remove`: 9.0 block was missing `head-saturation`,
  `pore-pressure-maximum`, `pore-pressure-saturation`, `stress-tensor`,
  `stress-yz`. Added. **Trap documented**: bare `apply-remove` (or with a
  misspelled first keyword) removes ALL conditions in range before any error
  is raised. (state: observed via removal messages)
- [x] Parse-and-execute trap documented in `apply-modifiers` reference:
  a trailing invalid token does not undo the already-executed valid prefix.
  (state)
- [x] Command renames 7.0→9.x fixed in 9.0 blocks (official form primary,
  legacy form noted as still accepted by 9.7): `zone geometry test` /
  `tolerance` / `update-interval`; `building-blocks set automatic-tolerance`.
  (syntax)
- [x] Existence verdicts for scan-suspect commands: `zone water` REAL
  (official 9.x index gap; engine enumerates clear/density/list/plane/set/table),
  `model domain strain-rate` REAL (official index gap), `zone consolidation`
  NOT in FLAC3D 9.7 (marked unavailable; possibly FLAC2D-only). (syntax)
- [x] `flac/command_docs/index.json` fracture category: removed PFC-inducing
  guidance (`contact model smoothjoint` note, Smooth-Joint description);
  `fracture contact-model` marked PFC-only. (static)
- [x] Python `Gridpoint.fix` / `set_fix`: **getter is 1-based (1=x, range
  1–5), setter is 0-based (0=x, range 0–3)** — engine API asymmetry, both
  sides now documented with warnings. (state)
- [x] Python `Gridpoint.sat` / `set_sat`: unfixed saturation writes are
  clamped back by the engine (reads 1.0 immediately after `set_sat(0.8)`;
  `zone gridpoint initialize saturation` reports "modified" but does not
  hold either); fixing saturation holds the value. Documented. (state)

### Batch 2 — plot / plot-items (2026-08-13)

- [x] Full FLAC3D 9.7 plot item type enumeration captured. The unified 9.x
  kernel enumerates ALL engines' item types (~95: ball/clump/rblock from
  PFC, block-* from 3DEC, mpoint-*, drawpoint/mineblock, ...) — acceptance
  does not imply the item renders FLAC data; documented in the plot-items
  index and new `flac3d-items.json`. (syntax)
- [x] New `flac/references/plot-items/flac3d-items.json`: verified top-level
  keyword sets for 20 3D item types (zone-vector/-tensor/-face/-isosurface/
  -profile/-boundary/-water/-interface/-attach/-joint/-track/-stereonet,
  struct-node-fix, structure-shell/-vector, chart-table, fos,
  history-locations, axes, scalebox) plus the beam-family set. Discovered
  quirks: `zonetensor` is an alias of `zone-tensor` (which REQUIRES a
  quantity keyword first); beam family carries CamelCase `Bar`/`BarScale`/
  `FlipBars` keywords (leaked internal names, really accepted); zone-face
  uses `highlight-selected` where zone uses `selected-highlight`. (syntax)
- [x] 2D/3D dimension differences recorded in zone/index, zone/contour,
  zone/label, gridpoint-fix, structure/index, structure/contour: 3D adds
  clip/cut/transparency + -z/-xz/-yz components + face-based label types;
  2D-only zone keywords (color, show-zone-id, text, zone-id-*) and contour
  attributes (fluid-bulk-modulus, saturation-apparent) rejected by 9.7.
  (syntax)
- [x] `plot view` 9.0: `perspective` keyword replaced by
  `projection <parallel|perspective>` (9.x rejects bare `perspective`;
  `extent` remains 2D-only as previously documented from PFC2D work).
  (syntax)
- [x] `plot export` (_common): all three version blocks had every format
  keyword's name collapsed to its trailing `size` sub-keyword (crawler
  artifact) and 9.0 was missing bitmap/pdf/postscript/svg entirely.
  Rebuilt: 9.0 live-verified (sub-keywords enumerated; bitmap export
  state-verified — PNG on disk, legend max matched `gridpointarray.disp()`
  readback to 5 significant digits); 7.0/6.0 names restored from the
  official FLAC3D 7.0 index. `postscript` is enumerated but DEPRECATED in
  9.x ("no longer supported" at execution). (state for bitmap; syntax rest)
- [x] `plot delete` trap documented: name goes BEFORE the verb
  (`plot 'name' delete`); `plot delete <name>` deletes the CURRENT plot
  first, then errors on the extra parameter. (state: observed)
- [x] `chart-history` (_common): 9.x top-level keyword list added
  (begin/end/skip were undocumented). (syntax)

## Open — from live verification

- [ ] `pore-pressure-maximum` exact semantics (cap? applied load limit?):
  state-grade verification needs a fluid model with nonzero pp field.
- [ ] `Gridpoint.fix` components 4–5 meaning (always True in probes; not
  pp/saturation/temperature fixity) and `set_fix` slot 3 (no observable
  effect).
- [ ] `zone gridpoint initialize saturation` clamp-back mechanics (probed in
  fluid-flow implicit mode only; behavior in explicit/unsaturated configs
  unknown).
- [ ] Thermal-gated keywords unprobed (`fix temperature` needs
  `model configure thermal`): repeat fix/free/apply enumeration with thermal
  configured.
- [ ] `zone face apply` first-token enumeration should be re-run with
  dynamic/creep/thermal configured — the keyword set may be process-gated.

## Open — from static scan (2026-08-13, full report in scan agent transcript)

P1 (confirmed real, ordered by impact):

- [ ] Backfill 7.0 blocks for body/ (55 files) + extruder/ (71 files); two
  whole directories were skipped by the crawler (verified present in the
  FLAC3D 7.0 official index). extruder/ needs the 7.0 `extrude` ↔ 9.0
  `sketch` verb mapping. Exceptions (true 9.0-new): `structure/
  beam-property-{elastic}.json`, `structure/shell-property-{elastic}.json`.
- [ ] `zone/face-apply-remove.json`: 88/88 keywords lack descriptions.
- [ ] `zone/property.json`: keywords empty in both version blocks (core
  command; agent currently sees no constitutive property names).
- [ ] 30 collapsed hyperlink anchors ("shown here", "listed here") across
  structure/ history/list/create files — restore targets or rewrite.
- [ ] Strip prose from syntax strings: 134 entries with `3D ONLY`/`2D ONLY`
  fused into syntax (e.g. `moi <f>2D ONLY`), plus `[beamcreateblock]`-style
  anchor IDs; 263 entries missing space after `>`.

P2:

- [ ] Add missing Python module `itasca.zone.field` (spatial interpolation
  API, 13th official FLAC3D module page).
- [ ] Duplicate keyword names in 7.0 blocks: `zone/initialize.json`
  (stress-* ×2 each), `zone/list.json`, `zone/history.json` (stress ×2).
- [ ] 6 figure references with no carried content (`zone/create.json`,
  `zone/create2d.json`, `structure/beam-history.json`,
  `structure/shell-property-{elastic}.json`).
- [ ] `domain/condition.json`: keywords empty; official index has
  destroy/periodic/reflect/stop.

P3 (design decisions, discuss before executing):

- [ ] 7.0 vs 9.0 keyword expansion granularity differs (92 commands show
  pseudo-drift: 7.0 flattened sub-keywords, 9.0 top-level only).
- [ ] `_common/` entries lack engine applicability markers (32 files with
  PFC/3DEC-specific content reachable from the FLAC index, worst:
  `fish/callback.json` ball/clump events); consider `applies_to` field.
- [ ] Python SDK scope: 131 structure commands but zero structure Python
  modules exposed to FLAC (official navtree puts `itasca.structure.*` under
  Common API); decide whether to pull common modules into the FLAC corpus.
- [ ] `vertexarray` described as "wall vertices" (faithful copy of an
  upstream wording bug) — add clarifying note.

## Open — plot follow-ups (from Batch 2)

- [ ] Author command docs for the 9 undocumented `plot` subcommands
  enumerated live: legend, load, movie, outline, print-size, reset, show,
  target, title-job (_common scope — verify on a second engine before
  writing).
- [ ] Drill-down keyword sets below the top level (e.g. `contour` config
  sub-keywords vs attributes are mixed in the positional `?` enumeration;
  `zone-isosurface`/`zone-profile` config keywords listed but not
  individually probed).
- [ ] structure-liner/-pile/-geogrid/-dowel/-hybrid keyword sets asserted by
  family analogy only (beam/cable and shell verified).

## Not yet started

- [ ] constitutive-models reference vs `zone cmodel` + property enumeration
- [ ] structure command family (131 files — largest block)
- [ ] Python SDK per-function verification (zone/zonearray/gridpointarray/
  interface*)
- [ ] FISH intrinsics, range-elements, remaining references/
- [ ] history / results / table commands

## Batch log

| Date | PR | Scope | Files touched |
|------|----|-------|---------------|
| 2026-08-13 | #75 | Batch 1: zone BC family live verification + scan P0 fixes + workspace setup | 15 corpus JSONs + docs/verification/ |
| 2026-08-13 | #76 | Batch 2: plot / plot-items FLAC3D 9.7 enumeration, 2D/3D diffs, export/view/delete fixes | 12 corpus JSONs (1 new) |

"""Write the state-verified MassFlow semantics into the corpus.

Batch 7 of the MassFlow verification campaign. Every note below was produced by
running the command on live MassFlow 9.7.47 and reading the resulting state back
— through `itasca.fish.get` for model state and `table.find` for tables, on the
tutorial model (9696 mine blocks, 7 drawpoints, day 20 / period 3 at rest).

The raw run is in the verification workspace as `sem4_results_massflow.txt`.

This script APPENDS to each doc's notes, so it runs last. Canonical order for
regenerating the whole MassFlow corpus:

    author_massflow_live_commands.py
    generate_massflow_index.py
    generate_massflow_file_formats.py
    generate_massflow_range_elements.py
    generate_massflow_fish_intrinsics.py
    generate_massflow_plot_items.py
    annotate_massflow_scoping.py
    annotate_massflow_semantics.py

Usage:
    uv run python scripts/corpus/annotate_massflow_semantics.py
"""

from __future__ import annotations

import json
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
CMD_DIR = RESOURCES / "massflow" / "command_docs" / "commands" / "massflow"
FISH_DIR = RESOURCES / "massflow" / "references" / "fish-intrinsics"

# Notes appended to a command's existing `notes`. The format pointer added in
# Batch 2 is preserved by appending rather than replacing.
NOTES: dict[str, list[str]] = {
    "compute.json": [
        "Verified on a model resting at day 20 / period 3: `compute days 5` -> day 25, "
        "again -> day 30, then `compute periods 1` -> day 37 (the tutorial's periods are "
        "7 days). Both keywords advance from wherever the model is.",
        "Bare `massflow compute` runs the `compute-days` / `compute-period` budget as an "
        "increment too, not as a target: from day 20 with `compute-days 20` it reached "
        "day 40, and after `massflow initialize compute-days 3` a further `compute` "
        "reached day 43.",
        "Markers are created lazily while computing — the marker count grows with the "
        "day count (1117 at day 20, 1450 at day 30 on the tutorial model).",
    ],
    "clean.json": [
        "Required before `massflow compute`. On MassFlow 9.7.47 a model that is fully "
        "imported and initialized but not cleaned terminates the process when `massflow "
        "compute` is issued, rather than reporting an error.",
        "`massflow clean` reports `Initialize Draw Points!` and `Solution initialized`. "
        "It creates no markers: the marker count is still zero afterwards and only rises "
        "during `massflow compute`.",
    ],
    "initialize.json": [
        "`filename <s>` is the save-file PREFIX, not a filename: with `filename 'zzsave' "
        "save-days 5` a 15-day run wrote `zzsave_Day5.sav`, `zzsave_Day10.sav` and "
        "`zzsave_Day15.sav` into the working directory.",
        "`compute-days` / `compute-period` set the budget that a bare `massflow compute` "
        "spends; they can be re-set between compute steps.",
    ],
    "marker-initialize.json": [
        "`spacing` is a fraction of the mine-block size, so the marker population scales "
        "steeply with it: on the tutorial model at day 5, spacing 0.5 gave 476 markers "
        "and spacing 0.25 gave 4865.",
        "Spacing is a discretisation choice, not just a display density — it changes the "
        "extracted-mass accounting (11700 vs 10359 over the same 5 days in that test), "
        "because extraction moves whole markers.",
    ],
    "record.json": [
        "The table is created empty and fills during `massflow compute`: one point per "
        "period, x = period number, y = mass.",
        "Recording starts at the period the command was issued in, not at period 1. "
        "Issued at period 3 and computed to period 5, the table held 3 points.",
        "`cumulative true` accumulates: (3, 1950) ... (5, 29250) for all drawpoints "
        "together, against (3, 650) ... (5, 1300) for a single drawpoint per period.",
    ],
    "drawpoint-dump-drawperiod.json": [
        "On MassFlow 9.7.47 this creates the named table but leaves it EMPTY. Tried on a "
        "model computed to day 50, with and without `drawpoint`, with and without "
        "`cumulative on`: `table list` reports 0 entries every time. Use "
        "`massflow record` for a mass-per-period table that does fill.",
    ],
    "marker-size-distribution.json": [
        "Writes a table named `size-distribution` unless `table <name>` renames it: "
        "x = fragment diameter, y = cumulative percent passing, running 0 to 100.",
        "`divisions` sets the number of points: the default run produced 50 points "
        "(0.00086 -> 3.767), `divisions 5` produced 5 (0.00185 -> 1.743).",
        "Plot it with `plot item create chart-table table 'size-distribution'`; a log "
        "x axis is the conventional presentation.",
    ],
    "fines-migration.json": [
        "This changes the solution, it is not a reporting switch. Same model, same 10 "
        "days: baseline ended with 1450 markers / 59150 mass, with fines migration on "
        "1432 markers / 62400 mass.",
    ],
    "secondary-fragmentation.json": [
        "This changes the solution, it is not a reporting switch. Same model, same 10 "
        "days: baseline ended with 59150 extracted mass, with secondary fragmentation "
        "on 59475.",
    ],
    "drawpoint-group.json": [
        "The engine reports what it assigned: `Group left assigned to 4 DrawPoint in "
        "slot Default.` A `range` really narrows it — `range position-x 0 1530` caught "
        "4 of the tutorial's 7 drawpoints.",
    ],
    "mine-block-group.json": [
        "The engine reports what it assigned. `range position-x 1500 2000` caught 4801 "
        "of the tutorial's 9696 mine blocks.",
    ],
    "marker-import-trace.json": [
        "Every point in the file must lie inside the mine-block model. On MassFlow "
        "9.7.47 a file with a point outside it terminates the process at import time — "
        "the file reader does no bounds check.",
        "`massflow marker trace position <x> <y> <z>` does check, and answers "
        "`Trace marker - No valid mineblock found at (x,y,z).` Use it to validate "
        "coordinates before committing them to a file.",
    ],
    "marker-trace.json": [
        "Bounds-checked: a position outside the mine-block model is refused with "
        "`Trace marker - No valid mineblock found at (x,y,z).` rather than accepted. "
        "Note the block-model extent is given by block CENTRES, so the solid reaches "
        "half a block past them.",
    ],
    "marker-group.json": [
        "Markers only exist once `massflow compute` has created them, so grouping by "
        "position before the material has moved there selects nothing: `range "
        "position-z 350 500` caught 0 of 1117 markers on a model at day 20.",
    ],
}

# Extra notes for the FISH families, same evidence run.
FISH_NOTES: dict[str, list[str]] = {
    "drawpoint.json": [
        "`mass.requested` is the scheduled daily tonnage — the period mass divided by "
        "the period length. On the tutorial model (2000 per 7-day period) it reads "
        "285.714 for every day of the period.",
        "`mass.actual` is quantised to whole markers, so a day either extracts a "
        "marker's worth or nothing: days 1-3 of DP1 read 325, 0, 0 while "
        "`mass.actual.cum` holds at 325. Over period 1 the requested 2000 came out as "
        "1625 = 5 x 325.",
        "`massflow.mass.DpDay(1,1)` returned 0 on that same model while "
        "`massflow.drawpoint.mass.actual(dp,1)` returned 325 — the two do not agree, so "
        "prefer the drawpoint accessors for per-day mass.",
    ],
    "marker.json": [
        "On the tutorial model at day 20 every active marker was also type 2 (fully "
        "bulked): 458 of 1117 by both counts.",
    ],
}


def _append(path: Path, notes: list[str]) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    existing = list(doc.get("notes", []))
    for note in notes:
        if note not in existing:
            existing.append(note)
    doc["notes"] = existing
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    for filename, notes in NOTES.items():
        path = CMD_DIR / filename
        if not path.exists():
            raise FileNotFoundError(path)
        _append(path, notes)

    for filename, notes in FISH_NOTES.items():
        path = FISH_DIR / filename
        if not path.exists():
            raise FileNotFoundError(path)
        _append(path, notes)

    print(f"annotated {len(NOTES)} command docs and {len(FISH_NOTES)} FISH families")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

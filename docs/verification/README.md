# Documentation Verification Workspace

Tracking workspace for the corpus verification effort: scanning the bundled
documentation (`src/itasca_mcp/knowledge/resources/`), validating it against
live engines, and closing coverage gaps. One checklist file per engine
(`flac.md`, `3dec.md`, ...); update the relevant checklist in the same PR as
the corpus changes it describes.

## Methodology

Every documented claim is graded by the strongest evidence behind it:

| Grade | Meaning |
|-------|---------|
| `static` | Cross-checked against official HTML docs / command indexes only |
| `syntax` | Live engine accepted or enumerated the command/keyword (error-enumeration probing) |
| `state` | Executed against a live engine **and** the resulting model state was read back and matched the documented semantics |

Rules of the road:

1. **Syntax acceptance is not verification.** Engines parse-and-execute
   incrementally and may report success while the state says otherwise
   (e.g. `zone gridpoint initialize saturation 0.8` reports "modified" but
   the value reads back 1.0). After executing a command or API call, read
   the state back through the Python SDK before writing semantics into the
   corpus. Descriptions backed only by `syntax`-grade evidence must say so.
2. **The live engine outranks the official HTML docs.** Official indexes
   have gaps in both directions (keywords the engine accepts but the docs
   omit, and pages for commands the engine rejects). Corpus notes record
   which side the discrepancy is on.
3. **Error-enumeration probing** is the workhorse for keyword sets: feed a
   bogus token at each syntax position and let the engine enumerate the
   legal tokens, then diff against the corpus.
4. **Demo-mode limits.** Only PFC 7.0 has a full license on the
   verification machine. FLAC3D 9.7 demo caps at 1000 zones and rejects at
   creation time with a misleading license error; keep verification models
   small (5x5x5 bricks).
5. **Bridge constraints.** No `program call` of .dat files (wedges the
   bridge); FISH + `io.out` only via synchronous execute; batch commands
   are normalized to one engine call each.

## Engine status

| Engine | Live target | Static baselines | Checklist |
|--------|-------------|------------------|-----------|
| FLAC | FLAC3D 9.7 (Itasca Software Subscription) | FLAC3D 7.0 + Itasca 9.7 HTML doc trees (`out_commands.txt` indexes) | [flac.md](flac.md) |
| PFC | PFC 7.0 (licensed) / PFC 9 demo | PFC 6/7/9 HTML doc trees | dogfooded continuously; no formal checklist yet |
| 3DEC | 9.x demo (subcontact cap ~666) | Itasca 9.7 HTML doc tree | not started |
| MPoint / MassFlow | demo | Itasca 9.7 HTML doc tree | not started |

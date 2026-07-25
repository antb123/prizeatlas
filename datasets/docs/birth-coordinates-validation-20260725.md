# Birth Coordinates Validation — Phase 2 — 20260725

## Goal

Find birth coordinates that point at the wrong place. Phase 1
(`docs/bulk-birth-coordinates-20260725.md`) fills cells; this decides whether what landed is
right.

Report only. It prints offending rows and changes nothing.

## Why not `PRAGMA integrity_check`

It returned `ok` for every defect found so far: a sign-flipped Shenzhen putting a laureate in
Nevada, an off-by-two block that gave Milnor and Roth their neighbours' coordinates, Ottawa
Kansas resolved to Ontario, and David Baltimore's *surname* geocoded as his birth city. It
validates page structure, not meaning.

## The tool

One SQL file. No Python, no new dependency:

```sh
sqlite3 awards.sqlite3 < scripts/check_coordinates.sql
```

Five `SELECT`s, each printing a labelled block of offending rows. Empty output means clean.
Pipe to a file to diff between runs.

## The checks

| # | Check | Catches |
|---|---|---|
| 1 | same `full_name`, coordinates >0.3° apart | the big one — a laureate in several datasets disagreeing with itself |
| 2 | same `(birth_city, birth_country)`, coordinates >0.3° apart | ambiguous names guessed wrong: Orange, Ottawa, Chiran, Bages |
| 3 | longitude sign wrong for the country | transcription sign flips — found `-114.0544` for Shenzhen |
| 4 | `birth_city` appears inside `full_name` | surname geocoded as birthplace — `lasker_awards-000400` |
| 5 | not `longitude,latitude` to 4dp, or out of range | malformed or swapped pairs |

Check 1 is worth more than the other four together, and needs no external source — the data
contradicts itself. Nearly always the coordinate is faithful to its row's `birth_city` and the
*city* is wrong: an affiliation or education city recorded as a birthplace.

Use 0.3° in checks 1 and 2 to stay quiet about city-vs-municipality entities that differ in
the fourth decimal. The country lists in check 3 are deliberately partial — extend as new
countries appear. A wrong entry there yields a false positive, which is the safe direction.

## Scope

| File | Action |
|---|---|
| `scripts/check_coordinates.sql` | new, ~60 lines |
| `awards.sqlite3` | read-only |

## Acceptance

- Clean database → every check prints nothing.
- A match prints the offending row with its `award_record_id`.
- Never writes.

## Working notes

- Run after every enrichment batch. The conflict set moves as rows fill: 7 laureates at 1,223
  filled rows, 7 different ones at 1,605, 14 at 1,749. Re-run rather than working a fixed list.
- Checks 1 and 2 need a human to pick the right side. Prefer the official-source row
  (`nobel-*` for a Nobel laureate) and confirm against the laureate's Wikidata P19.
- Fix by `award_record_id`, one row at a time, never by name.

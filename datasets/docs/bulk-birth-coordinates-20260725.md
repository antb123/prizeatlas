# Bulk Birth Coordinates Lookup — 20260725

## Goal

Fill `birth_coordinates` for the 993 rows that have a `birth_city` and `birth_country` but a
blank coordinate, by running `scripts/lookup_coordinates.py` over the 788 unique
`(birth_city, birth_country)` pairs.

Lookup only. Whether the results are *correct* is phase 2 —
`docs/birth-coordinates-validation-20260725.md`.

## Prerequisite: delete the bounding-box check

Remove `country_bbox`, `coordinate_in_bbox`, `validate_country_coordinate`, the
`NOMINATIM_API` constant, the `BoundingBox` alias, and the list-handling added to `api()`.
About 45 lines and one API dependency.

It is wrong in both directions and spends a network call per lookup to make results worse:

| Command | Result | Should be |
|---|---|---|
| `lookup_coordinates.py Q1297 --country France` | passes | rejected — that is Chicago |
| `lookup_coordinates.py Breslau --country Germany` | rejected | accepted — correctly resolved to Wrocław |

Country envelopes include overseas territories, so the box is meaningless for the countries
that dominate this work — the US box spans `-180` to `180` longitude.

`--country` stays required. Its real effect is line 264, which builds the query
`f"{query}, {country}"`; that is what makes `Ottawa, United States` fail closed instead of
silently returning Ontario. Keep it.

## The tool

No new script. The loop is shell:

```sh
cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d).bak

sqlite3 -noheader -separator '|' awards.sqlite3 \
 "SELECT DISTINCT birth_city, birth_country FROM awards
  WHERE birth_coordinates = '' AND birth_city <> '' AND birth_country <> ''
    AND birth_city NOT LIKE '%''%' AND birth_country NOT LIKE '%''%'" |
while IFS='|' read -r city country; do
  coord=$(uv run scripts/lookup_coordinates.py "$city" --country "$country" 2>>failed.log |
          jq -r .properties.dataset_coordinates) &&
  sqlite3 awards.sqlite3 "UPDATE awards SET birth_coordinates = '$coord'
    WHERE birth_coordinates = '' AND birth_city = '$city' AND birth_country = '$country'"
  sleep 1
done
```

Resume, no-overwrite, and success logging all fall out of the `birth_coordinates = ''`
predicate and the database itself. Failures go to `failed.log` as tool stderr.

`NOT LIKE '%''%'` skips the 8 pairs with an apostrophe (`Ta'izz|Yemen` plus 7 country
strings) — do those by hand rather than add a quoting layer.

Back up first: the database is the only source of truth now. The CSV snapshots are archived
under `old/` and `scripts/import_sqlite.py` is disabled.

## Expected yield

Measured on the 12 highest-volume pairs: **3 succeed, 9 fail.**

- `"Newark, United States"` is not a Wikipedia title, so the redirect lands on a
  disambiguation page — same for Washington, Columbus, Ashiya.
- Methuen, Wilkes-Barre, Alice: no Wikidata search result carries P625.
- Nagoya resolves correctly to Q11751, then is rejected for multiple equally ranked P625 values.

So expect roughly 200 of 788 pairs unattended. The rest need a QID, which the tool already
takes: `uv run scripts/lookup_coordinates.py Q138518 --country "United States"`. Read
`failed.log`, find the QID, rerun. That is normal operation — the tool refuses rather than
guesses, which is why the Ottawa / Orange / Chiran class of error stopped.

## Scope

| File | Action |
|---|---|
| `scripts/lookup_coordinates.py` | delete ~45 lines |
| `awards.sqlite3` | `birth_coordinates` only |
| `failed.log` | new, transient |

## Acceptance

- A resolved pair writes to every matching blank row, and nothing else changes.
- A non-zero exit appends to `failed.log`; the loop continues.
- Re-running skips already-filled pairs.
- `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` returns exactly `ok` — which proves the
  file is not corrupt and nothing about whether a coordinate points at the right place.

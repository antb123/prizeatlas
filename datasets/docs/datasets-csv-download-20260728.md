# Dataset CSV download

## Goals

Publish the full award dataset as a single downloadable CSV alongside the generated site, and link to it from the
footer of every page, so a visitor can take the data away without scraping the HTML or obtaining the SQLite file.

## Background

`website/build.py` renders the whole site from `datasets/awards.sqlite3` into `datasets/website/dist/`. The build
already loads every award row into memory: `read_database` (`website/build.py:612-696`) selects the 29 columns named
in `AWARD_COLUMNS` (`website/build.py:101-131`) and returns them as `AwardRecord` instances
(`website/build.py:150-181`). Nothing in the pipeline exposes those rows as a file — the only machine-readable
artifacts today are the explorer and map JSON payloads embedded in their pages.

`write_robots` (`website/build.py:1791-1793`) is the model to copy: a small function that writes one non-page file
into the staging directory, called from `build_site` (`website/build.py:1893-1918`) before `_make_world_readable`
(line 1913) and `_promote` (line 1914).

The footer lives once, in `website/templates/base.html:48-50`, and all 21 page templates extend `base.html` —
including `404.html`, which is rendered by a second, separate code path (`render_error_page`,
`website/build.py:1837-1863`) that passes absolute hrefs instead of relative ones.

## Assumptions

1. **(Load-bearing)** The CSV carries only the main `awards` table. `award_extra_affiliations` (positions 2+) is out
   of scope; the CSV therefore records at most one affiliation per row, the flat one, exactly as `AWARD_COLUMNS`
   spells it.
2. **(Load-bearing)** The exported columns are the 29 in `AWARD_COLUMNS`, in that order — the same set the site
   already reads and displays, including `sex` (`website/build.py:119`). The three table columns the site never
   reads — `source_laureate_id`, `field_language`, `remarks` — are not exported.
3. **(Load-bearing)** The CSV is built from the `records` already in memory, not from a second query. Every
   `AwardRecord` field is a `_text`-normalized `str` (`website/build.py:364-365`), never `None`, so no per-value
   coercion is needed.
4. **(Load-bearing)** `base.html` is rendered by two code paths with different href conventions, so any new template
   variable MUST be supplied in both. Jinja runs under `StrictUndefined` (`website/build.py:1800`) — a variable
   supplied in only one path fails the build the moment the 404 page renders.
5. **(Load-bearing)** `award_record_id` is a `str` (`website/build.py:153`), so ordering by it is lexicographic, not
   numeric. Production IDs are zero-padded (`abel_prize-000001`), so lexicographic order is the intended order there;
   unpadded IDs would sort `record-10` before `record-2`.
6. One row per award record — 3,093 rows in the current database.

## Scope

| File | Change | LOC |
| --- | --- | --- |
| `website/build.py` | `import csv`; add `write_dataset_csv`; call it in `build_site`; add `csv_href` to both render paths | ~14 |
| `website/templates/base.html` | Footer link | ~1 |
| `tests/test_build_website.py` | One new test | ~15 |

Three files, roughly 30 lines. No new dependency — `csv` is stdlib. No schema change, no new route, no JavaScript, no
CSS.

## Design

### 1. `write_dataset_csv` — `website/build.py`, new function directly after `write_robots` (line 1793)

Mirrors `write_robots`: takes the staging directory, writes one file, returns nothing.

```python
def write_dataset_csv(output: Path, records: Iterable[AwardRecord]) -> None:
    """Dump the award records as RFC 4180 CSV, ordered by award_record_id so the file is reproducible across builds."""
    with (output / "awards.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(AWARD_COLUMNS)
        writer.writerows(
            [getattr(record, column) for column in AWARD_COLUMNS]
            for record in sorted(records, key=lambda record: record.award_record_id)
        )
```

- `import csv` joins the stdlib imports at `website/build.py:11-30`.
- The filename is a bare literal, matching how every other output file in this module is named — `"sitemap.xml"`,
  `"robots.txt"`, `"favicon.svg"`, `"static/style.css"`. No constant.
- `getattr(record, column)` is exact, not incidental: `read_database` constructs each record with
  `*(_text(row[column]) for column in AWARD_COLUMNS)` (`website/build.py:691-692`), so the field names and their
  order are `AWARD_COLUMNS` by construction. `slots=True` does not interfere — it creates ordinary attribute
  descriptors.
- The file MUST be opened with `newline=""`. Without it, Python's text layer translates the `csv` module's `\r\n`
  terminators into `\r\r\n` and every row gains a stray carriage return.
- Ordering is deliberate. `read_database` issues `SELECT ... FROM awards` with no `ORDER BY`
  (`website/build.py:629`), so unsorted output would let SQLite's storage order leak into a published artifact and
  make two builds of the same database differ.
- 1,178 `motivation` values contain a comma and 20 contain a double quote, so quoting is load-bearing. The `csv`
  module handles it; no manual escaping.

### 2. Call site — `website/build.py`, in `build_site` after `write_robots` (line 1911)

```python
        write_robots(staging, normalized_base_url)
        write_dataset_csv(staging, records)
        render_error_page(environment, staging, normalized_base_url)
```

It MUST sit before `_make_world_readable(staging)` (line 1913) so the CSV is chmod'd `0644` with everything else, and
before `_promote` (line 1914) so it is published atomically with the pages that link to it. A build that fails after
this point promotes nothing; there is no window in which the site is live without its CSV.

### 3. `csv_href` — both render paths

Symmetric with the existing `favicon_href` / `style_href` pair. In `_render_job`
(`website/build.py:1808-1834`), beside `style_href` at line 1819:

```python
        csv_href=relative_file(job.route, "awards.csv"),
```

In `render_error_page` (`website/build.py:1837-1863`), beside `style_href` at line 1851:

```python
        csv_href=root + "awards.csv",
```

The 404 page is served for arbitrary request URLs, so its links resolve from the deployment root, not from the file's
own directory — the reason that function exists at all.

### 4. Footer — `website/templates/base.html:48-50`

```html
  <footer>
    <p>A static guide to international awards and their recipients. <a href="{{ href(about_route) }}">About this site</a> · <a href="{{ csv_href }}" download>Download the data (CSV)</a></p>
  </footer>
```

One line, no new CSS. The global `a` rule (`website/static/style.css:42-54`) already gives the link `--accent`,
underline offset, and a focus outline; `footer p` (`style.css:82-85`) keeps the `·` separator muted, so the link
reads as a link and the separator recedes. The `·` with surrounding spaces is the site's existing separator
(`prize.html:21`, `winner.html:6`, `person.html:7-8`, `subject.html:8`, `affiliation.html:15`).

The `download` attribute makes a same-origin link save the file rather than let the browser try to render it. Link
text is self-describing, so no `title` or `aria-label` — one would only create a mismatch with the visible text.

### File format

| Property | Value | Reason |
| --- | --- | --- |
| Path | `dist/awards.csv` | Site root, beside `robots.txt` and `sitemap.xml` |
| Encoding | UTF-8, no BOM | Laureate names are not ASCII; a BOM would corrupt the first header field for every non-Excel reader |
| Line terminator | `\r\n` | `csv.writer` default, RFC 4180 |
| Header | The 29 `AWARD_COLUMNS` names verbatim | The column names are the database's; a reader can map straight back |
| Blank values | Empty field, never `NULL` or `-` | Fields are already `""` after `_text` |
| Row order | Lexicographic by `award_record_id` | Reproducible builds |

### Rejected

- **Adding `awards.csv` to `sitemap.xml`.** The sitemap lists indexable HTML pages; a data file does not belong
  there. `robots.txt` already allows everything, so the file remains fetchable.
- **Exporting `award_extra_affiliations`.** Explicitly out of scope (Assumption 1). Doing so would need either a
  second file or a wider row shape, and would change what one CSV row means.
- **A `csv_rows=` counter on the build summary line.** `main` already prints `recipients={plan.recipient_count}`
  (`website/build.py:1939`), which is `len(records)` and therefore the CSV's row count. A second field would print
  the same variable twice.
- **A second query, or streaming from SQLite.** The records are already in memory and 3,093 rows is trivial.

## Behavior / Acceptance

### Requirement: Dataset dump — the build MUST write `dist/awards.csv` containing every award record

#### Scenario: Complete dump
- WHEN a site is built from a database with N rows in `awards`
- THEN `dist/awards.csv` exists
- AND its header row is the 29 `AWARD_COLUMNS` names in order
- AND it has exactly N data rows
- AND the rows appear in ascending lexicographic `award_record_id` order

#### Scenario: Values needing escaping survive
- WHEN a record's `motivation` contains a comma and a double quote
- THEN reading the file back with `csv.reader` yields that value unchanged

#### Scenario: Extra affiliations are excluded
- WHEN a record has rows in `award_extra_affiliations`
- THEN its CSV row is unaffected and carries only the flat position-1 affiliation columns

### Requirement: Footer link — every generated page MUST link to the CSV

#### Scenario: Nested page
- WHEN a page at a three-segment route such as `/nobel-prize/physics/2024/` is rendered
- THEN its footer contains a link to `../../../awards.csv`
- AND that path resolves to the written file

#### Scenario: Error page
- WHEN `404.html` is rendered for base URL `https://example.org/awards/`
- THEN its footer links to `/awards/awards.csv`, absolute from the deployment root

## Testing

One new test in `tests/test_build_website.py`, using the existing `create_database` fixture
(`tests/test_build_website.py:57-125`) and following the shape of
`test_error_page_and_robots_serve_from_the_deployment_root` (`tests/test_build_website.py:1180`):

`test_dataset_csv_dumps_every_award_and_is_linked_from_every_footer` — build a site from a database whose records
include one with a comma and a double quote in `motivation`, and one carrying an `award_extra_affiliations` row.
Assert: header equals `build.AWARD_COLUMNS`; row count equals the number of inserted records; the escaped value
round-trips through `csv.reader`; ordering is ascending by `award_record_id`; the footer link resolves to the written
file from a nested page, and is root-absolute on `404.html`.

The fixture's `award_record_id` values MUST be zero-padded (`nobel-01`, not `nobel-1`) if the test inserts ten or
more records, or the lexicographic ordering assertion will fail against a correct implementation (Assumption 5).

File mode and general link integrity are already covered by the existing mode sweep and link-resolution crawl in
`test_complete_build_routes_metadata_escaping_and_relative_links`; this test does not repeat them.

Before committing:

```sh
cd datasets
ruff check website/build.py
uv run python -m unittest tests/test_build_website.py
```

Manual check — note that `wc -l` is not a valid row count for CSV, since a quoted field may legally span lines:

```sh
uv run website/build.py --base-url https://example.org/awards/
head -1 website/dist/awards.csv
```

## Non-goals

- Per-view or filtered CSV exports (per prize, per country, per institution).
- JSON, Parquet, or any second export format.
- Publishing `awards.sqlite3` itself.
- Exporting `award_extra_affiliations`, `award_ranking`, or `affiliations`.
- A licence or attribution statement on the download. Worth doing, but it is an About-page content decision, not part
  of this change.

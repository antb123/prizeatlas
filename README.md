# Awards Explorer

Awards Explorer is a free, not-for-profit tool for discovering the people and
institutions behind major international awards.

## Our goal

We want to inspire young people to pursue research.

Important work can feel distant when it is presented only as a finished result
or a famous name. This project makes the paths behind that work easier to
explore: who contributed, what they studied, where they worked, when their
careers developed, and how discoveries connect across countries, institutions,
and fields.

Awards are an entry point, not a definition of whose work matters. The rankings
help visitors navigate the data; they are not a measure of a person's worth or
the only measure of research impact.

## What you can explore

- Laureates and all their recorded awards
- Prize families, categories, and award years
- Countries and research institutions
- Early-career winners and highly decorated researchers
- Leading researchers born in the visitor's country

The site is generated as static HTML from a curated SQLite database. It needs no
application server and remains useful if optional browser features, such as
country detection, are unavailable.

## Architecture

The project is static by design:

- `datasets/awards.sqlite3` is the source of truth.
- One build reads the database in read-only mode, validates the records, and
  renders the complete site with Python and Jinja.
- Pages, styles, scripts, sitemaps, and explorer data are written to
  `datasets/website/dist/`.
- The explorer dataset is embedded in its HTML, so browsing, searching,
  filtering, and charting need no API or database connection.
- The generated files can be served directly by nginx, object storage, or a
  CDN. There is no application process to run, scale, or keep alive.

This keeps page delivery fast, makes deployments inexpensive, and leaves very
little runtime infrastructure that can fail. The visitor-country ranking is the
only optional runtime request; the rest of the site works without it.

## Build locally

From the `datasets/` directory:

```sh
uv run website/build.py --base-url https://example.org/awards/
```

The generated site is written to `datasets/website/dist/`.

Run the website tests with:

```sh
uv run python -m unittest tests/test_build_website.py
```

## Python standards

- Use Python 3.12 or newer and run Python commands through `uv`.
- Prefer small functions, explicit inputs and outputs, and one obvious control
  path.
- Use purpose-specific dataclasses and type hints where they make intent
  clearer.
- Validate required data early and let unexpected failures propagate.
- Keep database reads explicit and transactions short; never hide failure
  behind a silent default.
- Avoid speculative abstractions, framework layers, and dependencies when the
  standard library is sufficient.
- Keep code readable and direct, with a default maximum line length of 180
  characters where no stricter rule exists.

Before committing Python changes, run:

```sh
cd datasets
ruff check website/build.py
uv run python -m unittest tests/test_build_website.py
```

## Data principles

The project favors traceable facts over guesses. Ambiguous identities remain
unmerged, uncertain values remain blank, and curated data is never overwritten
silently.

Official award sources establish the award records. Where possible, the project
uses Wikidata QIDs for stable identities and structured facts, and Wikipedia
for approachable background and discovery links. Material is linked rather
than copied when reuse rights are unclear.

See `datasets/AGENTS.md` for the full validation and build rules.

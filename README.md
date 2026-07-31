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

## Licensing

The source code is licensed under the GNU General Public License, version 2.0
or later; see [LICENSE](LICENSE). The curated data and original site content
are dual-licensed under CC BY-SA 4.0 and the GNU Free Documentation License;
see [CONTENT-LICENSE](CONTENT-LICENSE). Third-party material remains subject to
its source's terms.

## Architecture

The project is static by design:

- `datasets/awards.sqlite3` is the source of truth.
- The 467 non-science award rows (History, Arts, Literature, and Economics) were moved out of that live database and preserved in
  [`datasets/non_science.json`](datasets/non_science.json) for later restoration.
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

## Run locally

Local development is deliberately small: Python 3.12 or newer, the included
SQLite database, and the builder's two declared packages (Jinja and Pillow).
There is no Node.js install, application server, Docker setup, or database
migration. The recommended path uses [uv](https://docs.astral.sh/uv/), which
installs the builder's declared dependencies automatically.

The macOS and Linux shortcut is [`startdev.sh`](startdev.sh): it builds the
static site and serves `datasets/website/dist/` at the chosen local port. Stop
it with <kbd>Ctrl</kbd>+<kbd>C</kbd>.

### Download data only

When the public data snapshots are deployed, download them without cloning the
code or building the site:

```sh
wget -O awards.sqlite3 https://prizeatlas.org/awards.sqlite3
wget -O awards.csv https://prizeatlas.org/awards.csv
```

The SQLite file is the source-of-truth database. The CSV is a flat export of
the same award records, convenient for spreadsheets and data tools.

### macOS

After cloning or downloading the repository, install `uv` once and run the
shortcut from its root:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
cd prizeatlas
./startdev.sh
```

Open [http://localhost:8000/](http://localhost:8000/) or the
[Explorer](http://localhost:8000/explorer/). Pass a port if 8000 is in use:
`./startdev.sh 8080`.

### Linux

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
cd prizeatlas
./startdev.sh
```

Then open [http://localhost:8000/](http://localhost:8000/). Use
`./startdev.sh 8080` to choose another port.

### Windows (PowerShell)

`startdev.sh` is a Bash helper, so Windows uses the same two underlying
commands directly:

```powershell
winget install --id=astral-sh.uv -e
Set-Location prizeatlas\datasets
uv run website/build.py --base-url http://localhost:8000/
py -m http.server 8000 --directory website/dist
```

Open [http://localhost:8000/](http://localhost:8000/) while the final command
is running.

### pip alternative

If you prefer `pip`, create a virtual environment and install only the two
builder dependencies before running the same build and static server.

macOS/Linux:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'jinja2==3.1.6' 'pillow==11.3.0'
cd datasets
python website/build.py --base-url http://localhost:8000/
python -m http.server 8000 --directory website/dist
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install 'jinja2==3.1.6' 'pillow==11.3.0'
Set-Location datasets
python website/build.py --base-url http://localhost:8000/
python -m http.server 8000 --directory website/dist
```

Run the focused website tests from `datasets/` with:

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

See [`AGENTS.md`](AGENTS.md) for the full validation and build rules.

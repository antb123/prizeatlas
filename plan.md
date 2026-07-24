# Nobel & Breakthrough Awards Explorer

## Vision
Create a sleek, reactive FastAPI + HTMX web experience that lets visitors browse and search Nobel, Fields Medal, and Breakthrough Prize laureates by geography, affiliation, prize category, and year, while keeping the UI minimal, beautiful, and fast.

## Key Objectives
- Expose a unified laureate data model across Nobel, Fields, and Breakthrough datasets and all others.
- Deliver fast, incremental filtering (country, state/region, birth country, prize type, university, year range, gender).
- Offer drill-down details for each laureate with timelines, affiliations, and citation text.
- Render responsive, minimal HTML enhanced with HTMX for partial updates and subtle transitions.
- Provide an approachable developer experience with simple scripts and data pipelines.
- 


## Data Sources
- `datasets/nobel.csv`: Nobel Prize data (1901 onwards).
- `datasets/fields.txt`: Parsed into structured rows (Fields Medal winners).
- Breakthrough Prize: TODO — identify/ingest a comparable dataset.
- Additional metadata (country codes, region mappings) to normalize geography.

## Domain Model
- `PrizeEvent`: year, prize name, category, awarding body.
- `Laureate`: full name, birth info, demographics, primary affiliations.
- `Affiliation`: institution, city, country, active years.
- `Award`: join table mapping laureates to prize events with specific citations and share.
- `Geography`: normalized tables for countries/regions; optional `StateProvince` mapping (US states, Canadian provinces, etc.).

## Storage Strategy
- Phase 1: Lightweight CSV readers feeding in-memory structures cached per request cycle.
- Phase 2 (optional): Normalize into SQLite using an ETL script (`scripts/load_data.py`) for relational querying and indexing.
- Keep conversion scripts idempotent and re-runnable; store generated SQLite in `data/awards.sqlite` (ignored by git).

## API Surface (FastAPI)
- `GET /`: Landing page with global stats and search controls.
- `GET /search`: HTMX endpoint returning filtered laureate list; accepts query params `(prize, country, region, birth_country, affiliation, year_from, year_to, gender)`.
- `GET /laureate/{id}`: Detailed laureate panel (modal/side sheet) with biography and all awards.
- `GET /facets`: Optional endpoint returning counts for dynamic filter chips.
- `GET /health`: Basic liveness for deployment checks.

## Frontend & Interactions
- Base layout rendered with Jinja2 templates; progressive enhancement via HTMX requests.
- Search form triggers `hx-get="/search"` with `hx-target` list container; spinners via `hx-indicator`.
- Laureate rows clickable; `hx-get` details into dedicated panel.
- Use CSS utility micro-framework (e.g., [Pico.css](https://picocss.com)) for minimal styling, augment with custom typography & spacing tokens.
- Add subtle transitions using CSS only; avoid heavy JS frameworks.

## UX & Performance Notes
- Debounced search (~300ms) to limit server churn.
- Server-side caching of facet stats for popular filters.
- Pagination or virtual scrolling once result set exceeds ~150 items.
- Provide accessible color contrast and keyboard-friendly interactions.

## Data Processing Pipeline
1. **Parse & Normalize**
   - Nobel CSV: trim whitespace, standardize country names, generate stable `laureate_id`.
   - Fields Medal text: convert tab-delimited lines into structured rows; capture multiple citizenships.
   - Breakthrough Prize: define schema once data is sourced.
2. **Enrichment**
   - Map raw country names to ISO alpha-2/3 codes.
   - Derive `state/region` where applicable (US, Canada, Australia, India).
3. **Persistence**
   - CSV mode: cache parsed data in `fastapi.Depends` with lazy loading.
   - SQLite mode: load tables with indexes on `country`, `year`, `affiliation` for faster filtering.

## Testing & Validation
- Unit tests around parsers (pytest), ensuring consistent normalization.
- Endpoint tests for main search and detail views using FastAPI TestClient.
- Snapshot HTML tests for HTMX fragments to guard against regressions.

## Deployment Outline
- Containerize with slim Python base; multi-stage build to install dependencies.
- Serve via Uvicorn with workers tuned for CPU count; enable gzip/brotli.
- Optional CDN for static assets (Pico CSS, favicon, institutional logos).

## Programming Style Guidelines
- Embrace minimalistic, Unix/Perl-inspired Python: compose small, sharp utilities that can be chained and reused.
- Prefer iterator-based pipelines (`map`, generator expressions) over heavyweight abstractions; avoid unnecessary classes when functions suffice.
- Let data dictate structure: pass records as plain dicts or `NamedTuple`/`dataclass` only when clarity demands it.
- Keep modules short and focused, aiming for scripts that read like shell pipelines (`parse() | normalize() | emit()`).
- Use the standard library aggressively; pull dependencies only when they eliminate boilerplate.
- Document clever transformations with terse comments explaining intent, not mechanics.

## Roadmap & Milestones
1. Normalize existing datasets; stub Breakthrough loader.
2. Stand up FastAPI project structure (`app/main.py`, `app/routes`, `app/services`).
3. Build search endpoint + HTMX list fragment; wire to frontend.
4. Implement detail panel, facet counts, and caching.
5. Polish UI/UX (themes, typography, responsiveness) and add analytics hooks.
6. Add CI lint/test pipeline; document data refresh workflow.


# TODO — Winners near me

Spec: `datasets/docs/specs/website-winners-nearby-20260729.md`. Read its **Assumptions** block before starting any task
below; every block assumes it and nothing else.

All paths are relative to the repository root. Line numbers are as of 20260729 against the current working
tree — re-grep before editing, the file has moved under this spec once already.

```
N1 ─┬─> N2 ─┬─> N4 ─> N6
    │       └─> N5
    └─> N3
```

N2 and N3 touch different files and may run in parallel once N1 lands. N4 and N5 both wait on N2 (they consume the
payload shape). N6 is last: it asserts everything.

---

## N1 — route constant and template registration

**Depends-on:** none
**Files:** `datasets/website/build.py`

**Steps → verify:**

1. Add `NEARBY_ROUTE = "/nearby/"` immediately after `EXPLORER_ROUTE = "/explorer/"` (`build.py:82`).
2. Add `"nearby.html",` to `TEMPLATES` immediately after `"explorer.html",` (`build.py:62`).
3. Create `datasets/website/templates/nearby.html` as a stub that extends `base.html` with an empty
   `{% block content %}` — `_environment` (`build.py:2098`) compiles every name in `TEMPLATES` and the build fails
   without the file.
4. Add `nearby_route=NEARBY_ROUTE,` to **both** render contexts: `_render_job` beside `explorer_route`
   (`build.py:2136`) and `render_error_page` beside `explorer_route` (`build.py:2168`). Both are required —
   `404.html:1` extends `base.html`.

**Verify:** `cd datasets && uv run website/build.py --base-url https://example.org/awards/` succeeds and
`website/dist/nearby/index.html` does not yet exist (no job emits it).

---

## N2 — `nearby_payload`

**Depends-on:** N1
**Files:** `datasets/website/build.py` (new function after `map_json`, `build.py:606-607`)

Write `nearby_payload(records: list[AwardRecord], routes_by_laureate: dict[str, str]) -> dict[str, Any]`.

**Steps → verify:**

1. Walk `records` once. For each record with non-blank `birth_coordinates`, and for each entry of
   `record.affiliations` with non-blank `coordinates`, parse with
   `parse_map_points(value, record.award_record_id, field, multiple=False)[0]`. Do not write a second parser.
2. Identity key per laureate: `record.laureate_wikidata_qid or f"row:{record.award_record_id}"` — the same key
   `explorer_payload` builds at `build.py:427`.
3. Per person, store `[full_name, route]` where `route` is
   `relative_route(NEARBY_ROUTE, routes_by_laureate[qid])` when the QID is non-blank, else `""` (mirrors
   `build.py:433-435`).
4. Group by `(kind, point)` where kind is `"b"` or `"a"`. Per group keep a `set` of identity keys and a
   `Counter` of the recorded name.
   - birthplace name: `record.birth_city.strip()`; where: `record.birth_country.strip()`
   - institution name: `affiliation.name.strip()`; where: `", ".join` of non-blank city and country
   - when the name is blank, fall back to the first non-blank part of where, and drop it from where.
5. Emit places `sorted(...)` by `(kind, point)`. Per place:
   `{"k": kind, "g": [lng, lat], "n": headline, "w": where, "x": len(counter) - 1, "p": [indices]}`.
   The headline is `min(counter.items(), key=lambda item: (-item[1], item[0]))[0]` — same rule and tie-break as
   `build.py:579`. `x` mirrors `extra_labels` at `build.py:586`.
6. Emit `people` sorted by `(full_name, identity key)`; `places[].p` indexes into it, sorted the same way.
   **This ordering is load-bearing** — `SELECT ... FROM awards` (`build.py:651`) has no `ORDER BY`, so insertion
   order would make two builds of the same data differ.
7. Do **not** rename `map_json`; widen its annotation to `def map_json(payload: dict[str, Any]) -> str:`
   (`build.py:606`). `tests/test_build_website.py:332` calls it by name.

**Verify:** in a scratch check, `map_json(nearby_payload(records, routes))` run twice on the same database returns
identical bytes, and `len(payload["places"]) == 2080`, `len(payload["people"]) == 2349`.

---

## N3 — entry points

**Depends-on:** N1
**Files:** `datasets/website/templates/base.html`, `datasets/website/templates/explorer.html`

**Steps → verify:**

1. `base.html:30` — add `<a href="{{ href(nearby_route) }}">Nearby</a>` immediately after the `Map` link.
2. `explorer.html` — insert **after** `<figure id="local-winners-chart"></figure>` (`explorer.html:152`), as a new
   sibling inside the section:
   `<p class="section-note"><a href="{{ href(nearby_route) }}">Find the winners nearest you</a></p>`
   It MUST NOT go inside `#local-winners-note` (`explorer.html:151`): that paragraph's `textContent` is reassigned
   on both the success and the failure path of the country lookup, and the link would disappear on every load.
   No arrow character.
3. Change nothing else in `explorer.html` — no script, no payload, no geolocation.

**Verify:** build, then confirm `dist/explorer/index.html` contains the link outside the note paragraph, and
`dist/404.html` renders the Nearby nav item without a `StrictUndefined` failure.

---

## N4 — the page job and `llms.txt`

**Depends-on:** N2
**Files:** `datasets/website/build.py`

**Steps → verify:**

1. In `create_site_plan`, after the Explorer job (`build.py:1896-1906`):

```python
nearby = nearby_payload(records, routes_by_laureate)
jobs.append(
    _page(
        "nearby.html",
        NEARBY_ROUTE,
        "Award Winners Near You",
        "Find the laureate birthplaces and institutions closest to you, ranked by distance, using your browser's location.",
        (Breadcrumb("Home", "/"), Breadcrumb("Nearby", None)),
        payload=map_json(nearby),
        places=len(nearby["places"]),
        laureates=len(nearby["people"]),
    )
)
```

   `places` and `laureates` are read off the payload, never typed as literals.
2. `write_llms_txt` (`build.py:2005`): the Bulk data sentence at `build.py:2096` says "These two pages" — make it
   three, and add a bullet after the Map bullet naming `<script id="nearby-data" type="application/json">` and its
   `people` / `places` shape.

**Verify:** build; `dist/nearby/index.html` exists, page count is one higher than the previous build,
`dist/sitemap.xml` contains `/nearby/`, and `dist/llms.txt` names the page.

---

## N5 — the page

**Depends-on:** N2
**Files:** `datasets/website/templates/nearby.html` (replaces the N1 stub)

Follow spec §"The page" exactly — markup, row anatomy, and the eleven script rules. Do not touch `static/style.css`.

**Steps → verify:**

1. Markup per the spec sketch: `.page-intro` header; a separate `<section class="locate">` holding the button, the
   `role="status"` paragraph and the plain (**not** `.caveat`) privacy line; a hidden `<h2 id="near-h"
   tabindex="-1">`; `<ol id="near-list" class="near-list">`; a footnote carrying
   `{{ "{:,}".format(places) }}` and `{{ "{:,}".format(laureates) }}` and links to the Map and Countries pages.
2. `<script id="nearby-data" type="application/json">{{ payload|safe }}</script>`, then the page script.
3. Scoped CSS in `{% block head %}` only: `.near-list`, `.near-list > li`, `.near-meta`, `.near-name`, `.near-where`,
   `.near-dot`, `#status { min-height: 1.6em }`, and the button, copying `map.html:118-133`. Two columns at
   `@media (min-width: 40rem)` with `grid-template-columns: 6.5rem minmax(0,1fr)`. Reuse `.rank-units` and
   `.rank-units-more` from the global sheet for the names and the disclosure — do not restyle them.
   `--birth`/`--institution` and their dark-scheme values come from `map.html:14-32`.
4. Script, in this order: read the `#at=` fragment and validate it (`Number.isFinite`, `|lat| ≤ 90`,
   `|lng| ≤ 180`); guard `window.isSecureContext && navigator.geolocation`, removing the button when absent; bind
   one click handler. `JSON.parse` happens **inside** the handler (and the fragment path), never at load.
5. `getCurrentPosition(ok, fail, { timeout: 10000, maximumAge: located ? 0 : 300000 })`. Set the pending status
   sentence *before* the call. Button label changes exactly once, on first success, to `Update my location`.
6. Haversine as `2 * 6371 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))`. Format: `under 1 km`, one decimal below 10,
   whole km with `toLocaleString("en")` above. No metres bucket.
7. Render the 25 nearest. Row: meta line (`distance · dot · Born here|Worked here`), `.near-name` = `n`,
   `.near-where` = `w` plus `+ x other names recorded here` when `x`, then up to 4 laureate names as links with the
   remainder in `.rank-units-more`. Escape every name and label with the `esc` helper spelled at
   `explorer.html:231`; a person with `route === ""` renders as text, not `<a href="">`.
8. Heading is `Closest anywhere` when the nearest place is beyond 500 km, `Near you` otherwise; unhide and `.focus()`
   it on success. `#near-list` MUST NOT carry `aria-live`.
9. Status sentences per the spec's state table, including the fragment disclosure
   (`— from the address bar, not your location`).

**Verify:** `./startdev.sh 8000`, then walk the manual scenarios in the spec's Verification block:
`http://localhost:8000/nearby/` (Network panel shows page + CSS + favicon only), grant, re-click, deny,
`#at=42.3744,-71.1169`, `#at=-48.876,-123.393`, `#at=abc`.

---

## N6 — tests

**Depends-on:** N4, N5
**Files:** `datasets/tests/test_build_website.py`

Add one test beside the map test (`test_map_coordinates_aggregation_serialization_and_routes`), driving
`build.nearby_payload` over a small fixture and one assertion set over the built `dist/`.

**Steps → verify:**

1. Fixture records covering: one laureate with three awards at one institution; two laureates at one birthplace; a
   point recorded under two different institution names; a laureate whose name contains `<` and `&`; a birthplace
   and an institution sharing a coordinate.
2. Assert: the institution place lists that laureate once; `x == 1` on the two-name point and `n` is the commoner
   name; `people` and `places[].p` are ordered by `(name, key)`; `places` is ordered by `(kind, point)` so the
   institution precedes the birthplace at the shared coordinate; building the payload twice yields identical
   `map_json` bytes.
3. Assert on the built site: `dist/nearby/index.html` exists and holds one `application/json` block whose parse has
   `people` and `places` keys; `dist/explorer/index.html` links to `../nearby/`; `/nearby/` is in `sitemap.xml`.
4. Do not assert browser behaviour — the manual scenarios in the spec are marked `(manual)` for this reason.

**Verify:** `cd datasets && uv run -m pytest tests/test_build_website.py` — all green, including the pre-existing
`build.map_json` test at line 332, which the annotation widening must not disturb.

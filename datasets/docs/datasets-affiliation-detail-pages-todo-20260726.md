# TODO — affiliation detail pages (2026-07-26)

Spec: `docs/datasets-affiliation-detail-pages-20260726.md`

Run from `datasets/`. Do not expand scope. Branch per team convention before coding.

---

## T1 — `Affiliation` + `plan_places`

Depends-on: none  
Files: `website/build.py` (`Affiliation` ~147-152, `plan_places` ~446-488, call site ~854)

Steps:
1. Widen `Affiliation` with `slug`, `route`, `awards` as in the spec.
2. Change signature to `plan_places(people, records, record_routes)`.
3. Implement people-path counts, awards-path lists, parent union, slug fold, ascending award sort, country path unchanged.
4. Update call site to pass `records` and `all_record_routes` only after routes are complete.
5. Missing route → `BuildFailure`.

Verify: `uv run python -c "from website.build import plan_places"` import-clean; no other callers of old signature (grep).

---

## T2 — Site plan pages + TEMPLATES

Depends-on: T1  
Files: `website/build.py` (`TEMPLATES` ~36-49, affiliations block ~884-898)

Steps:
1. Add `"affiliation.html"` to `TEMPLATES`.
2. After index job, emit one detail `PageJob` per full affiliation list (title, description with year span, breadcrumbs, context).
3. Index still truncates to `AFFILIATION_ROWS` but passes objects that include `.route`.

Verify: dry logic — score route unique; country jobs unchanged count.

---

## T3 — Templates

Depends-on: T2 (or parallel after shape fixed)  
Files: `website/templates/affiliations.html`, `website/templates/affiliation.html` (new), `website/static/style.css` only if needed

Steps:
1. Link index name via `href(affiliation.route)`.
2. Add `affiliation.html` exactly per spec (omit laureate phrase when `count == 0`).
3. No CSS unless layout breaks.

Verify: templates parse under existing Jinja env (`StrictUndefined`).

---

## T4 — Tests

Depends-on: T1–T3  
Files: `tests/test_build_website.py`

Steps:
1. Add fixture covering: two awards one parent ordered oldest-first; blank QID still on detail; parent outside lowered `AFFILIATION_ROWS` has page; `Freelance` none; index contains href to detail; casing twin parents fold to one slug without failure.
2. `uv run pytest tests/test_build_website.py`

Verify: all green.

---

## T5 — Real rebuild smoke

Depends-on: T4  
Files: none (generated `website/dist/` only)

Steps:
1. `uv run website/build.py --base-url https://example.org/awards/`
2. Open `/affiliations/`, click Harvard (or top), confirm chronological list and winner links.
3. Confirm Caltech single page if both casings present in DB.

Verify: build exits 0; spot-check page readable.

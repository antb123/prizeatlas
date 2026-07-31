# Homepage: Top Women and Top Countries sections

## Goals

Add two new sections to the homepage, placed after "Recently awarded": a "Top Women" leaderboard mirroring the
existing "Most decorated" list, and a "Top Countries" list of the 7 countries with the most affiliated laureates.

## Background

`plan_home_page` (`datasets/website/build.py:2166`) already builds `decorated` (multi-award laureates) and
`top_institutions` for the homepage template (`datasets/website/templates/index.html`). Separately,
`create_site_plan` (`datasets/website/build.py:2394-2396`) already computes `country_places["Awarded"]` via
`plan_country_places(people, route, MEMBERS["Awarded"])` (`datasets/website/build.py:1106-1135`), which ranks
countries by affiliated-laureate count, descending, and is already sorted (`build.py:1134`). No new ranking logic
is needed for either section — only reuse.

Female laureates in this dataset never have more than one award (0 women with >1 award), so "Most decorated"'s
`len(person.awards) > 1` filter cannot be reused for "Top Women" as-is.

## Assumptions

1. **Load-bearing:** "Top Women" reuses the decorated sort key `(-len(person.awards), _surname_key(person.name))`
   without the `>1 awards` filter — just `sex == "Female"`, top `HOMEPAGE_ROWS` (8).
2. **Load-bearing:** the women percentage stat is `female / (female + male)`, computed from `records`, excluding
   blank-sex rows (organizations). Rendered as a rounded integer, e.g. `8%`.
3. "Top Countries" reuses `country_places["Awarded"]` as-is (already computed in `create_site_plan`, already
   sorted by laureate count descending); the homepage only takes the top 7 and renders name + count + route.
4. Both sections use the exact same markup pattern as "Most decorated" / "Recently awarded"
   (`<section><h2>...</h2><ol class="highlights">...`) — no new CSS.
5. `record.sex` values are `"Female"` / `"Male"` / blank (per `datasets/awards.sqlite3`); comparison is exact-match
   on `"Female"`.

## Scope

2 files changed, ~30 LOC.

- `datasets/website/build.py` — `plan_home_page` signature gains `country_places`, and its body gains ~15 lines.
- `datasets/website/templates/index.html` — two new `{% if %}` sections, ~20 lines.

## Backend — `datasets/website/build.py`

**`plan_home_page`** (`build.py:2166-2220`):

- Add parameter `country_places: dict[str, list[Place]]` (the same dict already built in `create_site_plan` at
  `build.py:2394`).
- After the existing `decorated = sorted(...)` block (`build.py:2193-2196`), add:

```python
women = sorted(
    (person for person in people if any(record.sex == "Female" for record, _ in person.awards)),
    key=lambda person: (-len(person.awards), _surname_key(person.name)),
)
women_pct = round(
    100 * sum(1 for record in records if record.sex == "Female")
    / sum(1 for record in records if record.sex in ("Female", "Male"))
)
top_countries = country_places["Awarded"][:7]
```

- Add to the `_page(...)` kwargs (alongside `decorated=` at `build.py:2218`):

```python
        top_women=tuple(women[:HOMEPAGE_ROWS]),
        women_pct=women_pct,
        top_countries=tuple(top_countries),
```

**Call site** (`build.py:2394-2396`, before `plan_home_page` is called): pass `country_places` through — the
dict is already built at this point (`country_places = {label: plan_country_places(...) for label, route in
COUNTRY_VIEWS}`, `build.py:2394`), so `plan_home_page` just needs the argument added at its call site.

## Frontend — `datasets/website/templates/index.html`

Insert after the "Recently awarded" section closes (`index.html:62`, before `{% include "_awards.html" %}` at
line 63):

```html
{% if top_women %}
<section>
  <h2>Top women</h2>
  <ol class="highlights">
    {% for person in top_women %}
    <li>
      <a href="{{ href(person.route) }}">{{ person.name }}</a>
      <span>
        {% for name, route in person.subjects %}<a class="subject-badge" href="{{ href(route) }}">{{ name }}</a>{% endfor %}
        {{ person.awards | length }} {{ "award" if person.awards | length == 1 else "awards" }}
      </span>
    </li>
    {% endfor %}
  </ol>
  <p>{{ women_pct }}% of winners are women.</p>
</section>
{% endif %}
{% if top_countries %}
<section>
  <h2>Top countries</h2>
  <ol class="highlights">
    {% for country in top_countries %}
    <li>
      <a href="{{ href(country.route) }}">{{ country.name }}</a>
      <span>{{ country.people | length }} {{ "laureate" if country.people | length == 1 else "laureates" }}</span>
    </li>
    {% endfor %}
  </ol>
</section>
{% endif %}
```

Uses the same `<section>` / `<h2>` / `<ol class="highlights">` / `<li><a>...<span>...</span></a></li>` structure
as the existing "Most decorated" and "Recently awarded" sections — no new CSS classes, no styling changes.

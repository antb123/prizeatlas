## Goals

Keep the global institution ranking scannable when a parent institution has many recorded units. The ranking MUST show
at most three units per institution before offering an accessible disclosure for the remaining units, while preserving
the existing institution detail page as the complete drill-in.

Success means that University of California occupies one compact ranking row with its three highest-count units visible,
the remaining ten units available through a `+ 10 more` disclosure, and no change to ranking counts, order, routes, or
institution detail-page content.

## Background

`website/templates/affiliations.html:11-27` currently renders every `affiliation.units` entry directly beneath its parent
ranking row. After the reviewed University of California normalization, that produces 13 child rows beneath one
institution and makes the global ranking visually noisy.

The units are materialized for each affiliation at `website/build.py:902-909`, with count-descending and name-tiebreak
ordering defined by `_ranked()` at `website/build.py:993-994`; the template receives the complete tuple at
`website/build.py:1548-1562`. Each institution name already links to its full detail page, where
`website/templates/affiliation.html:23-37` lists every award with its associated unit. No new route, data model, or
JavaScript behavior is needed.

## Assumptions

1. **Load-bearing:** “Top three” means the first three entries in the existing count-descending `affiliation.units` tuple.
2. **Load-bearing:** The disclosure is inline on the global ranking and uses native HTML `<details>` with no JavaScript.
3. Institutions with three or fewer units show every unit and no disclosure control.
4. The institution detail page remains the complete drill-in and does not gain separate campus or unit routes.

## Scope

Three files, approximately 30 changed lines:

| File | Expected change |
|---|---|
| `website/templates/affiliations.html:11-27` | Use a flow-content wrapper, render the first three units, and place any remainder in a native disclosure. |
| `website/static/style.css:317-347` | Style the compact disclosure consistently with the existing muted unit list. |
| `tests/test_build_website.py:896-937` | Add generated-site coverage for three visible units, the remainder count, and the no-disclosure boundary. |

`website/build.py` is unchanged: it already supplies complete, correctly ordered unit tuples. Data, schemas, generated
output, other ranking surfaces, and the institution detail template are out of scope.

## Ranking presentation

### Requirement: compact unit preview — MUST show no more than three units before disclosure

#### Scenario: institution has more than three units

- WHEN the global institution ranking renders an institution with five units
- THEN its first three units appear in the always-visible unit list
- AND a native disclosure summary reads `+ 2 more`
- AND opening the disclosure reveals units four and five in their existing order
- AND the parent institution count and rank remain unchanged.

#### Scenario: institution has exactly three units

- WHEN the global institution ranking renders an institution with three units
- THEN all three units appear directly
- AND no disclosure control renders.

#### Scenario: institution has no units

- WHEN the global institution ranking renders an institution with no recorded sub-name
- THEN the row retains its current name, rank, and count markup
- AND no empty unit list or disclosure renders.

## Accessibility and styling

The disclosure MUST use native `<details>` and `<summary>` elements so it remains keyboard-operable without JavaScript.
The summary MUST expose the exact number of hidden units. CSS in `website/static/style.css:317-347` SHOULD keep the
summary aligned with the unit list, use the existing muted text treatment, and preserve the browser’s disclosure
indicator rather than replacing it with a custom control.

The ranking row’s middle wrapper at `website/templates/affiliations.html:15-23` MUST change from `<span>` to `<div>`.
Both the existing `<ul>` and the new `<details>` are flow content and MUST NOT remain nested inside a phrasing-only
`<span>`.

The hidden unit list MUST retain semantic `<ul>`/`<li>` markup and the existing tabular unit counts. Opening or closing
the disclosure MUST NOT change the parent row’s rank bar, count, or link target.

## Compatibility and failure behavior

The feature is static HTML/CSS and requires no client-side state, persistence, or migration. Browsers without enhanced
styling still receive a functional native disclosure. Empty or short unit tuples are handled entirely by template
guards; malformed unit data continues to fail or render according to the existing build path.

## Verification

1. Add a fixture institution with five ordered units; isolate that institution’s ranking row and verify units one
   through three are outside and before its `<details>` block, the summary reads `+ 2 more`, and units four and five are
   inside the bounded `<details>...</details>` content in their existing order.
2. In the same generated page, isolate a fixture institution with exactly three units and verify its row contains all
   three units and no `<details>` block.
3. Isolate a fixture institution with no units and verify its row contains the unchanged parent rank/count/link markup,
   with no empty unit list or disclosure.
4. Verify the five-unit fixture’s parent rank and count are unchanged by the disclosure markup.
5. Run `uv run --with pytest pytest tests/test_build_website.py`.
6. Build with `uv run website/build.py --base-url https://example.org/awards/` and inspect
   `website/dist/affiliations/index.html`: University of California shows three units plus `+ 10 more`.
7. Confirm `website/dist/affiliations/university-of-california/index.html` remains complete and its 110-laureate,
   152-award totals are unchanged.

## Delivery constraints

Implement on one branch with generated tests, use a conventional commit, and do not merge until reviewed. A tracked
rename or move, if unexpectedly required, MUST use `git mv`. Squash-merge into the `202607` month branch.

# Contributing prizes and prize data

Awards Explorer welcomes proposals for new prize families, missing recipients, and corrections to existing records.
GitHub is the public place to propose and review those changes. It is not a second data store: the accepted data in
`datasets/awards.sqlite3` remains authoritative.

## Contribution model

Use the smallest path that makes the proposed change easy to review:

| Proposed change | Start with | Who applies the final data change |
| --- | --- | --- |
| Add a new prize family | GitHub issue | Maintainer |
| Add missing recipients or years | GitHub issue | Maintainer |
| Correct recipient facts | GitHub issue naming the exact record, when known | Maintainer |
| Correct an official URL, blurb, or other ranking copy | Pull request against `datasets/award_ranking.toml` | Contributor, after review |
| Change a prestige score or its reasoning | GitHub issue | Maintainer, after editorial review |
| Change affiliation data | GitHub issue following the affiliation rules | Maintainer |

Do not submit an unexplained binary change to `datasets/awards.sqlite3`. SQLite diffs do not show reviewers which cells
changed, what evidence supports them, or whether existing curated values were overwritten.

External contributors may open pull requests from a fork. Maintainers continue working in the current checkout without
creating project branches.

## Adding a prize family

Open one GitHub issue before preparing data. Use a title such as:

`Add prize: <official English name>`

The issue must provide:

1. The prize's official English name and official website.
2. The awarding organization.
3. A stable official page listing recipients, or one official recipient page per proposed record.
4. The first award year and the years covered by the proposed addition.
5. The prize's formal categories, if it has any. State explicitly when it has none.
6. The prize's Wikidata QID, when one has been verified.
7. One recipient per line, with award year, category, official source URL, and the recipient's Wikidata QID when
   confidently verified.
8. Any known complications, including shared awards, organizations, collaborations, renamed categories, missing years,
   or recipients whose identity is uncertain.
9. A short explanation of why the prize belongs in this collection.

Links to search results, copied biographies, generated summaries, or unsourced spreadsheets are not evidence. Prefer
the awarding body's own roster and recipient pages. Wikidata and Wikipedia may support identity and structured facts,
but they do not replace the official award source.

### Acceptance criteria

A prize may be accepted when:

- it is a recurring or historically established award with a clearly identified awarding body;
- its recipients and award years can be reconstructed from reliable sources;
- it recognizes substantial achievement rather than participation, membership, or placement in a competition;
- its identity is distinct from categories or medals that belong to another prize family; and
- the available evidence is sufficient to enter records without guessing.

Acceptance into the dataset and placement in the prestige ranking are separate editorial decisions. Inclusion does not
guarantee a particular score or position. A declined proposal is not a judgment on the value of the prize or its
recipients; it may simply lack a stable roster, adequate sourcing, or a clear fit with the collection.

## How an accepted prize enters the repository

A supported prize family exists in two coordinated places:

- `datasets/awards.sqlite3`, table `awards`, contains one row per recipient and award; and
- `datasets/award_ranking.toml` contains the prize family's QID, public slug, official URL, unique score, blurb, and
  ranking reasoning.

These sets must match exactly. `datasets/scripts/load_award_ranking.py` rejects missing, extra, or mismatched prize
families, so adding only a TOML block does not add a prize.

After accepting a proposal, a maintainer:

1. resolves unanswered identity and category questions before opening a write transaction;
2. backs up `datasets/awards.sqlite3`;
3. adds the award records with new, stable `award_record_id` values;
4. adds the corresponding `datasets/award_ranking.toml` entry;
5. loads the ranking seed and runs the repository's data validation;
6. checks SQLite integrity; and
7. rebuilds and tests the static website.

The maintainer records the issue or pull request as the research handoff. Source and confidence information must not be
placed in unrelated database columns merely to preserve it.

## Recipient and record corrections

For a correction, provide:

- the exact `award_record_id`, if known;
- the current value;
- the proposed value;
- an official or otherwise authoritative source supporting the change; and
- enough identity evidence to distinguish people or institutions with similar names.

The project fills blank cells only during enrichment and does not silently replace curated values. A proposal that
changes an existing nonblank value therefore needs explicit evidence that the current value is wrong.

Uncertainty is an acceptable outcome. Leave a field unresolved instead of inferring a date, identity, category,
affiliation, prize share, source identifier, or location.

## Data rules contributors need to know

The complete validation contract is in `AGENTS.md`. In particular:

- each named person is a separate award row;
- `laureate_type` is either `Individual` or `Organization`;
- organizations carry no personal birth, sex, or death data;
- dates use ISO `YYYY-MM-DD`, or `YYYY` when only the year is known;
- places use their present-day city and country names;
- `source_laureate_id` is only an identifier explicitly assigned by the official award source;
- a prize without formal categories has a blank `category`;
- a person must not be matched from their name alone; and
- existing `award_record_id` values are never renumbered.

Affiliations have additional identity, ownership, and provenance requirements. Read
`datasets/docs/datasets-affiliation-records-20260728.md` before proposing an affiliation value or a second affiliation.

## Pull request expectations

A pull request must be narrow and traceable:

- link the GitHub issue that established the scope;
- change only the accepted prize or records;
- cite sources in the issue or pull-request description, not in unrelated data fields;
- preserve existing curated values outside the accepted correction;
- include the validation commands that were run and their results; and
- exclude generated `datasets/website/dist/` output and database backup files.

Maintainers may ask for the proposal to return to an issue when a pull request exposes unresolved identity, sourcing,
ranking, or data-model questions.

## Future automation

A structured GitHub issue form is the next useful automation. It should require the fields in this document and route
new prizes, missing recipients, corrections, ranking changes, and affiliations separately.

If contribution volume later justifies an importer, it should accept a small human-readable proposal file, validate it,
and emit a review report before any guarded SQLite write. Until that workflow exists, GitHub issues plus maintainer
application provide the clearest audit trail without creating another source of truth.

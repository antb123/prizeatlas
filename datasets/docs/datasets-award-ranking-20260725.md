# Award prestige ranking table

## Goals

`awards.sqlite3` MUST contain one ranked row for every award family in `awards`.

Prestige means proven impact on human knowledge through the lasting achievements of recipients, with international
recognition not restricted to one organization, country, or nationality.

Each row contains the award identity, curated website slug, official URL, a unique 0–100 score, a blurb, and the
reason for the score. Rank is derived from descending score.

## Background

`awards.sqlite3` has 3,091 recipient rows and 14 distinct `award_wikidata_qid`/`prize_name` pairs. The 99 Economics
rows use `Sveriges Riksbank Prize in Economic Sciences` and QID `Q47170`, separate from the five Nobel Prize
families under QID `Q7191`.

The database previously had no table
describing the award families themselves. `AGENTS.md:35-58` makes the database the source of truth and requires a
backup and `PRAGMA integrity_check` for writes.

## Assumptions

1. **Load-bearing:** Proven contribution to knowledge matters; publicity, ceremony, and prize money do not.
2. **Load-bearing:** Awards must recognize recipients internationally, regardless of nationality or home country.
3. **Load-bearing:** Field specialization does not reduce prestige.
4. **Load-bearing:** Scores are editorial and unique, producing one global order.
5. `award_ranking.toml` is the complete source of the ranking table.
6. Each prize route is curated in `award_ranking.slug`, not derived from its display name.

## Ranking

| Rank | Prize | Score |
| ---: | --- | ---: |
| 1 | Nobel Prize | 100 |
| 2 | Fields Medal | 96 |
| 3 | Turing Award | 94 |
| 4 | Max Planck Medal | 92 |
| 5 | Abel Prize | 90 |
| 6 | Lasker Award | 87 |
| 7 | Canada Gairdner International Award | 84 |
| 8 | Wolf Prize | 81 |
| 9 | Kyoto Prize | 78 |
| 10 | Crafoord Prize | 75 |
| 11 | Shaw Prize | 72 |
| 12 | Japan Prize | 69 |
| 13 | Breakthrough Prize | 66 |
| 14 | Sveriges Riksbank Prize in Economic Sciences | 60 |

The seed stores the blurb and reasoning for each score. A younger award may rank lower because it has less history
from which to prove lasting impact.

## Data model

```sql
CREATE TABLE award_ranking (
        "award_wikidata_qid" TEXT PRIMARY KEY,
        "prize_name"         TEXT NOT NULL UNIQUE,
        "slug"               TEXT NOT NULL UNIQUE,
        "url"                TEXT NOT NULL,
        "score"              INTEGER NOT NULL UNIQUE CHECK (score BETWEEN 0 AND 100),
        "blurb"              TEXT NOT NULL,
        "reasoning"          TEXT NOT NULL
) STRICT;
```

`award_ranking_slug_idx` is a unique index over `slug`. Seed slugs match
`[a-z0-9]+(?:-[a-z0-9]+)*`; they are the stable public prize paths. There is no stored rank, tier, field, year, or
recipient count.

## Loading

`scripts/load_award_ranking.py`:

1. Reads and validates `award_ranking.toml`.
2. Requires its QID/name pairs to equal `SELECT DISTINCT award_wikidata_qid, prize_name FROM awards`.
3. In one transaction, creates or upgrades `award_ranking`, adds `slug TEXT NOT NULL DEFAULT ''` when needed,
   deletes its rows, creates `award_ranking_slug_idx`, and inserts the complete seed.
4. Rolls back on failure and runs `PRAGMA integrity_check` after success.

Full replacement is the simplest safe load: it removes stale rows and allows scores to be reordered without unique
constraint conflicts. The loader MUST NOT modify `awards`.

Dry run:

```text
uv run scripts/load_award_ranking.py --dry-run
```

Real load after backing up:

```text
cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d).bak
uv run scripts/load_award_ranking.py
```

## Files

Four implementation files, approximately 430 lines, plus the live database update:

| File | Lines | Purpose |
| --- | ---: | --- |
| `award_ranking.toml` | 1-111 | Complete 14-award seed, including curated slugs. |
| `scripts/load_award_ranking.py` | 1-155 | Validate, migrate, and load the seed. |
| `tests/test_load_award_ranking.py` | 1-250 | Focused validation, migration, rollback, and loader tests. |
| `AGENTS.md` | 35-58, 174-178 | Database workflow and Economics family documentation. |

## Acceptance

- Invalid, incomplete, or mismatched seed data MUST fail before writing.
- A valid load MUST make `award_ranking` exactly equal to the seed.
- Every prize MUST have a nonblank official HTTPS URL.
- Every prize MUST have a valid unique slug and the table MUST enforce it through `award_ranking_slug_idx`.
- Migrating a pre-slug table MUST add the column only inside the load transaction and index it after deleting
  duplicate migration defaults.
- A failed migration or insert MUST restore the previous schema and rows.
- Reordering scores MUST succeed.
- Failed insertion MUST preserve the previous ranking rows.
- Dry-run MUST perform no writes.
- The loader MUST leave `awards` unchanged.
- All 99 Economics rows MUST use `Sveriges Riksbank Prize in Economic Sciences` and QID `Q47170`.
- `PRAGMA integrity_check` MUST return `ok`.
- `uv run python -m unittest tests/test_load_award_ranking.py` MUST pass.

## Out of scope

Rendering, APIs, formulas, multiple ranking dimensions, and awards not present in the live database.

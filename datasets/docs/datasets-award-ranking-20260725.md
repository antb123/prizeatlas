# Award prestige ranking table

## Goals

Give `awards.sqlite3` a curated, human-readable ranking of the awards it already tracks — one row per prize, with a
0–100 prestige score, a blurb, and the reasoning behind the number — so the dataset can answer "how do these prizes
rank against each other, and why" without that judgment living in someone's head.

## Background

`awards.sqlite3` holds a single flat `awards` table, one row per laureate/recipient, 3091 rows across 13 prize
families. The prize identity on each row is `prize_name` (canonical family, e.g. `Nobel Prize`) plus
`award_wikidata_qid` (e.g. `Q7191`); the `prize` column carries the specific sub-award and varies per row
(`The Nobel Prize in Chemistry 1901`, `Breakthrough Prize in Life Sciences`). There is today no per-award table —
nothing describes an award as an entity, only its recipients.

The 13 prize families, with row counts and the year of first award present in the data:

| `prize_name` | `award_wikidata_qid` | rows | first |
| --- | --- | ---: | ---: |
| Nobel Prize | Q7191 | 1026 | 1901 |
| Lasker Award | Q921415 | 423 | 1946 |
| Wolf Prize | Q739936 | 391 | 1978 |
| Canada Gairdner International Award | Q1031994 | 387 | 1959 |
| Breakthrough Prize | Q17278140 | 148 | 2012 |
| Kyoto Prize | Q658444 | 129 | 1985 |
| Shaw Prize | Q584250 | 121 | 2004 |
| Japan Prize | Q908745 | 116 | 1985 |
| Max Planck Medal | Q317038 | 90 | 1929 |
| Crafoord Prize | Q583069 | 82 | 1982 |
| Turing Award | Q185667 | 81 | 1966 |
| Fields Medal | Q28835 | 68 | 1936 |
| Abel Prize | Q188184 | 29 | 2003 |

The presentation model is thegreatestbooks.org/lists: a single ranked list, each entry carrying a score and a short
justification. That site derives its score by counting appearances across published lists. No equivalent corpus
exists here, so the score is editorial — stated as opinion, defended in prose, not dressed up as a measurement.

Prerequisite context: `AGENTS.md` (`## current data target`) establishes `awards.sqlite3` as the sole source of
truth, requires a backup before any bulk write, and requires `PRAGMA integrity_check` after writes.

## Assumptions

1. **(load-bearing)** The score is editorial, not computed. No formula, no derived signals — a curated integer with
   prose reasoning. If the score must instead be reproducible from data, the schema grows signal columns and this
   design changes.
2. **(load-bearing)** One global ranking across all 13 awards, not a per-field ranking. Comparing the Turing Award
   to the Fields Medal is a judgment call; `reasoning` is where that judgment is defended and `field` exists only
   for filtering, never for scoping the rank.
3. **(load-bearing)** `score` is unique across rows, making `ORDER BY score DESC` a total order. Rank is therefore
   derived at query time and MUST NOT be stored. If ties are wanted, `rank` becomes a stored column and the
   uniqueness constraint is dropped.
4. `tier` is derived from `score` bands as a generated column — never curated independently, so the two cannot
   contradict each other.
5. The table describes only awards already present in `awards`. Every `award_wikidata_qid` MUST match an existing
   value in `awards.award_wikidata_qid`.
6. Nothing derivable from `awards` is stored here — no first year, no laureate count. Those are queries, not columns.
7. Scope is the table, its seed data, and the loader. No rendering, no HTML, no API.
8. SQLite is 3.45.1 (generated columns need ≥3.31, `STRICT` needs ≥3.37 — both satisfied). Python is 3.12, so
   `tomllib` is in the standard library. Scripts here use the standard library only; that holds.
9. The loader runs against the live `awards.sqlite3` and MUST NOT rebuild or replace it. `scripts/import_sqlite.py`
   is explicitly marked `DONT RUN - will destroy db!!`; the new loader is additive and idempotent by contrast.

## Scope

4 files, ~230 lines total.

| File | Change | Lines |
| --- | --- | ---: |
| `award_ranking.toml` | new — curated seed data, 13 blocks | ~110 |
| `scripts/load_award_ranking.py` | new — schema + idempotent loader | ~95 |
| `tests/test_load_award_ranking.py` | new — loader tests | ~65 |
| `AGENTS.md` | edit — document the table after line 47 | ~18 |

Note: `AGENTS.md:47` is inside the `## current data target` section, immediately after the line describing the
`awards` table's column set. The new table's documentation belongs there.

## Data model

```sql
CREATE TABLE award_ranking (
        "award_wikidata_qid" TEXT PRIMARY KEY,
        "prize_name"         TEXT NOT NULL UNIQUE,
        "score"              INTEGER NOT NULL UNIQUE CHECK (score BETWEEN 0 AND 100),
        "tier"               INTEGER GENERATED ALWAYS AS (
                                 CASE WHEN score >= 90 THEN 1
                                      WHEN score >= 80 THEN 2
                                      WHEN score >= 70 THEN 3
                                      WHEN score >= 60 THEN 4
                                      ELSE 5 END) VIRTUAL,
        "field"              TEXT NOT NULL CHECK (field IN ('general', 'mathematics', 'computing', 'medicine', 'physics')),
        "blurb"              TEXT NOT NULL,
        "reasoning"          TEXT NOT NULL
) STRICT;
```

Column contract:

- `award_wikidata_qid` — primary key; MUST exist in `awards.award_wikidata_qid`. The join key to the laureate rows.
- `prize_name` — MUST equal the `awards.prize_name` value for that QID exactly. Denormalised so the table reads
  standalone; the loader validates it rather than trusting it.
- `score` — curated 0–100. `UNIQUE` by design (assumption 3): with 13 rows over 101 values, a tie is a decision
  the curator declined to make.
- `tier` — `VIRTUAL` generated column. Not stored, not curated, cannot drift.
- `field` — filtering facet only. `general` means the award spans several unrelated disciplines.
- `blurb` — one or two sentences describing the award itself. Factual; no score talk.
- `reasoning` — prose defending the score. This is where the editorial judgment is exposed and argued with.

No index beyond the implicit primary key and the two `UNIQUE` constraints. Thirteen rows do not need one.

Relationship to the existing table:

```
awards.award_wikidata_qid  ──many-to-one──▶  award_ranking.award_wikidata_qid
   (3091 laureate rows)                          (13 award rows)
```

`STRICT` and the `"quoted"` column style follow `scripts/import_sqlite.py:84-86`.

### Derived queries this enables

Rank is derived, never stored:

```sql
SELECT ROW_NUMBER() OVER (ORDER BY score DESC) AS rank, prize_name, score, tier, field
FROM award_ranking ORDER BY score DESC;
```

Ranking joined to laureate counts (the reason nothing derivable is stored — assumption 6):

```sql
SELECT r.prize_name, r.score, r.tier, COUNT(a.award_record_id) AS laureates, MIN(a.year) AS first_year
FROM award_ranking r JOIN awards a USING (award_wikidata_qid)
GROUP BY r.award_wikidata_qid ORDER BY r.score DESC;
```

## Seed data

`award_ranking.toml`, hand-editable, one block per award. TOML over JSON/CSV because the prose fields are the point
and multi-line strings stay readable:

```toml
[Q7191]
prize_name = "Nobel Prize"
score = 100
field = "general"
blurb = """
Established by Alfred Nobel's 1895 will and first awarded in 1901, across physics, chemistry, physiology or
medicine, literature, and peace, with an economic sciences prize added by the Swedish central bank in 1968.
"""
reasoning = """
The reference point every other prize on this list is measured against — "the Nobel of X" is the standard
compliment. Oldest, most widely recognised outside its own disciplines, and the only one whose announcement is
general news. Scored 100 by definition: the scale is anchored here.
"""
```

Proposed scores, for review. The numbers and prose are a starting position, not a conclusion:

| # | Prize | Score | Tier | Field | Reasoning summary |
| ---: | --- | ---: | ---: | --- | --- |
| 1 | Nobel Prize | 100 | 1 | general | Anchors the scale. Oldest, broadest, the only one that is general news. |
| 2 | Fields Medal | 94 | 1 | mathematics | Awarded once every four years to at most four people under 40 — the most selective on the list by a wide margin. |
| 3 | Turing Award | 91 | 1 | computing | Uncontested summit of its field, with a $1M purse; capped only by computing's shorter history. |
| 4 | Abel Prize | 87 | 2 | mathematics | Explicitly built as mathematics' Nobel: annual, lifetime achievement, ~NOK 7.5M, Norwegian state backing. |
| 5 | Lasker Award | 85 | 2 | medicine | Long-running and a famously strong Nobel leading indicator, but confined to biomedicine and little known outside it. |
| 6 | Max Planck Medal | 82 | 2 | physics | Recipient roster is arguably the finest of any award here — Planck, Einstein, Bohr, Heisenberg, Schrödinger, Dirac, Pauli. Honorific only, no purse, narrow to theoretical physics, near-zero public profile. |
| 7 | Wolf Prize | 79 | 3 | general | Multi-field and a reliable Nobel precursor, especially in physics and medicine; overshadowed by the Nobel in every field it shares. |
| 8 | Kyoto Prize | 76 | 3 | general | ¥100M and deliberately covers ground the Nobel does not, including arts and philosophy. Respected, but thinly known in the West. |
| 9 | Crafoord Prize | 73 | 3 | general | Awarded by the same Royal Swedish Academy of Sciences and designed to fill the Nobel's disciplinary gaps — astronomy, mathematics, geosciences, biosciences. Borrowed prestige, rotating fields. |
| 10 | Shaw Prize | 70 | 3 | general | The "Nobel of the East": $1.2M, serious selection, strong astronomy record. Founded 2004, so its reputation is still accruing. |
| 11 | Breakthrough Prize | 67 | 4 | general | Largest purse of any ($3M) and the most publicity, but the youngest here and criticised for celebrity-gala framing over scholarly weight. |
| 12 | Canada Gairdner International Award | 64 | 4 | medicine | One of the best Nobel predictors in biomedicine — roughly a quarter of recipients go on to a Nobel — yet almost unknown outside the field. |
| 13 | Japan Prize | 60 | 4 | general | Substantial (¥50M) and state-backed, honouring science and technology broadly; the least internationally visible of the thirteen. |

Two rows to argue with first:

- **Max Planck Medal at 82 (tier 2).** You named it top tier. I scored it below 90 because it is honorific-only,
  narrow to theoretical physics, and essentially unknown outside it — the recipient list is extraordinary, the
  award's own reach is not. Raise it above 90 if peer prestige should outweigh reach; that is a coherent position
  and only the number changes.
- **Gairdner at 64, below Breakthrough at 67.** Gairdner is the better predictor of future Nobels; Breakthrough has
  far more money and visibility. Their order depends entirely on whether "prestige" means standing among
  specialists or standing in the world.

## Loader

`scripts/load_award_ranking.py`, standard library only, following the shape of `scripts/import_sqlite.py` — module
docstring, a single failure exception, `argparse`, grep-able one-line-per-fact output, exceptions propagating to a
`main` that returns an exit code.

Unlike `import_sqlite.py:153-184`, which builds a fresh database into a temp file and `os.replace`s it, this loader
writes to the live database in place (assumption 9). It therefore MUST be idempotent and MUST NOT touch `awards`.

```
load_award_ranking.py --database awards.sqlite3 --seed award_ranking.toml [--dry-run]

  read seed  ──▶  validate  ──▶  BEGIN  ──▶  create table if absent  ──▶  upsert 13 rows  ──▶  COMMIT
                     │                                                                            │
                     ├─ every QID exists in awards.award_wikidata_qid          integrity_check ◀───┘
                     ├─ prize_name matches awards for that QID                        │
                     ├─ score in 0..100 and unique across the seed          "ok" or ImportFailure
                     └─ field in the allowed set
                             │
                       ImportFailure → exit 1, nothing written
```

Requirements:

- **Validate before writing.** The loader MUST validate the whole seed file against `awards` before opening the
  write transaction, and MUST abort without writing if any row fails. Partial loads are not acceptable.
- **Idempotent.** Re-running with an unchanged seed MUST leave the table byte-identical. Re-running with an edited
  seed MUST update the changed rows in place. `INSERT ... ON CONFLICT(award_wikidata_qid) DO UPDATE SET ...`.
- **Additive.** The loader MUST NOT issue `DROP`, and MUST NOT write to `awards`.
- **Verified.** After commit it MUST run `PRAGMA integrity_check` and fail loudly on anything but `ok`, per
  `AGENTS.md`.
- **`--dry-run`** MUST validate and report what would change without opening a write transaction.
- Log lines carry the fact and the identifier, e.g. `loaded qid=Q7191 prize="Nobel Prize" score=100 action=insert`
  and a closing `database=... rows=13`.

Back up before the first real run, per `AGENTS.md`:

```
cp awards.sqlite3 awards.sqlite3.$(date +%Y%m%d).bak
```

## Behaviour / Acceptance

### Requirement: Seed integrity — the loader MUST reject a seed that does not describe the live data

#### Scenario: unknown award QID
- WHEN the seed contains a QID absent from `awards.award_wikidata_qid`
- THEN the loader exits non-zero naming the offending QID
- AND `award_ranking` is unchanged (or still absent)

#### Scenario: prize_name disagrees with awards
- WHEN a seed block's `prize_name` differs from the `awards.prize_name` for that QID
- THEN the loader exits non-zero naming both values
- AND nothing is written

#### Scenario: duplicate score
- WHEN two seed blocks carry the same `score`
- THEN the loader exits non-zero naming the colliding prizes
- AND nothing is written

### Requirement: Loading MUST be idempotent and additive

#### Scenario: repeated run, unchanged seed
- WHEN the loader runs twice against the same seed
- THEN the second run reports 13 rows with no net change
- AND `SELECT COUNT(*) FROM awards` is identical before and after both runs

#### Scenario: edited score
- WHEN a score is changed in the seed and the loader re-runs
- THEN that row's `score` is updated in place
- AND its `tier` reflects the new score's band without any separate edit

### Requirement: Derived columns MUST NOT be writable

#### Scenario: tier follows score
- WHEN a row is stored with `score = 87`
- THEN `SELECT tier` for that row returns `2`
- AND no seed field sets `tier` directly

## Out of scope

Rendering (HTML, thegreatestbooks-style page), computed//derived prestige signals, awards not already in
`awards.sqlite3`, and any change to the `awards` table or its 29 columns.

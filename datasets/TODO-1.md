# Dataset verification and retrieval TODO

Snapshot: 2026-07-24. This replaces the stale 2026-07-24 snapshot that predated 19 later data commits.

This is a data-collection backlog, not a software implementation plan. Each numbered dataset task covers no more than five recipient rows so that a small data verification/retrieval agent can complete it without writing code. Agents write verified results to `awards.sqlite3`; the CSV files are read-only source snapshots.

## Current structural state

- `awards.sqlite3` is the enrichment target. Its `awards` table contains all 3,091 current records and 29 columns.
- The table preserves the 26 CSV fields and adds `prize_name`, `award_wikidata_qid`, and `laureate_wikidata_qid`.
- All records have a unique `award_record_id`; `prize_name` and `award_wikidata_qid` are populated for all 13 prize families, and 114 existing person/organization QIDs have been carried into `laureate_wikidata_qid`.
- All 13 read-only CSV snapshots retain the canonical ordered 26-column header.
- The original 12-file canonical conversion is structurally complete. The older `docs/datasets-canonical-csv-schema-todo-20260723.md` has obsolete row-count and empty-coordinate checks and MUST NOT be executed literally.
- Blank cells are not automatically errors. A task is complete when every assigned row has been checked against the allowed sources and every blank is classified as filled, inapplicable, or unresolved.
- `uv run scripts/import_sqlite.py` replaces the database from the CSV snapshots. Once SQLite enrichment begins, agents MUST NOT run the importer because it would discard SQLite-only changes.

## Data-agent contract

Every dataset task below uses this contract:

1. Work only in `awards.sqlite3`, table `awards`, and only on the named `award_record_id` range. Treat every CSV as read-only. Do not change scripts, tests, configuration, schemas, generated files, or unrelated rows.
2. Read the award's official site and Wikipedia source listed in `AGENTS.md`; use direct source pages instead of general web search. For Gairdner, first complete `GAIRD-SRC-001`.
3. Confirm that the expected recipient, award year, prize, and category are represented. One person belongs in each row; a genuine team, institution, or collaboration remains one Organization row.
4. Inspect all 29 SQLite columns, but fill blank cells only. Never overwrite a nonblank value. If a nonblank value conflicts with a source, report the record ID, field, current value, proposed value, and source URL without editing it.
5. Retrieve only explicitly supported values: official source ID, laureate Wikidata QID, recipient type, birth details, citizenship, sex, affiliations, applicable death details, field/language, biographical note, remarks, category, motivation, or prize share. `award_wikidata_qid` and `prize_name` are already populated.
6. Leave uncertain or inapplicable cells blank. Do not infer prize share, death details for a living person, or personal data for an Organization.
7. Use ISO dates; city-only values in city fields; today's place and country names; and coordinates only after the named place has been verified.
8. Finish research before opening a write transaction. Keep the SQLite transaction short, update by exact `award_record_id`, and guard every filled field with its current blank value so concurrent work cannot overwrite data.
9. Preserve the table schema, row count, and every existing `award_record_id`. A split recipient gets a fresh ID after the current dataset maximum and MUST NOT renumber or delete another row.
10. Before committing the transaction, query every assigned row and confirm that only assigned blank cells changed. Roll back on any conflict or unexpected row count.
11. After committing, run `sqlite3 awards.sqlite3 "PRAGMA integrity_check;"` and require exactly `ok`. Confirm the assigned rows still exist and record any unresolved facts in the handoff.
12. Return a compact handoff: rows reviewed, cells filled, source URLs used, unresolved blanks, conflicts found but not edited, and integrity-check result.

Research tasks MAY run in parallel, including within one dataset, because record ranges do not overlap. SQLite writes MUST use short transactions; an agent MUST finish source research before acquiring the write lock.

## Abel Prize — 29 rows

Target: `awards.sqlite3`; source snapshot: `abel_prize.csv` (read-only).

Verify 29 missing source IDs; decide from sources whether category is inapplicable; review death status without filling living recipients. Birth and affiliation coordinates are already populated.

- [ ] `ABEL-001` — Verify and retrieve data for `abel_prize-000001` through `abel_prize-000005` (5 records).
- [ ] `ABEL-002` — Verify and retrieve data for `abel_prize-000006` through `abel_prize-000010` (5 records).
- [ ] `ABEL-003` — Verify and retrieve data for `abel_prize-000011` through `abel_prize-000015` (5 records).
- [ ] `ABEL-004` — Verify and retrieve data for `abel_prize-000016` through `abel_prize-000020` (5 records).
- [ ] `ABEL-005` — Verify and retrieve data for `abel_prize-000021` through `abel_prize-000025` (5 records).
- [ ] `ABEL-006` — Verify and retrieve data for `abel_prize-000026` through `abel_prize-000029` (4 records).

## Breakthrough Prize — 148 rows

Target: `awards.sqlite3`; source snapshot: `breakthrough.csv` (read-only).

Source-verify provisional person data; retrieve 148 source IDs; complete applicable birth, affiliation, death, and coordinate gaps. Existing malformed affiliation values are handled by QC tasks below and MUST NOT be overwritten in ordinary batches.

- [ ] `BREAK-001` — Verify and retrieve data for `breakthrough-000001` through `breakthrough-000005` (5 records).
- [ ] `BREAK-002` — Verify and retrieve data for `breakthrough-000006` through `breakthrough-000010` (5 records).
- [ ] `BREAK-003` — Verify and retrieve data for `breakthrough-000011` through `breakthrough-000015` (5 records).
- [ ] `BREAK-004` — Verify and retrieve data for `breakthrough-000016` through `breakthrough-000020` (5 records).
- [ ] `BREAK-005` — Verify and retrieve data for `breakthrough-000021` through `breakthrough-000025` (5 records).
- [ ] `BREAK-006` — Verify and retrieve data for `breakthrough-000026` through `breakthrough-000030` (5 records).
- [ ] `BREAK-007` — Verify and retrieve data for `breakthrough-000031` through `breakthrough-000035` (5 records).
- [ ] `BREAK-008` — Verify and retrieve data for `breakthrough-000036` through `breakthrough-000040` (5 records).
- [ ] `BREAK-009` — Verify and retrieve data for `breakthrough-000041` through `breakthrough-000045` (5 records).
- [ ] `BREAK-010` — Verify and retrieve data for `breakthrough-000046` through `breakthrough-000050` (5 records).
- [ ] `BREAK-011` — Verify and retrieve data for `breakthrough-000051` through `breakthrough-000055` (5 records).
- [ ] `BREAK-012` — Verify and retrieve data for `breakthrough-000056` through `breakthrough-000060` (5 records).
- [ ] `BREAK-013` — Verify and retrieve data for `breakthrough-000061` through `breakthrough-000065` (5 records).
- [ ] `BREAK-014` — Verify and retrieve data for `breakthrough-000066` through `breakthrough-000070` (5 records).
- [ ] `BREAK-015` — Verify and retrieve data for `breakthrough-000071` through `breakthrough-000075` (5 records).
- [ ] `BREAK-016` — Verify and retrieve data for `breakthrough-000076` through `breakthrough-000080` (5 records).
- [ ] `BREAK-017` — Verify and retrieve data for `breakthrough-000081` through `breakthrough-000085` (5 records).
- [ ] `BREAK-018` — Verify and retrieve data for `breakthrough-000086` through `breakthrough-000090` (5 records).
- [ ] `BREAK-019` — Verify and retrieve data for `breakthrough-000091` through `breakthrough-000095` (5 records).
- [ ] `BREAK-020` — Verify and retrieve data for `breakthrough-000096` through `breakthrough-000100` (5 records).
- [ ] `BREAK-021` — Verify and retrieve data for `breakthrough-000101` through `breakthrough-000105` (5 records).
- [ ] `BREAK-022` — Verify and retrieve data for `breakthrough-000106` through `breakthrough-000110` (5 records).
- [ ] `BREAK-023` — Verify and retrieve data for `breakthrough-000111` through `breakthrough-000115` (5 records).
- [ ] `BREAK-024` — Verify and retrieve data for `breakthrough-000116` through `breakthrough-000120` (5 records).
- [ ] `BREAK-025` — Verify and retrieve data for `breakthrough-000121` through `breakthrough-000125` (5 records).
- [ ] `BREAK-026` — Verify and retrieve data for `breakthrough-000126` through `breakthrough-000130` (5 records).
- [ ] `BREAK-027` — Verify and retrieve data for `breakthrough-000131` through `breakthrough-000135` (5 records).
- [ ] `BREAK-028` — Verify and retrieve data for `breakthrough-000136` through `breakthrough-000140` (5 records).
- [ ] `BREAK-029` — Verify and retrieve data for `breakthrough-000141` through `breakthrough-000145` (5 records).
- [ ] `BREAK-030` — Verify and retrieve data for `breakthrough-000146` through `breakthrough-000148` (3 records).

## Crafoord Prize — 82 rows

Target: `awards.sqlite3`; source snapshot: `crafoord.csv` (read-only).

Retrieve the 2 remaining source IDs, resolve the small birth-detail gaps, collect affiliations for all 82 rows, and add coordinates only after each place is verified.

- [ ] `CRAF-001` — Verify and retrieve data for `crafoord-000001` through `crafoord-000005` (5 records).
- [ ] `CRAF-002` — Verify and retrieve data for `crafoord-000006` through `crafoord-000010` (5 records).
- [ ] `CRAF-003` — Verify and retrieve data for `crafoord-000011` through `crafoord-000015` (5 records).
- [ ] `CRAF-004` — Verify and retrieve data for `crafoord-000016` through `crafoord-000020` (5 records).
- [ ] `CRAF-005` — Verify and retrieve data for `crafoord-000021` through `crafoord-000025` (5 records).
- [ ] `CRAF-006` — Verify and retrieve data for `crafoord-000026` through `crafoord-000030` (5 records).
- [ ] `CRAF-007` — Verify and retrieve data for `crafoord-000031` through `crafoord-000035` (5 records).
- [ ] `CRAF-008` — Verify and retrieve data for `crafoord-000036` through `crafoord-000040` (5 records).
- [ ] `CRAF-009` — Verify and retrieve data for `crafoord-000041` through `crafoord-000045` (5 records).
- [ ] `CRAF-010` — Verify and retrieve data for `crafoord-000046` through `crafoord-000050` (5 records).
- [ ] `CRAF-011` — Verify and retrieve data for `crafoord-000051` through `crafoord-000055` (5 records).
- [ ] `CRAF-012` — Verify and retrieve data for `crafoord-000056` through `crafoord-000060` (5 records).
- [ ] `CRAF-013` — Verify and retrieve data for `crafoord-000061` through `crafoord-000065` (5 records).
- [ ] `CRAF-014` — Verify and retrieve data for `crafoord-000066` through `crafoord-000070` (5 records).
- [ ] `CRAF-015` — Verify and retrieve data for `crafoord-000071` through `crafoord-000075` (5 records).
- [ ] `CRAF-016` — Verify and retrieve data for `crafoord-000076` through `crafoord-000080` (5 records).
- [ ] `CRAF-017` — Verify and retrieve data for `crafoord-000081` through `crafoord-000082` (2 records).

## Fields Medal — 68 rows

Target: `awards.sqlite3`; source snapshot: `fields.csv` (read-only).

Retrieve source IDs, separate affiliation cities from institution text where supported, verify whether category and motivation are inapplicable, and add verified coordinates. One malformed nonblank affiliation value is handled by QC-FIELDS-001.

- [ ] `FIELDS-001` — Verify and retrieve data for `fields-000001` through `fields-000005` (5 records).
- [ ] `FIELDS-002` — Verify and retrieve data for `fields-000006` through `fields-000010` (5 records).
- [ ] `FIELDS-003` — Verify and retrieve data for `fields-000011` through `fields-000015` (5 records).
- [ ] `FIELDS-004` — Verify and retrieve data for `fields-000016` through `fields-000020` (5 records).
- [ ] `FIELDS-005` — Verify and retrieve data for `fields-000021` through `fields-000025` (5 records).
- [ ] `FIELDS-006` — Verify and retrieve data for `fields-000026` through `fields-000030` (5 records).
- [ ] `FIELDS-007` — Verify and retrieve data for `fields-000031` through `fields-000035` (5 records).
- [ ] `FIELDS-008` — Verify and retrieve data for `fields-000036` through `fields-000040` (5 records).
- [ ] `FIELDS-009` — Verify and retrieve data for `fields-000041` through `fields-000045` (5 records).
- [ ] `FIELDS-010` — Verify and retrieve data for `fields-000046` through `fields-000050` (5 records).
- [ ] `FIELDS-011` — Verify and retrieve data for `fields-000051` through `fields-000055` (5 records).
- [ ] `FIELDS-012` — Verify and retrieve data for `fields-000056` through `fields-000060` (5 records).
- [ ] `FIELDS-013` — Verify and retrieve data for `fields-000061` through `fields-000065` (5 records).
- [ ] `FIELDS-014` — Verify and retrieve data for `fields-000066` through `fields-000068` (3 records).

## Canada Gairdner International Award — 387 rows

Target: `awards.sqlite3`; source snapshot: `gairdner_international_award.csv` (read-only).

New dataset omitted from the previous TODO. Verify the official roster and collect birth details, citizenship, affiliations, applicable death places, and verified coordinates. Preserve existing source IDs and biographical year hints.

Gairdner batches depend on `GAIRD-SRC-001` below.

- [ ] `GAIRD-001` — Verify and retrieve data for `gairdner_international_award-000001` through `gairdner_international_award-000005` (5 records).
- [ ] `GAIRD-002` — Verify and retrieve data for `gairdner_international_award-000006` through `gairdner_international_award-000010` (5 records).
- [ ] `GAIRD-003` — Verify and retrieve data for `gairdner_international_award-000011` through `gairdner_international_award-000015` (5 records).
- [ ] `GAIRD-004` — Verify and retrieve data for `gairdner_international_award-000016` through `gairdner_international_award-000020` (5 records).
- [ ] `GAIRD-005` — Verify and retrieve data for `gairdner_international_award-000021` through `gairdner_international_award-000025` (5 records).
- [ ] `GAIRD-006` — Verify and retrieve data for `gairdner_international_award-000026` through `gairdner_international_award-000030` (5 records).
- [ ] `GAIRD-007` — Verify and retrieve data for `gairdner_international_award-000031` through `gairdner_international_award-000035` (5 records).
- [ ] `GAIRD-008` — Verify and retrieve data for `gairdner_international_award-000036` through `gairdner_international_award-000040` (5 records).
- [ ] `GAIRD-009` — Verify and retrieve data for `gairdner_international_award-000041` through `gairdner_international_award-000045` (5 records).
- [ ] `GAIRD-010` — Verify and retrieve data for `gairdner_international_award-000046` through `gairdner_international_award-000050` (5 records).
- [ ] `GAIRD-011` — Verify and retrieve data for `gairdner_international_award-000051` through `gairdner_international_award-000055` (5 records).
- [ ] `GAIRD-012` — Verify and retrieve data for `gairdner_international_award-000056` through `gairdner_international_award-000060` (5 records).
- [ ] `GAIRD-013` — Verify and retrieve data for `gairdner_international_award-000061` through `gairdner_international_award-000065` (5 records).
- [ ] `GAIRD-014` — Verify and retrieve data for `gairdner_international_award-000066` through `gairdner_international_award-000070` (5 records).
- [ ] `GAIRD-015` — Verify and retrieve data for `gairdner_international_award-000071` through `gairdner_international_award-000075` (5 records).
- [ ] `GAIRD-016` — Verify and retrieve data for `gairdner_international_award-000076` through `gairdner_international_award-000080` (5 records).
- [ ] `GAIRD-017` — Verify and retrieve data for `gairdner_international_award-000081` through `gairdner_international_award-000085` (5 records).
- [ ] `GAIRD-018` — Verify and retrieve data for `gairdner_international_award-000086` through `gairdner_international_award-000090` (5 records).
- [ ] `GAIRD-019` — Verify and retrieve data for `gairdner_international_award-000091` through `gairdner_international_award-000095` (5 records).
- [ ] `GAIRD-020` — Verify and retrieve data for `gairdner_international_award-000096` through `gairdner_international_award-000100` (5 records).
- [ ] `GAIRD-021` — Verify and retrieve data for `gairdner_international_award-000101` through `gairdner_international_award-000105` (5 records).
- [ ] `GAIRD-022` — Verify and retrieve data for `gairdner_international_award-000106` through `gairdner_international_award-000110` (5 records).
- [ ] `GAIRD-023` — Verify and retrieve data for `gairdner_international_award-000111` through `gairdner_international_award-000115` (5 records).
- [ ] `GAIRD-024` — Verify and retrieve data for `gairdner_international_award-000116` through `gairdner_international_award-000120` (5 records).
- [ ] `GAIRD-025` — Verify and retrieve data for `gairdner_international_award-000121` through `gairdner_international_award-000125` (5 records).
- [ ] `GAIRD-026` — Verify and retrieve data for `gairdner_international_award-000126` through `gairdner_international_award-000130` (5 records).
- [ ] `GAIRD-027` — Verify and retrieve data for `gairdner_international_award-000131` through `gairdner_international_award-000135` (5 records).
- [ ] `GAIRD-028` — Verify and retrieve data for `gairdner_international_award-000136` through `gairdner_international_award-000140` (5 records).
- [ ] `GAIRD-029` — Verify and retrieve data for `gairdner_international_award-000141` through `gairdner_international_award-000145` (5 records).
- [ ] `GAIRD-030` — Verify and retrieve data for `gairdner_international_award-000146` through `gairdner_international_award-000150` (5 records).
- [ ] `GAIRD-031` — Verify and retrieve data for `gairdner_international_award-000151` through `gairdner_international_award-000155` (5 records).
- [ ] `GAIRD-032` — Verify and retrieve data for `gairdner_international_award-000156` through `gairdner_international_award-000160` (5 records).
- [ ] `GAIRD-033` — Verify and retrieve data for `gairdner_international_award-000161` through `gairdner_international_award-000165` (5 records).
- [ ] `GAIRD-034` — Verify and retrieve data for `gairdner_international_award-000166` through `gairdner_international_award-000170` (5 records).
- [ ] `GAIRD-035` — Verify and retrieve data for `gairdner_international_award-000171` through `gairdner_international_award-000175` (5 records).
- [ ] `GAIRD-036` — Verify and retrieve data for `gairdner_international_award-000176` through `gairdner_international_award-000180` (5 records).
- [ ] `GAIRD-037` — Verify and retrieve data for `gairdner_international_award-000181` through `gairdner_international_award-000185` (5 records).
- [ ] `GAIRD-038` — Verify and retrieve data for `gairdner_international_award-000186` through `gairdner_international_award-000190` (5 records).
- [ ] `GAIRD-039` — Verify and retrieve data for `gairdner_international_award-000191` through `gairdner_international_award-000195` (5 records).
- [ ] `GAIRD-040` — Verify and retrieve data for `gairdner_international_award-000196` through `gairdner_international_award-000200` (5 records).
- [ ] `GAIRD-041` — Verify and retrieve data for `gairdner_international_award-000201` through `gairdner_international_award-000205` (5 records).
- [ ] `GAIRD-042` — Verify and retrieve data for `gairdner_international_award-000206` through `gairdner_international_award-000210` (5 records).
- [ ] `GAIRD-043` — Verify and retrieve data for `gairdner_international_award-000211` through `gairdner_international_award-000215` (5 records).
- [ ] `GAIRD-044` — Verify and retrieve data for `gairdner_international_award-000216` through `gairdner_international_award-000220` (5 records).
- [ ] `GAIRD-045` — Verify and retrieve data for `gairdner_international_award-000221` through `gairdner_international_award-000225` (5 records).
- [ ] `GAIRD-046` — Verify and retrieve data for `gairdner_international_award-000226` through `gairdner_international_award-000230` (5 records).
- [ ] `GAIRD-047` — Verify and retrieve data for `gairdner_international_award-000231` through `gairdner_international_award-000235` (5 records).
- [ ] `GAIRD-048` — Verify and retrieve data for `gairdner_international_award-000236` through `gairdner_international_award-000240` (5 records).
- [ ] `GAIRD-049` — Verify and retrieve data for `gairdner_international_award-000241` through `gairdner_international_award-000245` (5 records).
- [ ] `GAIRD-050` — Verify and retrieve data for `gairdner_international_award-000246` through `gairdner_international_award-000250` (5 records).
- [ ] `GAIRD-051` — Verify and retrieve data for `gairdner_international_award-000251` through `gairdner_international_award-000255` (5 records).
- [ ] `GAIRD-052` — Verify and retrieve data for `gairdner_international_award-000256` through `gairdner_international_award-000260` (5 records).
- [ ] `GAIRD-053` — Verify and retrieve data for `gairdner_international_award-000261` through `gairdner_international_award-000265` (5 records).
- [ ] `GAIRD-054` — Verify and retrieve data for `gairdner_international_award-000266` through `gairdner_international_award-000270` (5 records).
- [ ] `GAIRD-055` — Verify and retrieve data for `gairdner_international_award-000271` through `gairdner_international_award-000275` (5 records).
- [ ] `GAIRD-056` — Verify and retrieve data for `gairdner_international_award-000276` through `gairdner_international_award-000280` (5 records).
- [ ] `GAIRD-057` — Verify and retrieve data for `gairdner_international_award-000281` through `gairdner_international_award-000285` (5 records).
- [ ] `GAIRD-058` — Verify and retrieve data for `gairdner_international_award-000286` through `gairdner_international_award-000290` (5 records).
- [ ] `GAIRD-059` — Verify and retrieve data for `gairdner_international_award-000291` through `gairdner_international_award-000295` (5 records).
- [ ] `GAIRD-060` — Verify and retrieve data for `gairdner_international_award-000296` through `gairdner_international_award-000300` (5 records).
- [ ] `GAIRD-061` — Verify and retrieve data for `gairdner_international_award-000301` through `gairdner_international_award-000305` (5 records).
- [ ] `GAIRD-062` — Verify and retrieve data for `gairdner_international_award-000306` through `gairdner_international_award-000310` (5 records).
- [ ] `GAIRD-063` — Verify and retrieve data for `gairdner_international_award-000311` through `gairdner_international_award-000315` (5 records).
- [ ] `GAIRD-064` — Verify and retrieve data for `gairdner_international_award-000316` through `gairdner_international_award-000320` (5 records).
- [ ] `GAIRD-065` — Verify and retrieve data for `gairdner_international_award-000321` through `gairdner_international_award-000325` (5 records).
- [ ] `GAIRD-066` — Verify and retrieve data for `gairdner_international_award-000326` through `gairdner_international_award-000330` (5 records).
- [ ] `GAIRD-067` — Verify and retrieve data for `gairdner_international_award-000331` through `gairdner_international_award-000335` (5 records).
- [ ] `GAIRD-068` — Verify and retrieve data for `gairdner_international_award-000336` through `gairdner_international_award-000340` (5 records).
- [ ] `GAIRD-069` — Verify and retrieve data for `gairdner_international_award-000341` through `gairdner_international_award-000345` (5 records).
- [ ] `GAIRD-070` — Verify and retrieve data for `gairdner_international_award-000346` through `gairdner_international_award-000350` (5 records).
- [ ] `GAIRD-071` — Verify and retrieve data for `gairdner_international_award-000351` through `gairdner_international_award-000355` (5 records).
- [ ] `GAIRD-072` — Verify and retrieve data for `gairdner_international_award-000356` through `gairdner_international_award-000360` (5 records).
- [ ] `GAIRD-073` — Verify and retrieve data for `gairdner_international_award-000361` through `gairdner_international_award-000365` (5 records).
- [ ] `GAIRD-074` — Verify and retrieve data for `gairdner_international_award-000366` through `gairdner_international_award-000370` (5 records).
- [ ] `GAIRD-075` — Verify and retrieve data for `gairdner_international_award-000371` through `gairdner_international_award-000375` (5 records).
- [ ] `GAIRD-076` — Verify and retrieve data for `gairdner_international_award-000376` through `gairdner_international_award-000380` (5 records).
- [ ] `GAIRD-077` — Verify and retrieve data for `gairdner_international_award-000381` through `gairdner_international_award-000385` (5 records).
- [ ] `GAIRD-078` — Verify and retrieve data for `gairdner_international_award-000386` through `gairdner_international_award-000387` (2 records).

## Japan Prize — 116 rows

Target: `awards.sqlite3`; source snapshot: `japan_prize.csv` (read-only).

Retrieve source IDs; resolve the bounded birth, sex, and affiliation-city gaps; determine category only from the official award source; and collect applicable death data and verified coordinates.

- [ ] `JAPAN-001` — Verify and retrieve data for `japan_prize-000001` through `japan_prize-000005` (5 records).
- [ ] `JAPAN-002` — Verify and retrieve data for `japan_prize-000006` through `japan_prize-000010` (5 records).
- [ ] `JAPAN-003` — Verify and retrieve data for `japan_prize-000011` through `japan_prize-000015` (5 records).
- [ ] `JAPAN-004` — Verify and retrieve data for `japan_prize-000016` through `japan_prize-000020` (5 records).
- [ ] `JAPAN-005` — Verify and retrieve data for `japan_prize-000021` through `japan_prize-000025` (5 records).
- [ ] `JAPAN-006` — Verify and retrieve data for `japan_prize-000026` through `japan_prize-000030` (5 records).
- [ ] `JAPAN-007` — Verify and retrieve data for `japan_prize-000031` through `japan_prize-000035` (5 records).
- [ ] `JAPAN-008` — Verify and retrieve data for `japan_prize-000036` through `japan_prize-000040` (5 records).
- [ ] `JAPAN-009` — Verify and retrieve data for `japan_prize-000041` through `japan_prize-000045` (5 records).
- [ ] `JAPAN-010` — Verify and retrieve data for `japan_prize-000046` through `japan_prize-000050` (5 records).
- [ ] `JAPAN-011` — Verify and retrieve data for `japan_prize-000051` through `japan_prize-000055` (5 records).
- [ ] `JAPAN-012` — Verify and retrieve data for `japan_prize-000056` through `japan_prize-000060` (5 records).
- [ ] `JAPAN-013` — Verify and retrieve data for `japan_prize-000061` through `japan_prize-000065` (5 records).
- [ ] `JAPAN-014` — Verify and retrieve data for `japan_prize-000066` through `japan_prize-000070` (5 records).
- [ ] `JAPAN-015` — Verify and retrieve data for `japan_prize-000071` through `japan_prize-000075` (5 records).
- [ ] `JAPAN-016` — Verify and retrieve data for `japan_prize-000076` through `japan_prize-000080` (5 records).
- [ ] `JAPAN-017` — Verify and retrieve data for `japan_prize-000081` through `japan_prize-000085` (5 records).
- [ ] `JAPAN-018` — Verify and retrieve data for `japan_prize-000086` through `japan_prize-000090` (5 records).
- [ ] `JAPAN-019` — Verify and retrieve data for `japan_prize-000091` through `japan_prize-000095` (5 records).
- [ ] `JAPAN-020` — Verify and retrieve data for `japan_prize-000096` through `japan_prize-000100` (5 records).
- [ ] `JAPAN-021` — Verify and retrieve data for `japan_prize-000101` through `japan_prize-000105` (5 records).
- [ ] `JAPAN-022` — Verify and retrieve data for `japan_prize-000106` through `japan_prize-000110` (5 records).
- [ ] `JAPAN-023` — Verify and retrieve data for `japan_prize-000111` through `japan_prize-000115` (5 records).
- [ ] `JAPAN-024` — Verify and retrieve data for `japan_prize-000116` through `japan_prize-000116` (1 record).

## Kyoto Prize — 129 rows

Target: `awards.sqlite3`; source snapshot: `kyoto_prize.csv` (read-only).

Retrieve source IDs; finish remaining birth and affiliation details; review death status; and add verified birth and affiliation coordinates.

- [ ] `KYOTO-001` — Verify and retrieve data for `kyoto_prize-000001` through `kyoto_prize-000005` (5 records).
- [ ] `KYOTO-002` — Verify and retrieve data for `kyoto_prize-000006` through `kyoto_prize-000010` (5 records).
- [ ] `KYOTO-003` — Verify and retrieve data for `kyoto_prize-000011` through `kyoto_prize-000015` (5 records).
- [ ] `KYOTO-004` — Verify and retrieve data for `kyoto_prize-000016` through `kyoto_prize-000020` (5 records).
- [ ] `KYOTO-005` — Verify and retrieve data for `kyoto_prize-000021` through `kyoto_prize-000025` (5 records).
- [ ] `KYOTO-006` — Verify and retrieve data for `kyoto_prize-000026` through `kyoto_prize-000030` (5 records).
- [ ] `KYOTO-007` — Verify and retrieve data for `kyoto_prize-000031` through `kyoto_prize-000035` (5 records).
- [ ] `KYOTO-008` — Verify and retrieve data for `kyoto_prize-000036` through `kyoto_prize-000040` (5 records).
- [ ] `KYOTO-009` — Verify and retrieve data for `kyoto_prize-000041` through `kyoto_prize-000045` (5 records).
- [ ] `KYOTO-010` — Verify and retrieve data for `kyoto_prize-000046` through `kyoto_prize-000050` (5 records).
- [ ] `KYOTO-011` — Verify and retrieve data for `kyoto_prize-000051` through `kyoto_prize-000055` (5 records).
- [ ] `KYOTO-012` — Verify and retrieve data for `kyoto_prize-000056` through `kyoto_prize-000060` (5 records).
- [ ] `KYOTO-013` — Verify and retrieve data for `kyoto_prize-000061` through `kyoto_prize-000065` (5 records).
- [ ] `KYOTO-014` — Verify and retrieve data for `kyoto_prize-000066` through `kyoto_prize-000070` (5 records).
- [ ] `KYOTO-015` — Verify and retrieve data for `kyoto_prize-000071` through `kyoto_prize-000075` (5 records).
- [ ] `KYOTO-016` — Verify and retrieve data for `kyoto_prize-000076` through `kyoto_prize-000080` (5 records).
- [ ] `KYOTO-017` — Verify and retrieve data for `kyoto_prize-000081` through `kyoto_prize-000085` (5 records).
- [ ] `KYOTO-018` — Verify and retrieve data for `kyoto_prize-000086` through `kyoto_prize-000090` (5 records).
- [ ] `KYOTO-019` — Verify and retrieve data for `kyoto_prize-000091` through `kyoto_prize-000095` (5 records).
- [ ] `KYOTO-020` — Verify and retrieve data for `kyoto_prize-000096` through `kyoto_prize-000100` (5 records).
- [ ] `KYOTO-021` — Verify and retrieve data for `kyoto_prize-000101` through `kyoto_prize-000105` (5 records).
- [ ] `KYOTO-022` — Verify and retrieve data for `kyoto_prize-000106` through `kyoto_prize-000110` (5 records).
- [ ] `KYOTO-023` — Verify and retrieve data for `kyoto_prize-000111` through `kyoto_prize-000115` (5 records).
- [ ] `KYOTO-024` — Verify and retrieve data for `kyoto_prize-000116` through `kyoto_prize-000120` (5 records).
- [ ] `KYOTO-025` — Verify and retrieve data for `kyoto_prize-000121` through `kyoto_prize-000125` (5 records).
- [ ] `KYOTO-026` — Verify and retrieve data for `kyoto_prize-000126` through `kyoto_prize-000129` (4 records).

## Lasker Awards — 423 rows

Target: `awards.sqlite3`; source snapshot: `lasker_awards.csv` (read-only).

Source-verify provisional person and death data; retrieve source IDs; collect affiliations for all 423 rows; resolve remaining birth details; and add verified coordinates.

- [ ] `LASKER-001` — Verify and retrieve data for `lasker_awards-000001` through `lasker_awards-000005` (5 records).
- [ ] `LASKER-002` — Verify and retrieve data for `lasker_awards-000006` through `lasker_awards-000010` (5 records).
- [ ] `LASKER-003` — Verify and retrieve data for `lasker_awards-000011` through `lasker_awards-000015` (5 records).
- [ ] `LASKER-004` — Verify and retrieve data for `lasker_awards-000016` through `lasker_awards-000020` (5 records).
- [ ] `LASKER-005` — Verify and retrieve data for `lasker_awards-000021` through `lasker_awards-000025` (5 records).
- [ ] `LASKER-006` — Verify and retrieve data for `lasker_awards-000026` through `lasker_awards-000030` (5 records).
- [ ] `LASKER-007` — Verify and retrieve data for `lasker_awards-000031` through `lasker_awards-000035` (5 records).
- [ ] `LASKER-008` — Verify and retrieve data for `lasker_awards-000036` through `lasker_awards-000040` (5 records).
- [ ] `LASKER-009` — Verify and retrieve data for `lasker_awards-000041` through `lasker_awards-000045` (5 records).
- [ ] `LASKER-010` — Verify and retrieve data for `lasker_awards-000046` through `lasker_awards-000050` (5 records).
- [ ] `LASKER-011` — Verify and retrieve data for `lasker_awards-000051` through `lasker_awards-000055` (5 records).
- [ ] `LASKER-012` — Verify and retrieve data for `lasker_awards-000056` through `lasker_awards-000060` (5 records).
- [ ] `LASKER-013` — Verify and retrieve data for `lasker_awards-000061` through `lasker_awards-000065` (5 records).
- [ ] `LASKER-014` — Verify and retrieve data for `lasker_awards-000066` through `lasker_awards-000070` (5 records).
- [ ] `LASKER-015` — Verify and retrieve data for `lasker_awards-000071` through `lasker_awards-000075` (5 records).
- [ ] `LASKER-016` — Verify and retrieve data for `lasker_awards-000076` through `lasker_awards-000080` (5 records).
- [ ] `LASKER-017` — Verify and retrieve data for `lasker_awards-000081` through `lasker_awards-000085` (5 records).
- [ ] `LASKER-018` — Verify and retrieve data for `lasker_awards-000086` through `lasker_awards-000090` (5 records).
- [ ] `LASKER-019` — Verify and retrieve data for `lasker_awards-000091` through `lasker_awards-000095` (5 records).
- [ ] `LASKER-020` — Verify and retrieve data for `lasker_awards-000096` through `lasker_awards-000100` (5 records).
- [ ] `LASKER-021` — Verify and retrieve data for `lasker_awards-000101` through `lasker_awards-000105` (5 records).
- [ ] `LASKER-022` — Verify and retrieve data for `lasker_awards-000106` through `lasker_awards-000110` (5 records).
- [ ] `LASKER-023` — Verify and retrieve data for `lasker_awards-000111` through `lasker_awards-000115` (5 records).
- [ ] `LASKER-024` — Verify and retrieve data for `lasker_awards-000116` through `lasker_awards-000120` (5 records).
- [ ] `LASKER-025` — Verify and retrieve data for `lasker_awards-000121` through `lasker_awards-000125` (5 records).
- [ ] `LASKER-026` — Verify and retrieve data for `lasker_awards-000126` through `lasker_awards-000130` (5 records).
- [ ] `LASKER-027` — Verify and retrieve data for `lasker_awards-000131` through `lasker_awards-000135` (5 records).
- [ ] `LASKER-028` — Verify and retrieve data for `lasker_awards-000136` through `lasker_awards-000140` (5 records).
- [ ] `LASKER-029` — Verify and retrieve data for `lasker_awards-000141` through `lasker_awards-000145` (5 records).
- [ ] `LASKER-030` — Verify and retrieve data for `lasker_awards-000146` through `lasker_awards-000150` (5 records).
- [ ] `LASKER-031` — Verify and retrieve data for `lasker_awards-000151` through `lasker_awards-000155` (5 records).
- [ ] `LASKER-032` — Verify and retrieve data for `lasker_awards-000156` through `lasker_awards-000160` (5 records).
- [ ] `LASKER-033` — Verify and retrieve data for `lasker_awards-000161` through `lasker_awards-000165` (5 records).
- [ ] `LASKER-034` — Verify and retrieve data for `lasker_awards-000166` through `lasker_awards-000170` (5 records).
- [ ] `LASKER-035` — Verify and retrieve data for `lasker_awards-000171` through `lasker_awards-000175` (5 records).
- [ ] `LASKER-036` — Verify and retrieve data for `lasker_awards-000176` through `lasker_awards-000180` (5 records).
- [ ] `LASKER-037` — Verify and retrieve data for `lasker_awards-000181` through `lasker_awards-000185` (5 records).
- [ ] `LASKER-038` — Verify and retrieve data for `lasker_awards-000186` through `lasker_awards-000190` (5 records).
- [ ] `LASKER-039` — Verify and retrieve data for `lasker_awards-000191` through `lasker_awards-000195` (5 records).
- [ ] `LASKER-040` — Verify and retrieve data for `lasker_awards-000196` through `lasker_awards-000200` (5 records).
- [ ] `LASKER-041` — Verify and retrieve data for `lasker_awards-000201` through `lasker_awards-000205` (5 records).
- [ ] `LASKER-042` — Verify and retrieve data for `lasker_awards-000206` through `lasker_awards-000210` (5 records).
- [ ] `LASKER-043` — Verify and retrieve data for `lasker_awards-000211` through `lasker_awards-000215` (5 records).
- [ ] `LASKER-044` — Verify and retrieve data for `lasker_awards-000216` through `lasker_awards-000220` (5 records).
- [ ] `LASKER-045` — Verify and retrieve data for `lasker_awards-000221` through `lasker_awards-000225` (5 records).
- [ ] `LASKER-046` — Verify and retrieve data for `lasker_awards-000226` through `lasker_awards-000230` (5 records).
- [ ] `LASKER-047` — Verify and retrieve data for `lasker_awards-000231` through `lasker_awards-000235` (5 records).
- [ ] `LASKER-048` — Verify and retrieve data for `lasker_awards-000236` through `lasker_awards-000240` (5 records).
- [ ] `LASKER-049` — Verify and retrieve data for `lasker_awards-000241` through `lasker_awards-000245` (5 records).
- [ ] `LASKER-050` — Verify and retrieve data for `lasker_awards-000246` through `lasker_awards-000250` (5 records).
- [ ] `LASKER-051` — Verify and retrieve data for `lasker_awards-000251` through `lasker_awards-000255` (5 records).
- [ ] `LASKER-052` — Verify and retrieve data for `lasker_awards-000256` through `lasker_awards-000260` (5 records).
- [ ] `LASKER-053` — Verify and retrieve data for `lasker_awards-000261` through `lasker_awards-000265` (5 records).
- [ ] `LASKER-054` — Verify and retrieve data for `lasker_awards-000266` through `lasker_awards-000270` (5 records).
- [ ] `LASKER-055` — Verify and retrieve data for `lasker_awards-000271` through `lasker_awards-000275` (5 records).
- [ ] `LASKER-056` — Verify and retrieve data for `lasker_awards-000276` through `lasker_awards-000280` (5 records).
- [ ] `LASKER-057` — Verify and retrieve data for `lasker_awards-000281` through `lasker_awards-000285` (5 records).
- [ ] `LASKER-058` — Verify and retrieve data for `lasker_awards-000286` through `lasker_awards-000290` (5 records).
- [ ] `LASKER-059` — Verify and retrieve data for `lasker_awards-000291` through `lasker_awards-000295` (5 records).
- [ ] `LASKER-060` — Verify and retrieve data for `lasker_awards-000296` through `lasker_awards-000300` (5 records).
- [ ] `LASKER-061` — Verify and retrieve data for `lasker_awards-000301` through `lasker_awards-000305` (5 records).
- [ ] `LASKER-062` — Verify and retrieve data for `lasker_awards-000306` through `lasker_awards-000310` (5 records).
- [ ] `LASKER-063` — Verify and retrieve data for `lasker_awards-000311` through `lasker_awards-000315` (5 records).
- [ ] `LASKER-064` — Verify and retrieve data for `lasker_awards-000316` through `lasker_awards-000320` (5 records).
- [ ] `LASKER-065` — Verify and retrieve data for `lasker_awards-000321` through `lasker_awards-000325` (5 records).
- [ ] `LASKER-066` — Verify and retrieve data for `lasker_awards-000326` through `lasker_awards-000330` (5 records).
- [ ] `LASKER-067` — Verify and retrieve data for `lasker_awards-000331` through `lasker_awards-000335` (5 records).
- [ ] `LASKER-068` — Verify and retrieve data for `lasker_awards-000336` through `lasker_awards-000340` (5 records).
- [ ] `LASKER-069` — Verify and retrieve data for `lasker_awards-000341` through `lasker_awards-000345` (5 records).
- [ ] `LASKER-070` — Verify and retrieve data for `lasker_awards-000346` through `lasker_awards-000350` (5 records).
- [ ] `LASKER-071` — Verify and retrieve data for `lasker_awards-000351` through `lasker_awards-000355` (5 records).
- [ ] `LASKER-072` — Verify and retrieve data for `lasker_awards-000356` through `lasker_awards-000360` (5 records).
- [ ] `LASKER-073` — Verify and retrieve data for `lasker_awards-000361` through `lasker_awards-000365` (5 records).
- [ ] `LASKER-074` — Verify and retrieve data for `lasker_awards-000366` through `lasker_awards-000370` (5 records).
- [ ] `LASKER-075` — Verify and retrieve data for `lasker_awards-000371` through `lasker_awards-000375` (5 records).
- [ ] `LASKER-076` — Verify and retrieve data for `lasker_awards-000376` through `lasker_awards-000380` (5 records).
- [ ] `LASKER-077` — Verify and retrieve data for `lasker_awards-000381` through `lasker_awards-000385` (5 records).
- [ ] `LASKER-078` — Verify and retrieve data for `lasker_awards-000386` through `lasker_awards-000390` (5 records).
- [ ] `LASKER-079` — Verify and retrieve data for `lasker_awards-000391` through `lasker_awards-000395` (5 records).
- [ ] `LASKER-080` — Verify and retrieve data for `lasker_awards-000396` through `lasker_awards-000400` (5 records).
- [ ] `LASKER-081` — Verify and retrieve data for `lasker_awards-000401` through `lasker_awards-000405` (5 records).
- [ ] `LASKER-082` — Verify and retrieve data for `lasker_awards-000406` through `lasker_awards-000410` (5 records).
- [ ] `LASKER-083` — Verify and retrieve data for `lasker_awards-000411` through `lasker_awards-000415` (5 records).
- [ ] `LASKER-084` — Verify and retrieve data for `lasker_awards-000416` through `lasker_awards-000420` (5 records).
- [ ] `LASKER-085` — Verify and retrieve data for `lasker_awards-000421` through `lasker_awards-000423` (3 records).

## Max Planck Medal — 90 rows

Target: `awards.sqlite3`; source snapshot: `max_planck_medal.csv` (read-only).

Retrieve source IDs and 64 missing official citations; resolve birth and affiliation gaps; verify category applicability; review death status; and add verified coordinates.

- [ ] `MAXP-001` — Verify and retrieve data for `max_planck_medal-000001` through `max_planck_medal-000005` (5 records).
- [ ] `MAXP-002` — Verify and retrieve data for `max_planck_medal-000006` through `max_planck_medal-000010` (5 records).
- [ ] `MAXP-003` — Verify and retrieve data for `max_planck_medal-000011` through `max_planck_medal-000015` (5 records).
- [ ] `MAXP-004` — Verify and retrieve data for `max_planck_medal-000016` through `max_planck_medal-000020` (5 records).
- [ ] `MAXP-005` — Verify and retrieve data for `max_planck_medal-000021` through `max_planck_medal-000025` (5 records).
- [ ] `MAXP-006` — Verify and retrieve data for `max_planck_medal-000026` through `max_planck_medal-000030` (5 records).
- [ ] `MAXP-007` — Verify and retrieve data for `max_planck_medal-000031` through `max_planck_medal-000035` (5 records).
- [ ] `MAXP-008` — Verify and retrieve data for `max_planck_medal-000036` through `max_planck_medal-000040` (5 records).
- [ ] `MAXP-009` — Verify and retrieve data for `max_planck_medal-000041` through `max_planck_medal-000045` (5 records).
- [ ] `MAXP-010` — Verify and retrieve data for `max_planck_medal-000046` through `max_planck_medal-000050` (5 records).
- [ ] `MAXP-011` — Verify and retrieve data for `max_planck_medal-000051` through `max_planck_medal-000055` (5 records).
- [ ] `MAXP-012` — Verify and retrieve data for `max_planck_medal-000056` through `max_planck_medal-000060` (5 records).
- [ ] `MAXP-013` — Verify and retrieve data for `max_planck_medal-000061` through `max_planck_medal-000065` (5 records).
- [ ] `MAXP-014` — Verify and retrieve data for `max_planck_medal-000066` through `max_planck_medal-000070` (5 records).
- [ ] `MAXP-015` — Verify and retrieve data for `max_planck_medal-000071` through `max_planck_medal-000075` (5 records).
- [ ] `MAXP-016` — Verify and retrieve data for `max_planck_medal-000076` through `max_planck_medal-000080` (5 records).
- [ ] `MAXP-017` — Verify and retrieve data for `max_planck_medal-000081` through `max_planck_medal-000085` (5 records).
- [ ] `MAXP-018` — Verify and retrieve data for `max_planck_medal-000086` through `max_planck_medal-000090` (5 records).

## Nobel Prize — 1026 rows

Target: `awards.sqlite3`; source snapshot: `nobel.csv` (read-only).

Collect citizenship and coordinates for all rows where applicable; resolve 88 missing motivations, 31 birth-date/country gaps, about 268 affiliation gaps, applicable death-place gaps, and 400 field/language gaps. Organizations carry no personal data.

- [ ] `NOBEL-001` — Verify and retrieve data for `nobel-000001` through `nobel-000005` (5 records).
- [ ] `NOBEL-002` — Verify and retrieve data for `nobel-000006` through `nobel-000010` (5 records).
- [ ] `NOBEL-003` — Verify and retrieve data for `nobel-000011` through `nobel-000015` (5 records).
- [ ] `NOBEL-004` — Verify and retrieve data for `nobel-000016` through `nobel-000020` (5 records).
- [ ] `NOBEL-005` — Verify and retrieve data for `nobel-000021` through `nobel-000025` (5 records).
- [ ] `NOBEL-006` — Verify and retrieve data for `nobel-000026` through `nobel-000030` (5 records).
- [ ] `NOBEL-007` — Verify and retrieve data for `nobel-000031` through `nobel-000035` (5 records).
- [ ] `NOBEL-008` — Verify and retrieve data for `nobel-000036` through `nobel-000040` (5 records).
- [ ] `NOBEL-009` — Verify and retrieve data for `nobel-000041` through `nobel-000045` (5 records).
- [ ] `NOBEL-010` — Verify and retrieve data for `nobel-000046` through `nobel-000050` (5 records).
- [ ] `NOBEL-011` — Verify and retrieve data for `nobel-000051` through `nobel-000055` (5 records).
- [ ] `NOBEL-012` — Verify and retrieve data for `nobel-000056` through `nobel-000060` (5 records).
- [ ] `NOBEL-013` — Verify and retrieve data for `nobel-000061` through `nobel-000065` (5 records).
- [ ] `NOBEL-014` — Verify and retrieve data for `nobel-000066` through `nobel-000070` (5 records).
- [ ] `NOBEL-015` — Verify and retrieve data for `nobel-000071` through `nobel-000075` (5 records).
- [ ] `NOBEL-016` — Verify and retrieve data for `nobel-000076` through `nobel-000080` (5 records).
- [ ] `NOBEL-017` — Verify and retrieve data for `nobel-000081` through `nobel-000085` (5 records).
- [ ] `NOBEL-018` — Verify and retrieve data for `nobel-000086` through `nobel-000090` (5 records).
- [ ] `NOBEL-019` — Verify and retrieve data for `nobel-000091` through `nobel-000095` (5 records).
- [ ] `NOBEL-020` — Verify and retrieve data for `nobel-000096` through `nobel-000100` (5 records).
- [ ] `NOBEL-021` — Verify and retrieve data for `nobel-000101` through `nobel-000105` (5 records).
- [ ] `NOBEL-022` — Verify and retrieve data for `nobel-000106` through `nobel-000110` (5 records).
- [ ] `NOBEL-023` — Verify and retrieve data for `nobel-000111` through `nobel-000115` (5 records).
- [ ] `NOBEL-024` — Verify and retrieve data for `nobel-000116` through `nobel-000120` (5 records).
- [ ] `NOBEL-025` — Verify and retrieve data for `nobel-000121` through `nobel-000125` (5 records).
- [ ] `NOBEL-026` — Verify and retrieve data for `nobel-000126` through `nobel-000130` (5 records).
- [ ] `NOBEL-027` — Verify and retrieve data for `nobel-000131` through `nobel-000135` (5 records).
- [ ] `NOBEL-028` — Verify and retrieve data for `nobel-000136` through `nobel-000140` (5 records).
- [ ] `NOBEL-029` — Verify and retrieve data for `nobel-000141` through `nobel-000145` (5 records).
- [ ] `NOBEL-030` — Verify and retrieve data for `nobel-000146` through `nobel-000150` (5 records).
- [ ] `NOBEL-031` — Verify and retrieve data for `nobel-000151` through `nobel-000155` (5 records).
- [ ] `NOBEL-032` — Verify and retrieve data for `nobel-000156` through `nobel-000160` (5 records).
- [ ] `NOBEL-033` — Verify and retrieve data for `nobel-000161` through `nobel-000165` (5 records).
- [ ] `NOBEL-034` — Verify and retrieve data for `nobel-000166` through `nobel-000170` (5 records).
- [ ] `NOBEL-035` — Verify and retrieve data for `nobel-000171` through `nobel-000175` (5 records).
- [ ] `NOBEL-036` — Verify and retrieve data for `nobel-000176` through `nobel-000180` (5 records).
- [ ] `NOBEL-037` — Verify and retrieve data for `nobel-000181` through `nobel-000185` (5 records).
- [ ] `NOBEL-038` — Verify and retrieve data for `nobel-000186` through `nobel-000190` (5 records).
- [ ] `NOBEL-039` — Verify and retrieve data for `nobel-000191` through `nobel-000195` (5 records).
- [ ] `NOBEL-040` — Verify and retrieve data for `nobel-000196` through `nobel-000200` (5 records).
- [ ] `NOBEL-041` — Verify and retrieve data for `nobel-000201` through `nobel-000205` (5 records).
- [ ] `NOBEL-042` — Verify and retrieve data for `nobel-000206` through `nobel-000210` (5 records).
- [ ] `NOBEL-043` — Verify and retrieve data for `nobel-000211` through `nobel-000215` (5 records).
- [ ] `NOBEL-044` — Verify and retrieve data for `nobel-000216` through `nobel-000220` (5 records).
- [ ] `NOBEL-045` — Verify and retrieve data for `nobel-000221` through `nobel-000225` (5 records).
- [ ] `NOBEL-046` — Verify and retrieve data for `nobel-000226` through `nobel-000230` (5 records).
- [ ] `NOBEL-047` — Verify and retrieve data for `nobel-000231` through `nobel-000235` (5 records).
- [ ] `NOBEL-048` — Verify and retrieve data for `nobel-000236` through `nobel-000240` (5 records).
- [ ] `NOBEL-049` — Verify and retrieve data for `nobel-000241` through `nobel-000245` (5 records).
- [ ] `NOBEL-050` — Verify and retrieve data for `nobel-000246` through `nobel-000250` (5 records).
- [ ] `NOBEL-051` — Verify and retrieve data for `nobel-000251` through `nobel-000255` (5 records).
- [ ] `NOBEL-052` — Verify and retrieve data for `nobel-000256` through `nobel-000260` (5 records).
- [ ] `NOBEL-053` — Verify and retrieve data for `nobel-000261` through `nobel-000265` (5 records).
- [ ] `NOBEL-054` — Verify and retrieve data for `nobel-000266` through `nobel-000270` (5 records).
- [ ] `NOBEL-055` — Verify and retrieve data for `nobel-000271` through `nobel-000275` (5 records).
- [ ] `NOBEL-056` — Verify and retrieve data for `nobel-000276` through `nobel-000280` (5 records).
- [ ] `NOBEL-057` — Verify and retrieve data for `nobel-000281` through `nobel-000285` (5 records).
- [ ] `NOBEL-058` — Verify and retrieve data for `nobel-000286` through `nobel-000290` (5 records).
- [ ] `NOBEL-059` — Verify and retrieve data for `nobel-000291` through `nobel-000295` (5 records).
- [ ] `NOBEL-060` — Verify and retrieve data for `nobel-000296` through `nobel-000300` (5 records).
- [ ] `NOBEL-061` — Verify and retrieve data for `nobel-000301` through `nobel-000305` (5 records).
- [ ] `NOBEL-062` — Verify and retrieve data for `nobel-000306` through `nobel-000310` (5 records).
- [ ] `NOBEL-063` — Verify and retrieve data for `nobel-000311` through `nobel-000315` (5 records).
- [ ] `NOBEL-064` — Verify and retrieve data for `nobel-000316` through `nobel-000320` (5 records).
- [ ] `NOBEL-065` — Verify and retrieve data for `nobel-000321` through `nobel-000325` (5 records).
- [ ] `NOBEL-066` — Verify and retrieve data for `nobel-000326` through `nobel-000330` (5 records).
- [ ] `NOBEL-067` — Verify and retrieve data for `nobel-000331` through `nobel-000335` (5 records).
- [ ] `NOBEL-068` — Verify and retrieve data for `nobel-000336` through `nobel-000340` (5 records).
- [ ] `NOBEL-069` — Verify and retrieve data for `nobel-000341` through `nobel-000345` (5 records).
- [ ] `NOBEL-070` — Verify and retrieve data for `nobel-000346` through `nobel-000350` (5 records).
- [ ] `NOBEL-071` — Verify and retrieve data for `nobel-000351` through `nobel-000355` (5 records).
- [ ] `NOBEL-072` — Verify and retrieve data for `nobel-000356` through `nobel-000360` (5 records).
- [ ] `NOBEL-073` — Verify and retrieve data for `nobel-000361` through `nobel-000365` (5 records).
- [ ] `NOBEL-074` — Verify and retrieve data for `nobel-000366` through `nobel-000370` (5 records).
- [ ] `NOBEL-075` — Verify and retrieve data for `nobel-000371` through `nobel-000375` (5 records).
- [ ] `NOBEL-076` — Verify and retrieve data for `nobel-000376` through `nobel-000380` (5 records).
- [ ] `NOBEL-077` — Verify and retrieve data for `nobel-000381` through `nobel-000385` (5 records).
- [ ] `NOBEL-078` — Verify and retrieve data for `nobel-000386` through `nobel-000390` (5 records).
- [ ] `NOBEL-079` — Verify and retrieve data for `nobel-000391` through `nobel-000395` (5 records).
- [ ] `NOBEL-080` — Verify and retrieve data for `nobel-000396` through `nobel-000400` (5 records).
- [ ] `NOBEL-081` — Verify and retrieve data for `nobel-000401` through `nobel-000405` (5 records).
- [ ] `NOBEL-082` — Verify and retrieve data for `nobel-000406` through `nobel-000410` (5 records).
- [ ] `NOBEL-083` — Verify and retrieve data for `nobel-000411` through `nobel-000415` (5 records).
- [ ] `NOBEL-084` — Verify and retrieve data for `nobel-000416` through `nobel-000420` (5 records).
- [ ] `NOBEL-085` — Verify and retrieve data for `nobel-000421` through `nobel-000425` (5 records).
- [ ] `NOBEL-086` — Verify and retrieve data for `nobel-000426` through `nobel-000430` (5 records).
- [ ] `NOBEL-087` — Verify and retrieve data for `nobel-000431` through `nobel-000435` (5 records).
- [ ] `NOBEL-088` — Verify and retrieve data for `nobel-000436` through `nobel-000440` (5 records).
- [ ] `NOBEL-089` — Verify and retrieve data for `nobel-000441` through `nobel-000445` (5 records).
- [ ] `NOBEL-090` — Verify and retrieve data for `nobel-000446` through `nobel-000450` (5 records).
- [ ] `NOBEL-091` — Verify and retrieve data for `nobel-000451` through `nobel-000455` (5 records).
- [ ] `NOBEL-092` — Verify and retrieve data for `nobel-000456` through `nobel-000460` (5 records).
- [ ] `NOBEL-093` — Verify and retrieve data for `nobel-000461` through `nobel-000465` (5 records).
- [ ] `NOBEL-094` — Verify and retrieve data for `nobel-000466` through `nobel-000470` (5 records).
- [ ] `NOBEL-095` — Verify and retrieve data for `nobel-000471` through `nobel-000475` (5 records).
- [ ] `NOBEL-096` — Verify and retrieve data for `nobel-000476` through `nobel-000480` (5 records).
- [ ] `NOBEL-097` — Verify and retrieve data for `nobel-000481` through `nobel-000485` (5 records).
- [ ] `NOBEL-098` — Verify and retrieve data for `nobel-000486` through `nobel-000490` (5 records).
- [ ] `NOBEL-099` — Verify and retrieve data for `nobel-000491` through `nobel-000495` (5 records).
- [ ] `NOBEL-100` — Verify and retrieve data for `nobel-000496` through `nobel-000500` (5 records).
- [ ] `NOBEL-101` — Verify and retrieve data for `nobel-000501` through `nobel-000505` (5 records).
- [ ] `NOBEL-102` — Verify and retrieve data for `nobel-000506` through `nobel-000510` (5 records).
- [ ] `NOBEL-103` — Verify and retrieve data for `nobel-000511` through `nobel-000515` (5 records).
- [ ] `NOBEL-104` — Verify and retrieve data for `nobel-000516` through `nobel-000520` (5 records).
- [ ] `NOBEL-105` — Verify and retrieve data for `nobel-000521` through `nobel-000525` (5 records).
- [ ] `NOBEL-106` — Verify and retrieve data for `nobel-000526` through `nobel-000530` (5 records).
- [ ] `NOBEL-107` — Verify and retrieve data for `nobel-000531` through `nobel-000535` (5 records).
- [ ] `NOBEL-108` — Verify and retrieve data for `nobel-000536` through `nobel-000540` (5 records).
- [ ] `NOBEL-109` — Verify and retrieve data for `nobel-000541` through `nobel-000545` (5 records).
- [ ] `NOBEL-110` — Verify and retrieve data for `nobel-000546` through `nobel-000550` (5 records).
- [ ] `NOBEL-111` — Verify and retrieve data for `nobel-000551` through `nobel-000555` (5 records).
- [ ] `NOBEL-112` — Verify and retrieve data for `nobel-000556` through `nobel-000560` (5 records).
- [ ] `NOBEL-113` — Verify and retrieve data for `nobel-000561` through `nobel-000565` (5 records).
- [ ] `NOBEL-114` — Verify and retrieve data for `nobel-000566` through `nobel-000570` (5 records).
- [ ] `NOBEL-115` — Verify and retrieve data for `nobel-000571` through `nobel-000575` (5 records).
- [ ] `NOBEL-116` — Verify and retrieve data for `nobel-000576` through `nobel-000580` (5 records).
- [ ] `NOBEL-117` — Verify and retrieve data for `nobel-000581` through `nobel-000585` (5 records).
- [ ] `NOBEL-118` — Verify and retrieve data for `nobel-000586` through `nobel-000590` (5 records).
- [ ] `NOBEL-119` — Verify and retrieve data for `nobel-000591` through `nobel-000595` (5 records).
- [ ] `NOBEL-120` — Verify and retrieve data for `nobel-000596` through `nobel-000600` (5 records).
- [ ] `NOBEL-121` — Verify and retrieve data for `nobel-000601` through `nobel-000605` (5 records).
- [ ] `NOBEL-122` — Verify and retrieve data for `nobel-000606` through `nobel-000610` (5 records).
- [ ] `NOBEL-123` — Verify and retrieve data for `nobel-000611` through `nobel-000615` (5 records).
- [ ] `NOBEL-124` — Verify and retrieve data for `nobel-000616` through `nobel-000620` (5 records).
- [ ] `NOBEL-125` — Verify and retrieve data for `nobel-000621` through `nobel-000625` (5 records).
- [ ] `NOBEL-126` — Verify and retrieve data for `nobel-000626` through `nobel-000630` (5 records).
- [ ] `NOBEL-127` — Verify and retrieve data for `nobel-000631` through `nobel-000635` (5 records).
- [ ] `NOBEL-128` — Verify and retrieve data for `nobel-000636` through `nobel-000640` (5 records).
- [ ] `NOBEL-129` — Verify and retrieve data for `nobel-000641` through `nobel-000645` (5 records).
- [ ] `NOBEL-130` — Verify and retrieve data for `nobel-000646` through `nobel-000650` (5 records).
- [ ] `NOBEL-131` — Verify and retrieve data for `nobel-000651` through `nobel-000655` (5 records).
- [ ] `NOBEL-132` — Verify and retrieve data for `nobel-000656` through `nobel-000660` (5 records).
- [ ] `NOBEL-133` — Verify and retrieve data for `nobel-000661` through `nobel-000665` (5 records).
- [ ] `NOBEL-134` — Verify and retrieve data for `nobel-000666` through `nobel-000670` (5 records).
- [ ] `NOBEL-135` — Verify and retrieve data for `nobel-000671` through `nobel-000675` (5 records).
- [ ] `NOBEL-136` — Verify and retrieve data for `nobel-000676` through `nobel-000680` (5 records).
- [ ] `NOBEL-137` — Verify and retrieve data for `nobel-000681` through `nobel-000685` (5 records).
- [ ] `NOBEL-138` — Verify and retrieve data for `nobel-000686` through `nobel-000690` (5 records).
- [ ] `NOBEL-139` — Verify and retrieve data for `nobel-000691` through `nobel-000695` (5 records).
- [ ] `NOBEL-140` — Verify and retrieve data for `nobel-000696` through `nobel-000700` (5 records).
- [ ] `NOBEL-141` — Verify and retrieve data for `nobel-000701` through `nobel-000705` (5 records).
- [ ] `NOBEL-142` — Verify and retrieve data for `nobel-000706` through `nobel-000710` (5 records).
- [ ] `NOBEL-143` — Verify and retrieve data for `nobel-000711` through `nobel-000715` (5 records).
- [ ] `NOBEL-144` — Verify and retrieve data for `nobel-000716` through `nobel-000720` (5 records).
- [ ] `NOBEL-145` — Verify and retrieve data for `nobel-000721` through `nobel-000725` (5 records).
- [ ] `NOBEL-146` — Verify and retrieve data for `nobel-000726` through `nobel-000730` (5 records).
- [ ] `NOBEL-147` — Verify and retrieve data for `nobel-000731` through `nobel-000735` (5 records).
- [ ] `NOBEL-148` — Verify and retrieve data for `nobel-000736` through `nobel-000740` (5 records).
- [ ] `NOBEL-149` — Verify and retrieve data for `nobel-000741` through `nobel-000745` (5 records).
- [ ] `NOBEL-150` — Verify and retrieve data for `nobel-000746` through `nobel-000750` (5 records).
- [ ] `NOBEL-151` — Verify and retrieve data for `nobel-000751` through `nobel-000755` (5 records).
- [ ] `NOBEL-152` — Verify and retrieve data for `nobel-000756` through `nobel-000760` (5 records).
- [ ] `NOBEL-153` — Verify and retrieve data for `nobel-000761` through `nobel-000765` (5 records).
- [ ] `NOBEL-154` — Verify and retrieve data for `nobel-000766` through `nobel-000770` (5 records).
- [ ] `NOBEL-155` — Verify and retrieve data for `nobel-000771` through `nobel-000775` (5 records).
- [ ] `NOBEL-156` — Verify and retrieve data for `nobel-000776` through `nobel-000780` (5 records).
- [ ] `NOBEL-157` — Verify and retrieve data for `nobel-000781` through `nobel-000785` (5 records).
- [ ] `NOBEL-158` — Verify and retrieve data for `nobel-000786` through `nobel-000790` (5 records).
- [ ] `NOBEL-159` — Verify and retrieve data for `nobel-000791` through `nobel-000795` (5 records).
- [ ] `NOBEL-160` — Verify and retrieve data for `nobel-000796` through `nobel-000800` (5 records).
- [ ] `NOBEL-161` — Verify and retrieve data for `nobel-000801` through `nobel-000805` (5 records).
- [ ] `NOBEL-162` — Verify and retrieve data for `nobel-000806` through `nobel-000810` (5 records).
- [ ] `NOBEL-163` — Verify and retrieve data for `nobel-000811` through `nobel-000815` (5 records).
- [ ] `NOBEL-164` — Verify and retrieve data for `nobel-000816` through `nobel-000820` (5 records).
- [ ] `NOBEL-165` — Verify and retrieve data for `nobel-000821` through `nobel-000825` (5 records).
- [ ] `NOBEL-166` — Verify and retrieve data for `nobel-000826` through `nobel-000830` (5 records).
- [ ] `NOBEL-167` — Verify and retrieve data for `nobel-000831` through `nobel-000835` (5 records).
- [ ] `NOBEL-168` — Verify and retrieve data for `nobel-000836` through `nobel-000840` (5 records).
- [ ] `NOBEL-169` — Verify and retrieve data for `nobel-000841` through `nobel-000845` (5 records).
- [ ] `NOBEL-170` — Verify and retrieve data for `nobel-000846` through `nobel-000850` (5 records).
- [ ] `NOBEL-171` — Verify and retrieve data for `nobel-000851` through `nobel-000855` (5 records).
- [ ] `NOBEL-172` — Verify and retrieve data for `nobel-000856` through `nobel-000860` (5 records).
- [ ] `NOBEL-173` — Verify and retrieve data for `nobel-000861` through `nobel-000865` (5 records).
- [ ] `NOBEL-174` — Verify and retrieve data for `nobel-000866` through `nobel-000870` (5 records).
- [ ] `NOBEL-175` — Verify and retrieve data for `nobel-000871` through `nobel-000875` (5 records).
- [ ] `NOBEL-176` — Verify and retrieve data for `nobel-000876` through `nobel-000880` (5 records).
- [ ] `NOBEL-177` — Verify and retrieve data for `nobel-000881` through `nobel-000885` (5 records).
- [ ] `NOBEL-178` — Verify and retrieve data for `nobel-000886` through `nobel-000890` (5 records).
- [ ] `NOBEL-179` — Verify and retrieve data for `nobel-000891` through `nobel-000895` (5 records).
- [ ] `NOBEL-180` — Verify and retrieve data for `nobel-000896` through `nobel-000900` (5 records).
- [ ] `NOBEL-181` — Verify and retrieve data for `nobel-000901` through `nobel-000905` (5 records).
- [ ] `NOBEL-182` — Verify and retrieve data for `nobel-000906` through `nobel-000910` (5 records).
- [ ] `NOBEL-183` — Verify and retrieve data for `nobel-000911` through `nobel-000915` (5 records).
- [ ] `NOBEL-184` — Verify and retrieve data for `nobel-000916` through `nobel-000920` (5 records).
- [ ] `NOBEL-185` — Verify and retrieve data for `nobel-000921` through `nobel-000925` (5 records).
- [ ] `NOBEL-186` — Verify and retrieve data for `nobel-000926` through `nobel-000930` (5 records).
- [ ] `NOBEL-187` — Verify and retrieve data for `nobel-000931` through `nobel-000935` (5 records).
- [ ] `NOBEL-188` — Verify and retrieve data for `nobel-000936` through `nobel-000940` (5 records).
- [ ] `NOBEL-189` — Verify and retrieve data for `nobel-000941` through `nobel-000945` (5 records).
- [ ] `NOBEL-190` — Verify and retrieve data for `nobel-000946` through `nobel-000950` (5 records).
- [ ] `NOBEL-191` — Verify and retrieve data for `nobel-000951` through `nobel-000955` (5 records).
- [ ] `NOBEL-192` — Verify and retrieve data for `nobel-000956` through `nobel-000960` (5 records).
- [ ] `NOBEL-193` — Verify and retrieve data for `nobel-000961` through `nobel-000965` (5 records).
- [ ] `NOBEL-194` — Verify and retrieve data for `nobel-000966` through `nobel-000970` (5 records).
- [ ] `NOBEL-195` — Verify and retrieve data for `nobel-000971` through `nobel-000975` (5 records).
- [ ] `NOBEL-196` — Verify and retrieve data for `nobel-000976` through `nobel-000980` (5 records).
- [ ] `NOBEL-197` — Verify and retrieve data for `nobel-000981` through `nobel-000985` (5 records).
- [ ] `NOBEL-198` — Verify and retrieve data for `nobel-000986` through `nobel-000990` (5 records).
- [ ] `NOBEL-199` — Verify and retrieve data for `nobel-000991` through `nobel-000995` (5 records).
- [ ] `NOBEL-200` — Verify and retrieve data for `nobel-000996` through `nobel-001000` (5 records).
- [ ] `NOBEL-201` — Verify and retrieve data for `nobel-001001` through `nobel-001005` (5 records).
- [ ] `NOBEL-202` — Verify and retrieve data for `nobel-001006` through `nobel-001010` (5 records).
- [ ] `NOBEL-203` — Verify and retrieve data for `nobel-001011` through `nobel-001015` (5 records).
- [ ] `NOBEL-204` — Verify and retrieve data for `nobel-001016` through `nobel-001020` (5 records).
- [ ] `NOBEL-205` — Verify and retrieve data for `nobel-001021` through `nobel-001025` (5 records).
- [ ] `NOBEL-206` — Verify and retrieve data for `nobel-001026` through `nobel-001026` (1 record).

## Shaw Prize — 121 rows

Target: `awards.sqlite3`; source snapshot: `shaw_prize.csv` (read-only).

Retrieve 87 missing source IDs; complete recipient birth, sex, affiliation, and applicable death details; move official category information only when explicitly supported; and add verified coordinates.

- [ ] `SHAW-001` — Verify and retrieve data for `shaw_prize-000001` through `shaw_prize-000005` (5 records).
- [ ] `SHAW-002` — Verify and retrieve data for `shaw_prize-000006` through `shaw_prize-000010` (5 records).
- [ ] `SHAW-003` — Verify and retrieve data for `shaw_prize-000011` through `shaw_prize-000015` (5 records).
- [ ] `SHAW-004` — Verify and retrieve data for `shaw_prize-000016` through `shaw_prize-000020` (5 records).
- [ ] `SHAW-005` — Verify and retrieve data for `shaw_prize-000021` through `shaw_prize-000025` (5 records).
- [ ] `SHAW-006` — Verify and retrieve data for `shaw_prize-000026` through `shaw_prize-000030` (5 records).
- [ ] `SHAW-007` — Verify and retrieve data for `shaw_prize-000031` through `shaw_prize-000035` (5 records).
- [ ] `SHAW-008` — Verify and retrieve data for `shaw_prize-000036` through `shaw_prize-000040` (5 records).
- [ ] `SHAW-009` — Verify and retrieve data for `shaw_prize-000041` through `shaw_prize-000045` (5 records).
- [ ] `SHAW-010` — Verify and retrieve data for `shaw_prize-000046` through `shaw_prize-000050` (5 records).
- [ ] `SHAW-011` — Verify and retrieve data for `shaw_prize-000051` through `shaw_prize-000055` (5 records).
- [ ] `SHAW-012` — Verify and retrieve data for `shaw_prize-000056` through `shaw_prize-000060` (5 records).
- [ ] `SHAW-013` — Verify and retrieve data for `shaw_prize-000061` through `shaw_prize-000065` (5 records).
- [ ] `SHAW-014` — Verify and retrieve data for `shaw_prize-000066` through `shaw_prize-000070` (5 records).
- [ ] `SHAW-015` — Verify and retrieve data for `shaw_prize-000071` through `shaw_prize-000075` (5 records).
- [ ] `SHAW-016` — Verify and retrieve data for `shaw_prize-000076` through `shaw_prize-000080` (5 records).
- [ ] `SHAW-017` — Verify and retrieve data for `shaw_prize-000081` through `shaw_prize-000085` (5 records).
- [ ] `SHAW-018` — Verify and retrieve data for `shaw_prize-000086` through `shaw_prize-000090` (5 records).
- [ ] `SHAW-019` — Verify and retrieve data for `shaw_prize-000091` through `shaw_prize-000095` (5 records).
- [ ] `SHAW-020` — Verify and retrieve data for `shaw_prize-000096` through `shaw_prize-000100` (5 records).
- [ ] `SHAW-021` — Verify and retrieve data for `shaw_prize-000101` through `shaw_prize-000105` (5 records).
- [ ] `SHAW-022` — Verify and retrieve data for `shaw_prize-000106` through `shaw_prize-000110` (5 records).
- [ ] `SHAW-023` — Verify and retrieve data for `shaw_prize-000111` through `shaw_prize-000115` (5 records).
- [ ] `SHAW-024` — Verify and retrieve data for `shaw_prize-000116` through `shaw_prize-000120` (5 records).
- [ ] `SHAW-025` — Verify and retrieve data for `shaw_prize-000121` through `shaw_prize-000121` (1 record).

## Turing Award — 81 rows

Target: `awards.sqlite3`; source snapshot: `turing_award.csv` (read-only).

Retrieve source IDs; resolve the one remaining birth-city gap and applicable death-place gaps; verify category applicability; and add verified coordinates.

- [ ] `TURING-001` — Verify and retrieve data for `turing_award-000001` through `turing_award-000005` (5 records).
- [ ] `TURING-002` — Verify and retrieve data for `turing_award-000006` through `turing_award-000010` (5 records).
- [ ] `TURING-003` — Verify and retrieve data for `turing_award-000011` through `turing_award-000015` (5 records).
- [ ] `TURING-004` — Verify and retrieve data for `turing_award-000016` through `turing_award-000020` (5 records).
- [ ] `TURING-005` — Verify and retrieve data for `turing_award-000021` through `turing_award-000025` (5 records).
- [ ] `TURING-006` — Verify and retrieve data for `turing_award-000026` through `turing_award-000030` (5 records).
- [ ] `TURING-007` — Verify and retrieve data for `turing_award-000031` through `turing_award-000035` (5 records).
- [ ] `TURING-008` — Verify and retrieve data for `turing_award-000036` through `turing_award-000040` (5 records).
- [ ] `TURING-009` — Verify and retrieve data for `turing_award-000041` through `turing_award-000045` (5 records).
- [ ] `TURING-010` — Verify and retrieve data for `turing_award-000046` through `turing_award-000050` (5 records).
- [ ] `TURING-011` — Verify and retrieve data for `turing_award-000051` through `turing_award-000055` (5 records).
- [ ] `TURING-012` — Verify and retrieve data for `turing_award-000056` through `turing_award-000060` (5 records).
- [ ] `TURING-013` — Verify and retrieve data for `turing_award-000061` through `turing_award-000065` (5 records).
- [ ] `TURING-014` — Verify and retrieve data for `turing_award-000066` through `turing_award-000070` (5 records).
- [ ] `TURING-015` — Verify and retrieve data for `turing_award-000071` through `turing_award-000075` (5 records).
- [ ] `TURING-016` — Verify and retrieve data for `turing_award-000076` through `turing_award-000080` (5 records).
- [ ] `TURING-017` — Verify and retrieve data for `turing_award-000081` through `turing_award-000081` (1 record).

## Wolf Prize — 391 rows

Target: `awards.sqlite3`; source snapshot: `wolf_prize.csv` (read-only).

Retrieve source IDs; complete birth and affiliation data for the remaining categories, especially the 269 affiliation gaps; review applicable death details; add verified coordinates; and preserve meaningful YYYY/YYYY year labels.

- [ ] `WOLF-001` — Verify and retrieve data for `wolf_prize-000001` through `wolf_prize-000005` (5 records).
- [ ] `WOLF-002` — Verify and retrieve data for `wolf_prize-000006` through `wolf_prize-000010` (5 records).
- [ ] `WOLF-003` — Verify and retrieve data for `wolf_prize-000011` through `wolf_prize-000015` (5 records).
- [ ] `WOLF-004` — Verify and retrieve data for `wolf_prize-000016` through `wolf_prize-000020` (5 records).
- [ ] `WOLF-005` — Verify and retrieve data for `wolf_prize-000021` through `wolf_prize-000025` (5 records).
- [ ] `WOLF-006` — Verify and retrieve data for `wolf_prize-000026` through `wolf_prize-000030` (5 records).
- [ ] `WOLF-007` — Verify and retrieve data for `wolf_prize-000031` through `wolf_prize-000035` (5 records).
- [ ] `WOLF-008` — Verify and retrieve data for `wolf_prize-000036` through `wolf_prize-000040` (5 records).
- [ ] `WOLF-009` — Verify and retrieve data for `wolf_prize-000041` through `wolf_prize-000045` (5 records).
- [ ] `WOLF-010` — Verify and retrieve data for `wolf_prize-000046` through `wolf_prize-000050` (5 records).
- [ ] `WOLF-011` — Verify and retrieve data for `wolf_prize-000051` through `wolf_prize-000055` (5 records).
- [ ] `WOLF-012` — Verify and retrieve data for `wolf_prize-000056` through `wolf_prize-000060` (5 records).
- [ ] `WOLF-013` — Verify and retrieve data for `wolf_prize-000061` through `wolf_prize-000065` (5 records).
- [ ] `WOLF-014` — Verify and retrieve data for `wolf_prize-000066` through `wolf_prize-000070` (5 records).
- [ ] `WOLF-015` — Verify and retrieve data for `wolf_prize-000071` through `wolf_prize-000075` (5 records).
- [ ] `WOLF-016` — Verify and retrieve data for `wolf_prize-000076` through `wolf_prize-000080` (5 records).
- [ ] `WOLF-017` — Verify and retrieve data for `wolf_prize-000081` through `wolf_prize-000085` (5 records).
- [ ] `WOLF-018` — Verify and retrieve data for `wolf_prize-000086` through `wolf_prize-000090` (5 records).
- [ ] `WOLF-019` — Verify and retrieve data for `wolf_prize-000091` through `wolf_prize-000095` (5 records).
- [ ] `WOLF-020` — Verify and retrieve data for `wolf_prize-000096` through `wolf_prize-000100` (5 records).
- [ ] `WOLF-021` — Verify and retrieve data for `wolf_prize-000101` through `wolf_prize-000105` (5 records).
- [ ] `WOLF-022` — Verify and retrieve data for `wolf_prize-000106` through `wolf_prize-000110` (5 records).
- [ ] `WOLF-023` — Verify and retrieve data for `wolf_prize-000111` through `wolf_prize-000115` (5 records).
- [ ] `WOLF-024` — Verify and retrieve data for `wolf_prize-000116` through `wolf_prize-000120` (5 records).
- [ ] `WOLF-025` — Verify and retrieve data for `wolf_prize-000121` through `wolf_prize-000125` (5 records).
- [ ] `WOLF-026` — Verify and retrieve data for `wolf_prize-000126` through `wolf_prize-000130` (5 records).
- [ ] `WOLF-027` — Verify and retrieve data for `wolf_prize-000131` through `wolf_prize-000135` (5 records).
- [ ] `WOLF-028` — Verify and retrieve data for `wolf_prize-000136` through `wolf_prize-000140` (5 records).
- [ ] `WOLF-029` — Verify and retrieve data for `wolf_prize-000141` through `wolf_prize-000145` (5 records).
- [ ] `WOLF-030` — Verify and retrieve data for `wolf_prize-000146` through `wolf_prize-000150` (5 records).
- [ ] `WOLF-031` — Verify and retrieve data for `wolf_prize-000151` through `wolf_prize-000155` (5 records).
- [ ] `WOLF-032` — Verify and retrieve data for `wolf_prize-000156` through `wolf_prize-000160` (5 records).
- [ ] `WOLF-033` — Verify and retrieve data for `wolf_prize-000161` through `wolf_prize-000165` (5 records).
- [ ] `WOLF-034` — Verify and retrieve data for `wolf_prize-000166` through `wolf_prize-000170` (5 records).
- [ ] `WOLF-035` — Verify and retrieve data for `wolf_prize-000171` through `wolf_prize-000175` (5 records).
- [ ] `WOLF-036` — Verify and retrieve data for `wolf_prize-000176` through `wolf_prize-000180` (5 records).
- [ ] `WOLF-037` — Verify and retrieve data for `wolf_prize-000181` through `wolf_prize-000185` (5 records).
- [ ] `WOLF-038` — Verify and retrieve data for `wolf_prize-000186` through `wolf_prize-000190` (5 records).
- [ ] `WOLF-039` — Verify and retrieve data for `wolf_prize-000191` through `wolf_prize-000195` (5 records).
- [ ] `WOLF-040` — Verify and retrieve data for `wolf_prize-000196` through `wolf_prize-000200` (5 records).
- [ ] `WOLF-041` — Verify and retrieve data for `wolf_prize-000201` through `wolf_prize-000205` (5 records).
- [ ] `WOLF-042` — Verify and retrieve data for `wolf_prize-000206` through `wolf_prize-000210` (5 records).
- [ ] `WOLF-043` — Verify and retrieve data for `wolf_prize-000211` through `wolf_prize-000215` (5 records).
- [ ] `WOLF-044` — Verify and retrieve data for `wolf_prize-000216` through `wolf_prize-000220` (5 records).
- [ ] `WOLF-045` — Verify and retrieve data for `wolf_prize-000221` through `wolf_prize-000225` (5 records).
- [ ] `WOLF-046` — Verify and retrieve data for `wolf_prize-000226` through `wolf_prize-000230` (5 records).
- [ ] `WOLF-047` — Verify and retrieve data for `wolf_prize-000231` through `wolf_prize-000235` (5 records).
- [ ] `WOLF-048` — Verify and retrieve data for `wolf_prize-000236` through `wolf_prize-000240` (5 records).
- [ ] `WOLF-049` — Verify and retrieve data for `wolf_prize-000241` through `wolf_prize-000245` (5 records).
- [ ] `WOLF-050` — Verify and retrieve data for `wolf_prize-000246` through `wolf_prize-000250` (5 records).
- [ ] `WOLF-051` — Verify and retrieve data for `wolf_prize-000251` through `wolf_prize-000255` (5 records).
- [ ] `WOLF-052` — Verify and retrieve data for `wolf_prize-000256` through `wolf_prize-000260` (5 records).
- [ ] `WOLF-053` — Verify and retrieve data for `wolf_prize-000261` through `wolf_prize-000265` (5 records).
- [ ] `WOLF-054` — Verify and retrieve data for `wolf_prize-000266` through `wolf_prize-000270` (5 records).
- [ ] `WOLF-055` — Verify and retrieve data for `wolf_prize-000271` through `wolf_prize-000275` (5 records).
- [ ] `WOLF-056` — Verify and retrieve data for `wolf_prize-000276` through `wolf_prize-000280` (5 records).
- [ ] `WOLF-057` — Verify and retrieve data for `wolf_prize-000281` through `wolf_prize-000285` (5 records).
- [ ] `WOLF-058` — Verify and retrieve data for `wolf_prize-000286` through `wolf_prize-000290` (5 records).
- [ ] `WOLF-059` — Verify and retrieve data for `wolf_prize-000291` through `wolf_prize-000295` (5 records).
- [ ] `WOLF-060` — Verify and retrieve data for `wolf_prize-000296` through `wolf_prize-000300` (5 records).
- [ ] `WOLF-061` — Verify and retrieve data for `wolf_prize-000301` through `wolf_prize-000305` (5 records).
- [ ] `WOLF-062` — Verify and retrieve data for `wolf_prize-000306` through `wolf_prize-000310` (5 records).
- [ ] `WOLF-063` — Verify and retrieve data for `wolf_prize-000311` through `wolf_prize-000315` (5 records).
- [ ] `WOLF-064` — Verify and retrieve data for `wolf_prize-000316` through `wolf_prize-000320` (5 records).
- [ ] `WOLF-065` — Verify and retrieve data for `wolf_prize-000321` through `wolf_prize-000325` (5 records).
- [ ] `WOLF-066` — Verify and retrieve data for `wolf_prize-000326` through `wolf_prize-000330` (5 records).
- [ ] `WOLF-067` — Verify and retrieve data for `wolf_prize-000331` through `wolf_prize-000335` (5 records).
- [ ] `WOLF-068` — Verify and retrieve data for `wolf_prize-000336` through `wolf_prize-000340` (5 records).
- [ ] `WOLF-069` — Verify and retrieve data for `wolf_prize-000341` through `wolf_prize-000345` (5 records).
- [ ] `WOLF-070` — Verify and retrieve data for `wolf_prize-000346` through `wolf_prize-000350` (5 records).
- [ ] `WOLF-071` — Verify and retrieve data for `wolf_prize-000351` through `wolf_prize-000355` (5 records).
- [ ] `WOLF-072` — Verify and retrieve data for `wolf_prize-000356` through `wolf_prize-000360` (5 records).
- [ ] `WOLF-073` — Verify and retrieve data for `wolf_prize-000361` through `wolf_prize-000365` (5 records).
- [ ] `WOLF-074` — Verify and retrieve data for `wolf_prize-000366` through `wolf_prize-000370` (5 records).
- [ ] `WOLF-075` — Verify and retrieve data for `wolf_prize-000371` through `wolf_prize-000375` (5 records).
- [ ] `WOLF-076` — Verify and retrieve data for `wolf_prize-000376` through `wolf_prize-000380` (5 records).
- [ ] `WOLF-077` — Verify and retrieve data for `wolf_prize-000381` through `wolf_prize-000385` (5 records).
- [ ] `WOLF-078` — Verify and retrieve data for `wolf_prize-000386` through `wolf_prize-000390` (5 records).
- [ ] `WOLF-079` — Verify and retrieve data for `wolf_prize-000391` through `wolf_prize-000391` (1 record).

## Priority verification tasks

The Breakthrough affiliation locations below were cleared after malformed mappings were detected and may be filled only from verified sources. Any remaining nonblank conflict is report-only and MUST NOT be overwritten.

- [ ] `QC-BREAK-001` — Verify the correct affiliation name/city/country mapping for `breakthrough-000020`, `breakthrough-000031`, `breakthrough-000034`, `breakthrough-000050`, and `breakthrough-000067`; report exact corrections and source URLs.
- [ ] `QC-BREAK-002` — Verify the correct affiliation name/city/country mapping for `breakthrough-000076`, `breakthrough-000080`, `breakthrough-000125`, `breakthrough-000126`, and `breakthrough-000130`; report exact corrections and source URLs.
- [ ] `QC-BREAK-003` — Verify the correct affiliation name/city/country mapping for `breakthrough-000138` and `breakthrough-000139`; report exact corrections and source URLs.
- [ ] `QC-FIELDS-001` — Verify the correct affiliation city for `fields-000004`; report the exact correction and source URL.
- [ ] `GAIRD-SRC-001` — Identify and verify the authoritative Gairdner winner list/profile source and the relevant Wikipedia list page; report stable direct URLs and confirm how existing `source_laureate_id` values map to official profiles.

## Maintainer-only follow-up

Do not assign these to data retrieval agents.

- [ ] `MAINT-000` — Before the first agent write, create an outside-worktree backup of `awards.sqlite3`, record its SHA-256 and row count, and prevent the CSV importer from being rerun during enrichment.
- [ ] `MAINT-001` — Review reported nonblank conflicts and authorize explicit corrections before any correction is made.
- [ ] `MAINT-002` — Add verified Gairdner source URLs to `AGENTS.md` after `GAIRD-SRC-001`.
- [ ] `MAINT-003` — Recompute the SQLite blank-cell census after each dataset's final batch and update that dataset's focus paragraph.
- [ ] `MAINT-004` — Decide whether to keep, ignore, or remove the untracked cache JSON files and `scripts/__pycache__`.
- [ ] `MAINT-005` — Review the untracked `tests/`, `datasets/trash/`, and repository-level `trash/` separately; do not delete them without confirming ownership.
- [ ] `MAINT-006` — Run final SQLite validation: 29-column schema, expected row count, stable/unique IDs, QID formats, ISO dates, valid laureate types, organization-person rules, and `PRAGMA integrity_check`.
- [ ] `MAINT-007` — Review and complete the Git workflow. The work is still on `feat/canonical-csv-schema`; no remote or local `202607` branch is currently configured.
- [ ] `MAINT-008` — Decide how enriched SQLite data will be versioned or exported. The database is currently Git-ignored, so agent changes are not preserved by Git automatically.

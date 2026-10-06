# Nobel medicine 2026 — database update

Added three records to `datasets/awards.sqlite3` on 2026-10-06. Existing records were preserved.

| Record | Recipient | Official source ID | Wikidata |
|---|---|---|---|
| nobel-001027 | Karl Deisseroth | 1061 | Q935993 |
| nobel-001028 | Peter Hegemann | 1062 | Q2075526 |
| nobel-001029 | Georg Nagel | 1063 | Q1247068 |

Sources retrieved directly from the official Nobel API:

- https://api.nobelprize.org/2.1/nobelPrizes?nobelPrizeYear=2026&nobelPrizeCategory=med
- https://api.nobelprize.org/2/laureate/1061
- https://api.nobelprize.org/2/laureate/1062
- https://api.nobelprize.org/2/laureate/1063

The award endpoint confirms the 2026 award, announcement date 2026-10-05, names, official IDs, one-third shares, and motivation.
Each laureate endpoint explicitly provides the recorded Wikidata identity, birth date, birthplace, and sex. These claims have high confidence from the official source.
Boston, MA / USA was normalized to Boston / United States. Category `Medicine` and award-family QID `Q7191` follow existing Nobel records.

At initial insertion, affiliations and coordinates were left blank pending separate verification. The API names Howard Hughes Medical Institute and Stanford University for Deisseroth,
Humboldt University of Berlin for Hegemann, and University of Würzburg for Nagel. Institution QIDs and coordinates were not verified in this update.
Other unsupported fields remain blank. No citizenship was inferred from birthplace.

Existing Lasker records contain conflicting birth details: `lasker_awards-000396` has Deisseroth's birth date as 1975, and `lasker_awards-000397` has Hegemann's birthplace as Ludwigshafen.
Those records were not changed. The new records use the Nobel API dates and places, which agree with other existing award records.

Backup: `datasets/awards.sqlite3.20261006-medicine.bak`.
One immediate transaction rejected duplicate 2026 medicine records or existing Nobel source IDs, inserted exactly three rows, and compared every existing award row with the backup before committing.
Readback matched the intended records. Both database and backup returned `ok` from `PRAGMA integrity_check`.
The documented `scripts/check_coordinates.sql` is absent from this checkout; no coordinates were added.
`uv run scripts/validate_awards.py --database <database> --detail 200` produced identical reports for the backup and updated database.
Both exited 1 on the same pre-existing failures: 57 institution-facts-disagree groups and 2 coords-shared-across-cities groups. No validator findings were introduced.

## Affiliation links and regeneration

Linked the existing institutions on 2026-10-06 following the curator's instruction:

| Record | Position | Institution | QID | City | Country | Coordinates |
|---|---|---|---|---|---|---|
| nobel-001027 | 1 | Stanford University | Q41506 | Stanford | United States | -122.1700,37.4275 |
| nobel-001027 | 2 | Howard Hughes Medical Institute | Q1512226 | blank | United States | blank |
| nobel-001028 | 1 | Humboldt University of Berlin | Q152087 | Berlin | Germany | 13.3933,52.5181 |
| nobel-001029 | 1 | University of Würzburg | Q161976 | Würzburg | Germany | 9.9353,49.7881 |

The Nobel laureate endpoints above supply the affiliations at the award date. Wikidata `wbgetentities` confirmed each institution's English Wikipedia title and identity.
`lookup_coordinates.py` confirmed Q41506, Q152087, and Q161976; sequential Nominatim reverse lookups confirmed the countries and university locations.
Stanford's existing point is on the same campus as Wikidata's current -122.1703,37.4275 point, approximately 26 metres away; Nominatim resolves it to Jane Stanford Way, Stanford.
Humboldt and Würzburg match the retrieved Wikidata coordinates exactly at four decimals.
Institution identity sources: https://www.wikidata.org/wiki/Q41506, https://www.wikidata.org/wiki/Q1512226, https://www.wikidata.org/wiki/Q152087, https://www.wikidata.org/wiki/Q161976.

Nobel supplies only USA for HHMI. Its city and coordinates remain blank rather than assigning its headquarters or another award's location to Deisseroth.
The extra affiliation was added to `award_extra_affiliations.tsv` and loaded with the existing loader, after its dry run and a complete TSV/database comparison.
The pre-load TSV matched all 94 existing extra affiliations. The loader wrote 95 rows; all 94 existing rows remain unchanged.

Pre-link backup: `datasets/awards.sqlite3.20261006-medicine-affiliations.bak`.
Exact-ID, official-ID, laureate-QID, and blank-field guards updated one row per university. Readback confirms all four links.
Comparison with the backup confirms no unrelated award changes, no lost or changed existing extras, and no changed pre-existing ROR IDs. Integrity check returns `ok`.
The normalizer dry run proposes zero changes.
The validator still reports the same two fatal checks. HHMI's previously failing institution-facts group now includes the intentionally blank location,
and missing-place has one new backlog entry for that HHMI affiliation; no new university conflicts were introduced.

The first full build reported `missing subject record_id=nobel-001027`. The existing `CATEGORY_SUBJECTS` mapping in `scripts/set_award_subjects.py` maps Medicine to Biology.
After backup `datasets/awards.sqlite3.20261006-medicine-subjects.bak`, exactly the three new rows' blank `high_school_subject` cells were filled with Biology.
This is the website classification; `field_language` remains blank. The guarded update changed three rows and passed integrity checking.

Validation: `uv run --python 3.12 --with pytest --with jinja2==3.1.6 --with pillow==11.3.0 --with shapely pytest tests/` passed all 171 tests.
An earlier test collection attempt lacked Shapely; it was rerun with that dependency. `uv run --with ruff ruff check` reports 35 pre-existing issues in untouched Python files.

Full regeneration completed with `uv run --script website/build.py --base-url https://prizeatlas.org/`: 30,996 planned pages across English, Spanish, French, and Japanese.
All twelve localized 2026 recipient pages contain the expected institution links. A SHA-256 comparison confirms the website build did not change the database.
Generated output remains local in `datasets/website/dist/`; `git diff --check` passes.

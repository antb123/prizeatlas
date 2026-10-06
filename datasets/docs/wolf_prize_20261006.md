# Wolf Prize 2026 — database update (20261006)

Added eight records to `datasets/awards.sqlite3` on 2026-10-06 following `docs/new_laureate_runbook_20261006.md`. Existing award rows were preserved.
The 2026 laureates were announced 1-2 October 2026; the ceremony is June 2027 (Knesset, Jerusalem). The Wolf Foundation's own pages give no announcement date, so the date follows press reports.

| Record | Category | Recipient | Laureate QID | Born | Position 1 | Position 2 |
|---|---|---|---|---|---|---|
| wolf_prize-000392 | Chemistry | Shankar Balasubramanian | Q7488670 | 1966-09-30, Chennai, India | University of Cambridge (Q35794) | |
| wolf_prize-000393 | Chemistry | David Klenerman | Q21165838 | 1959-09-09 | University of Cambridge (Q35794) | |
| wolf_prize-000394 | Chemistry | Pascal Mayer | Q100310865 | 1963-07-14, Saint-Avold, France | Alphanosos (no QID) | University of Strasbourg (Q157575) |
| wolf_prize-000395 | Mathematics | Joseph Bernstein | Q370530 | 1945-04-18, Moscow, Russia | Tel Aviv University (Q319239) | |
| wolf_prize-000396 | Mathematics | David Kazhdan | Q1174945 | 1946-06-20, Moscow, Russia | Hebrew University of Jerusalem (Q174158) | |
| wolf_prize-000397 | Medicine | Charles S. Zuker | Q5083992 | 1957, Arica, Chile | Columbia University (Q49088) | Howard Hughes Medical Institute (Q1512226) |
| wolf_prize-000398 | Physics | Immanuel F. Bloch | Q100694 | 1972-11-16, Fulda, Germany | Max Planck Society / Max Planck Institute of Quantum Optics (Q158085) | LMU Munich (Q55044) |
| wolf_prize-000399 | Physics | Jun Ye | Q22005647 | 1967, Shanghai, China | National Institute of Standards and Technology (Q176691) | University of Colorado, Boulder (Q736674) |

## Sources

Roster, read in full from the Wolf Foundation: `https://wolffund.org.il/<slug>/` for `immanuel-f-bloch`, `jun-ye`, `charles-s-zuker`, `shankar-balasubramanian`, `david-klenerman`, `pascal-mayer`, `david-kazhdan`, `joseph-bernstein`.
Each page supplies the category, the citation (stored as the motivation, capitalised and ended with a period like the family's older rows), and the affiliation as printed. The roster states no prize share, so `prize_share` is blank (older Wolf rows use a whole-year denominator and were not copied).
`source_laureate_id` is blank: the Wolf Foundation exposes no identifier.

Laureate QIDs: five people already held a QID on other rows (Balasubramanian, Klenerman, Mayer, Kazhdan, Ye) and the new rows use the same one. Bloch Q100694, Zuker Q5083992 and Bernstein Q370530 were found by Wikidata search.
Each was confirmed by birth year and birthplace against the roster text (Wikidata does not list the 2026 prize yet). `enrich.py` filled birth, sex and type from those QIDs; no one has died.

Corrections made to `enrich.py` output on the new rows: `Duchy of Moscow` to `Russia` (Bernstein, Kazhdan), `People's Republic of China` to `China` (Ye), Zuker's `1957-01-01` to `1957` (Wikidata precision is year).
Klenerman's birth city and country are blank: Wikidata has no birthplace and the roster says only that he grew up in London.

Affiliations: position 1 names come from the roster. Cambridge, Tel Aviv, Hebrew University, Columbia, Max Planck Institute of Quantum Optics, LMU Munich, Strasbourg, Colorado Boulder reuse the spelling, QID, city and coordinates the database already held for that QID.
Bloch's unit and Ye's Colorado affiliation are supported by Wikidata P108 as well as the roster. Position 2 rows were added through `award_extra_affiliations.tsv` and `load_extra_affiliations.py`.
Howard Hughes Medical Institute carries a country but no city or coordinates, as for Deisseroth: the roster gives no place for it.
NIST Boulder coordinates `-105.2633,39.9942` come from the Wikidata item for NIST Boulder (Q40215915, used for the point only; the row keeps the parent QID Q176691). Nominatim reverse places the point at "National Institute of Standards and Technology (Building 1), 325 Broadway, Boulder".
The build requires coordinates for any affiliation that has a city and country, so Boulder without a verified point failed the build until this was added.
Alphanosos has no Wikidata item, so its QID, ROR and OpenAlex institution id are blank.

Author identifiers (`lookup_authors.py`, confirmed by exact Wikidata claim): ORCID for Klenerman, Mayer, Bernstein, Bloch, Ye; OpenAlex author id for Klenerman, Mayer, Bloch, Ye.
Klenerman: the tool returned the 6-work profile `A5128297507`; the same ORCID also maps to the main profile `A5042822683` (548 works), which is stored instead.
Balasubramanian: ORCID `0000-0002-0281-5815` was taken from his existing rows and OpenAlex `A5040551102` from an ORCID filter on OpenAlex (497 works). Kazhdan: existing valid OpenAlex id `A5015976690`. Zuker: no verified identifier, left blank.
`lookup_ror.py` and `lookup_openalex.py` filled seven rows (all but Alphanosos); every value equals what existing rows with the same QID already carry.

`high_school_subject` copies the family's mapping: Chemistry, Math, Biology (Medicine), Physics.
Inserted rows initially held NULL in unspecified columns where older rows hold empty strings; they were normalised to `''` for the eight rows.

## Also in this change

- The Lasker Public Service Award category (70 rows, 1946-2026) was removed: the site covers science prizes only. One matching `award_extra_affiliations` row and its TSV line went with it.
- New catalogue entry `terms.country.Chile` in `en`, `es`, `fr`, `ja` (Chile, Chile, Chili, チリ), unreviewed.
- The award calendar pages (`website/calendar/`, `scripts/build_calendar.py`) and the Wolf announcement date there were corrected to 2026-10-01.
- `tests/test_build_website.py` now copies `website/calendar/` into its fixture and expects the two calendar URLs in the sitemap.

## Backups and checks

Backups (gitignored): `awards.sqlite3.20261006-wolf2026.bak` (before insert), `…-155911.enrich.bak`, `…-160112.authors.bak`, `…-160447-wolf-affiliations.bak`, `…-161518-preload.bak`, `…-161535.ror.bak`, `…-161551.openalex.bak`, `…-162449-nist.bak`.
Insert compared every existing row with the backup (0 changed or lost). Extras load: 94 old rows, 98 after, 0 old rows missing or changed. `PRAGMA integrity_check` returns `ok`.
`validate_awards.py`: the same two fatal checks fail before and after (institution-facts-disagree, coords-shared-across-cities). Only existing groups grew: Alphanosos without QID (1 to 2), Howard Hughes missing place (1 to 2), and the NIST group gained a Boulder row.
`normalize_affiliations.py` dry run proposes no changes. Tests: 171 passed. `ruff check` is clean on the files changed here.
Full build: 30,104 planned pages plus the two calendar pages. The explorer and the new person pages render.

## Defects noticed, not changed

- Jun Ye's existing Breakthrough row has `birth_date` 1974-08-16; Wikidata and the Wolf roster give 1967.
- Existing OpenAlex author ids for Klenerman (`A5136260150`) and Balasubramanian (`A5136377854`) return 404.
- Klenerman's older rows record his birthplace as London, United Kingdom, which neither Wikidata nor the roster states.
- `AGENTS.md` names `University of Colorado Boulder` as the canonical spelling (the English Wikipedia title); `normalize_affiliations.py` maps it to `University of Colorado, Boulder`. The new row follows the normalizer so the institution is not split in rankings.
- Existing NIST rows carry `-105.2705450,40.0149856` (the Boulder city point) and `-105.2928,40.0194`, neither verified as NIST's site.
- Older rows still hold `Duchy of Moscow` and `People's Republic of China` as birth countries.
- `scripts/check_coordinates.sql` named in `AGENTS.md` is missing from the checkout.
- JILA (Q1586184) remains a joint NIST and Colorado institute with no single parent; Ye's row records NIST and Colorado as the roster does.

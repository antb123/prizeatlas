# Max Planck Medal 2027 — database update (20261125)

Added one record to `datasets/awards.sqlite3` on 2026-11-25 following `docs/new_laureate_runbook_20261006.md`. Existing award rows were preserved.
The DPG announced the 2027 medal on 2026-11-19 (DPG-Pressemitteilung 21/2026); it is presented at the 90th DPG annual meeting, Regensburg, March 2027.

| Record | Recipient | Laureate QID | Born | Position 1 | Position 2 |
|---|---|---|---|---|---|
| max_planck_medal-000091 | Frank Jülicher | Q1443519 | 1965-03-19, Ludwigsburg, Germany | Max Planck Society / Max Planck Institute for the Physics of Complex Systems (Q158085) | TU Dresden (Q158158) |

## Sources

- DPG prize page `https://www.dpg-physik.de/auszeichnungen/uebersicht-preisjahrgaenge/2027` and the DPG press release on `dpg-physik.de`: blocked by Cloudflare (HTTP 403) for both WebFetch and curl; not read.
- DPG press release 21/2026, as distributed by idw: `https://idw-online.de/de/news881188` (19.11.2026). Recipient, field, affiliation "Max-Planck-Institut für Physik komplexer Systeme in Dresden".
- Physik Journal news (Maike Pfalz / DPG): `https://pro-physik.de/nachrichten/dpg-medaillen-2027`. Formal citation, ceremony place and month, career (TU Dresden professorship).

The motivation is an English rendering, in the family's "In recognition of …" form, of the citation printed by pro-physik:
"für seine bahnbrechenden Arbeiten zu biologischen Kondensaten, zellulärer Selbstorganisation und Nichtgleichgewichts-Phasenseparation, die das Verständnis lebender Systeme
und damit die theoretische Biophysik revolutioniert haben". The DPG's own English wording could not be read; replace it if the DPG page later shows a different text.
`category` and `source_laureate_id` are blank as for the family; `prize_share` is `1/1` like the family's recent rows.

## Person

QID Q1443519 ("German biophysicist") is the single Wikidata match. Confirmed beyond the name: its awards include the Robert Wichard Pohl Prize (2006, stated in the DPG release)
and the Leibniz Prize (2016, stated by pro-physik); employers (P108) are MPI-PKS and TU Dresden. Wikidata does not list the 2027 medal yet.
`enrich.py` filled birth date `1965-03-19` (precision 11, day), birth city Ludwigsburg, birth country Germany, sex Male; German Wikipedia gives the same date and place.
Birth country is today's country `Germany` (born in West Germany), matching how the family's older rows record it. Citizenship `Germany` from Wikidata P27.
Birth point `9.1895,48.8954`: Nominatim (Ludwigsburg relation 405292); Wikidata Q622 gives `9.1919,48.8975` (~300 m); the existing Ludwigsburg row uses the same value. Reverse: Ludwigsburg-Mitte, `de`.
Living: no death fields. `field_language`, `biographical_note`, `remarks` are blank on every Max Planck Medal row and stay blank. `high_school_subject` Physics, as the family.
Not stored (no column): doctorate (University of Cologne, 1994), doctoral supervisor, research fields, birth region.

Author identifiers (`lookup_authors.py`, exact Wikidata claim): ORCID `0000-0003-4731-9185`, OpenAlex `A5080597344` (546 works). The same ORCID also maps to a 2-work fragment `A5124189966`, not used.

## Affiliations

Position 1 follows the DPG release. Parent Max Planck Society (Q158085), unit Max Planck Institute for the Physics of Complex Systems, as for the other Max Planck institute rows.
Point `13.7169,51.0267` from the institute's own item Q1912086; Nominatim reverse: Nöthnitzer Straße 38, Dresden, `de`. Dresden city point is `13.7381,51.0493`, so this is not the city centre.
ROR `01hhn8329` and OpenAlex institution `I149899117` from `lookup_ror.py` / `lookup_openalex.py`; both equal what every other Max Planck Society row carries.

Position 2, TU Dresden (Q158158, enwiki title "TU Dresden"): not in the DPG release; his concurrent professorship is stated by pro-physik and Wikidata P108, and the curator asked for it.
Point `13.7267,51.0281` from Q158158; Nominatim reverse: Mommsenstraße, Dresden, `de`. Added through `award_extra_affiliations.tsv` and `load_extra_affiliations.py`.

## Also in this change

- `website/i18n/labels.toml`: one line for Q158158 (`Universidad Técnica de Dresde` / `université de technologie de Dresde`), the exact value `fetch_wikidata_labels.py` produces. The full refresh was not written (see below).
- `website/calendar/events.toml` and `docs/when.md`: the 2026 announcement moved from projected 2026-11-12 to confirmed 2026-11-19; the March 2027 ceremony is confirmed for Regensburg. Calendar pages regenerated with `scripts/build_calendar.py`.

## Backups and checks

Backups (gitignored): `awards.sqlite3.20261125-julicher.bak` (before insert), `….enrich.bak`, `….affiliations.bak`, `….extras.bak`, `awards.sqlite3.20261125-101657.extras.bak` (loader), `….ror.bak`, `….openalex.bak`.
Insert compared every existing row with the backup (0 changed or lost; 2681 to 2682). Extras load: 102 old rows, 103 after, 0 old rows missing or changed. `PRAGMA integrity_check` returns `ok`. Gap query: 0 gaps.
`validate_awards.py`: the same two fatal checks fail before and after; the only diff is Dresden joining the existing Max Planck Society `institution-facts-disagree` group.
`normalize_affiliations.py` dry run: one alias row, `brain_prize-000049` (Heidelberg University), present before this change. Tests: calendar, label and extra-affiliation tests pass (3).
Full build: 30,944 pages; award and person pages exist in en, es, fr, ja; es and fr show the translated TU Dresden label; ja uses the English name as for every institution.

## Defects noticed, not changed

- `fetch_wikidata_labels.py` against the current database rewrites about 50 unrelated lines of `labels.toml` (dropped labels for institutions no longer in the data, capitalisation changes in French, new labels). A full refresh needs its own review.
- `brain_prize-000049` still holds `Heidelberg University`, which the normalizer maps to `University of Heidelberg`.

one row per laureate/recipient
places - use todays name, country, location

## validation rules

- one person per row. if `full_name` lists several people or a collaboration, split into
  one record per named person; a genuine collaboration/team/institution is a single row
  with `laureate_type` = Organization and no personal bio.
- `laureate_type` is `Individual` or `Organization` only.
- preserve the 26-column header and every existing `award_record_id`. new split rows get
  fresh ids; never renumber existing ones.
- fill blank cells only — never overwrite an existing curated value.
- leave a cell blank when unsure. do not guess or infer.
- dates are ISO `YYYY-MM-DD` (or `YYYY` when only the year is known). no other format.
- `birth_city` is the city alone; the country belongs in `birth_country`. no "City, State".
- places use today's names (city, country).
- if a person has died, `death_date` (and place, if known) must be filled; blank death for
  the living. cross-check the "(YYYY–YYYY)" hint in `biographical_note` when present.
- `birth_year` is optional when a complete `birth_date` already supplies it.
- add `birth_coordinates` / `affiliation_coordinates` only after the named place is verified.
- do not infer `prize_share` or death details for the living.
- Organizations carry no birth/sex/death data.

main award files:
- abel_prize.csv
- breakthrough.csv
- crafoord.csv
- fields.csv
- japan_prize.csv
- kyoto_prize.csv
- lasker_awards.csv
- max_planck_medal.csv
- nobel.csv
- shaw_prize.csv
- turing_award.csv
- wolf_prize.csv

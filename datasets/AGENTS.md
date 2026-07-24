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

main award files (source url under each — read it instead of searching):
- abel_prize.csv
  https://abelprize.no
- breakthrough.csv
  https://breakthroughprize.org
- crafoord.csv
  https://www.crafoordprize.se
- fields.csv
  https://www.mathunion.org/imu-awards/fields-medal
- japan_prize.csv
  https://www.japanprize.jp/en/
- kyoto_prize.csv
  https://www.kyotoprize.org/en/
- lasker_awards.csv
  https://laskerfoundation.org
- max_planck_medal.csv
  https://www.dpg-physik.de/auszeichnungen/dpg-preise/max-planck-medaille
- nobel.csv
  https://www.nobelprize.org
- shaw_prize.csv
  https://www.shawprize.org
- turing_award.csv
  https://amturing.acm.org
- wolf_prize.csv
  https://wolffund.org.il

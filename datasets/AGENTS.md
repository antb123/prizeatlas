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

main award files (sources under each — read these instead of searching):
- abel_prize.csv
  official:   https://abelprize.no
  wikipedia:  https://en.wikipedia.org/wiki/Abel_Prize
- breakthrough.csv
  official:   https://breakthroughprize.org
  wikipedia:  https://en.wikipedia.org/wiki/Breakthrough_Prize
- crafoord.csv
  official:   https://www.crafoordprize.se
  wikipedia:  https://en.wikipedia.org/wiki/Crafoord_Prize
- fields.csv
  official:   https://www.mathunion.org/imu-awards/fields-medal
  wikipedia:  https://en.wikipedia.org/wiki/Fields_Medal
- japan_prize.csv
  official:   https://www.japanprize.jp/en/
  wikipedia:  https://en.wikipedia.org/wiki/Japan_Prize
- kyoto_prize.csv
  official:   https://www.kyotoprize.org/en/
  wikipedia:  https://en.wikipedia.org/wiki/Kyoto_Prize
- lasker_awards.csv
  official:   https://laskerfoundation.org
  wikipedia:  https://en.wikipedia.org/wiki/Lasker_Award
- max_planck_medal.csv
  official:   https://www.dpg-physik.de/auszeichnungen/dpg-preise/max-planck-medaille
  wikipedia:  https://en.wikipedia.org/wiki/Max_Planck_Medal
- nobel.csv
  official:   https://www.nobelprize.org
  wikipedia:  https://en.wikipedia.org/wiki/List_of_Nobel_laureates
- shaw_prize.csv
  official:   https://www.shawprize.org
  wikipedia:  https://en.wikipedia.org/wiki/Shaw_Prize
- turing_award.csv
  official:   https://amturing.acm.org
  wikipedia:  https://en.wikipedia.org/wiki/Turing_Award
- wolf_prize.csv
  official:   https://wolffund.org.il
  wikipedia:  https://en.wikipedia.org/wiki/Wolf_Prize

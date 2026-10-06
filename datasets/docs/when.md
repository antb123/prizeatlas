# When the awards happen

A calendar of the 16 award families in `award_ranking`, January to December.
Winners are announced in one month and honoured at a ceremony in another, so each prize appears twice; the Note column links the two.
Dates are the most recent cycle (ISO `YYYY-MM-DD`), checked 20261006. Exact days move each year; the month and week are the stable part.
A month with no day (`YYYY-MM`) means only the month is known.

The same data drives the web pages: `website/calendar/events.toml` is the source, and `uv run scripts/build_calendar.py` renders `website/calendar/2026.html` and `2027.html` (draft).

## January

| Date       | Prize          | Event     | Note                                  |
|------------|----------------|-----------|---------------------------------------|
| 2026-01-21 | Japan Prize    | Announced | → ceremony 2026-04-14, Tokyo          |
| 2026-01-29 | Crafoord Prize | Announced | → ceremony 2026-05-21, Stockholm      |

## February

No events.

## March

| Date       | Prize                  | Event     | Note                                                         |
|------------|------------------------|-----------|--------------------------------------------------------------|
| 2026-03    | Max Planck Medal       | Ceremony  | DPG annual meeting; ← announced 2025-11-13                   |
| 2026-03-05 | The Brain Prize        | Announced | → ceremony 2026-05-20, Copenhagen                            |
| 2026-03-18 | Turing Award           | Announced | → banquet 2026-06-13, San Francisco (2025 award)             |
| 2026-03-19 | Abel Prize             | Announced | → ceremony 2026-05-26, Oslo                                  |
| 2026-03-31 | Canada Gairdner International Award | Announced | → gala 2026-10-22                                            |

## April

| Date       | Prize              | Event                | Note                                          |
|------------|--------------------|----------------------|-----------------------------------------------|
| 2026-04-14 | Japan Prize        | Ceremony             | Tokyo; ← announced 2026-01-21                 |
| 2026-04-18 | Breakthrough Prize | Announced + ceremony | same day, Santa Monica, California            |

## May

| Date       | Prize                       | Event     | Note                                                                   |
|------------|-----------------------------|-----------|------------------------------------------------------------------------|
| 2026-05-20 | The Brain Prize             | Ceremony  | Copenhagen; ← announced 2026-03-05                                     |
| 2026-05-21 | Crafoord Prize              | Ceremony  | Stockholm, Crafoord Days 18-21 May; ← announced 2026-01-29             |
| 2026-05-26 | Abel Prize                  | Ceremony  | Oslo; ← announced 2026-03-19                                           |
| 2026-05-27 | Shaw Prize                  | Announced | → ceremony 2026-10 (day not yet announced), Hong Kong                  |
| 2027-05    | Millennium Technology Prize | Ceremony  | Helsinki, May or June; every two years, next 2027                      |

## June

| Date       | Prize        | Event     | Note                                                                |
|------------|--------------|-----------|---------------------------------------------------------------------|
| 2026-06-10 | Kavli Prize  | Announced | even years only; → ceremony 2026-09-01, Oslo                        |
| 2026-06-13 | Turing Award | Ceremony  | ACM Awards Banquet, San Francisco; ← announced 2026-03-18          |
| 2026-06-19 | Kyoto Prize  | Announced | → ceremony 2026-11-10, Kyoto                                        |
| 2027-06    | Wolf Prize   | Ceremony  | Knesset, Jerusalem; ← announced 2026-10-04                          |

## July

| Date       | Prize        | Event                | Note                                                                                   |
|------------|--------------|----------------------|----------------------------------------------------------------------------------------|
| 2026-07-23 | Fields Medal | Announced + ceremony | opening of the International Congress of Mathematicians; every four years, next 2030   |

## August

No events.

## September

| Date       | Prize         | Event     | Note                                  |
|------------|---------------|-----------|---------------------------------------|
| 2026-09-01 | Kavli Prize   | Ceremony  | Oslo; ← announced 2026-06-10          |
| 2026-09-09 | Lasker Award | Announced | → ceremony 2026-09-17, New York       |
| 2026-09-17 | Lasker Award | Ceremony  | New York; ← announced 2026-09-09      |

## October

| Date       | Prize                  | Event     | Note                                                                                 |
|------------|------------------------|-----------|--------------------------------------------------------------------------------------|
| 2026-10-04 | Wolf Prize             | Announced | → ceremony 2027-06; earlier cycles announced in February                             |
| 2026-10-05 | Nobel Prize            | Announced | Physiology or Medicine, first full week of October; → ceremony 2026-12-10            |
| 2026-10-06 | Nobel Prize            | Announced | Physics                                                                              |
| 2026-10-07 | Nobel Prize            | Announced | Chemistry                                                                            |
| 2026-10    | Shaw Prize             | Ceremony  | Hong Kong; day not yet announced (2025: 2025-10-21); ← announced 2026-05-27         |
| 2026-10-22 | Canada Gairdner International Award | Ceremony  | gala; ← announced 2026-03-31                                                         |

## November

| Date       | Prize            | Event     | Note                                                            |
|------------|------------------|-----------|-----------------------------------------------------------------|
| 2026-11-10 | Kyoto Prize      | Ceremony  | Kyoto, every year on 10 November; ← announced 2026-06-19        |
| 2026-11-12 | Max Planck Medal | Announced | projected, mid-November; → ceremony 2027-03 (DPG meeting)       |

## December

| Date       | Prize       | Event    | Note                                                                          |
|------------|-------------|----------|-------------------------------------------------------------------------------|
| 2026-12-10 | Nobel Prize | Ceremony | anniversary of Nobel's death; Stockholm          |

## By prize

| Prize                       | Announced               | Ceremony             | Cycle         |
|-----------------------------|-------------------------|----------------------|---------------|
| Nobel Prize                 | October (first 2 weeks) | 10 December          | yearly        |
| Fields Medal                | July                    | July (same day)      | every 4 years |
| Turing Award                | March                   | June                 | yearly        |
| Max Planck Medal            | November                | March                | yearly        |
| Abel Prize                  | March                   | May                  | yearly        |
| Lasker Award               | September               | September            | yearly        |
| Canada Gairdner International Award      | March                   | October              | yearly        |
| Wolf Prize                  | October (2026)          | June                 | yearly        |
| Kyoto Prize                 | June                    | November             | yearly        |
| Crafoord Prize              | January                 | May                  | yearly        |
| The Brain Prize             | March                   | May                  | yearly        |
| Shaw Prize                  | May                     | October              | yearly        |
| Kavli Prize                 | June                    | September            | even years    |
| Japan Prize                 | January                 | April                | yearly        |
| Millennium Technology Prize | spring                  | May or June          | every 2 years |
| Breakthrough Prize          | April                   | April (same day)     | yearly        |

## Caveats

- Max Planck Medal March ceremony has no verified day; the DPG holds it at its annual spring meeting.
- Millennium Technology Prize: winner decided December 2026, announced spring 2027, ceremony May or June 2027 in Helsinki. No exact day published yet.
- Wolf Prize moved its announcement from February to October with the 2026 cycle; confirm against `wolffund.org.il` before relying on October for 2027.
- Shaw Prize 2026 ceremony date was "to be announced"; 2025-10-21 is last year's ceremony.
- Science prizes only, matching `awards.sqlite3`: Nobel Physics, Chemistry and Physiology or Medicine. The Literature, Peace and Economic Sciences prizes are not in the database and are not listed. Kyoto Prize covers only its Basic Sciences and Advanced Technology categories.
- Nobel announcement times are "at the earliest"; the order (Medicine, Physics, Chemistry) is fixed.

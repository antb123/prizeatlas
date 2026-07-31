# PrizeAtlas Dataset Documentation

PrizeAtlas publishes curated award data as open-source, downloadable datasets. This page describes what's available, how to access it, how to use it, and what the data contains.

## Quick Start

Download the datasets:

```sh
# SQLite database (recommended for queries)
wget https://prizeatlas.org/awards.sqlite3

# CSV export (for spreadsheets, data tools)
wget https://prizeatlas.org/awards.csv
```

Both files contain the same award records. Choose based on your tools:

- **SQLite** if you want to query with SQL, work with relationships, or build applications
- **CSV** if you work with spreadsheets, data analysis tools (Python, R), or need a flat export

## What's in the Data

The datasets contain one row per award recipient across 14 international science prizes, back to their founding (earliest: 1901). Each row captures:

- **The award**: Prize name, category, year, award citation
- **The recipient**: Name, birth/death dates and places, Wikidata identifier, ORCID
- **The institution**: Where the work was done, with Wikidata and ROR identifiers
- **The field**: High school subject classification (Biology, Physics, Chemistry, etc.)
- **External links**: Wikidata, ORCID, OpenAlex, ROR, and awarding body URLs

### Coverage

As of the current snapshot:

- **8,000+** award recipients
- **14** prize families (Nobel Prize, Breakthrough Prize, Shaw Prize, Abel Prize, Turing Award, and others)
- **123** years of award history
- **~11,000** institutions linked to Wikidata and ROR

See the [About page](https://prizeatlas.org/about/) for the full list of prizes and data sourcing philosophy.

## Data Files

### awards.sqlite3

The source of truth. A relational SQLite database with four tables:

#### `awards` table

The main table. One row per award recipient. Use this for most queries.

| Column | Type | Notes |
|--------|------|-------|
| **award_record_id** | TEXT (PK) | Unique identifier for this award (e.g., "nobel_prize-physics-1921-1") |
| **year** | TEXT | Award year (e.g., "1921", or "1936-1937" for multi-year awards) |
| **category** | TEXT | Prize category (e.g., "Physics", "Medicine", "Medicine/Physiology") |
| **prize** | TEXT | Prize code (e.g., "nobel_prize", "turing_award") |
| **prize_name** | TEXT | Display name (e.g., "Nobel Prize") |
| **award_wikidata_qid** | TEXT | Wikidata ID of the award (e.g., "Q44586") |
| **motivation** | TEXT | Award citation (why this person won) |
| **prize_share** | TEXT | If shared, the recipient's fraction (e.g., "1/2", "1/3") |
| **laureate_wikidata_qid** | TEXT | Wikidata ID of the person (empty if not found) |
| **laureate_type** | TEXT | "Person" or "Organization" |
| **full_name** | TEXT | Laureate's name as recorded by the awarding body |
| **birth_date** | TEXT | Birth date in ISO 8601 format (YYYY-MM-DD), or empty if unknown |
| **birth_year** | TEXT | Birth year only (YYYY) |
| **birth_city** | TEXT | City of birth (present-day name) |
| **birth_country** | TEXT | Country of birth (present-day name) |
| **birth_coordinates** | TEXT | Latitude,longitude (WGS84) of birthplace, or empty |
| **citizenship_countries** | TEXT | Semicolon-separated list of citizenship countries |
| **sex** | TEXT | "M", "F", or empty if not recorded |
| **affiliation_name** | TEXT | Name of the institution where work was done |
| **affiliation_sub_name** | TEXT | Department or subdivision within institution |
| **affiliation_wikidata_qid** | TEXT | Wikidata ID of the institution |
| **affiliation_city** | TEXT | City where the institution is located |
| **affiliation_country** | TEXT | Country where the institution is located |
| **affiliation_coordinates** | TEXT | Latitude,longitude of the institution |
| **death_date** | TEXT | Death date in ISO 8601 format, or empty if still living |
| **death_city** | TEXT | City of death |
| **death_country** | TEXT | Country of death |
| **biographical_note** | TEXT | Short career note or note about the award |
| **high_school_subject** | TEXT | Classification: "Biology", "Physics", "Chemistry", "Math", "CS", "Earth Science", "History", "Lit", "Arts", "Economics", or "" (unclassified) |
| **orc_id** | TEXT | ORCID identifier (without https://orcid.org/ prefix), or empty |
| **affiliate_ror** | TEXT | ROR (Research Organization Registry) ID, or empty |
| **author_openalex_id** | TEXT | OpenAlex author ID, or empty |
| **institution_openalex_id** | TEXT | OpenAlex institution ID, or empty |

**Indexes**: `awards_prize_category_year_idx`, `awards_full_name_idx`, `awards_laureate_qid_idx`

#### `award_ranking` table

Metadata about each prize: its prestige score, description, and official URL.

| Column | Type | Notes |
|--------|------|-------|
| **award_wikidata_qid** | TEXT (PK) | Wikidata ID (e.g., "Q44586" for Nobel Prize) |
| **prize_name** | TEXT | Display name (unique) |
| **score** | INTEGER | Prestige score 0–100. Higher = more selective/prestigious |
| **blurb** | TEXT | One-sentence description for the site |
| **reasoning** | TEXT | Explanation of the score and selection criteria |
| **url** | TEXT | Official award website |
| **slug** | TEXT | URL-friendly identifier (e.g., "nobel-prize") |
| **logo_url** | TEXT | URL to prize logo, or empty |

**Indexes**: `award_ranking_slug_idx`

#### `affiliations` table

Metadata about institutions. Linked from `awards.affiliation_wikidata_qid`.

| Column | Type | Notes |
|--------|------|-------|
| **affiliation_wikidata_qid** | TEXT (PK) | Wikidata ID (e.g., "Q191897" for MIT) |
| **logo_url** | TEXT | Logo URL, or empty |
| **description** | TEXT | Short description (e.g., research area, founding year) |
| **application_url** | TEXT | Link to admissions or "how to join" page, or empty |
| **kind** | TEXT | Institution type (e.g., "university", "research center", "company") |

#### `award_extra_affiliations` table

When a laureate held multiple positions at the time of the award, this table captures additional affiliations.

| Column | Type | Notes |
|--------|------|-------|
| **award_record_id** | TEXT (FK) | Foreign key to `awards` table |
| **position** | INTEGER | Position number (2, 3, ...). Position 1 is in the main `awards` table |
| **affiliation_name** | TEXT | Institution name |
| **affiliation_sub_name** | TEXT | Department or subdivision |
| **affiliation_city** | TEXT | City |
| **affiliation_country** | TEXT | Country |
| **affiliation_coordinates** | TEXT | Latitude,longitude |
| **affiliation_wikidata_qid** | TEXT | Wikidata ID |

**Primary key**: `(award_record_id, position)`

### awards.csv

A flat, RFC 4180–compliant CSV export. One row per award recipient. Columns match the `awards` table above, in this order:

```
award_record_id, year, category, prize, prize_name, award_wikidata_qid, motivation,
prize_share, laureate_wikidata_qid, laureate_type, full_name, birth_date, birth_year,
birth_city, birth_country, birth_coordinates, citizenship_countries, sex,
affiliation_name, affiliation_sub_name, affiliation_wikidata_qid, affiliation_city,
affiliation_country, affiliation_coordinates, death_date, death_city, death_country,
biographical_note, high_school_subject, orc_id, affiliate_ror, author_openalex_id,
institution_openalex_id
```

No external affiliations are included in the CSV (see `award_extra_affiliations` in the SQLite database).

## Usage Examples

### SQLite

Install SQLite (included on macOS and Linux; available via `choco install sqlite` on Windows).

**List all Nobel Prize winners in Physics:**

```sh
sqlite3 awards.sqlite3 "
  SELECT year, full_name, birth_country, affiliation_name, motivation
  FROM awards
  WHERE prize_name = 'Nobel Prize' AND category = 'Physics'
  ORDER BY year DESC
  LIMIT 10;
"
```

**Find repeat winners:**

```sh
sqlite3 awards.sqlite3 "
  SELECT full_name, COUNT(*) as award_count, GROUP_CONCAT(prize_name, '; ') as prizes
  FROM awards
  GROUP BY laureate_wikidata_qid
  HAVING COUNT(*) > 1
  ORDER BY award_count DESC;
"
```

**Count awards by country of birth:**

```sh
sqlite3 awards.sqlite3 "
  SELECT birth_country, COUNT(*) as count
  FROM awards
  WHERE birth_country != ''
  GROUP BY birth_country
  ORDER BY count DESC
  LIMIT 20;
"
```

**Find early-career winners (won before age 40):**

```sh
sqlite3 awards.sqlite3 "
  SELECT full_name, birth_year, year, (CAST(year AS INT) - CAST(birth_year AS INT)) as age_at_award, prize_name
  FROM awards
  WHERE birth_year != '' AND year != ''
    AND (CAST(year AS INT) - CAST(birth_year AS INT)) < 40
  ORDER BY age_at_award, year;
"
```

**Get all awards with multiple affiliations:**

```sh
sqlite3 awards.sqlite3 "
  SELECT a.award_record_id, a.full_name, a.year, a.affiliation_name
  FROM awards a
  WHERE a.award_record_id IN (
    SELECT award_record_id FROM award_extra_affiliations
  )
  ORDER BY a.award_record_id, a.year;
"
```

### CSV in Python

Load with `pandas`:

```python
import pandas as pd

df = pd.read_csv('awards.csv')

# Winners by country
by_country = df[df['birth_country'] != ''].groupby('birth_country').size().sort_values(ascending=False)
print(by_country.head(10))

# Average age at award (where birth_year and year are available)
df['birth_year_int'] = pd.to_numeric(df['birth_year'], errors='coerce')
df['award_year_int'] = pd.to_numeric(df['year'], errors='coerce')
df['age_at_award'] = df['award_year_int'] - df['birth_year_int']
print(df['age_at_award'].mean())

# Prize distribution
prize_counts = df['prize_name'].value_counts()
print(prize_counts)
```

### CSV in R

```r
library(tidyverse)

awards <- read_csv('awards.csv')

# Most common affiliations
awards %>%
  filter(affiliation_country != '') %>%
  group_by(affiliation_country) %>%
  summarize(count = n()) %>%
  arrange(desc(count))

# Recipients by high school subject
awards %>%
  filter(high_school_subject != '') %>%
  group_by(high_school_subject) %>%
  summarize(count = n())
```

### CSV in Excel or Google Sheets

1. Download `awards.csv`
2. Open in Excel or Google Sheets
3. Use pivot tables, filters, and formulas
4. Example: Create a pivot table of prizes × birth countries

## Data Quality

### What's Filled In

- **award_record_id, year, category, prize, prize_name**: Always present
- **full_name, laureate_wikidata_qid**: Always present (core identity)
- **affiliation_name, affiliation_city, affiliation_country**: Present for nearly all records (>99%)
- **birth_year**: Present for >95% of records
- **motivation**: Always present (award citation)

### What May Be Missing

- **birth_date, death_date**: Present for ~70% of records. Partial dates (year-month only) are included as-is
- **birth_city, birth_coordinates**: Present for ~90% of records. Historical cities use present-day names
- **death_city, death_country**: Present for ~40% of records (many laureates still living)
- **sex**: Present for ~98% of records
- **orc_id, author_openalex_id, institution_openalex_id**: Present for ~30–40% of records. These are cross-references to external systems
- **biographical_note**: Sparse; included when it illuminates the award
- **high_school_subject**: All records are classified; a few older or cross-disciplinary awards may be tagged as ""

### Missing Data Philosophy

The standing rule is to **leave a cell blank rather than guess**. A missing value means "we couldn't confirm this," not "it's unknown" or "it was rounded to something plausible." This is why some fields are sparse.

### Coordinates

Birth and affiliation coordinates are WGS84 (latitude,longitude) in decimal degrees. Coordinates are sourced from Wikidata, ROR, and OpenAlex and are only included when a precise, current location could be confirmed.

### Names and Places

- **Laureate names** are as recorded by the awarding body's official record
- **Place names** use present-day official names (e.g., a laureate born in Königsberg in 1904 is listed under "Kaliningrad, Russia")
- **Affiliation names** are normalized where possible using Wikidata and ROR, but the original name recorded at award time is sometimes preserved in `affiliation_sub_name` or `biographical_note`

## Licensing and Attribution

The datasets are **dual-licensed**:

1. **Creative Commons Attribution-ShareAlike 4.0 International** ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/))
2. **GNU Free Documentation License** (unversioned, with no invariant sections) ([GFDL](https://www.gnu.org/licenses/fdl-1.3.html))

**You may comply with either license.**

### What This Means

- You may **freely download, use, remix, and redistribute** the data
- If you redistribute, you must **attribute PrizeAtlas** (and, where practical, the original awarding bodies and sources)
- If you create derivative works (modified datasets, analyses, visualizations), you must share them under a **compatible license** (CC BY-SA or GFDL)

### Third-Party Material

The award citations, names, and official records come from the awarding bodies. Data from Wikidata, Wikipedia, ROR, and OpenAlex is subject to their respective licenses (CC0, CC BY-SA, CC0, and CC BY-SA, respectively). All are compatible with this dual license.

See [CONTENT-LICENSE](CONTENT-LICENSE) for the full legal text.

## External Identifiers and Cross-References

Every record links out to authoritative sources where practical:

- **Wikidata**: `laureate_wikidata_qid`, `award_wikidata_qid`, `affiliation_wikidata_qid`
- **ORCID**: `orc_id` (researcher identifier; use as `https://orcid.org/{orc_id}`)
- **ROR**: `affiliate_ror` (institution identifier; use as `https://ror.org/{affiliate_ror}`)
- **OpenAlex**: `author_openalex_id`, `institution_openalex_id` (research metadata platform)
- **Awarding body**: Links to the official record for each prize

These enable you to **trace facts back to their sources** and **connect to other datasets** (bibliographies, institution metadata, researcher profiles).

## Common Questions

**Q: How current is the data?**  
A: Snapshots are published after major award ceremonies (roughly annually). Check the website for the snapshot date.

**Q: Can I use this data in my research or application?**  
A: Yes, provided you comply with CC BY-SA 4.0 or GFDL (attribution + share-alike).

**Q: Can I publish a subset or derivative?**  
A: Yes, provided you license it under CC BY-SA or GFDL and attribute PrizeAtlas.

**Q: Are there awards I think should be included?**  
A: Yes! Open an issue on [GitHub](https://github.com/anthropics/prizeatlas/) or send an email to the authors. We're open to adding prizes that meet the criteria.

**Q: How do I report missing or incorrect data?**  
A: Open an issue on [GitHub](https://github.com/anthropics/prizeatlas/) with details.

**Q: Can I get data for non-science awards?**  
A: The current datasets focus on science and math. Non-science awards (Literature, Peace, Economics) were historically included but are not in the current snapshot. See [AGENTS.md](AGENTS.md) for the curation philosophy.

**Q: How do I combine data from multiple years?**  
A: The `awards` table is append-only; each snapshot includes all historical records plus new awards from recent years. Download the latest snapshot and use it as your source of truth.

## Getting Help

- **Questions about the data**: Open an issue on [GitHub](https://github.com/anthropics/prizeatlas/)
- **Questions about licensing**: See [CONTENT-LICENSE](CONTENT-LICENSE)
- **For researchers or institutions**: Email the authors (see [README](README.md))

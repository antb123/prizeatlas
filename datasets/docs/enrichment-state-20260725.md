# Enrichment State Report — `awards.sqlite3`

**Date:** 2026-07-25 (re-run)

---

## 1. Overview

| Metric | Count |
|---|---|
| Total rows | 3,091 |
| QID coverage | 3,085 / 3,091 (99.8%) |
| Individuals | 3,047 |
| Organizations | 44 |
| Type blank | 0 |

---

## 2. Per-Prize Census

| Prize | Rows | Indiv | Orgs | No QID | Per-laureate gaps (Indiv only) |
|---|---|---|---|---|---|
| Nobel Prize | 1,026 | 995 | 31 | 0 | **0** (31 blanks are all orgs) |
| Lasker Award | 423 | 415 | 8 | 3 | **0** (8 blanks are all orgs) |
| Wolf Prize | 391 | 391 | 0 | 0 | 0 |
| Gairdner Intl | 387 | 387 | 0 | 0 | 0 |
| Breakthrough | 148 | 143 | 5 | 3 | **0** (4 blanks are all orgs) |
| Kyoto Prize | 129 | 129 | 0 | 0 | 0 |
| Shaw Prize | 121 | 121 | 0 | 0 | 0 |
| Japan Prize | 116 | 116 | 0 | 0 | 0 |
| Max Planck Medal | 90 | 90 | 0 | 0 | 0 |
| Crafoord Prize | 82 | 82 | 0 | 0 | 0 |
| Turing Award | 81 | 81 | 0 | 0 | 0 |
| Fields Medal | 68 | 68 | 0 | 0 | 0 |
| Abel Prize | 29 | 29 | 0 | 0 | 0 |

**0 individuals** with personal-data gaps. Every Individual row has birth_date, birth_country, citizenship_countries, and sex populated.

---

## 3. QID-Missing Rows (6 total)

### 5 Organizations — legitimately blank

| award_record_id | full_name |
|---|---|
| breakthrough-000051 | Contributors to Gravitational Waves paper (LIGO) |
| breakthrough-000115 | ATLAS/CMS/ALICE/LHCb collaborations |
| breakthrough-000121 | Muon g-2 collaboration |
| lasker_awards-000063 | Nursing Services of the U.S. Public Health Service |
| lasker_awards-000297 | Science Times of The New York Times |

### 1 Individual — needs QID

| award_record_id | full_name |
|---|---|
| lasker_awards-000420 | Jesús (Tito) González |

---

## 4. Actionable Individual Gaps

**None.** All 3,047 Individuals have birth_date, birth_country, citizenship_countries, and sex populated.

---

## 5. Coordinates (Individuals only)

| Prize | Individuals | No birth_coords | No affil_coords |
|---|---|---|---|
| Nobel Prize | 995 | 63 | 993 |
| Lasker Award | 415 | 151 | 415 |
| Wolf Prize | 391 | 155 | 391 |
| Gairdner Intl | 387 | 21 | 254 |
| Breakthrough | 143 | 26 | 133 |
| Kyoto Prize | 129 | 19 | 46 |
| Shaw Prize | 121 | 59 | 121 |
| Japan Prize | 116 | 55 | 116 |
| Max Planck Medal | 90 | 18 | 90 |
| Crafoord Prize | 82 | 36 | 82 |
| Turing Award | 81 | 27 | 81 |
| Fields Medal | 68 | 2 | 6 |
| Abel Prize | 29 | 0 | 0 |
| **Total** | **3,047** | **632** | **2,728** |

## 6. Other Bulk

| Item | For | Count |
|---|---|---|
| Missing affiliation_name | Individuals | 828 |
| Missing motivation | Max Planck Medal | 64 |

---

## 7. Integrity Check

```
ok
```

---

## 8. Suspect Values

| record_id | issue |
|---|---|
| `breakthrough-000041` | **laureate_type = Organization** but **sex = Male**. Arthur B. McDonald and the Sudbury Neutrino Observatory Team — sex should be blank. |

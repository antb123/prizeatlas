#!/usr/bin/env python3
"""Merge lasker_batch*.tsv biographical data into lasker_awards.csv.

Each batch line is pipe-delimited:
  record_id|laureate_type|birth_date|birth_year|birth_city|birth_country|sex|death_date|death_city|death_country

Only non-empty values are written; blank cells are left untouched. Idempotent.
"""
import csv
import glob

FIELDS = ["laureate_type", "birth_date", "birth_year", "birth_city",
          "birth_country", "sex", "death_date", "death_city", "death_country"]

data: dict[str, dict[str, str]] = {}
for path in sorted(glob.glob("lasker_batch*.tsv")):
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("|")
            while len(parts) > 10 and parts[-1] == "":
                parts.pop()  # drop stray trailing empty fields
            if len(parts) > 10:
                raise SystemExit(f"bad line in {path}: {line!r}")
            parts += [""] * (10 - len(parts))  # pad truncated trailing blanks
            rid, *vals = parts
            data[rid] = dict(zip(FIELDS, vals))

with open("lasker_awards.csv", newline="") as f:
    reader = csv.DictReader(f)
    header = reader.fieldnames
    rows = list(reader)

filled = {k: 0 for k in FIELDS}
for row in rows:
    rec = data.get(row["award_record_id"])
    if not rec:
        continue
    for k in FIELDS:
        v = rec[k].strip()
        if v:
            row[k] = v
            filled[k] += 1

with open("lasker_awards.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    w.writerows(rows)

print("Merged from batches. Cells filled:")
for k, v in filled.items():
    print(f"  {k:15} {v}")

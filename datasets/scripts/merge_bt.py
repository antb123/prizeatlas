#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Merge bt_batch*.tsv into breakthrough.csv, filling ONLY blank cells.

Batch line: record_id|birth_date|birth_year|birth_city|birth_country|
            citizenship_countries|sex|death_date|death_city|death_country
Existing values are never overwritten. Idempotent.
"""
import csv
import glob

FIELDS = ["birth_date", "birth_year", "birth_city", "birth_country",
          "citizenship_countries", "sex", "death_date", "death_city", "death_country"]

data: dict[str, dict[str, str]] = {}
for path in sorted(glob.glob("bt_batch*.tsv")):
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("|")
            while len(parts) > 10 and parts[-1] == "":
                parts.pop()
            if len(parts) > 10:
                raise SystemExit(f"bad line in {path}: {line!r}")
            parts += [""] * (10 - len(parts))
            rid, *vals = parts
            data[rid] = dict(zip(FIELDS, vals))

with open("breakthrough.csv", newline="") as f:
    reader = csv.DictReader(f)
    header = reader.fieldnames
    rows = list(reader)

filled = {k: 0 for k in FIELDS}
seen = set()
for row in rows:
    rec = data.get(row["award_record_id"])
    if not rec:
        continue
    seen.add(row["award_record_id"])
    for k in FIELDS:
        v = rec[k].strip()
        if v and not row[k].strip():   # fill blanks only
            row[k] = v
            filled[k] += 1

with open("breakthrough.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    w.writerows(rows)

missing = [r["award_record_id"] for r in rows if r["award_record_id"] not in seen]
print("Merged (blanks only). Cells filled:")
for k, v in filled.items():
    print(f"  {k:22} {v}")
print(f"\nrecords with no batch line ({len(missing)}): {missing}")

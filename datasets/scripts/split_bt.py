#!/usr/bin/env python3
"""Restructure breakthrough.csv: split lumped laureate rows into one row per person.

- SPLIT: full_name lists several named people -> one row each. First person keeps
  the original id; the rest get fresh ids from 000131 up. Shared context (year,
  category, prize, motivation, affiliation) is copied; person bio stays blank.
- RENAME: person + team -> keep the single named person, drop the team text.
- ORG: named collaborations -> laureate_type = Organization, no bio.
Every other row is a single person -> laureate_type = Individual.
"""
import csv

SPLIT = {
    "breakthrough-000022": ["Peter Jenni", "Fabiola Gianotti", "Michel Della Negra",
                            "Tejinder Singh Virdee", "Guido Tonelli", "Joe Incandela", "Lyn Evans"],
    "breakthrough-000024": ["Michael Green", "John Henry Schwarz"],
    "breakthrough-000031": ["Saul Perlmutter", "Brian P. Schmidt", "Adam Riess"],
    "breakthrough-000045": ["Takaaki Kajita", "Yōichirō Suzuki"],
    "breakthrough-000052": ["Ronald Drever", "Kip Thorne", "Rainer Weiss"],
    "breakthrough-000053": ["Andrew Strominger", "Cumrun Vafa"],
    "breakthrough-000063": ["Norman Jarosik", "Lyman Page Jr.", "David N. Spergel"],
    "breakthrough-000071": ["Charles Kane", "Eugene Mele"],
    "breakthrough-000088": ["Eric Adelberger", "Jens H. Gundlach", "Blayne Heckel"],
}
RENAME = {
    "breakthrough-000042": "Arthur B. McDonald",
    "breakthrough-000043": "Atsuto Suzuki",
    "breakthrough-000044": "Kōichirō Nishikawa",
}
ORG = {"breakthrough-000051", "breakthrough-000080", "breakthrough-000115", "breakthrough-000121"}

with open("breakthrough.csv", newline="") as f:
    reader = csv.DictReader(f)
    header = reader.fieldnames
    rows = list(reader)

next_id = 131
out = []
for row in rows:
    rid = row["award_record_id"]
    if rid in ORG:
        row["laureate_type"] = "Organization"
        out.append(row)
    elif rid in RENAME:
        row["full_name"] = RENAME[rid]
        row["laureate_type"] = "Individual"
        out.append(row)
    elif rid in SPLIT:
        for i, name in enumerate(SPLIT[rid]):
            r = dict(row)
            r["full_name"] = name
            r["laureate_type"] = "Individual"
            if i:
                r["award_record_id"] = f"breakthrough-{next_id:06d}"
                next_id += 1
            out.append(r)
    else:
        row["laureate_type"] = "Individual"
        out.append(row)

with open("breakthrough.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    w.writerows(out)

print(f"rows: {len(rows)} -> {len(out)}  (new ids 000131..{next_id-1:06d})")

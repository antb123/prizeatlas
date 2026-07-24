#!/usr/bin/env python3
"""Dump context rows for breakthrough.csv enrichment (one line per record)."""
import csv

with open("breakthrough.csv", newline="") as f:
    for row in csv.DictReader(f):
        print("\t".join([
            row["award_record_id"], row["full_name"], row["year"],
            row["category"], row["citizenship_countries"], row["affiliation_name"],
        ]))

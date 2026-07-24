#!/usr/bin/env python3
"""Dump id<TAB>full_name<TAB>citizenship for lasker_awards.csv laureates."""
import csv

with open("lasker_awards.csv", newline="") as f:
    for row in csv.DictReader(f):
        print(f"{row['award_record_id']}\t{row['full_name']}\t{row['citizenship_countries']}")

#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pycountry"]
# ///
"""Write birth coordinates whose reverse-geocoded country disagrees with the database."""

import csv
import sqlite3
import sys
from pathlib import Path

import pycountry
import reverse_nominatim

DB = Path("awards.sqlite3")
CACHE = Path(".nominatim-birth-cache.json")
OUTPUT = Path("birth_country_mismatches.tsv")


def country_code(name):
    if name == "Turkey":
        name = "Türkiye"
    try:
        return pycountry.countries.search_fuzzy(name)[0].alpha_2.lower()
    except LookupError:
        return None


connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row
rows = connection.execute(
    "SELECT award_record_id, full_name, birth_city, birth_country, birth_coordinates "
    "FROM awards WHERE laureate_type = 'Individual' AND trim(birth_coordinates) <> '' ORDER BY award_record_id"
).fetchall()
connection.close()

lookups = {}
for coordinates in sorted({row["birth_coordinates"] for row in rows}):
    try:
        longitude, latitude = reverse_nominatim.parse_coordinates(coordinates)
        lookups[coordinates] = reverse_nominatim.clean(reverse_nominatim.lookup(longitude, latitude, CACHE))
    except Exception as error:
        print(f"lookup failed coordinates={coordinates} error={error}", file=sys.stderr)

with OUTPUT.open("w", newline="") as file:
    writer = csv.writer(file, delimiter="\t")
    writer.writerow((*rows[0].keys(), "reverse_country"))
    for row in rows:
        result = lookups.get(row["birth_coordinates"])
        expected = country_code(row["birth_country"])
        if result and ((expected and expected != result["country_code"]) or (not expected and row["birth_country"] != result["country"])):
            writer.writerow((*row, result["country"]))

print(f"mismatches={sum(1 for _ in OUTPUT.open()) - 1} output={OUTPUT}")

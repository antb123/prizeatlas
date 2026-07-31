#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pycountry"]
# ///
# SPDX-License-Identifier: GPL-2.0-or-later
"""Print birth coordinates whose reverse-geocoded country disagrees with the database."""

import csv
import sqlite3
import sys
from pathlib import Path

import pycountry
import reverse_nominatim

DB = Path("awards.sqlite3")
CACHE = Path(".nominatim-birth-cache.json")


# Names search_fuzzy cannot resolve. Without an entry here the code falls through to comparing the
# database name against Nominatim's LOCAL-LANGUAGE name, which reports a false mismatch: the Congo
# row was flagged only because Nominatim answers "République démocratique du Congo".
ALIASES = {
    "Turkey": "Türkiye",
    "Democratic Republic of the Congo": "Congo, The Democratic Republic of the",
}


def country_code(name):
    name = ALIASES.get(name, name)
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
    except (OSError, TypeError, ValueError) as error:
        print(f"lookup failed coordinates={coordinates} error={error}", file=sys.stderr)

writer = csv.writer(sys.stdout, delimiter="\t")
writer.writerow((*rows[0].keys(), "reverse_country"))
mismatches = 0
for row in rows:
    result = lookups.get(row["birth_coordinates"])
    expected = country_code(row["birth_country"])
    if result and ((expected and expected != result["country_code"]) or (not expected and row["birth_country"] != result["country"])):
        writer.writerow((*row, result["country"]))
        mismatches += 1

print(f"birth country check complete mismatches={mismatches}", file=sys.stderr)
